"""
services/proteomics/translator.py

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
# 3. البحث عن كودون البداية (Start Codon)
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
def translate_dna_to_protein(raw_sequence: str) -> TranslationResult:
    """
    يحول تسلسل DNA/RNA خام إلى سلسلة أحماض أمينية وفق الشفرة الوراثية القياسية.

    Args:
        raw_sequence: السلسلة الخام كما وردت من الملف المرفوع (قد تحتوي أحرف صغيرة،
                      مسافات، أو حتى RNA).

    Returns:
        TranslationResult: قاموس يحتوي على تسلسل الأحماض الأمينية، وحالة وجود
        كودون البداية، وحالة التوقف عند كودون إيقاف طبيعي، وقائمة التحذيرات.
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

    # 2) البحث عن كودون البداية ATG
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
    if remainder != 0:
        warnings.append(
            f"طول التسلسل القابل للترجمة ({len(coding_sequence)} قاعدة) "
            f"ليس من مضاعفات 3. سيتم تجاهل آخر {remainder} قاعدة/قواعد غير مكتملة "
            f"(احتمال Frameshift)."
        )
        # قص الأحرف الزائدة غير المكتملة في نهاية التسلسل
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
            # كودون يحتوي على N أو حرف مجهول لم يُترجم من القاموس
            amino_acids.append(UNKNOWN_AA_SYMBOL)
            unknown_codon_positions.append(start_index + i)
        else:
            amino_acids.append(amino_acid)

    if unknown_codon_positions:
        warnings.append(
            f"تم العثور على {len(unknown_codon_positions)} كودون يحتوي على "
            f"أحرف مجهولة (N) وتمت ترجمته كـ '{UNKNOWN_AA_SYMBOL}'."
        )

    if not stopped_at_stop_codon:
        warnings.append(
            "انتهى التسلسل قبل الوصول إلى كودون إيقاف طبيعي "
            "(TAA / TAG / TGA)."
        )

    return {
        "amino_acid_sequence": "".join(amino_acids),
        "has_start_codon": has_start_codon,
        "stopped_at_stop_codon": stopped_at_stop_codon,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# اختبار سريع عند تشغيل الملف مباشرة
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        "atgGTCCACCTGACTCCTGAGGAGAAGTAAextra",  # سليم + كودون إيقاف
        "uugAUGGUCCACCUGACUCCUGAGGAGAAGUGA",     # RNA يحتاج تحويل
        "ATGGTCCACCTGACTCCTGAGGAGAAG",           # بدون كودون إيقاف
        "ATGGTCNACCTGACTCCTGAGTAA",              # يحتوي N
        "GGGATGGTCCACTGA",                       # ATG ليست في البداية
        "CCCTTTGGG",                             # بدون ATG إطلاقاً
        "ATGGTCCACCTGACTCCTGAGGAGAAGT",          # طول غير مضاعف لـ 3
    ]

    for seq in test_cases:
        result = translate_dna_to_protein(seq)
        print(f"Input: {seq}")
        print(f"Result: {result}\n")