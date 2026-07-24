"""
services/pipeline_manager.py
====================================================================
المنسّق المركزي لكل خطوات pipeline التحليل الجيني.
يُستدعى حصرياً من Celery task في apps.genomics.tasks — ما بيلمس
Django request/response مباشرة.

الترتيب الصحيح للـ pipeline (محدّث):
  0) تحديد موقع تسلسل المريض على الكروموسوم (DNA_locator)
  1) جلب التسلسل السليم (control) بنفس الإحداثيات تماماً (fetcher)
  2) DNase على المريض + DNase على السليم
  3) Motifs/Proteins على المريض + على السليم (من DNA لحاله)، ثم مقارنة
     النتيجتين لتحديد أي بروتين "مفقود/متأثر" عند المريض (is_missing)
  4) Hi-C على المريض + على السليم (DNA + DNase سوا لكل واحد)
  5) تحويل كل مصفوفة Hi-C لإحداثيات 3D (مريض + سليم)
  6) توليد التقرير عبر LLM بناءً على كل النتائج السابقة
  7) حفظ كل شي بـ OutputData حسب حقول الموديل
====================================================================
"""
import os
import logging
from core.utils.genomics_utils import normalize_chromosome_name
logger = logging.getLogger(__name__)


class PipelineCancelledError(Exception):
    """يُرفع عندما يطلب المستخدم إيقاف التحليل أثناء التنفيذ."""


class GenomicPipelineManager:

    def __init__(self, input_data_id: int):
        self.input_data_id = input_data_id
        self._input_data = None

    def _check_cancelled(self, input_data) -> None:
        from apps.genomics.models import InputData
        current_status = (
            InputData.objects.filter(pk=self.input_data_id)
            .values_list("status", flat=True)
            .first()
        )
        if current_status == "cancelling":
            logger.info("[Pipeline %s] Cancellation detected — stopping pipeline", self.input_data_id)
            raise PipelineCancelledError(
                f"Pipeline for InputData id={self.input_data_id} was cancelled by user"
            )

    # ------------------------------------------------------------------
    # Main entry point — called from the Celery task
    # ------------------------------------------------------------------
    def run(self) -> dict:
        from apps.genomics.models import InputData

        input_data: InputData = InputData.objects.select_related(
            "cell_type", "patient"
        ).get(pk=self.input_data_id)
        self._input_data = input_data

        patient_fasta_path: str = input_data.dna_sequence_file.path
        enformer_id: int = input_data.cell_type.target_enformer_id
        chromosome: str = normalize_chromosome_name(input_data.chromosome)

        # Step 0
        self._check_cancelled(input_data)
        coords = self._step_locate(patient_fasta_path, chromosome, input_data)

        # Step 1
        self._check_cancelled(input_data)
        control_fasta_path = self._step_fetch_reference(coords, input_data)

        # Step 2
        self._check_cancelled(input_data)
        dnase_patient_file = self._step_dnase(patient_fasta_path, enformer_id, input_data, tag="patient")
        self._check_cancelled(input_data)
        dnase_control_file = self._step_dnase(control_fasta_path, enformer_id, input_data, tag="control")

        # Step 3 (Hi-C)
        self._check_cancelled(input_data)
        hic_patient_file = self._step_hic(patient_fasta_path, dnase_patient_file, input_data, coords=coords, tag="patient")
        self._check_cancelled(input_data)
        hic_control_file = self._step_hic(control_fasta_path, dnase_control_file, input_data, coords=coords, tag="control")

        # Step 4 (3D) — لازم قبل الموتيفس هلق
        self._check_cancelled(input_data)
        coords_patient_file = self._step_3d(hic_patient_file, input_data, tag="patient")
        self._check_cancelled(input_data)
        coords_control_file = self._step_3d(hic_control_file, input_data, tag="control")

        # Step 5 (Motifs + Docking بالاعتماد على نقاط الـ 3D)
        self._check_cancelled(input_data)
        affected_proteins = self._step_motifs(
            patient_fasta_path, control_fasta_path, input_data,
            dnase_patient_file=dnase_patient_file,
            dnase_control_file=dnase_control_file,
            coords_patient_file=coords_patient_file,   # ← جديد
            coords_control_file=coords_control_file,   # ← جديد
            resolution=5000,                           # ← جديد (أو من settings)
        )

        return {
            "hic_patient_file": hic_patient_file,
            "hic_control_file": hic_control_file,
            "coords_patient_file": coords_patient_file,
            "coords_control_file": coords_control_file,
            "affected_proteins": affected_proteins,
        }

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------
    def _step_locate(self, patient_fasta_path: str, chromosome: str, input_data) -> dict:
        from services.Genome_reference1.DNA_locator import locate_patient_sequence
        chromosome = normalize_chromosome_name(chromosome)
        self._update_status(input_data, "pending")  # ما في status مخصص لهاد بالـ model حالياً
        logger.info("[Pipeline %s] -> Locating patient sequence on %s", self.input_data_id, chromosome)

        coords: dict = locate_patient_sequence(patient_fasta_path, chromosome_hint=chromosome)

        logger.info(
            "[Pipeline %s] Located: %s:%s-%s (strand=%s, identity=%.3f)",
            self.input_data_id, coords["chromosome"], coords["start"], coords["end"],
            coords["strand"], coords["identity"],
        )
        return coords

    def _step_fetch_reference(self, coords: dict, input_data) -> str:
        from django.conf import settings
        from services.Genome_reference1.fetcher import fetch_reference_sequence_as_fasta_file

        logger.info("[Pipeline %s] -> Fetching healthy reference sequence", self.input_data_id)

        control_fasta_path = fetch_reference_sequence_as_fasta_file(
            chromosome=coords["chromosome"],
            start=coords["start"],
            end=coords["end"],
            output_dir=str(settings.MEDIA_ROOT) + "/genomics/raw_inputs/fasta/",
            record_id=f"control_{self.input_data_id}",
        )

        input_data.dna_control_file = control_fasta_path          # ← غيّرنا هون
        input_data.save(update_fields=["dna_control_file"])

        logger.info("[Pipeline %s] Reference fetched: %s", self.input_data_id, control_fasta_path)
        return control_fasta_path

    def _step_dnase(self, fasta_path: str, enformer_id: int, input_data, tag: str) -> str:
        from services.DNASE.predictor import predict_dnase_profiles

        self._update_status(input_data, "predicting_dnase")
        logger.info("[Pipeline %s] -> DNase prediction started (%s)", self.input_data_id, tag)

        dnase_file: str = predict_dnase_profiles(fasta_path, enformer_id)

        field = "predicted_dnase_patient" if tag == "patient" else "predicted_dnase_control"
        setattr(input_data, field, dnase_file)
        input_data.save(update_fields=[field])

        logger.info("[Pipeline %s] DNase done (%s): %s", self.input_data_id, tag, dnase_file)
        return dnase_file

    def _step_motifs(self, patient_fasta_path: str, control_fasta_path: str, input_data,
                  dnase_patient_file: str = None, dnase_control_file: str = None,
                  coords_patient_file: str = None, coords_control_file: str = None,
                  resolution: int = 5000) -> dict:
        import json
        import numpy as np
        from django.conf import settings
        from services.scanning_motifs.scanner import (
            calculate_spatial_docking,
            run_motif_delta_analysis,
        )

        self._update_status(input_data, "scanning_motifs")
        logger.info("[Pipeline %s] -> Motif scanning started (patient + control)", self.input_data_id)

        # DNase arrays (زي ما كانت)
        patient_dnase_array = None
        control_dnase_array = None
        if dnase_patient_file:
            p_path = os.path.join(settings.MEDIA_ROOT, dnase_patient_file)
            if os.path.exists(p_path):
                patient_dnase_array = np.load(p_path).astype(np.float32)
        if dnase_control_file:
            c_path = os.path.join(settings.MEDIA_ROOT, dnase_control_file)
            if os.path.exists(c_path):
                control_dnase_array = np.load(c_path).astype(np.float32)

        patient_motifs: dict = run_motif_delta_analysis(patient_fasta_path, dnase_signal=patient_dnase_array)
        control_motifs: dict = run_motif_delta_analysis(control_fasta_path, dnase_signal=control_dnase_array)

        # نحمّل نقاط الـ 3D (بدل ما نفتعل موقع بمعادلة وهمية)
        def _load_coords_raw(rel_path):
            if not rel_path:
                return []
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            if not os.path.exists(abs_path):
                return []
            with open(abs_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            # الملف مباشرة فيه coords_raw بالمستوى الأعلى (مو تحت "patient"/"control")
            return payload.get("coords_raw", [])
        

        patient_coords_raw = _load_coords_raw(coords_patient_file)
        control_coords_raw = _load_coords_raw(coords_control_file)

        MAX_PROTEINS = 20  # ← حد أقصى لعدد البروتينات المُعالَجة/المُرجَعة

        all_protein_ids = set(patient_motifs.keys()) | set(control_motifs.keys())

        # نرتب حسب أقوى delta_score (قيمة مطلقة) ونكتفي بأعلى MAX_PROTEINS —
        # فلترة قبل حلقة المعالجة نفسها، مش بعدها، حتى نوفر حسابات docking
        # الزايدة عن الحاجة على بروتينات رح نرميها أصلاً
        def _score_key(pid: str) -> float:
            info = patient_motifs.get(pid) or control_motifs.get(pid) or {}
            return abs(info.get("delta_score") or 0)

        all_protein_ids = sorted(all_protein_ids, key=_score_key, reverse=True)[:MAX_PROTEINS]

        affected_proteins = {}

        for protein_id in all_protein_ids:
            patient_info = patient_motifs.get(protein_id)
            control_info = control_motifs.get(protein_id)
            is_missing = control_info is not None and patient_info is None
            motif_info = patient_info or control_info
            protein_name = motif_info.get("protein_name") or protein_id

            # نحسب موقع الدوكينغ من bin المطابق بالإحداثيات الجاهزة — بدون أي PDB
            patient_position_index = patient_info.get("position_index") if patient_info else None
            control_position_index = control_info.get("position_index") if control_info else None

            patient_docking = calculate_spatial_docking(patient_coords_raw, patient_position_index, resolution) \
                if patient_info else None
            control_docking = calculate_spatial_docking(control_coords_raw, control_position_index, resolution) \
                if control_info else None

            delta_score = None
            if patient_info and control_info:
                delta_score = patient_info.get("delta_score", 0) - control_info.get("delta_score", 0)
            elif motif_info:
                delta_score = motif_info.get("delta_score")

            affected_proteins[protein_id] = {
                "protein_name": protein_name,
                "position_index": patient_position_index if patient_position_index is not None else control_position_index,
                "delta_score": delta_score,
                "is_missing": is_missing,
                "patient": {
                    "present": patient_info is not None,
                    "binding_score": patient_info.get("delta_score") if patient_info else None,
                    "position_index": patient_position_index,
                    "coords": patient_docking,   
                } if patient_info else None,
                "control": {
                    "present": control_info is not None,
                    "binding_score": control_info.get("delta_score") if control_info else None,
                    "position_index": control_position_index,
                    "coords": control_docking,
                } if control_info else None,
            }

        logger.info(
            "[Pipeline %s] Motifs done - %d proteins (patient=%d, control=%d, missing=%d)",
            self.input_data_id, len(affected_proteins), len(patient_motifs), len(control_motifs),
            sum(1 for p in affected_proteins.values() if p["is_missing"]),
        )
        # تنظيف numpy scalars (int64/float32/bool_...) لأنها مش JSON-serializable
        # بشكل افتراضي — لازم نحولها لأنواع بايثون عادية قبل الحفظ بـ JSONField
        affected_proteins = self._to_json_safe(affected_proteins)
        return affected_proteins

    def _step_hic(self, fasta_path: str, dnase_file: str, input_data, coords: dict, tag: str) -> str:
        from services.HI_C.predictorHIC import generate_hic_matrices

        self._update_status(input_data, "generating_hic")
        logger.info("[Pipeline %s] -> Hi-C generation started (%s)", self.input_data_id, tag)

        # استخراج الإحداثيات الحقيقية المحددة من step 0
        chrom = coords.get("chromosome", input_data.chromosome)
        start_pos = coords.get("start", 0)

        hic_file: str = generate_hic_matrices(
            fasta_path,
            dnase_file,
            output_name_hint=f"input_{self.input_data_id}_{tag}",
            chrom=chrom,          # ← الكروموسوم الحقيقي (مثل 'chr21')
            start_pos=start_pos,  # ← البداية الحقيقية بالـ bp (مثل 14200000)
        )

        logger.info("[Pipeline %s] Hi-C done (%s): %s", self.input_data_id, tag, hic_file)
        return hic_file
    def _step_3d(self, hic_file_path: str, input_data, tag: str) -> str:
        from services.calculating_3d.coords_service import convert_hic_to_3d_coords

        self._update_status(input_data, "generating_hic_coords")
        logger.info("[Pipeline %s] -> Starting 3D MDS transformation (%s)", self.input_data_id, tag)

        coords_relative_file = convert_hic_to_3d_coords(
            hic_relative_path=hic_file_path,
            alpha=0.5,
            output_name_hint=f"input_{self.input_data_id}_{tag}",
        )

        logger.info(
            "[Pipeline %s] 3D coordinates file generated (%s): %s",
            self.input_data_id, tag, coords_relative_file,
        )
        return coords_relative_file

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _to_json_safe(value):
        """
        يحوّل أي numpy scalar/array (int64, float32, bool_, ndarray...) جوا
        بنية متداخلة (dict/list) لأنواع بايثون عادية — لأنه json.dumps
        الافتراضي (يلي بيستخدمه Django JSONField) ما بيعرف يسريلايز numpy
        types أصلاً، وهاد كان سبب TypeError عند الحفظ بـ OutputData.
        """
        import numpy as np

        if isinstance(value, dict):
            return {k: GenomicPipelineManager._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [GenomicPipelineManager._to_json_safe(v) for v in value]
        if isinstance(value, np.generic):  # أي numpy scalar (int64, float32, bool_...)
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @staticmethod
    def _update_status(input_data, status: str) -> None:
        input_data.status = status
        input_data.save(update_fields=["status"])