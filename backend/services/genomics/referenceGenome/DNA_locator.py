"""
services/genome_reference/DNA_locator.py
====================================================================
يستقبل تسلسل المريض (طول متغير) + رقم الكروموسوم فقط (بدون أي إحداثيات
مسبقة)، ويلاقي موقعه الحقيقي (start/end) على ذاك الكروموسوم بالتحديد
من الجينوم المرجعي.

ليش مش minimap2؟
-----------------
minimap2 محتاج binary/compile على مستوى نظام التشغيل (لينوكس/دوكر)،
وهاد غير متوفر ببيئة التطوير الحالية. بدلاً منه، هاد الملف بيطبّق
خوارزمية "seed-and-extend" خفيفة، pure Python فقط:

  1) نجيب تسلسل الكروموسوم المطلوب (وبس هو، مش الجينوم كامل) عبر
     pyfaidx (نفس المكتبة المستخدمة أصلاً بـ fetcher.py).
  2) ناخذ عدة "seeds" (مقاطع قصيرة، افتراضياً 25bp) من أماكن متفرقة
     بتسلسل المريض.
  3) نلاقي كل مواقع التطابق التام لكل seed بالكروموسوم عبر str.find
     (بحث نصي C-optimized، سريع جداً حتى على كروموسوم كامل).
  4) كل seed match بيرجّح "موقع بداية مرشح" للتسلسل الكامل
     (candidate_start = match_pos - seed_offset_in_patient).
  5) نصوّت (voting/Counter) على أكثر موقع مرشح تكرر بين كل الـ seeds.
  6) نتحقق (verify) بمقارنة التسلسل كامل عند ذاك الموقع، ونحسب نسبة
     التطابق (identity %) كبديل عملي عن mapq.
  7) نجرب أيضاً الـ reverse complement (لأنه المريض ممكن يكون تسلسله
     من الخيط المعاكس)، ونختار الأفضل (identity أعلى) بين الاتجاهين.

هاد الأسلوب مش بديل عام عن aligner كامل (زي minimap2)، بس كافي ومنطقي
لحالتنا: عندنا رقم الكروموسوم مسبقاً (مش لازم نفتش الجينوم كامل)،
وبنتوقع تسلسل مريض قريب جداً من المرجعي (SNPs/small variants) مش
تسلسل عشوائي كامل الاختلاف.
====================================================================
"""

import logging
from collections import Counter
from pathlib import Path

from django.conf import settings
from pyfaidx import Fasta

from services.genomics.referenceGenome.kmer_index import get_or_build_kmer_index

logger = logging.getLogger(__name__)

# إعدادات الخوارزمية (قابلة للتعديل حسب طول التسلسلات المتوقعة)
SEED_LENGTH = 25          # طول كل seed (25bp نادراً ما يتكرر عشوائياً بكروموسوم كامل)
SEED_STRIDE = 200         # المسافة بين كل seed والتالي على طول تسلسل المريض
MIN_SEEDS_REQUIRED = 1    # أقل عدد seeds لازم تتفق على نفس الموقع المرشح
MIN_IDENTITY = 0.80       # أقل نسبة تطابق مقبولة بعد التحقق (verify)
AMBIGUITY_IDENTITY_MARGIN = 0.02   # الفرق الأدنى المطلوب بين أفضل مرشح والثاني
MAX_RAW_SEED_HITS_BEFORE_WARNING = 50  # عدد مواقع seed matches اللي لو تعداه، فالمنطقة غالباً متكررة (low-complexity)


MAX_HITS_PER_SEED = 100

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


class SequenceLocationError(Exception):
    """يُرفع عند فشل مطابقة تسلسل المريض على الجينوم المرجعي."""


class SequenceAmbiguityError(SequenceLocationError):
    """
    يُرفع عندما نلاقي أكتر من موقع مرشح بنفس قوة التطابق تقريباً — عادة
    لأنه التسلسل المُدخل من منطقة متكررة بطبيعتها بالجينوم (تيلومير،
    سنترومير، أو أي low-complexity/repetitive region)، فمافي موقع
    "صحيح وحيد" أصلاً لنحدده بثقة.
    """


def _read_fasta_sequence(fasta_path: str) -> str:
    with open(fasta_path, "r") as f:
        lines = f.readlines()
    return "".join(line.strip() for line in lines if not line.startswith(">")).upper()


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def _load_chromosome_sequence(chromosome: str) -> tuple[str, str]:
    """
    يجيب تسلسل كروموسوم واحد بس (مش الجينوم كامل) عبر pyfaidx.

    Returns
    -------
    (sequence, genome_fa_path): التسلسل + مسار ملف genome.fa الأصلي —
    المسار لازم نرجعه كمان حتى نقدر نبني/نتحقق من فهرس الـ k-mer
    (get_or_build_kmer_index بيحتاجه لمقارنة mtime).
    """
    fasta_path = Path(settings.GENOME_REFERENCE_ROOT) / "genome.fa"
    if not fasta_path.exists():
        raise SequenceLocationError(f"Reference genome not found at {fasta_path}")

    genome = Fasta(str(fasta_path), rebuild=False)

    chrom_key = chromosome
    if chrom_key not in genome.keys():
        alt = f"chr{chromosome}" if not chromosome.startswith("chr") else chromosome.replace("chr", "", 1)
        if alt in genome.keys():
            chrom_key = alt
        else:
            available_preview = list(genome.keys())[:5]
            raise SequenceLocationError(
                f"Chromosome '{chromosome}' not found in reference. Available: {available_preview}..."
            )

    sequence = str(genome[chrom_key][:]).upper()
    genome.close()
    return sequence, str(fasta_path)


def _seed_and_extend(patient_seq: str, chrom_seq: str, kmer_index: dict) -> dict | None:
    """
    يرجع dict فيه: start, identity, is_ambiguous, second_best_identity,
    raw_seed_hit_count — أو None لو ما لقى تطابق كافي إطلاقاً.

    kmer_index: فهرس k-mer مبني مسبقاً لنفس chrom_seq (من kmer_index.py)
    — بيستخدم فقط لحالة الـ seeds العادية (طول SEED_LENGTH بالضبط).
    """
    patient_len = len(patient_seq)
    chrom_len = len(chrom_seq)

    if patient_len < SEED_LENGTH:
        
        first_pos = chrom_seq.find(patient_seq)
        if first_pos == -1:
            return None
        second_pos = chrom_seq.find(patient_seq, first_pos + 1)
        return {
            "start": first_pos,
            "identity": 1.0,
            "is_ambiguous": second_pos != -1,
            "second_best_identity": 1.0 if second_pos != -1 else 0.0,
            "raw_seed_hit_count": 2 if second_pos != -1 else 1,
        }

   
    if patient_len - SEED_LENGTH + 1 <= SEED_STRIDE:
        dense_stride = max(5, (patient_len - SEED_LENGTH) // 4) or 1
        seed_offsets = range(0, patient_len - SEED_LENGTH + 1, dense_stride)
    else:
        seed_offsets = range(0, patient_len - SEED_LENGTH + 1, SEED_STRIDE)

    candidate_votes: Counter = Counter()
    raw_seed_hit_count = 0        # مجموع كل الـ hits المقبولة (المستخدمة فعلياً بالتصويت)
    skipped_repetitive_seeds = 0  # عدد الـ seeds يلي رفضناها لأنها ضربت السقف (تشخيصي بس)

    for offset in seed_offsets:
        seed = patient_seq[offset: offset + SEED_LENGTH]
        if "N" in seed:
            continue  # seed فيه قواعد غير معروفة — نتخطاه لأنه غير موثوق

        
        seed_positions = kmer_index.get(seed)
        if not seed_positions:
            continue  # ما في أي تطابق تام لهاد الـ seed بالكروموسوم إطلاقاً

        if len(seed_positions) > MAX_HITS_PER_SEED:
            # نفس المنطق القديم بالضبط: seed بمنطقة متكررة جداً (زي Alu) —
            # نرفض كل أصوات هالـ seed حتى ما نلوّث التصويت بانحياز جزئي.
            skipped_repetitive_seeds += 1
            continue

        for match_pos in seed_positions:
            candidate_start = match_pos - offset
            if 0 <= candidate_start < chrom_len:
                candidate_votes[candidate_start] += 1
                raw_seed_hit_count += 1

    if skipped_repetitive_seeds:
        logger.warning(
            "[Locator] تجاهلنا %d seed من أصل تسلسل المريض لأنها بمناطق "
            "متكررة جداً (تعدّت %d تكرار) — اعتمدنا فقط على الـ seeds الفريدة "
            "لتحديد الموقع.",
            skipped_repetitive_seeds, MAX_HITS_PER_SEED,
        )

    if not candidate_votes:
        return None

    # 2) نتحقق (verify) من كل المرشحين المحتملين — مش أفضل واحد بس —
    #    حتى نقدر نقارن أفضل نتيجة بالثانية ونكشف الـ ambiguity
    verified_candidates = []  # [(start, identity), ...]
    # نوسّع دائرة الفحص شوي (10 بدل 5) لأنه بمناطق متكررة ممكن الموقع
    # الصحيح يكون مو أعلى تصويت بالضبط
    for candidate_start, votes in candidate_votes.most_common(10):
        if votes < MIN_SEEDS_REQUIRED:
            continue
        candidate_end = candidate_start + patient_len
        if candidate_end > chrom_len:
            continue

        reference_window = chrom_seq[candidate_start:candidate_end]
        matches = sum(1 for a, b in zip(patient_seq, reference_window) if a == b)
        identity = matches / patient_len
        verified_candidates.append((candidate_start, identity))

    if not verified_candidates:
        return None

    verified_candidates.sort(key=lambda pair: pair[1], reverse=True)
    best_start, best_identity = verified_candidates[0]
    second_best_identity = verified_candidates[1][1] if len(verified_candidates) > 1 else 0.0

    # الموقع يعتبر "ambiguous" لو في مرشح تاني قريب جداً من الأفضل بالتطابق،
    # أو لو عدد مواقع الـ seed hits الخام كان كبير جداً (مؤشر لمنطقة متكررة)
    is_ambiguous = (
        (best_identity - second_best_identity) < AMBIGUITY_IDENTITY_MARGIN
        or raw_seed_hit_count > MAX_RAW_SEED_HITS_BEFORE_WARNING
    )

    return {
        "start": best_start,
        "identity": best_identity,
        "is_ambiguous": is_ambiguous,
        "second_best_identity": second_best_identity,
        "raw_seed_hit_count": raw_seed_hit_count,
    }


def locate_patient_sequence(
    patient_fasta_path: str,
    chromosome_hint: str | None = None,
    **kwargs,
) -> dict:
    """
    يحدد موقع تسلسل المريض الحقيقي على الكروموسوم المُعطى، عبر
    seed-and-extend (بدون minimap2 أو أي binary خارجي).

    Parameters
    ----------
    patient_fasta_path : مسار ملف الـ FASTA تبع المريض
    chromosome_hint : رقم/اسم الكروموسوم (إلزامي عملياً بحالتنا — هو
                       المعلومة الوحيدة المتوفرة مسبقاً عن الموقع)

    Returns
    -------
    dict فيه: chromosome, start, end, strand, identity

    Raises
    ------
    SequenceLocationError لو ما قدرنا نلاقي موقع بنسبة تطابق كافية
    """
    if not chromosome_hint:
        raise SequenceLocationError("chromosome_hint is required — لازم رقم الكروموسوم")

    patient_seq = _read_fasta_sequence(patient_fasta_path)
    if not patient_seq:
        raise SequenceLocationError("Patient FASTA file is empty or unreadable")

    chromosome = str(chromosome_hint)
    logger.info("[Locator] Loading chromosome '%s' reference sequence...", chromosome)
    chrom_seq, genome_fa_path = _load_chromosome_sequence(chromosome)

    # فهرس الـ k-mer: يُبنى مرة وحدة فقط لكل كروموسوم (ويُخزّن على القرص)،
    # وبعدين نفس الفهرس مستخدم للبحث بالاتجاهين (forward + reverse
    # complement) — لأنه الفهرس مبني على chrom_seq (الخيط الموجب) فقط،
    # والاتجاه المعاكس بنعالجه بعمل reverse complement لتسلسل المريض
    # نفسه، مش بإعادة فهرسة الكروموسوم.
    kmer_index = get_or_build_kmer_index(
        chromosome=chromosome,
        chrom_seq=chrom_seq,
        genome_fa_path=genome_fa_path,
        cache_dir=settings.GENOME_KMER_INDEX_CACHE_ROOT,
    )

    logger.info("[Locator] Searching forward strand (%d bp patient seq)...", len(patient_seq))
    forward_result = _seed_and_extend(patient_seq, chrom_seq, kmer_index)

    logger.info("[Locator] Searching reverse-complement strand...")
    reverse_seq = _reverse_complement(patient_seq)
    reverse_result = _seed_and_extend(reverse_seq, chrom_seq, kmer_index)

    # نختار الاتجاه صاحب أعلى identity
    best_strand, best_result = "+", forward_result
    if reverse_result and (not forward_result or reverse_result["identity"] > forward_result["identity"]):
        best_strand, best_result = "-", reverse_result

    if best_result is None or best_result["identity"] < MIN_IDENTITY:
        found_identity = round(best_result["identity"], 3) if best_result else 0.0
        raise SequenceLocationError(
            f"Could not confidently locate patient sequence on chromosome '{chromosome}' "
            f"(best identity found: {found_identity}, minimum required: {MIN_IDENTITY})"
        )

    if best_result["is_ambiguous"]:
        raise SequenceAmbiguityError(
            f"Patient sequence matches multiple locations on chromosome '{chromosome}' "
            f"with near-equal confidence (best identity={best_result['identity']:.3f}, "
            f"second best identity={best_result['second_best_identity']:.3f}, "
            f"raw seed hits={best_result['raw_seed_hit_count']}). "
            f"This usually means the sequence falls in a repetitive region "
            f"(telomere, centromere, or other low-complexity DNA) where no single "
            f"location can be confidently determined. Consider using a longer or "
            f"more unique region of the patient's sequence."
        )

    start = best_result["start"]
    identity = best_result["identity"]
    end = start + len(patient_seq)

    logger.info(
        "[Locator] Located: %s:%s-%s (strand=%s, identity=%.3f)",
        chromosome, start, end, best_strand, identity,
    )

    return {
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "strand": best_strand,
        "identity": round(identity, 4),
    }