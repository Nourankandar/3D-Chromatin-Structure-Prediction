"""
tests/test_fetcher.py
تيست لـ services/Genome_reference1/fetcher.py

بنعمل mock لـ pyfaidx.Fasta حتى ما نحتاج ملف genome.fa حقيقي عالقرص.

شغّل بـ: pytest tests/test_fetcher.py -v
"""
import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock

from services.Genome_reference1.fetcher import (
    fetch_reference_sequence,
    fetch_reference_sequence_as_fasta_file,
    ReferenceFetchError,
)

CHROM_SEQ = "ACGTACGGTTCAGCTAGCTAGGGCATCGATCGATCGTAGCTAGCATCGATCG" * 5  # 260bp تقريباً


def _fake_fasta(chrom_name="1", seq=CHROM_SEQ):
    class FakeSeqSlice:
        def __init__(self, s):
            self._s = s
        def __str__(self):
            return self._s

    class FakeChromRecord:
        def __len__(self):
            return len(seq)
        def __getitem__(self, sl):
            return FakeSeqSlice(seq[sl])

    fake = MagicMock()
    fake.keys.return_value = [chrom_name]
    fake.__getitem__.side_effect = lambda key: FakeChromRecord()
    fake.close.return_value = None
    return fake


def test_fetch_reference_sequence_exact_match():
    fake = _fake_fasta()
    with patch("services.Genome_reference1.fetcher.settings") as mock_settings, \
         patch("services.Genome_reference1.fetcher.Fasta", return_value=fake), \
         patch("services.Genome_reference1.fetcher.Path.exists", return_value=True):
        mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
        result = fetch_reference_sequence("1", 10, 30)

    assert result == CHROM_SEQ[10:30].upper()
    assert len(result) == 20


def test_fetch_reference_sequence_alt_chromosome_name():
    """لو طلبت 'chr1' وهي مخزنة كـ '1' بالفاستا، لازم يلاقيها تلقائياً."""
    fake = _fake_fasta(chrom_name="1")
    with patch("services.Genome_reference1.fetcher.settings") as mock_settings, \
         patch("services.Genome_reference1.fetcher.Fasta", return_value=fake), \
         patch("services.Genome_reference1.fetcher.Path.exists", return_value=True):
        mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
        result = fetch_reference_sequence("chr1", 0, 10)

    assert result == CHROM_SEQ[0:10].upper()


def test_fetch_reference_sequence_invalid_coords():
    with pytest.raises(ReferenceFetchError, match="Invalid coordinates"):
        fetch_reference_sequence("1", 50, 10)  # end < start


def test_fetch_reference_sequence_chromosome_not_found():
    fake = _fake_fasta(chrom_name="2")  # فقط '2' موجود
    with patch("services.Genome_reference1.fetcher.settings") as mock_settings, \
         patch("services.Genome_reference1.fetcher.Fasta", return_value=fake), \
         patch("services.Genome_reference1.fetcher.Path.exists", return_value=True):
        mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
        with pytest.raises(ReferenceFetchError, match="not found in reference"):
            fetch_reference_sequence("99", 0, 10)


def test_fetch_reference_sequence_end_exceeds_length():
    fake = _fake_fasta()
    with patch("services.Genome_reference1.fetcher.settings") as mock_settings, \
         patch("services.Genome_reference1.fetcher.Fasta", return_value=fake), \
         patch("services.Genome_reference1.fetcher.Path.exists", return_value=True):
        mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
        with pytest.raises(ReferenceFetchError, match="exceeds chromosome length"):
            fetch_reference_sequence("1", 0, len(CHROM_SEQ) + 100)


def test_fetch_reference_sequence_genome_file_missing():
    with patch("services.Genome_reference1.fetcher.settings") as mock_settings, \
         patch("services.Genome_reference1.fetcher.Path.exists", return_value=False):
        mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
        with pytest.raises(ReferenceFetchError, match="not found"):
            fetch_reference_sequence("1", 0, 10)


def test_fetch_reference_sequence_as_fasta_file_writes_correct_content():
    fake = _fake_fasta()
    output_dir = tempfile.mkdtemp()
    try:
        with patch("services.Genome_reference1.fetcher.settings") as mock_settings, \
             patch("services.Genome_reference1.fetcher.Fasta", return_value=fake), \
             patch("services.Genome_reference1.fetcher.Path.exists", return_value=True):
            mock_settings.GENOME_REFERENCE_ROOT = "/fake/genome/root"
            output_path = fetch_reference_sequence_as_fasta_file(
                "1", 5, 25, output_dir, record_id="control_test"
            )

        assert os.path.exists(output_path)
        with open(output_path) as f:
            content = f.read()
        assert content.startswith(">control_test|chr1:5-25")
        written_seq = "".join(
            line.strip() for line in content.splitlines() if not line.startswith(">")
        )
        assert written_seq == CHROM_SEQ[5:25].upper()
    finally:
        shutil.rmtree(output_dir)
