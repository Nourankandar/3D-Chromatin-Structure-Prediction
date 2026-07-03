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

import logging

logger = logging.getLogger(__name__)


class GenomicPipelineManager:

    def __init__(self, input_data_id: int):
        self.input_data_id = input_data_id
        self._input_data = None

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
        chromosome: str = input_data.chromosome

        # ── Step 0: تحديد موقع تسلسل المريض ──────────────────────────
        coords = self._step_locate(patient_fasta_path, chromosome, input_data)

        # ── Step 1: جلب التسلسل السليم بنفس الإحداثيات ───────────────
        control_fasta_path = self._step_fetch_reference(coords, input_data)

        # ── Step 2: DNase (مريض + سليم) ──────────────────────────────
        dnase_patient_file = self._step_dnase(
            patient_fasta_path, enformer_id, input_data, tag="patient"
        )
        dnase_control_file = self._step_dnase(
            control_fasta_path, enformer_id, input_data, tag="control"
        )

        # ── Step 3: Motifs/Proteins (مريض + سليم) + مقارنة ───────────
        affected_proteins = self._step_motifs(
            patient_fasta_path, control_fasta_path, input_data
        )

        # ── Step 4: Hi-C (مريض + سليم) ────────────────────────────────
        hic_patient_file = self._step_hic(
            patient_fasta_path, dnase_patient_file, input_data, tag="patient"
        )
        hic_control_file = self._step_hic(
            control_fasta_path, dnase_control_file, input_data, tag="control"
        )

        # ── Step 5: 3D Coordinates (مريض + سليم) ──────────────────────
        coords_patient_file = self._step_3d(hic_patient_file, input_data, tag="patient")
        coords_control_file = self._step_3d(hic_control_file, input_data, tag="control")

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

        self._update_status(input_data, "pending")  # ما في status مخصص لهاد بالـ model حالياً
        logger.info("[Pipeline %s] -> Locating patient sequence on chr%s", self.input_data_id, chromosome)

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
            output_dir=str(settings.MEDIA_ROOT) + "/genomics/reference_sequences/",
            record_id=f"control_{self.input_data_id}",
        )

        input_data.reference_sequence_file = control_fasta_path
        input_data.save(update_fields=["reference_sequence_file"])

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

    def _step_motifs(self, patient_fasta_path: str, control_fasta_path: str, input_data) -> dict:
        from services.scanning_motifs.scanner import (
            calculate_spatial_docking,
            fetch_pdb_file,
            run_motif_delta_analysis,
        )

        self._update_status(input_data, "scanning_motifs")
        logger.info("[Pipeline %s] -> Motif scanning started (patient + control)", self.input_data_id)

        patient_motifs: dict = run_motif_delta_analysis(patient_fasta_path)
        control_motifs: dict = run_motif_delta_analysis(control_fasta_path)

        # نبني قائمة موحّدة على كل البروتينات يلي ظهرت بأي من الجهتين
        all_protein_ids = set(patient_motifs.keys()) | set(control_motifs.keys())

        affected_proteins = {}
        for protein_id in all_protein_ids:
            patient_info = patient_motifs.get(protein_id)
            control_info = control_motifs.get(protein_id)

            # مفقود عند المريض = موجود بالسليم وغير موجود عند المريض
            is_missing = control_info is not None and patient_info is None

            # لو موجود بس بمكان/سكور مختلف بشكل واضح، منعتبره متأثر مش مفقود بالكامل
            # (منستخدم بيانات المريض لو موجودة، وإلا بيانات السليم كمرجع للموقع)
            motif_info = patient_info or control_info

            pdb_path = fetch_pdb_file(protein_id)
            docking_coords = calculate_spatial_docking(pdb_path, motif_info)

            delta_score = None
            if patient_info and control_info:
                delta_score = patient_info.get("delta_score", 0) - control_info.get("delta_score", 0)
            elif motif_info:
                delta_score = motif_info.get("delta_score")

            affected_proteins[protein_id] = {
                "pdb_file": pdb_path,
                "position": docking_coords.get("position"),
                "rotation": docking_coords.get("rotation"),
                "binding_score": motif_info.get("delta_score") if motif_info else None,
                "delta_score": delta_score,
                "is_missing": is_missing,
            }

        logger.info(
            "[Pipeline %s] Motifs done - %d proteins found (patient=%d, control=%d, missing=%d)",
            self.input_data_id, len(affected_proteins), len(patient_motifs), len(control_motifs),
            sum(1 for p in affected_proteins.values() if p["is_missing"]),
        )
        return affected_proteins

    def _step_hic(self, fasta_path: str, dnase_file: str, input_data, tag: str) -> str:
        from services.HI_C.predictorHIC import generate_hic_matrices

        self._update_status(input_data, "generating_hic")
        logger.info("[Pipeline %s] -> Hi-C generation started (%s)", self.input_data_id, tag)

        hic_file: str = generate_hic_matrices(
            fasta_path, dnase_file, output_name_hint=f"input_{self.input_data_id}_{tag}"
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
    def _update_status(input_data, status: str) -> None:
        input_data.status = status
        input_data.save(update_fields=["status"])