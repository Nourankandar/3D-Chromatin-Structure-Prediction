"""
services/pipeline_manager.py
====================================================================
المنسّق المركزي لكل خطوات pipeline التحليل الجيني.

الترتيب الصحيح (محدّث بالكامل):
  0) تحديد موقع تسلسل المريض (DNA_locator)
  2) تحديد الجينات المتقاطعة + الـ transcript الرسمي (gtf_index) —
     وحساب نافذة الجلب النهائية (union بين نافذة المريض وحدود كل جين)
  1) جلب السليم بنفس النافذة الموسّعة (fetcher) + تكميل أي جزء ناقص
     من تسلسل المريض نفسه من المرجع (لو الجين أوسع من ملف المريض)
  3) نيوكليوتيد ديف مباشر (sequence_diff) على مستوى النافذة الكاملة
  4) لكل جين: قص CDS (splicer) لمريض وسليم
  5) لكل جين: ترجمة (translator)
  6) لكل جين: تصنيف الطفرة (mutation_classifier)
  7) DNase على المريض + السليم (على مستوى النافذة الكاملة)
  8) Hi-C على المريض + السليم
  9) 3D coordinates (+ nucleosome track مدموجة فيها) لمريض وسليم
  10) Motifs/التنظيميات (scanner) بالاعتماد على DNase + 3D موقفة حاليا 
  11) تجميع كل الفروقات بـ report_payload واحد وإرجاعه
====================================================================
"""
import os
import logging
import numpy as np
from django.conf import settings
from core.utils.genomics_utils import normalize_chromosome_name

logger = logging.getLogger(__name__)


class PipelineCancelledError(Exception):
    """يُرفع عند اكتشاف إلغاء صريح من المستخدم أثناء تنفيذ الـ pipeline."""

class GenomicPipelineManager:

    def __init__(self, input_data_id: int):
        self.input_data_id = input_data_id
        self._input_data = None

    # ------------------------------------------------------------------
    # نقطة الدخول الرئيسية
    # ------------------------------------------------------------------
    def run(self) -> dict:
        from apps.genomics.models import InputData

        input_data: InputData = InputData.objects.select_related(
            "cell_type", "patient"
        ).get(pk=self.input_data_id)
        self._input_data = input_data

        patient_fasta_path: str = input_data.dna_sequence_file.path
        basset_track_id: int = input_data.cell_type.target_basset_track_id
        chromosome: str = normalize_chromosome_name(input_data.chromosome)

        # الخطوة 0: تحديد موقع تسلسل المريض
        coords = self._step_locate(patient_fasta_path, chromosome, input_data)

        # الخطوة 2: تحديد الجينات المتقاطعة + حساب النافذة الموسّعة
        genes_info, expanded_window = self._step_find_genes(coords, input_data)

        # الخطوة 1: جلب السليم بالنافذة الموسّعة + تكميل ناقص المريض لو لزم
        patient_seq, control_seq = self._step_fetch_and_complete(
            patient_fasta_path, coords, expanded_window, input_data
        )

        # الخطوة 3: نيوكليوتيد ديف مباشر على مستوى النافذة كاملة
        nucleotide_diff = self._step_nucleotide_diff(patient_seq, control_seq, expanded_window)

        # الخطوات 4-6: لكل جين — قص، ترجمة، تصنيف طفرة
        proteins_diff = self._step_proteins(patient_seq, control_seq, expanded_window, genes_info)

        # الخطوة 7: DNase (مريض + سليم) — بالاعتماد على ملفات الفاستا الفعلية
        patient_fasta_for_dnase, control_fasta_for_dnase = self._write_window_fasta_files(
            patient_seq, control_seq, expanded_window, input_data
        )
        dnase_patient_file = self._step_dnase(patient_fasta_for_dnase, basset_track_id, input_data, tag="patient")
        dnase_control_file = self._step_dnase(control_fasta_for_dnase, basset_track_id, input_data, tag="control")

        # الخطوة 8: DNase ديف (مقارنة المناطق المفتوحة/المغلقة)
        dnase_diff = self._step_dnase_diff(dnase_patient_file, dnase_control_file)

        # الخطوة 9: Hi-C (مريض + سليم)
        hic_patient_file = self._step_hic(
            patient_fasta_for_dnase, dnase_patient_file, input_data, coords=expanded_window, tag="patient"
        )
        hic_control_file = self._step_hic(
            control_fasta_for_dnase, dnase_control_file, input_data, coords=expanded_window, tag="control"
        )

        # الخطوة 10: 3D coordinates (+ nucleosome مدموجة) لمريض وسليم
        coords_patient_file = self._step_3d(
            hic_patient_file, input_data, tag="patient", dnase_file=dnase_patient_file
        )
        coords_control_file = self._step_3d(
            hic_control_file, input_data, tag="control", dnase_file=dnase_control_file
        )

        # الخطوة 11: Hi-C ديف (مقارنة بنيوية مبسطة)
        hic_diff = self._step_hic_diff(coords_patient_file, coords_control_file)

        # الخطوة 12: Motifs/البروتينات التنظيمية
        affected_proteins = self._step_motifs(
            patient_fasta_for_dnase, control_fasta_for_dnase, input_data,
            dnase_patient_file=dnase_patient_file,
            dnase_control_file=dnase_control_file,
            coords_patient_file=coords_patient_file,
            coords_control_file=coords_control_file,
            resolution=5000,
        )

        # الخطوة 13: تجميع كل شي بحمولة واحدة موحدة للتقرير
        report_payload = self._build_report_payload(
            genes_info=genes_info,
            nucleotide_diff=nucleotide_diff,
            proteins_diff=proteins_diff,
            dnase_diff=dnase_diff,
            hic_diff=hic_diff,
            affected_proteins=affected_proteins,
        )

        return {
            "hic_patient_file": hic_patient_file,
            "hic_control_file": hic_control_file,
            "coords_patient_file": coords_patient_file,
            "coords_control_file": coords_control_file,
            "affected_proteins": affected_proteins,
            "proteins_diff": proteins_diff, 
            "report_payload": report_payload,   
        }

    # ------------------------------------------------------------------
    # الخطوة 0
    # ------------------------------------------------------------------
    def _step_locate(self, patient_fasta_path: str, chromosome: str, input_data) -> dict:
        from services.genomics.referenceGenome.DNA_locator import locate_patient_sequence

        coords: dict = locate_patient_sequence(patient_fasta_path, chromosome_hint=chromosome)

        logger.info(
            "[Pipeline %s] الموقع: %s:%s-%s (strand=%s, identity=%.3f)",
            self.input_data_id, coords["chromosome"], coords["start"], coords["end"],
            coords["strand"], coords["identity"],
        )

        # المستخدم ما عاد يدخل start_pos/end_pos يدوياً — بنحفظ القيم المحسوبة
        # هون فور تحديدها، حتى تضل موجودة بالموديل (للعرض بالفرونت أو أي استعلام لاحق)
        input_data.start_pos = coords["start"]
        input_data.end_pos = coords["end"]
        input_data.save(update_fields=["start_pos", "end_pos"])

        return coords

    # ------------------------------------------------------------------
    # الخطوة 2: تحديد الجينات + حساب النافذة الموسّعة
    # ------------------------------------------------------------------
    def _step_find_genes(self, coords: dict, input_data) -> tuple[list, dict]:
        from services.genomics.proteomics.gtf_index import (
            build_gtf_index, find_genes_in_region, select_representative_transcript,
        )

        self._update_status(input_data, "pending")
        logger.info("[Pipeline %s] -> البحث عن الجينات المتقاطعة", self.input_data_id)

        gtf_path = settings.GTF_ANNOTATION_PATH          # مسار ملف gencode.v50.basic.annotation.gtf.gz
        cache_path = settings.GTF_INDEX_CACHE_PATH        # مسار ملف الفهرس المخزن (pickle)

        index = build_gtf_index(gtf_path, cache_path)
        raw_genes = find_genes_in_region(index, coords["chromosome"], coords["start"], coords["end"])

        genes_info = []
        expanded_start, expanded_end = coords["start"], coords["end"]

        for gene in raw_genes:
            transcript = select_representative_transcript(gene)
            if transcript is None:
                continue  # جين غير مرمّز (non-coding) — نتجاهله بمسار البروتين

            is_complete = gene["start"] >= coords["start"] and gene["end"] <= coords["end"]

            genes_info.append({
                "gene_id": gene["gene_id"],
                "gene_name": gene["gene_name"],
                "strand": gene["strand"],
                "gene_start": gene["start"],
                "gene_end": gene["end"],
                "transcript_id": transcript["transcript_id"],
                "exons": transcript["exons"],
                "cds_start": transcript["cds_start"],
                "cds_end": transcript["cds_end"],
                "is_complete_in_patient_sample": is_complete,   # ← لازم يترسم بالتقرير لو False
            })

            # توسيع النافذة لتغطي حدود الجين الكاملة
            expanded_start = min(expanded_start, gene["start"])
            expanded_end = max(expanded_end, gene["end"])

        expanded_window = {
            "chromosome": coords["chromosome"],
            "start": expanded_start,
            "end": expanded_end,
        }

        logger.info(
            "[Pipeline %s] لقينا %d جين مرمّز، النافذة الموسّعة: %s:%d-%d",
            self.input_data_id, len(genes_info),
            expanded_window["chromosome"], expanded_window["start"], expanded_window["end"],
        )
        return genes_info, expanded_window

    # ------------------------------------------------------------------
    # الخطوة 1: جلب السليم بالنافذة الموسّعة + تكميل ناقص المريض
    # ------------------------------------------------------------------
    def _step_fetch_and_complete(self, patient_fasta_path: str, coords: dict,
                                  expanded_window: dict, input_data) -> tuple[str, str]:
        from services.genomics.referenceGenome.fetcher import fetch_reference_sequence, fetch_reference_sequence_as_fasta_file
        from services.genomics.referenceGenome.DNA_locator import _read_fasta_sequence, _reverse_complement

        self._update_status(input_data, "pending")
        logger.info("[Pipeline %s] -> جلب السليم بالنافذة الموسّعة", self.input_data_id)

        # 1) السليم بالكامل — دايماً من المرجع، بالنافذة الموسّعة كاملة
        control_seq = fetch_reference_sequence(
            expanded_window["chromosome"], expanded_window["start"], expanded_window["end"]
        )

        control_fasta_path = fetch_reference_sequence_as_fasta_file(
            chromosome=expanded_window["chromosome"],
            start=expanded_window["start"],
            end=expanded_window["end"],
            output_dir=str(settings.MEDIA_ROOT) + "/genomics/raw_inputs/fasta/",
            record_id=f"control_{self.input_data_id}",
        )
        input_data.dna_control_file = control_fasta_path
        input_data.save(update_fields=["dna_control_file"])

        # 2) المريض — التسلسل الأصلي يلي عندنا
        original_patient_seq = _read_fasta_sequence(patient_fasta_path)

        # DNA_locator بيجرب الاتجاهين (+ و -) ويختار الأفضل تطابقاً.
        # لو طلع إنه أفضل تطابق كان عالـ reverse complement (strand == "-")،
        # هاد معناه إنه ملف المريض المرفوع أصلاً معكوس الاتجاه (مثلاً جاي من
        # NCBI efetch بصيغة complement/strand=2 بدل strand=1 المعتمدة عندنا).
        # لازم نصحح الاتجاه هون *قبل* أي مقارنة أو قص، لأنه control_seq
        # دايماً بيجي من fetcher.py بالخيط الموجب (plus) بشكل ثابت — فلو
        # ما صححنا، رح تنقارن تسلسلين بمنطقين معاكسين وتطلع مئات الفروقات
        # الوهمية بدل الطفرة الحقيقية الوحيدة.
        if coords.get("strand") == "-":
            logger.warning(
                "[Pipeline %s] تسلسل المريض المرفوع كان بالاتجاه المعاكس (reverse complement) "
                "— تم تصحيحه تلقائياً للخيط الموجب قبل المقارنة مع السليم",
                self.input_data_id,
            )
            original_patient_seq = _reverse_complement(original_patient_seq)

        # لو النافذة الموسّعة أكبر من نافذة المريض الأصلية (جين طالع برا حدود الملف)،
        # نكمّل الجزء الناقص من المرجع نفسه (مش من المريض — لأنه مش متوفر حقيقياً)
        if expanded_window["start"] < coords["start"] or expanded_window["end"] > coords["end"]:
            logger.warning(
                "[Pipeline %s] النافذة الموسّعة (%d-%d) أكبر من نافذة المريض الأصلية (%d-%d) — "
                "الأجزاء الناقصة رح تُكمّل من المرجع (مش من عينة المريض الفعلية)",
                self.input_data_id, expanded_window["start"], expanded_window["end"],
                coords["start"], coords["end"],
            )

            left_pad = ""
            if expanded_window["start"] < coords["start"]:
                left_pad = fetch_reference_sequence(
                    expanded_window["chromosome"], expanded_window["start"], coords["start"]
                )

            right_pad = ""
            if expanded_window["end"] > coords["end"]:
                right_pad = fetch_reference_sequence(
                    expanded_window["chromosome"], coords["end"], expanded_window["end"]
                )

            patient_seq = left_pad + original_patient_seq + right_pad
        else:
            patient_seq = original_patient_seq

        logger.info(
            "[Pipeline %s] المريض: %d bp، السليم: %d bp (بعد التوسيع)",
            self.input_data_id, len(patient_seq), len(control_seq),
        )
        return patient_seq, control_seq

    # ------------------------------------------------------------------
    # الخطوة 3: نيوكليوتيد ديف
    # ------------------------------------------------------------------
    def _step_nucleotide_diff(self, patient_seq: str, control_seq: str, expanded_window: dict) -> list:
        from services.genomics.referenceGenome.sequence_diff import compare_sequences_as_dict

        logger.info("[Pipeline %s] -> مقارنة النيوكليوتيدات", self.input_data_id)
        variants = compare_sequences_as_dict(patient_seq, control_seq, expanded_window["start"])
        logger.info("[Pipeline %s] لقينا %d فرق نيوكليوتيدي", self.input_data_id, len(variants))
        return variants

# ------------------------------------------------------------------
    # الخطوات 4-6: قص + بناء خريطة الكودونات + تصنيف الطفرة لكل جين
    # ------------------------------------------------------------------
    def _step_proteins(self, patient_seq: str, control_seq: str, expanded_window: dict, genes_info: list) -> list:
        from services.genomics.proteomics.splicer import extract_mature_cds_with_position_map, SplicingError
        from services.genomics.proteomics.translator import translate_dna_to_protein, build_codon_map
        from services.genomics.proteomics.mutation_classifier import classify_mutation

        self._update_status(input_data=self._input_data, status="pending")
        logger.info("[Pipeline %s] -> ترجمة ومقارنة البروتينات لـ %d جين", self.input_data_id, len(genes_info))

        proteins_diff = []

        for gene in genes_info:
            try:
                patient_cds, patient_position_map = extract_mature_cds_with_position_map(
                    genomic_sequence=patient_seq,
                    genomic_sequence_start=expanded_window["start"],
                    exons=gene["exons"], cds_start=gene["cds_start"], cds_end=gene["cds_end"],
                    strand=gene["strand"],
                )
                control_cds, control_position_map = extract_mature_cds_with_position_map(
                    genomic_sequence=control_seq,
                    genomic_sequence_start=expanded_window["start"],
                    exons=gene["exons"], cds_start=gene["cds_start"], cds_end=gene["cds_end"],
                    strand=gene["strand"],
                )
            except SplicingError as exc:
                logger.error("[Pipeline %s] فشل قص الجين %s: %s", self.input_data_id, gene["gene_name"], exc)
                proteins_diff.append({
                    "gene_name": gene["gene_name"],
                    "gene_id": gene["gene_id"],
                    "error": str(exc),
                    "is_complete_in_patient_sample": gene["is_complete_in_patient_sample"],
                })
                continue

            # ترجمة الملخص (سلسلة الأحماض الأمينية + تحذيرات) — زي ما كانت
            patient_result = translate_dna_to_protein(patient_cds, skip_atg_search=True)
            control_result = translate_dna_to_protein(control_cds, skip_atg_search=True)

            # خريطة الكودونات التفصيلية (رقم + كودون + حمض أميني + موقع جينومي)
            try:
                patient_codons = build_codon_map(patient_cds, patient_position_map)
                control_codons = build_codon_map(control_cds, control_position_map)
            except ValueError as exc:
                logger.error(
                    "[Pipeline %s] فشل بناء خريطة الكودونات للجين %s: %s",
                    self.input_data_id, gene["gene_name"], exc,
                )
                proteins_diff.append({
                    "gene_name": gene["gene_name"],
                    "gene_id": gene["gene_id"],
                    "error": str(exc),
                    "is_complete_in_patient_sample": gene["is_complete_in_patient_sample"],
                })
                continue

            diff = classify_mutation(
                patient_codons=patient_codons,
                control_codons=control_codons,
                patient_aa_seq=patient_result["amino_acid_sequence"],
                control_aa_seq=control_result["amino_acid_sequence"],
                patient_cds_len=len(patient_cds),
                control_cds_len=len(control_cds),
            )

            proteins_diff.append({
                "gene_name": gene["gene_name"],
                "gene_id": gene["gene_id"],
                "transcript_id": gene["transcript_id"],
                "strand": gene["strand"],
                "is_complete_in_patient_sample": gene["is_complete_in_patient_sample"],

                "mutation_type": diff["mutation_type"],
                "mutated_codons": diff["mutated_codons"],

                "patient": {
                    "mrna_sequence": patient_cds.replace("T", "U"),
                    "amino_acid_sequence": diff["patient_sequence"],
                    "protein_length": len(diff["patient_sequence"]),
                    "translation_warnings": patient_result["warnings"],
                },
                "control": {
                    "mrna_sequence": control_cds.replace("T", "U"),
                    "amino_acid_sequence": diff["control_sequence"],
                    "protein_length": len(diff["control_sequence"]),
                    "translation_warnings": control_result["warnings"],
                },

                # محفوظين داخلياً بس (مش لازم يترسلوا كاملين بالـ API response —
                # الـ serializer بيقدر يستبعدهم أو يستخدمهم لأغراض تانية زي AlphaFold)
                "_patient_codons_full": patient_codons,
                "_control_codons_full": control_codons,
            })

        logger.info("[Pipeline %s] تمت ترجمة ومقارنة %d جين", self.input_data_id, len(proteins_diff))
        return proteins_diff

    # ------------------------------------------------------------------
    # كتابة ملفات فاستا مؤقتة للنافذة الموسّعة (لازمة لـ DNase/Hi-C يلي بتاخد مسار ملف)
    # ------------------------------------------------------------------
    def _write_window_fasta_files(self, patient_seq: str, control_seq: str,
                                   expanded_window: dict, input_data) -> tuple[str, str]:
        folder = os.path.join(settings.MEDIA_ROOT, "genomics/raw_inputs/fasta/")
        os.makedirs(folder, exist_ok=True)

        def _write(seq: str, tag: str) -> str:
            path = os.path.join(folder, f"input_{self.input_data_id}_{tag}_window.fasta")
            with open(path, "w") as f:
                f.write(f">{tag}_{self.input_data_id}\n")
                for i in range(0, len(seq), 60):
                    f.write(seq[i:i + 60] + "\n")
            return path

        patient_path = _write(patient_seq, "patient")
        control_path = _write(control_seq, "control")
        return patient_path, control_path

    # ------------------------------------------------------------------
    # الخطوة 7: DNase
    # ------------------------------------------------------------------
    def _step_dnase(self, fasta_path: str, basset_track_id: int, input_data, tag: str) -> str:
        from services.genomics.DNASE.predictor import predict_dnase_profiles

        self._update_status(input_data, "predicting_dnase")
        logger.info("[Pipeline %s] -> DNase (%s)", self.input_data_id, tag)

        dnase_file: str = predict_dnase_profiles(fasta_path, basset_track_id)

        field = "predicted_dnase_patient" if tag == "patient" else "predicted_dnase_control"
        setattr(input_data, field, dnase_file)
        input_data.save(update_fields=[field])

        return dnase_file

    # ------------------------------------------------------------------
    # الخطوة 8: DNase ديف
    # ------------------------------------------------------------------
    def _step_dnase_diff(self, dnase_patient_file: str, dnase_control_file: str) -> dict:
        from core.utils.genomics_utils import call_dnase_peaks

        p_path = os.path.join(settings.MEDIA_ROOT, dnase_patient_file)
        c_path = os.path.join(settings.MEDIA_ROOT, dnase_control_file)

        patient_signal = np.load(p_path).astype(np.float32)
        control_signal = np.load(c_path).astype(np.float32)

        patient_peaks = call_dnase_peaks(patient_signal, min_fraction_of_max=0.5, min_peak_width=10)
        control_peaks = call_dnase_peaks(control_signal, min_fraction_of_max=0.5, min_peak_width=10)

        def _peak_set(peaks):
            return {(s, e) for s, e in peaks}

        patient_set, control_set = _peak_set(patient_peaks), _peak_set(control_peaks)

        return {
            "patient_open_regions": patient_peaks,
            "control_open_regions": control_peaks,
            "regions_lost_in_patient": list(control_set - patient_set),   # كانت مفتوحة، صارت مقفولة
            "regions_gained_in_patient": list(patient_set - control_set), # العكس
        }

    # ------------------------------------------------------------------
    # الخطوة 9: Hi-C
    # ------------------------------------------------------------------
    def _step_hic(self, fasta_path: str, dnase_file: str, input_data, coords: dict, tag: str) -> str:
        from services.genomics.HI_C.predictorHIC import generate_hic_matrices

        self._update_status(input_data, "generating_hic")
        logger.info("[Pipeline %s] -> Hi-C (%s)", self.input_data_id, tag)

        hic_file: str = generate_hic_matrices(
            fasta_path, dnase_file,
            output_name_hint=f"input_{self.input_data_id}_{tag}",
            chrom=coords.get("chromosome"), start_pos=coords.get("start", 0),
        )
        return hic_file

    # ------------------------------------------------------------------
    # الخطوة 10: 3D coordinates (+ nucleosome مدموجة جواها)
    # ------------------------------------------------------------------
    def _step_3d(self, hic_file_path: str, input_data, tag: str, dnase_file: str = None) -> str:
        import json
        from services.genomics.calculating_3d.coords_service import build_structure

        self._update_status(input_data, "generating_hic_coords")
        logger.info("[Pipeline %s] -> بناء الشكل ثلاثي الأبعاد (%s)", self.input_data_id, tag)

        dnase_array = None
        if dnase_file:
            p = os.path.join(settings.MEDIA_ROOT, dnase_file)
            if os.path.exists(p):
                dnase_array = np.load(p).astype(np.float32)

        absolute_hic_path = os.path.join(settings.MEDIA_ROOT, hic_file_path)
        result = build_structure(
            absolute_hic_path, alpha=0.5, verbose=False, dnase_signal=dnase_array,
        )

        relative_folder = "genomics/coordinates_3d/json/"
        absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
        os.makedirs(absolute_folder, exist_ok=True)

        output_filename = f"input_{self.input_data_id}_{tag}_coords.json"
        absolute_output_path = os.path.join(absolute_folder, output_filename)

        with open(absolute_output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

        return os.path.join(relative_folder, output_filename)

    # ------------------------------------------------------------------
    # الخطوة 11: Hi-C ديف (مقارنة بنيوية مبسطة)
    # ------------------------------------------------------------------
    def _step_hic_diff(self, coords_patient_file: str, coords_control_file: str) -> dict:
        import json

        def _load(rel_path):
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            with open(abs_path, "r", encoding="utf-8") as f:
                return json.load(f)

        patient = _load(coords_patient_file)
        control = _load(coords_control_file)

        return {
            "patient_stress": patient.get("stress"),
            "control_stress": control.get("stress"),
            "patient_n_tads": patient.get("n_tads"),
            "control_n_tads": control.get("n_tads"),
            "patient_collapse_ratio": patient.get("collapse_ratio"),
            "control_collapse_ratio": control.get("collapse_ratio"),
            # ملاحظة: هاي مقارنة إحصائية سطحية بس (استقرار الحساب نفسه)،
            # مش مقارنة بنيوية حقيقية بين المصفوفتين — لازم تتطور لاحقاً
            # لو المركز طلب تفاصيل بنيوية أدق (زي RMSD بين المصفوفتين).
        }

    # ------------------------------------------------------------------
    # الخطوة 12: Motifs (زي ما كانت، بدون تغيير بالمنطق)
    # ------------------------------------------------------------------
    def _step_motifs(self, patient_fasta_path: str, control_fasta_path: str, input_data,
                      dnase_patient_file: str = None, dnase_control_file: str = None,
                      coords_patient_file: str = None, coords_control_file: str = None,
                      resolution: int = 5000) -> dict:
        import json
        # from services.genomics.scanning_motifs.scanner import calculate_spatial_docking, run_motif_delta_analysis

        # self._update_status(input_data, "scanning_motifs")
        # logger.info("[Pipeline %s] -> فحص الـ Motifs", self.input_data_id)

        # patient_dnase_array = control_dnase_array = None
        # if dnase_patient_file:
        #     p_path = os.path.join(settings.MEDIA_ROOT, dnase_patient_file)
        #     if os.path.exists(p_path):
        #         patient_dnase_array = np.load(p_path).astype(np.float32)
        # if dnase_control_file:
        #     c_path = os.path.join(settings.MEDIA_ROOT, dnase_control_file)
        #     if os.path.exists(c_path):
        #         control_dnase_array = np.load(c_path).astype(np.float32)

        # patient_motifs = run_motif_delta_analysis(patient_fasta_path, dnase_signal=patient_dnase_array)
        # control_motifs = run_motif_delta_analysis(control_fasta_path, dnase_signal=control_dnase_array)

        # def _load_coords_raw(rel_path):
        #     if not rel_path:
        #         return []
        #     abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
        #     if not os.path.exists(abs_path):
        #         return []
        #     with open(abs_path, "r", encoding="utf-8") as f:
        #         return json.load(f).get("coords_raw", [])

        # patient_coords_raw = _load_coords_raw(coords_patient_file)
        # control_coords_raw = _load_coords_raw(coords_control_file)

        # all_protein_ids = set(patient_motifs.keys()) | set(control_motifs.keys())
        # affected_proteins = {}

        # for protein_id in all_protein_ids:
        #     patient_info = patient_motifs.get(protein_id)
        #     control_info = control_motifs.get(protein_id)
        #     is_missing = control_info is not None and patient_info is None
        #     motif_info = patient_info or control_info
        #     protein_name = motif_info.get("protein_name") or protein_id

        #     patient_position_index = patient_info.get("position_index") if patient_info else None
        #     control_position_index = control_info.get("position_index") if control_info else None

        #     patient_docking = calculate_spatial_docking(patient_coords_raw, patient_position_index, resolution) \
        #         if patient_info else None
        #     control_docking = calculate_spatial_docking(control_coords_raw, control_position_index, resolution) \
        #         if control_info else None

        #     delta_score = None
        #     if patient_info and control_info:
        #         delta_score = patient_info.get("delta_score", 0) - control_info.get("delta_score", 0)
        #     elif motif_info:
        #         delta_score = motif_info.get("delta_score")
        #     # now we dont need it so empty dict for missing proteins, but we keep it for now for backward compatibility
        #     affected_proteins[protein_id] =  {} 

        return {}

    # ------------------------------------------------------------------
    # الخطوة 13: تجميع كل الفروقات بحمولة واحدة موحدة (اللي بتنبعت للتقرير)
    # ------------------------------------------------------------------
    def _build_report_payload(self, genes_info, nucleotide_diff, proteins_diff,
                               dnase_diff, hic_diff, affected_proteins) -> dict:
        """
        الحمولة النهائية الموحدة — هاي يلي رح تنبعت لتابع توليد التقرير
        (وبعدين لـ LLM). كل قيمها محسوبة مسبقاً (deterministic) —
        دور LLM لاحقاً بس صياغة، مش استنتاج.
        """
        return {
            "genes": genes_info,
            "nucleotide_diff": nucleotide_diff,
            "amino_acid_and_protein_diff": proteins_diff,
            "dnase_diff": dnase_diff,
            "hic_diff": hic_diff,
            "regulatory_binding_diff": affected_proteins,
            "summary_counts": {
                "n_nucleotide_variants": len(nucleotide_diff),
                "n_genes_analyzed": len(proteins_diff),
                "n_genes_with_mutation": sum(
                    1 for p in proteins_diff if p.get("mutation_type") not in (None, "none")
                ),
                "n_incomplete_genes": sum(
                    1 for g in genes_info if not g.get("is_complete_in_patient_sample", True)
                ),
            },
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _update_status(input_data, status: str) -> None:
        input_data.refresh_from_db(fields=["status"])
        if input_data.status == "cancelled":
            raise PipelineCancelledError(
                f"Pipeline cancelled by user request (InputData id={input_data.pk})"
            )

        input_data.status = status
        input_data.save(update_fields=["status", "updated_at"])   # ← تأكد إنه فيها updated_at