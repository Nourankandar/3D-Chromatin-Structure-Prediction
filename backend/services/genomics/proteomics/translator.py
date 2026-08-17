"""
services/genomics/referenceGenome/translator.py
مسؤولية هذا الملف: تحويل تسلسل DNA (أو RNA) إلى تسلسل أحماض أمينية (Protein)
باستخدام الشفرة الوراثية القياسية (Standard Genetic Code).

هذه العملية حتمية بالكامل (deterministic) ولا تعتمد على أي نموذج ذكاء اصطناعي.
"""

from typing import Dict, List, TypedDict


# ---------------------------------------------------------------------------
# 1. جدول الشفرة الوراثية القياسية (Standard Genetic Code)
# ---------------------------------------------------------------------------
CODON_TABLE: Dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",

    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",

    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",

    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

STOP_CODONS = {"TAA", "TAG", "TGA"}
START_CODON = "ATG"
UNKNOWN_AA_SYMBOL = "X"
VALID_DNA_BASES = {"A", "C", "G", "T"}


class TranslationResult(TypedDict):
    amino_acid_sequence: str
    has_start_codon: bool
    stopped_at_stop_codon: bool
    warnings: List[str]


# ---------------------------------------------------------------------------
# 2. تنظيف وتنظيم المدخلات (Data Sanitization)
# ---------------------------------------------------------------------------
def _sanitize_sequence(raw_sequence: str, warnings: List[str]) -> str:
    """
    - تحويل الأحرف إلى حروف كبيرة.
    - تحويل U (RNA) إلى T (DNA) تلقائياً.
    - إزالة أي مسافات/أسطر جديدة قد تكون مرفقة بالملف.
    - الإبقاء فقط على A, C, G, T, N (الحرف N = قاعدة مجهولة).
    """
    sequence = raw_sequence.strip().upper()
    sequence = "".join(sequence.split())  # إزالة أي whitespace داخلي

    if "U" in sequence:
        warnings.append(
            "تم اكتشاف تسلسل RNA (يحتوي على U) وتم تحويله تلقائياً إلى DNA (T)."
        )
        sequence = sequence.replace("U", "T")

    allowed_chars = VALID_DNA_BASES | {"N"}
    invalid_chars = {ch for ch in sequence if ch not in allowed_chars}
    if invalid_chars:
        warnings.append(
            f"تم العثور على أحرف غير مقبولة في التسلسل وتم تجاهلها: "
            f"{', '.join(sorted(invalid_chars))}"
        )
        sequence = "".join(ch for ch in sequence if ch in allowed_chars)

    return sequence


# ---------------------------------------------------------------------------
# 3. البحث عن كودون البداية (Start Codon) — يُستخدم فقط لو skip_atg_search=False
# ---------------------------------------------------------------------------
def _find_start_index(sequence: str) -> int:
    """
    يرجع فهرس (index) أول ظهور لـ ATG في التسلسل.
    يرجع -1 إن لم يوجد كودون بداية.
    """
    return sequence.find(START_CODON)


# ---------------------------------------------------------------------------
# 4. التابع الرئيسي: الترجمة الكاملة
# ---------------------------------------------------------------------------
def translate_dna_to_protein(
    raw_sequence: str,
    skip_atg_search: bool = False,
) -> TranslationResult:
    """
    يحول تسلسل DNA/RNA خام إلى سلسلة أحماض أمينية وفق الشفرة الوراثية القياسية.

    Args:
        raw_sequence: السلسلة الخام (قد تحتوي أحرف صغيرة، مسافات، أو RNA).
        skip_atg_search: لو True، يبدأ الترجمة من أول حرف بالتسلسل مباشرة
                          بدون أي بحث عن ATG — يُستخدم حصراً لما يكون
                          التسلسل قادم من splicer.py (extract_mature_cds)،
                          لأنه بهاي الحالة بداية الترجمة مؤكدة 100% من
                          حدود CDS بملف GTF نفسه، والبحث العشوائي عن ATG
                          ممكن يلتقط ATG خاطئ لو صدفة تكرر داخل الـ CDS
                          (upstream في-frame match غير حقيقي).
                          لو False (الافتراضي)، يبحث عن أول ATG بالتسلسل —
                          يُستخدم فقط للاختبار المستقل أو لو ما توفر GTF.

    Returns:
        TranslationResult
    """
    warnings: List[str] = []

    # 1) تنظيف المدخلات
    sequence = _sanitize_sequence(raw_sequence, warnings)

    if not sequence:
        warnings.append("التسلسل فارغ بعد عملية التنظيف.")
        return {
            "amino_acid_sequence": "",
            "has_start_codon": False,
            "stopped_at_stop_codon": False,
            "warnings": warnings,
        }

    if skip_atg_search:
        coding_sequence = sequence
        has_start_codon = sequence.startswith(START_CODON)
        if not has_start_codon:
            warnings.append(
                "التسلسل القادم من الـ splicer لا يبدأ بـ ATG كما هو متوقع — "
                "تحقق من حدود الـ CDS بملف GTF أو من دقة عملية القص."
            )
    else:
        start_index = _find_start_index(sequence)
        has_start_codon = start_index != -1

        if not has_start_codon:
            warnings.append(
                "لم يتم العثور على كودون بداية (ATG) في التسلسل؛ "
                "لا يمكن بدء عملية الترجمة."
            )
            return {
                "amino_acid_sequence": "",
                "has_start_codon": False,
                "stopped_at_stop_codon": False,
                "warnings": warnings,
            }

        coding_sequence = sequence[start_index:]

    # 3) التحقق من أن الطول من مضاعفات 3 (Frameshift check)
    remainder = len(coding_sequence) % 3
    start_index_for_reporting = 0 if skip_atg_search else sequence.find(coding_sequence)
    if remainder != 0:
        warnings.append(
            f"طول التسلسل القابل للترجمة ({len(coding_sequence)} قاعدة) "
            f"ليس من مضاعفات 3. سيتم تجاهل آخر {remainder} قاعدة/قواعد غير مكتملة "
            f"(احتمال Frameshift حقيقي لو المصدر splicer — راجع طول الـ CDS بالـ GTF)."
        )
        coding_sequence = coding_sequence[: len(coding_sequence) - remainder]

    # 4) الترجمة كودون-كودون مع التوقف عند كودون الإيقاف
    amino_acids: List[str] = []
    stopped_at_stop_codon = False
    unknown_codon_positions: List[int] = []

    for i in range(0, len(coding_sequence), 3):
        codon = coding_sequence[i : i + 3]

        if codon in STOP_CODONS:
            stopped_at_stop_codon = True
            break

        amino_acid = CODON_TABLE.get(codon)

        if amino_acid is None:
            amino_acids.append(UNKNOWN_AA_SYMBOL)
            unknown_codon_positions.append(start_index_for_reporting + i)
        else:
            amino_acids.append(amino_acid)

    if unknown_codon_positions:
        warnings.append(
            f"تم العثور على {len(unknown_codon_positions)} كودون يحتوي على "
            f"أحرف مجهولة (N) وتمت ترجمته كـ '{UNKNOWN_AA_SYMBOL}'."
        )

    if not stopped_at_stop_codon:
        if skip_atg_search:
            
            pass
        else:
            warnings.append(
                "انتهى التسلسل قبل الوصول إلى كودون إيقاف طبيعي "
                "(TAA / TAG / TGA) — لم يتم العثور على ATG بدء صريح "
                "متبوع بكودون إيقاف ضمن التسلسل المُدخل."
            )

    return {
        "amino_acid_sequence": "".join(amino_acids),
        "has_start_codon": has_start_codon,
        "stopped_at_stop_codon": stopped_at_stop_codon,
        "warnings": warnings,
    }


# إضافة على translator.py

AMINO_ACID_FULL_NAMES: Dict[str, str] = {
    "A": "Ala", "R": "Arg", "N": "Asn", "D": "Asp", "C": "Cys",
    "E": "Glu", "Q": "Gln", "G": "Gly", "H": "His", "I": "Ile",
    "L": "Leu", "K": "Lys", "M": "Met", "F": "Phe", "P": "Pro",
    "S": "Ser", "T": "Thr", "W": "Trp", "Y": "Tyr", "V": "Val",
    "*": "Stop", "X": "Unknown",
}


class CodonInfo(TypedDict):
    codon_number: int          # 1-based
    codon: str                 # بصيغة mRNA (U مش T)
    amino_acid: str            # "Val (V)" مثلاً
    genomic_position: int      # موقع أول حرف بالكودون عالكروموسوم


def build_codon_map(
    mature_cds: str,
    position_map: List[int],
    skip_atg_search: bool = True,
) -> List[CodonInfo]:
    """
    يبني قائمة كاملة بكل كودون مترجم مع رقمه وموقعه الجينومي — بالاعتماد
    على mature_cds و position_map (الطالعين من
    splicer.extract_mature_cds_with_position_map، بنفس الطول بالضبط).

    ملاحظة: هاي دالة منفصلة عن translate_dna_to_protein — بترجع تفاصيل
    كل كودون (مفيدة لعرض الطفرة بدقة)، بينما translate_dna_to_protein
    بترجع الملخص (سلسلة الأحماض الأمينية + تحذيرات).
    """
    warnings: List[str] = []
    sequence = _sanitize_sequence(mature_cds, warnings)

    if len(sequence) != len(position_map):
        # لو صار تنظيف (شيل أحرف غير صالحة)، الطول بيختل — نوقف بأمان
        raise ValueError(
            f"طول التسلسل بعد التنظيف ({len(sequence)}) لا يطابق طول "
            f"position_map ({len(position_map)}) — تأكد من نظافة مدخلات CDS."
        )

    remainder = len(sequence) % 3
    if remainder:
        sequence = sequence[: len(sequence) - remainder]

    codons: List[CodonInfo] = []
    for codon_index, i in enumerate(range(0, len(sequence), 3),start=1):
        codon_dna = sequence[i : i + 3]
        codon_mrna = codon_dna.replace("T", "U")

        if codon_dna in STOP_CODONS:
            break

        amino_acid_letter = CODON_TABLE.get(codon_dna, UNKNOWN_AA_SYMBOL)
        full_name = AMINO_ACID_FULL_NAMES.get(amino_acid_letter, "Unknown")

        codons.append({
            "codon_number": codon_index,
            "codon": codon_mrna,
            "amino_acid": f"{full_name} ({amino_acid_letter})",
            "genomic_position": position_map[i],
        })

    return codons