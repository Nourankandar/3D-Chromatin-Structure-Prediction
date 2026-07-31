"""
tests/test_coords_service.py
تيست لـ services/calculating_3d/coords_service.py

هاد أسهل ملف لعمله تيست حقيقي (بدون mock) لأنه المنطق العلمي (hic_to_json)
pure numpy/scipy، ما فيه استدعاء لموديلات AI ثقيلة. فقط الجسر
convert_hic_to_3d_coords محتاج mock لـ settings.MEDIA_ROOT.

شغّل بـ: pytest tests/test_coords_service.py -v
"""
import os
import json
import shutil
import tempfile
import numpy as np
import pytest
from unittest.mock import patch

from backend.services.genomics.calculating_3d.coords_service import (
    hic_to_json,
    convert_hic_to_3d_coords,
    HiCValidationError,
    _validate_matrix,
    _drop_empty_bins,
    _contacts_to_distances,
    _classical_mds,
)


def _make_valid_hic_matrix(n=10, seed=42):
    """يبني مصفوفة تفاعل Hi-C واقعية الشكل: متناظرة، غير سالبة، القطر أعلى قيمة."""
    rng = np.random.default_rng(seed)
    base = rng.random((n, n))
    sym = (base + base.T) / 2.0
    sym = np.abs(sym)
    np.fill_diagonal(sym, sym.max() * 2)  # القطر أعلى قيمة، متل بيانات Hi-C حقيقية
    return sym


def test_validate_matrix_rejects_non_square():
    with pytest.raises(HiCValidationError, match="مربعة"):
        _validate_matrix(np.ones((3, 4)), n_dims=3)


def test_validate_matrix_rejects_negative_values():
    matrix = _make_valid_hic_matrix(6)
    matrix[0, 1] = -5
    matrix[1, 0] = -5
    with pytest.raises(HiCValidationError, match="سالبة"):
        _validate_matrix(matrix, n_dims=3)


def test_validate_matrix_symmetrizes_near_symmetric_input():
    matrix = _make_valid_hic_matrix(6)
    matrix[0, 1] += 0.001  # كسر التناظر بشكل بسيط
    validated = _validate_matrix(matrix, n_dims=3)
    np.testing.assert_array_almost_equal(validated, validated.T)


def test_drop_empty_bins_removes_zero_rows():
    matrix = _make_valid_hic_matrix(6)
    matrix[2, :] = 0
    matrix[:, 2] = 0
    filtered, mask = _drop_empty_bins(matrix)
    assert filtered.shape == (5, 5)
    assert mask[2] == False
    assert mask.sum() == 5


def test_contacts_to_distances_zero_contacts_get_large_distance():
    contacts = np.array([[0, 0, 1], [0, 0, 1], [1, 1, 0]], dtype=float)
    distances = _contacts_to_distances(contacts, alpha=1.0)
    # القطر لازم يبقى صفر
    assert distances[0, 0] == 0.0
    assert distances[1, 1] == 0.0
    # التفاعل الصفري لازم يترجم لمسافة أكبر من التفاعل الموجب
    assert distances[0, 1] > distances[0, 2]


def test_classical_mds_returns_valid_coords_and_stress():
    matrix = _make_valid_hic_matrix(8)
    distances = _contacts_to_distances(matrix, alpha=0.25)
    coords, stress = _classical_mds(distances, n_dims=3)
    assert coords.shape == (8, 3)
    assert stress >= 0.0
    assert not np.isnan(stress)


def test_hic_to_json_end_to_end_structure():
    matrix = _make_valid_hic_matrix(10)
    result = hic_to_json(matrix, alpha=0.25, normalize=True, as_string=False)

    assert result["n_points"] == 10
    assert len(result["coordinates"]) == 10
    assert all(len(point) == 3 for point in result["coordinates"])
    assert "stress" in result
    assert "bounds" in result
    assert "min" in result["bounds"] and "max" in result["bounds"]
    # edges لازم تربط بينات متتالية فقط
    for edge in result["edges"]:
        assert edge[1] == edge[0] + 1


def test_hic_to_json_as_string_returns_valid_json():
    matrix = _make_valid_hic_matrix(6)
    result_str = hic_to_json(matrix, as_string=True)
    parsed = json.loads(result_str)
    assert parsed["n_points"] == 6


def test_hic_to_json_rejects_too_few_bins_after_dropping_empty():
    matrix = _make_valid_hic_matrix(5)
    # نفرّغ 3 من 5 بينات -> يبقى 2 بس، أقل من الحد الأدنى (4)
    matrix[0, :] = 0
    matrix[:, 0] = 0
    matrix[1, :] = 0
    matrix[:, 1] = 0
    matrix[2, :] = 0
    matrix[:, 2] = 0
    with pytest.raises(HiCValidationError, match="عدد كافٍ"):
        hic_to_json(matrix)


def test_convert_hic_to_3d_coords_reads_npz_and_saves_json(tmp_path):
    media_root = str(tmp_path)
    matrix = _make_valid_hic_matrix(10)

    hic_relative_path = "genomics/hic_matrices/input_1_patient_hic.npz"
    hic_absolute_path = os.path.join(media_root, hic_relative_path)
    os.makedirs(os.path.dirname(hic_absolute_path), exist_ok=True)
    np.savez_compressed(hic_absolute_path, hic_matrix=matrix)

    with patch("services.calculating_3d.coords_service.settings") as mock_settings:
        mock_settings.MEDIA_ROOT = media_root
        result_relative_path = convert_hic_to_3d_coords(
            hic_relative_path=hic_relative_path,
            alpha=0.5,
            output_name_hint="input_1_patient",
        )

    assert result_relative_path == os.path.join(
        "genomics/spatial_coordinates/", "input_1_patient_coords.json"
    )
    result_absolute_path = os.path.join(media_root, result_relative_path)
    assert os.path.exists(result_absolute_path)

    with open(result_absolute_path) as f:
        saved = json.load(f)
    assert saved["n_points"] == 10
    assert "stress" in saved


def test_convert_hic_to_3d_coords_missing_npz_raises_filenotfound(tmp_path):
    media_root = str(tmp_path)
    with patch("services.calculating_3d.coords_service.settings") as mock_settings:
        mock_settings.MEDIA_ROOT = media_root
        with pytest.raises(FileNotFoundError):
            convert_hic_to_3d_coords(
                hic_relative_path="genomics/hic_matrices/does_not_exist.npz",
                output_name_hint="ghost",
            )
