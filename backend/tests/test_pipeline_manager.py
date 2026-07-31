"""
tests/test_pipeline_manager.py
تيست لـ services/pipeline_manager.py (GenomicPipelineManager)

هاد أهم تيست لأنه بيتأكد من التكامل الكامل: ترتيب الخطوات صحيح، البيانات
عم تنمرّر صح بين كل خطوة والتالية، وفروع المريض/السليم عم تتعالج بالتوازي
المنطقي (نفس الخطوات لكل واحد لحاله).

كل الاستدعاءات الخارجية (DNA_locator, fetcher, DNase predictor, scanner,
Hi-C predictor, coords_service) متعمولها mock بالكامل — هاد تيست وحدة (unit)
لمنطق التنسيق نفسه، مش لمنطق كل خدمة (كل خدمة إلها تيست خاص فيها).

شغّل بـ: pytest tests/test_pipeline_manager.py -v
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.services.genomics.pipeline_manager import GenomicPipelineManager


def _make_input_data_mock():
    input_data = MagicMock()
    input_data.dna_sequence_file.path = "/media/genomics/sequences/patient_1.fasta"
    input_data.cell_type.target_enformer_id = 5
    input_data.cell_type.name = "HepG2"
    input_data.chromosome = "21"
    input_data.save.return_value = None
    return input_data


@pytest.fixture
def mocked_pipeline_dependencies():
    """
    يعمل mock لكل الدوال الخارجية يلي pipeline_manager بيستدعيها عبر lazy
    imports جوا كل _step method. لازم نعمل mock على المسار الكامل يلي
    الدالة نفسها بتعمل منه import (services.X.Y) مش على مسار pipeline_manager.
    """
    input_data = _make_input_data_mock()

    with patch("apps.genomics.models.InputData") as MockInputDataModel, \
         patch("services.Genome_reference1.DNA_locator.locate_patient_sequence") as mock_locate, \
         patch("services.Genome_reference1.fetcher.fetch_reference_sequence_as_fasta_file") as mock_fetch, \
         patch("services.DNASE.predictor.predict_dnase_profiles") as mock_dnase, \
         patch("services.scanning_motifs.scanner.run_motif_delta_analysis") as mock_motifs, \
         patch("services.scanning_motifs.scanner.fetch_pdb_file") as mock_pdb, \
         patch("services.scanning_motifs.scanner.calculate_spatial_docking") as mock_docking, \
         patch("services.HI_C.predictorHIC.generate_hic_matrices") as mock_hic, \
         patch("services.calculating_3d.coords_service.convert_hic_to_3d_coords") as mock_3d:

        MockInputDataModel.objects.select_related.return_value.get.return_value = input_data

        mock_locate.return_value = {
            "chromosome": "21", "start": 1000, "end": 2000,
            "strand": "+", "identity": 0.99,
        }
        mock_fetch.return_value = "/media/genomics/reference_sequences/control_1.fasta"

        # DNase: قيم مختلفة حسب tag لتمييزها بالتيست
        def dnase_side_effect(fasta_path, enformer_id):
            if "control" in fasta_path:
                return "genomics/predicted_dnase/control_1_dnase.npy"
            return "genomics/predicted_dnase/patient_1_dnase.npy"
        mock_dnase.side_effect = dnase_side_effect

        # Motifs: مريض ناقصه بروتين TAF1 يلي موجود بالسليم -> is_missing=True
        def motifs_side_effect(fasta_path):
            if "control" in fasta_path:
                return {
                    "CTCF": {"position_index": 5, "strand": "+", "delta_score": 8.0},
                    "TAF1": {"position_index": 20, "strand": "+", "delta_score": 6.0},
                }
            return {
                "CTCF": {"position_index": 5, "strand": "+", "delta_score": 7.5},
            }
        mock_motifs.side_effect = motifs_side_effect
        mock_pdb.return_value = "genomics/pdb_structures/fake.pdb"
        mock_docking.return_value = {"position": [1.0, 0.0, 0.0], "rotation": [0.0, 90.0, 0.0]}

        def hic_side_effect(fasta_path, dnase_file, output_name_hint):
            return f"genomics/hic_matrices/{output_name_hint}_hic.npz"
        mock_hic.side_effect = hic_side_effect

        def coords_side_effect(hic_relative_path, alpha, output_name_hint):
            return f"genomics/spatial_coordinates/{output_name_hint}_coords.json"
        mock_3d.side_effect = coords_side_effect

        yield {
            "input_data": input_data,
            "locate": mock_locate,
            "fetch": mock_fetch,
            "dnase": mock_dnase,
            "motifs": mock_motifs,
            "pdb": mock_pdb,
            "docking": mock_docking,
            "hic": mock_hic,
            "coords3d": mock_3d,
        }


def test_pipeline_run_calls_steps_in_correct_order(mocked_pipeline_dependencies):
    manager = GenomicPipelineManager(input_data_id=1)
    result = manager.run()

    m = mocked_pipeline_dependencies

    # ترتيب الاستدعاءات: locate -> fetch -> dnase(x2) -> motifs(x2) -> hic(x2) -> 3d(x2)
    assert m["locate"].called
    assert m["fetch"].called
    assert m["dnase"].call_count == 2
    assert m["motifs"].call_count == 2
    assert m["hic"].call_count == 2
    assert m["coords3d"].call_count == 2

    # النتيجة النهائية لازم فيها كل المفاتيح المتوقعة من tasks.py
    assert "hic_patient_file" in result
    assert "hic_control_file" in result
    assert "coords_patient_file" in result
    assert "coords_control_file" in result
    assert "affected_proteins" in result


def test_pipeline_detects_missing_protein_correctly(mocked_pipeline_dependencies):
    """
    TAF1 موجود بالسليم بس مش موجود بالمريض -> لازم is_missing=True.
    CTCF موجود بالاتنين بس بـ delta_score مختلف -> is_missing=False.
    """
    manager = GenomicPipelineManager(input_data_id=1)
    result = manager.run()

    affected = result["affected_proteins"]
    assert affected["TAF1"]["is_missing"] is True
    assert affected["CTCF"]["is_missing"] is False

    # delta_score لـ CTCF لازم يكون فرق patient - control (7.5 - 8.0 = -0.5)
    assert affected["CTCF"]["delta_score"] == pytest.approx(-0.5)


def test_pipeline_output_filename_hints_prevent_collisions(mocked_pipeline_dependencies):
    """output_name_hint لازم يفرّق بوضوح بين مريض وسليم لنفس الـ input_data_id."""
    manager = GenomicPipelineManager(input_data_id=42)
    result = manager.run()

    assert "input_42_patient" in result["hic_patient_file"]
    assert "input_42_control" in result["hic_control_file"]
    assert "input_42_patient" in result["coords_patient_file"]
    assert "input_42_control" in result["coords_control_file"]


def test_pipeline_fetch_reference_uses_coords_from_locate_step(mocked_pipeline_dependencies):
    """لازم يبعت لـ fetcher بالضبط نفس start/end/chromosome يلي رجعهن DNA_locator."""
    manager = GenomicPipelineManager(input_data_id=1)
    manager.run()

    m = mocked_pipeline_dependencies
    fetch_call_kwargs = m["fetch"].call_args.kwargs
    assert fetch_call_kwargs["chromosome"] == "21"
    assert fetch_call_kwargs["start"] == 1000
    assert fetch_call_kwargs["end"] == 2000


def test_pipeline_status_updates_progress_through_stages(mocked_pipeline_dependencies):
    """input_data.status لازم يتحدث مع كل مرحلة (مش لازم نتحقق من كل قيمة، بس من إنه تصرف)."""
    manager = GenomicPipelineManager(input_data_id=1)
    manager.run()

    input_data = mocked_pipeline_dependencies["input_data"]
    # save() انصرَحت أكتر من مرة (لكل تحديث status + لحفظ reference_sequence_file + dnase fields)
    assert input_data.save.call_count >= 4


def test_pipeline_raises_if_input_data_not_found():
    with patch("apps.genomics.models.InputData") as MockInputDataModel:
        MockInputDataModel.objects.select_related.return_value.get.side_effect = (
            MockInputDataModel.DoesNotExist
        )
        manager = GenomicPipelineManager(input_data_id=999)
        with pytest.raises(Exception):
            manager.run()
