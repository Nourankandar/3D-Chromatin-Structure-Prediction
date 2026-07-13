"""
services/HI_C/predictorHIC.py

Real Hi-C matrix generator utilizing the Chromogen Deep Learning Model.
Handles sequence padding for short sequences and window-splitting/merging
for long sequences.

يقبل الآن DNA و DNase كبيانات مباشرة (in-memory) أو كمسارات ملفات —
الأفضل بالـ pipeline الداخلي هو تمريرها كـ arrays مباشرة لتفادي I/O متكرر،
خصوصاً إنه نفس الموديل بينشغل مرتين (مريض + سليم) بكل تشغيلة.
"""

import os
import sys
import logging
from typing import Union

import numpy as np
import torch
from django.conf import settings

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ai_engine.models.hi_c.Get_hic import predict_hic

logger = logging.getLogger(__name__)

MODEL_WINDOW_SIZE = 1280000
MODEL_NUM_BINS = 256
# مُصحَّح: 1,280,000 / 256 = 5000 بالضبط — لازم تطابق دقة الموديل الداخلية
# (كانت 20000 بالغلط، وهاد كان يسبب 75% من الـ bins تضل صفر + ضياع كامل
# للنوافذ اللاحقة بمنطق الدمج merge_hic_matrices)
DEFAULT_RESOLUTION = 5000

# ترتيب الترميز الثابت لقنوات الـ one-hot — لازم يتطابق مع يلي اتدرب عليه الموديل
_BASE_TO_INDEX = {"A": 0, "C": 1, "G": 2, "T": 3}


# ---------------------------------------------------------------------- #
# تحويل DNA من نص إلى one-hot encoding حقيقي (بديل mock_dna)
# ---------------------------------------------------------------------- #

def encode_dna_one_hot(dna_sequence: str, target_len: int) -> np.ndarray:
    """
    يحوّل تسلسل DNA (string A/C/G/T/N) إلى مصفوفة one-hot بشكل (1, 4, target_len)
    متوافقة مع مدخل الموديل. القواعد غير المعروفة (N أو غيرها) بتترمز كأصفار
    بكل القنوات (بدل ما نفتعل قيمة عشوائية).
    """
    sequence = dna_sequence.upper()
    seq_len = len(sequence)

    one_hot = np.zeros((4, target_len), dtype=np.float32)

    usable_len = min(seq_len, target_len)
    for i in range(usable_len):
        base = sequence[i]
        idx = _BASE_TO_INDEX.get(base)
        if idx is not None:
            one_hot[idx, i] = 1.0
        # إذا N أو حرف غير معروف: تبقى كلها أصفار (no-signal)، هيك أدق من عشوائي

    if seq_len < target_len:
        logger.warning(
            "[HiC] DNA sequence shorter than model window (%d < %d) — padded with zeros",
            seq_len, target_len,
        )
    elif seq_len > target_len:
        logger.warning(
            "[HiC] DNA sequence longer than model window (%d > %d) — truncated",
            seq_len, target_len,
        )

    return one_hot[np.newaxis, :, :]  # shape: (1, 4, target_len)


def _resolve_dna_array(dna_input: Union[str, np.ndarray], target_len: int) -> np.ndarray:
    """
    يقبل DNA إما كـ:
      - str: مسار لملف FASTA (بيتقرأ ويترمز)
      - str: تسلسل DNA نفسه مباشرة (لو مش مسار موجود على القرص)
      - np.ndarray: already one-hot encoded array بشكل (1, 4, L) — بترجع كما هي (مع padding/slicing لو لزم)
    """
    if isinstance(dna_input, np.ndarray):
        if dna_input.shape[-1] == target_len:
            return dna_input
        # إعادة تحجيم عبر padding/slicing لو الطول مش مطابق
        fixed = np.zeros((1, 4, target_len), dtype=np.float32)
        usable = min(dna_input.shape[-1], target_len)
        fixed[:, :, :usable] = dna_input[:, :, :usable]
        return fixed

    if isinstance(dna_input, str):
        if os.path.exists(dna_input):
            with open(dna_input, "r") as f:
                lines = f.readlines()
            sequence = "".join(line.strip() for line in lines if not line.startswith(">"))
        else:
            sequence = dna_input  # اعتبرناه تسلسل DNA خام مباشرة
        return encode_dna_one_hot(sequence, target_len)

    raise TypeError(f"Unsupported dna_input type: {type(dna_input)}")


def _resolve_dnase_array(dnase_input: Union[str, np.ndarray]) -> np.ndarray:
    """
    يقبل DNase إما كـ:
      - str: مسار نسبي (relative to MEDIA_ROOT) لملف .npy محفوظ
      - np.ndarray: بيانات DNase جاهزة بالذاكرة
    """
    if isinstance(dnase_input, np.ndarray):
        return dnase_input

    if isinstance(dnase_input, str):
        dnase_absolute_path = os.path.join(settings.MEDIA_ROOT, dnase_input)
        if not os.path.exists(dnase_absolute_path):
            raise FileNotFoundError(f"DNase track not found at: {dnase_absolute_path}")
        raw_signal = np.load(dnase_absolute_path).astype(np.float32)
        return np.nan_to_num(raw_signal, nan=0.0, posinf=0.0, neginf=0.0)

    raise TypeError(f"Unsupported dnase_input type: {type(dnase_input)}")


def _pad_or_slice_signal(signal: np.ndarray, target_len: int) -> np.ndarray:
    if len(signal) < target_len:
        padded = np.zeros(target_len, dtype=np.float32)
        padded[:len(signal)] = signal
        return padded
    return signal[:target_len]


def merge_hic_matrices(matrices_list: list, total_bins: int, window_bins: int = 256, stride_bins: int = 128) -> np.ndarray:
    big_matrix = np.zeros((total_bins, total_bins), dtype=np.float32)
    weights_matrix = np.zeros((total_bins, total_bins), dtype=np.float32)

    for idx, mat in enumerate(matrices_list):
        # الحساب يعتمد على الـ stride_bins الفعلي لتداخل المصفوفات
        start_bin = idx * stride_bins
        end_bin = start_bin + window_bins

        actual_end_i = min(end_bin, total_bins)
        actual_end_j = min(end_bin, total_bins)

        slice_i = actual_end_i - start_bin
        slice_j = actual_end_j - start_bin

        if slice_i <= 0 or slice_j <= 0:
            continue

        big_matrix[start_bin:actual_end_i, start_bin:actual_end_j] += mat[:slice_i, :slice_j]
        weights_matrix[start_bin:actual_end_i, start_bin:actual_end_j] += 1.0

    # حساب المتوسط بدقة في مناطق التداخل
    np.divide(big_matrix, weights_matrix, out=big_matrix, where=weights_matrix > 0)
    return big_matrix


# ---------------------------------------------------------------------- #
# الدالة الرئيسية — الآن تقبل dna_input بدل ما تفتعله عشوائياً
# ---------------------------------------------------------------------- #

def generate_hic_matrices(
    dna_input: Union[str, np.ndarray],
    dnase_input: Union[str, np.ndarray],
    output_name_hint: str = "sample",
) -> str:
    """
    الجسر الفعلي المستدعى بواسطة GenomicPipelineManager._step_hic().

    Parameters
    ----------
    dna_input : إما مسار FASTA، أو تسلسل DNA كنص خام، أو مصفوفة one-hot جاهزة (1,4,L)
                *يفضّل تمرير المصفوفة one-hot مباشرة لو متوفرة أصلاً من خطوة سابقة
                لتفادي إعادة الترميز مرتين (مريض/سليم لكل واحد مرة)*
    dnase_input : إما مسار نسبي لملف .npy، أو مصفوفة DNase جاهزة بالذاكرة
    output_name_hint : اسم مميز يُستخدم لبناء اسم ملف الإخراج (مثلاً "patient_123" أو "control_123")
                        بما إنه ما عاد عندنا اسم ملف DNase مضمون الوجود دايماً
    """
    raw_signal = _resolve_dnase_array(dnase_input)
    total_length = len(raw_signal)

    total_bins = int(np.ceil(total_length / DEFAULT_RESOLUTION))
    if total_bins < 10:
        total_bins = 10

    predicted_sub_matrices = []
    stride = MODEL_WINDOW_SIZE

    if total_length <= MODEL_WINDOW_SIZE:
        # ─── الحالة الأولى: قصيرة أو تساوي نافذة الموديل ───
        dna_array = _resolve_dna_array(dna_input, MODEL_WINDOW_SIZE)

        binned_dnase = np.zeros((1, MODEL_NUM_BINS), dtype=np.float32)
        actual_bins_count = max(2, int(np.ceil(total_length / DEFAULT_RESOLUTION)))

        for i in range(min(actual_bins_count, MODEL_NUM_BINS)):
            start_idx = i * DEFAULT_RESOLUTION
            end_idx = min((i + 1) * DEFAULT_RESOLUTION, total_length)
            if end_idx > start_idx:
                binned_dnase[0, i] = raw_signal[start_idx:end_idx].mean()

        full_pred = predict_hic(dna_array, binned_dnase)

        final_bins = min(total_bins, MODEL_NUM_BINS)
        hic_matrix = full_pred[:final_bins, :final_bins]
        total_bins = final_bins

    else:
        # ─── الحالة الثانية: أطول من نافذة الموديل — تقطيع مع تداخل 50% ودمج ───
        full_dna_array = _resolve_dna_array(dna_input, total_length) if not isinstance(dna_input, np.ndarray) else dna_input

        # جعل القفزة نصف حجم النافذة للتداخل
        stride = MODEL_WINDOW_SIZE // 2 
        start_idx = 0
        
        while start_idx < total_length:
            end_idx = start_idx + MODEL_WINDOW_SIZE

            # لتجنب البادينغ الزائد في آخر نافذة، نثبت النهاية ونرجع بالبداية للخلف
            if end_idx > total_length:
                end_idx = total_length
                start_idx = max(0, end_idx - MODEL_WINDOW_SIZE)

            chunk_dnase = raw_signal[start_idx:end_idx]
            if len(chunk_dnase) < MODEL_WINDOW_SIZE:
                chunk_dnase = _pad_or_slice_signal(chunk_dnase, MODEL_WINDOW_SIZE)

            dna_chunk = full_dna_array[:, :, start_idx:end_idx]
            if dna_chunk.shape[-1] < MODEL_WINDOW_SIZE:
                fixed_chunk = np.zeros((1, 4, MODEL_WINDOW_SIZE), dtype=np.float32)
                fixed_chunk[:, :, :dna_chunk.shape[-1]] = dna_chunk
                dna_chunk = fixed_chunk

            binned_dnase_chunk = np.zeros((1, MODEL_NUM_BINS), dtype=np.float32)
            for i in range(MODEL_NUM_BINS):
                b_start = i * DEFAULT_RESOLUTION
                b_end = (i + 1) * DEFAULT_RESOLUTION
                if b_start < len(chunk_dnase):
                    binned_dnase_chunk[0, i] = chunk_dnase[b_start:b_end].mean()

            sub_matrix = predict_hic(dna_chunk, binned_dnase_chunk)
            predicted_sub_matrices.append(sub_matrix)

            if end_idx == total_length:
                break

            start_idx += stride

        # stride_bins يعادل نصف عدد البينات للنافذة (128) ليوافق تداخل الـ 50%
        stride_bins = MODEL_NUM_BINS // 2
        hic_matrix = merge_hic_matrices(predicted_sub_matrices, total_bins, MODEL_NUM_BINS, stride_bins)
    hic_matrix = (hic_matrix + hic_matrix.T) * 0.5
    np.fill_diagonal(hic_matrix, hic_matrix.max() if hic_matrix.max() > 0 else 1.0)

    relative_folder = 'genomics/hic_matrices/npz/'
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)

    output_filename = f"{output_name_hint}_hic.npz"
    absolute_output_path = os.path.join(absolute_folder, output_filename)

    np.savez_compressed(
        absolute_output_path,
        hic_matrix=hic_matrix,
        chrom='unknown',
        start=0,
        end=total_bins * DEFAULT_RESOLUTION,
        resolution=DEFAULT_RESOLUTION,
    )

    return os.path.join(relative_folder, output_filename)