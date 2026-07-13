#!/usr/bin/env python3
"""
hic_to_json.py
====================================================================
يحوّل مصفوفة Hi-C إلى JSON يحتوي فقط على الإحداثيات (x, y, z) جاهزة
للرسم/الاستخدام مباشرة في أي مشروع (frontend / Three.js / matplotlib...).

طريقتين للاستخدام:

1) كمكتبة (import) داخل مشروعك:
    from hic_to_json import hic_to_json
    result_json_string = hic_to_json(matrix)          # str
    result_dict = hic_to_json(matrix, as_string=False)  # dict

2) من سطر الأوامر (CLI) — يطبع JSON خام على stdout فقط،
   بحيث تقدر تستدعيه كعملية فرعية (subprocess) من أي لغة:
    python3 hic_to_json.py hic_matrix.tsv > coords.json
    python3 hic_to_json.py hic_matrix.tsv --scale 100   # تحجيم للرسم

شكل الإخراج:
{
  "n_points": 14,
  "coordinates": [[x, y, z], [x, y, z], ...],
  "valid_bin_ids": [0, 1, 2, 4, 5, ...],   // معرّفات البينات الأصلية (بعض البينات قد تُستبعد لو فارغة)
  "edges": [[0, 1], [1, 2], ...],          // خط السلسلة الجينومية (لرسم خط متصل بين البينات المتتالية)
  "bounds": {"min": [x,y,z], "max": [x,y,z]},
  "stress": 0.0621                          // مقياس جودة الإسقاط (كل ما قلّ كان أدق)
}
====================================================================
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Union

import numpy as np
from scipy.linalg import eigh

# الـ logging يروح لـ stderr حصرًا حتى ما يلوّث stdout (اللي لازم يبقى JSON نقي)
logger = logging.getLogger("hic_to_json")
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.WARNING)


class HiCValidationError(ValueError):
    """يُرفع عند وجود مشكلة في بيانات مصفوفة Hi-C المدخلة."""


# ---------------------------------------------------------------------- #
# النواة العلمية (نفس منطق contact -> distance -> MDS)
# ---------------------------------------------------------------------- #

def _validate_matrix(matrix: np.ndarray, n_dims: int) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=float)

    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise HiCValidationError(f"المصفوفة يجب أن تكون مربعة (n x n)، الشكل: {matrix.shape}")
    if matrix.shape[0] < n_dims + 1:
        raise HiCValidationError(f"عدد البينات ({matrix.shape[0]}) صغير جدًا")
    if np.any(matrix < 0):
        raise HiCValidationError("لا يجوز وجود قيم سالبة في مصفوفة Hi-C")

    if not np.allclose(matrix, matrix.T, equal_nan=True):
        matrix = (matrix + matrix.T) / 2.0

    return matrix


def _drop_empty_bins(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    row_sums = np.nansum(matrix, axis=1)
    valid_mask = row_sums > 0
    return matrix[np.ix_(valid_mask, valid_mask)], valid_mask


def _balance_matrix(matrix: np.ndarray, max_iter: int = 50, tol: float = 1e-5) -> np.ndarray:
    """موازنة تكرارية (Sinkhorn-Knopp) تشبه خوارزمية ICE."""
    m = matrix.copy()
    bias = np.ones(m.shape[0])
    for _ in range(max_iter):
        row_sums = m.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        factor = row_sums / row_sums.mean()
        factor[factor == 0] = 1.0
        m = m / factor[:, None] / factor[None, :]
        bias *= factor
        if np.max(np.abs(factor - 1.0)) < tol:
            break
    return m


def _contacts_to_distances(contacts: np.ndarray, alpha: float) -> np.ndarray:
    contacts = contacts.copy()
    contacts[np.isnan(contacts)] = 0
    positive = contacts[contacts > 0]
    min_nonzero = positive.min() if positive.size else 1e-6
    contacts[contacts == 0] = min_nonzero * 0.01
    distances = np.power(contacts, -alpha)
    np.fill_diagonal(distances, 0.0)
    return distances


def _classical_mds(distance_matrix: np.ndarray, n_dims: int) -> tuple[np.ndarray, float]:
    n = distance_matrix.shape[0]
    d2 = distance_matrix ** 2
    j = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * j @ d2 @ j

    eigvals, eigvecs = eigh(b)
    idx = np.argsort(eigvals)[::-1]
    eigvals, eigvecs = eigvals[idx], eigvecs[:, idx]

    top_vals = np.clip(eigvals[:n_dims], a_min=0, a_max=None)
    coords = eigvecs[:, :n_dims] * np.sqrt(top_vals)

    diff = coords[:, None, :] - coords[None, :, :]
    projected = np.sqrt(np.sum(diff ** 2, axis=-1))
    num = np.sum((distance_matrix - projected) ** 2)
    den = np.sum(distance_matrix ** 2)
    stress = float(np.sqrt(num / den)) if den > 0 else 0.0

    return coords, stress


def _prepare_for_rendering(coords: np.ndarray, scale: float | None) -> np.ndarray:
    """يوسّط الإحداثيات حول الأصل (0,0,0)، ويحجّمها اختياريًا — مفيد مباشرة للرسم."""
    coords = coords - coords.mean(axis=0)  # توسيط مركز الكتلة عند الأصل

    if scale is not None:
        max_extent = np.abs(coords).max()
        if max_extent > 0:
            coords = coords * (scale / max_extent)

    return coords


# ---------------------------------------------------------------------- #
# الواجهة الرئيسية (هاي اللي بتستدعيها من مشروعك)
# ---------------------------------------------------------------------- #

def hic_to_json(
    hic_matrix: Union[np.ndarray, list],
    alpha: float = 0.25,
    normalize: bool = True,
    scale: float | None = None,
    as_string: bool = True,
    indent: int | None = None,
) -> Union[str, dict]:
    """
    يحوّل مصفوفة Hi-C إلى إحداثيات 3D ويرجعها بصيغة JSON.

    Parameters
    ----------
    hic_matrix : np.ndarray | list
        مصفوفة تفاعلات Hi-C (n x n).
    alpha : float
        أس تحويل التفاعل إلى مسافة (افتراضي 0.25).
    normalize : bool
        تطبيع المصفوفة (يشبه ICE) قبل الحساب.
    scale : float | None
        لو محدد (مثلًا 100)، بيتم تحجيم الإحداثيات بحيث أكبر قيمة مطلقة = scale.
        مفيد جدًا للرسم مباشرة (WebGL/Three.js) بدون ما تحتاج تطبيع بالـ frontend.
    as_string : bool
        True -> يرجع str جاهز للطباعة/الإرسال. False -> يرجع dict مباشرة.
    indent : int | None
        عدد المسافات لتنسيق JSON (None = سطر واحد مضغوط، أفضل للـ API/الشبكة).

    Returns
    -------
    str | dict
        JSON فيه: n_points, coordinates, valid_bin_ids, edges, bounds, stress.
    """
    matrix = _validate_matrix(np.array(hic_matrix), n_dims=3)
    matrix, valid_mask = _drop_empty_bins(matrix)
    valid_bin_ids = np.where(valid_mask)[0].tolist()

    if matrix.shape[0] < 4:
        raise HiCValidationError("بعد استبعاد البينات الفارغة، لم يعد هناك عدد كافٍ من البينات")

    if normalize:
        matrix = _balance_matrix(matrix)

    distances = _contacts_to_distances(matrix, alpha=alpha)
    coords, stress = _classical_mds(distances, n_dims=3)
    coords = _prepare_for_rendering(coords, scale=scale)

    # edges: خط السلسلة الجينومية بين البينات المتتالية (لرسم خط متصل عبر البنية)
    # نربط فقط البينات المتتالية أصلًا (valid_bin_ids متتالية بالترقيم الأصلي)
    edges = [
        [i, i + 1]
        for i in range(len(valid_bin_ids) - 1)
        if valid_bin_ids[i + 1] == valid_bin_ids[i] + 1
    ]

    result = {
        "n_points": int(coords.shape[0]),
        "coordinates": np.round(coords, 4).tolist(),
        "valid_bin_ids": valid_bin_ids,
        "edges": edges,
        "bounds": {
            "min": np.round(coords.min(axis=0), 4).tolist(),
            "max": np.round(coords.max(axis=0), 4).tolist(),
        },
        "stress": round(stress, 4),
    }

    return json.dumps(result, ensure_ascii=False, indent=indent) if as_string else result


# ---------------------------------------------------------------------- #
# CLI: يطبع JSON خام فقط على stdout
# ---------------------------------------------------------------------- #

def _load_matrix_file(path: str) -> np.ndarray:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"الملف غير موجود: {path}")
    if p.suffix == ".npy":
        return np.load(p)
    sep = "," if p.suffix.lower() == ".csv" else "\t"
    return np.loadtxt(p, delimiter=sep)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Hi-C matrix -> 3D coordinates JSON")
    parser.add_argument("hic_path", help="مسار ملف مصفوفة Hi-C (.tsv/.csv/.npy)")
    parser.add_argument("--alpha", type=float, default=0.25)
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--scale", type=float, default=None, help="تحجيم الإحداثيات للرسم (مثلًا 100)")
    parser.add_argument("--pretty", action="store_true", help="تنسيق JSON بشكل مقروء")
    args = parser.parse_args()

    matrix = _load_matrix_file(args.hic_path)
    output = hic_to_json(
        matrix,
        alpha=args.alpha,
        normalize=not args.no_normalize,
        scale=args.scale,
        as_string=True,
        indent=2 if args.pretty else None,
    )
    print(output)  # stdout = JSON فقط، بدون أي شيء إضافي


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------- #
# الجسر مع الـ pipeline (Django) — هاي اللي بينادي عليها pipeline_manager
# ---------------------------------------------------------------------- #

def convert_hic_to_3d_coords(
    hic_relative_path: str,
    alpha: float = 0.5,
    output_name_hint: str = "sample",
) -> str:
    """
    بتفتح ملف Hi-C المحفوظ (.npz، طالع من HI_C/predictor.py)، بتستخرج منه
    hic_matrix، بتنادي hic_to_json() الموجودة فوق (نفس المنطق العلمي)،
    وبتحفظ الناتج كملف .json تحت MEDIA_ROOT/genomics/spatial_coordinates/.

    Parameters
    ----------
    hic_relative_path : المسار النسبي لملف .npz (نسبة لـ MEDIA_ROOT) —
                         هو نفس القيمة اللي بترجعها generate_hic_matrices()
    alpha : أس تحويل التفاعل إلى مسافة (بينمرر مباشرة لـ hic_to_json)
    output_name_hint : اسم مميز لملف الإخراج (مثلاً "input_5_patient")
                        لتفادي تصادم الأسماء بين مريض/سليم/سجلات مختلفة

    Returns
    -------
    str: المسار النسبي (relative to MEDIA_ROOT) لملف الإحداثيات JSON
         الجاهز للحفظ في OutputData.coords_patient_file / coords_control_file

    Raises
    ------
    HiCValidationError لو المصفوفة غير صالحة
    FileNotFoundError لو ملف .npz مش موجود
    """
    import os
    from django.conf import settings

    absolute_hic_path = os.path.join(settings.MEDIA_ROOT, hic_relative_path)
    if not os.path.exists(absolute_hic_path):
        raise FileNotFoundError(f"Hi-C matrix file not found at: {absolute_hic_path}")

    with np.load(absolute_hic_path) as npz_data:
        hic_matrix = npz_data["hic_matrix"]

    result_dict = hic_to_json(
        hic_matrix,
        alpha=alpha,
        normalize=True,
        scale=None,
        as_string=False,
    )

    relative_folder = "genomics/coordinates_3d/json/"
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)

    output_filename = f"{output_name_hint}_coords.json"
    absolute_output_path = os.path.join(absolute_folder, output_filename)

    with open(absolute_output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False)

    logger.info(
        "[Coords] 3D coordinates saved: %s (n_points=%d, stress=%.4f)",
        absolute_output_path, result_dict["n_points"], result_dict["stress"],
    )

    return os.path.join(relative_folder, output_filename)
