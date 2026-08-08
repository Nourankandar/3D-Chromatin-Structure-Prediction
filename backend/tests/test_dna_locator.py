"""
tests/test_dna_locator.py
تيست لـ services/Genome_reference1/DNA_locator.py

بيعتمد على mock لـ pyfaidx.Fasta و settings.GENOME_REFERENCE_ROOT حتى ما نحتاج
جينوم حقيقي عالقرص. بنبني كروموسوم وهمي قصير (500bp) ونحط فيه تسلسل معروف
مكانه مسبقاً، وبعدين نتأكد إن الخوارزمية بترجع نفس الموقع بالضبط.

شغّل بـ: pytest tests/test_dna_locator.py -v
"""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from backend.services.genomics.referenceGenome.DNA_locator import (
    locate_patient_sequence,
    SequenceLocationError,
    SequenceAmbiguityError,
    _reverse_complement,
)

# كروموسوم وهمي: 500bp غير متكرر (شبه عشوائي بس ثابت) حتى seeds تكون فريدة
CHROM_SEQ = (
    "ACGTACGGTTCAGCTAGCTAGGGCATCGATCGATCGTAGCTAGCATCGATCGTAGCATCG"
    "TTAGCTAGCTAGCATCGATCGTAGCTAGCTGACTGATCGTAGCTAGCATCGTAGCTAGCT"
    "AGCTAGCATCGATCGATCGTAGCATCGATCGATCGTAGCTAGCATCGATCGTAGCTAGCT"
    "GGGCCATATATCGATCGGGATCGTATCGATCGTAGCTAGCATGCATGCATCGATCGTAGC"
    "TAGCATCGATCGTAGCATGCATGCATGCATCGATCGTAGCATGCATGCATCGATCGTAGC"
    "ATGCATGCATCGATCGTAGCATGCATCGATCGTAGCATGCATCGATCGTAGCATGCATCG"
    "ATCGTAGCATGCATCGATCGTAGCATGCATCGATCGTAGCATGCATCGATCGTAGCATGC"
    "ATCGATCGTAGCATGCATCGATCGTAGCATGCATCGATCGTAGCATGCATCGATCGTAGC"
)[:500]


def _make_fake_fasta(chrom_seq: str, chrom_name: str = "1"):
    """يبني mock object يقلّد واجهة pyfaidx.Fasta بأقل قدر ممكن."""
    fake_record = MagicMock()
    fake_record.__getitem__.side_effect = lambda sl: MagicMock(
        __str__=lambda self, s=chrom_seq, sl=sl: s[sl] if isinstance(sl, slice) else s
    )
    # أبسط: نخليها ترجع string مباشرة عبر __str__ على كامل التسلسل أو سلايس منه
    class FakeSeqSlice:
        def __init__(self, s):
            self._s = s
        def __str__(self):
            return self._s

    class FakeChromRecord:
        def __getitem__(self, sl):
            return FakeSeqSlice(chrom_seq[sl])
        def __len__(self):
            return len(chrom_seq)

    fake_fasta = MagicMock()
    fake_fasta.keys.return_value = [chrom_name]
    fake_fasta.__getitem__.side_effect = lambda key: FakeChromRecord()
    fake_fasta.close.return_value = None
    return fake_fasta


@pytest.fixture
def patient_fasta_file():
    """تسلسل مريض = مقطع 120bp مأخوذ حرفياً من CHROM_SEQ بدءاً من الموقع 150."""
    true_start = 150
    true_end = true_start + 120
    patient_seq = CHROM_SEQ[true_start:true_end]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as f:
        f.write(">patient_test\n")
        f.write(patient_seq + "\n")
        path = f.name

    yield path, true_start, true_end
    os.unlink(path)


def test_locate_exact_match_forward_strand(patient_fasta_file):
    """التسلسل موجود حرفياً بالكروموسوم -> لازم يلاقي نفس start/end بـ identity=1.0"""
    fasta_path, expected_start, expected_end = patient_fasta_file
    fake_fasta = _make_fake_fasta(CHROM_SEQ)

    with patch("services.Genome_reference1.DNA_locator.settings") as mock_settings, \
         patch("services.Genome_reference1.DNA_locator.Fasta", return_value=fake_fasta):
        mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
        with patch("services.Genome_reference1.DNA_locator.Path.exists", return_value=True):
            result = locate_patient_sequence(fasta_path, chromosome_hint="1")

    assert result["start"] == expected_start
    assert result["end"] == expected_end
    assert result["strand"] == "+"
    assert result["identity"] == 1.0
    assert result["chromosome"] == "1"


def test_locate_reverse_complement_strand(patient_fasta_file):
    """لو التسلسل معطى كـ reverse complement، لازم يكتشف strand='-' ونفس الموقع."""
    fasta_path, expected_start, expected_end = patient_fasta_file
    with open(fasta_path) as f:
        lines = f.readlines()
    original_seq = "".join(l.strip() for l in lines if not l.startswith(">"))
    rc_seq = _reverse_complement(original_seq)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as f:
        f.write(">patient_rc\n" + rc_seq + "\n")
        rc_path = f.name

    fake_fasta = _make_fake_fasta(CHROM_SEQ)
    try:
        with patch("services.Genome_reference1.DNA_locator.settings") as mock_settings, \
             patch("services.Genome_reference1.DNA_locator.Fasta", return_value=fake_fasta):
            mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
            with patch("services.Genome_reference1.DNA_locator.Path.exists", return_value=True):
                result = locate_patient_sequence(rc_path, chromosome_hint="1")
    finally:
        os.unlink(rc_path)

    assert result["strand"] == "-"
    assert result["start"] == expected_start
    assert result["identity"] == 1.0


def test_locate_raises_on_missing_chromosome_hint(patient_fasta_file):
    fasta_path, _, _ = patient_fasta_file
    with pytest.raises(SequenceLocationError, match="chromosome_hint is required"):
        locate_patient_sequence(fasta_path, chromosome_hint=None)


def test_locate_raises_on_no_match():
    """تسلسل غريب كلياً (مش موجود بالكروموسوم) لازم يفشل بـ SequenceLocationError."""
    random_seq = "GGGGGGGGGGCCCCCCCCCCTTTTTTTTTTAAAAAAAAAA" * 3  # لا يتطابق مع CHROM_SEQ
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as f:
        f.write(">no_match\n" + random_seq + "\n")
        path = f.name

    fake_fasta = _make_fake_fasta(CHROM_SEQ)
    try:
        with patch("services.Genome_reference1.DNA_locator.settings") as mock_settings, \
             patch("services.Genome_reference1.DNA_locator.Fasta", return_value=fake_fasta):
            mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
            with patch("services.Genome_reference1.DNA_locator.Path.exists", return_value=True):
                with pytest.raises(SequenceLocationError):
                    locate_patient_sequence(path, chromosome_hint="1")
    finally:
        os.unlink(path)


def test_locate_raises_on_ambiguous_repetitive_region():
    """
    تسلسل قصير جداً (اقل من SEED_LENGTH) وموجود بمكانين بنفس الكروموسوم
    -> لازم يرفع SequenceAmbiguityError (مش يرجع نتيجة واحدة بثقة كاذبة).
    """
    repetitive_chrom = "AAACCCTTT" * 40  # فيه تكرار كثير لأي مقطع قصير منه
    short_patient_seq = "AAACCCTTT"  # أقصر من SEED_LENGTH=25 -> بيدخل مسار "مطابقة مباشرة"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as f:
        f.write(">short_repetitive\n" + short_patient_seq + "\n")
        path = f.name

    fake_fasta = _make_fake_fasta(repetitive_chrom)
    try:
        with patch("services.Genome_reference1.DNA_locator.settings") as mock_settings, \
             patch("services.Genome_reference1.DNA_locator.Fasta", return_value=fake_fasta):
            mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
            with patch("services.Genome_reference1.DNA_locator.Path.exists", return_value=True):
                with pytest.raises(SequenceAmbiguityError):
                    locate_patient_sequence(path, chromosome_hint="1")
    finally:
        os.unlink(path)


def test_locate_raises_on_empty_fasta():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as f:
        f.write(">empty\n")
        path = f.name
    try:
        with pytest.raises(SequenceLocationError, match="empty or unreadable"):
            locate_patient_sequence(path, chromosome_hint="1")
    finally:
        os.unlink(path)
