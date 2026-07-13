"""
tests/test_bridge.py
تيست لـ services/llm_service/bridge.py

بنعمل mock لـ generate_clinical_llm_report (استدعاء Gemini API الفعلي) حتى
التيست يشتغل offline بدون API key. الهدف: التأكد إن run_llm_report_bridge
عم يبني missing_proteins وdisrupted_motifs وmatrix_difference_summary من
البيانات الحقيقية (affected_proteins + ملفات coords JSON) مش من نص ثابت.

شغّل بـ: pytest tests/test_bridge.py -v
"""
import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from services.llm_service.bridge import run_llm_report_bridge, _load_coords_json


def _make_output_data_mock(affected_proteins, coords_patient_file=None, coords_control_file=None):
    """يبني mock لـ OutputData instance بأقل قدر ضروري لتشتغل run_llm_report_bridge."""
    output = MagicMock()
    output.affected_proteins = affected_proteins
    output.coords_patient_file = coords_patient_file
    output.coords_control_file = coords_control_file

    output.input_data.cell_type.name = "HepG2"
    output.input_data.chromosome = "21"
    output.input_data.start_pos = 1000
    output.input_data.end_pos = 2000
    output.input_data.patient.name = "Test Patient"
    return output


def test_load_coords_json_returns_none_for_empty_path():
    assert _load_coords_json(None) is None
    assert _load_coords_json("") is None


def test_load_coords_json_returns_none_for_missing_file(tmp_path):
    with patch("services.llm_service.bridge.settings") as mock_settings:
        mock_settings.MEDIA_ROOT = str(tmp_path)
        result = _load_coords_json("genomics/spatial_coordinates/missing.json")
    assert result is None


def test_load_coords_json_reads_valid_file(tmp_path):
    media_root = str(tmp_path)
    rel_path = "genomics/spatial_coordinates/test_coords.json"
    abs_path = os.path.join(media_root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w") as f:
        json.dump({"stress": 0.05, "n_points": 10}, f)

    with patch("services.llm_service.bridge.settings") as mock_settings:
        mock_settings.MEDIA_ROOT = media_root
        result = _load_coords_json(rel_path)

    assert result["stress"] == 0.05


def test_bridge_builds_missing_proteins_from_affected_proteins():
    affected_proteins = {
        "CTCF": {"is_missing": True, "delta_score": None},
        "SP1": {"is_missing": False, "delta_score": 2.5},
        "YY1": {"is_missing": False, "delta_score": None},  # لا missing ولا delta -> ما بينحسب altered
    }
    output = _make_output_data_mock(affected_proteins)

    with patch("services.llm_service.bridge.generate_clinical_llm_report") as mock_generate:
        mock_generate.return_value = "## Report\n..."
        result = run_llm_report_bridge(output)

    assert result == "## Report\n..."
    called_kwargs = mock_generate.call_args.kwargs

    assert called_kwargs["missing_proteins"] == ["CTCF"]
    assert "CTCF" in called_kwargs["alignment_info"]["disrupted_motifs"]
    assert "1 protein(s)" in called_kwargs["alignment_info"]["disrupted_motifs"]
    assert called_kwargs["delta_analysis"]["affected_genes"] == ["SP1"]


def test_bridge_no_missing_proteins_produces_clean_message():
    affected_proteins = {
        "SP1": {"is_missing": False, "delta_score": 1.0},
    }
    output = _make_output_data_mock(affected_proteins)

    with patch("services.llm_service.bridge.generate_clinical_llm_report") as mock_generate:
        mock_generate.return_value = "report"
        run_llm_report_bridge(output)

    called_kwargs = mock_generate.call_args.kwargs
    assert called_kwargs["missing_proteins"] == []
    assert "No protein-binding motifs" in called_kwargs["alignment_info"]["disrupted_motifs"]


def test_bridge_computes_stress_delta_when_both_coords_available(tmp_path):
    media_root = str(tmp_path)

    patient_rel = "genomics/spatial_coordinates/patient.json"
    control_rel = "genomics/spatial_coordinates/control.json"
    os.makedirs(os.path.join(media_root, "genomics/spatial_coordinates"), exist_ok=True)
    with open(os.path.join(media_root, patient_rel), "w") as f:
        json.dump({"stress": 0.08}, f)
    with open(os.path.join(media_root, control_rel), "w") as f:
        json.dump({"stress": 0.05}, f)

    output = _make_output_data_mock({}, coords_patient_file=patient_rel, coords_control_file=control_rel)

    with patch("services.llm_service.bridge.settings") as mock_settings, \
         patch("services.llm_service.bridge.generate_clinical_llm_report") as mock_generate:
        mock_settings.MEDIA_ROOT = media_root
        mock_generate.return_value = "report"
        run_llm_report_bridge(output)

    called_kwargs = mock_generate.call_args.kwargs
    summary = called_kwargs["delta_analysis"]["matrix_difference_summary"]
    assert "patient=0.08" in summary
    assert "control=0.05" in summary
    assert "Δ=0.03" in summary


def test_bridge_handles_missing_coords_gracefully():
    output = _make_output_data_mock({}, coords_patient_file=None, coords_control_file=None)

    with patch("services.llm_service.bridge.generate_clinical_llm_report") as mock_generate:
        mock_generate.return_value = "report"
        run_llm_report_bridge(output)

    called_kwargs = mock_generate.call_args.kwargs
    assert "not available" in called_kwargs["delta_analysis"]["matrix_difference_summary"]


def test_bridge_mutation_details_flags_pending_diff_implementation():
    """
    مهم: mutation_details لازم توضّح إنها لسا مش مبنية على diff حقيقي
    (pending diff_patient_vs_reference) — مش نص مزيّف يوهم إنه فيه تحليل فعلي.
    """
    output = _make_output_data_mock({})
    with patch("services.llm_service.bridge.generate_clinical_llm_report") as mock_generate:
        mock_generate.return_value = "report"
        run_llm_report_bridge(output)

    called_kwargs = mock_generate.call_args.kwargs
    assert "not yet implemented" in called_kwargs["alignment_info"]["mutation_details"]
    assert "diff_patient_vs_reference" in called_kwargs["alignment_info"]["mutation_details"]
