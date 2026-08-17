"""
services/genome_reference/kmer_index.py
====================================================================
فهرس K-mer للكروموسوم — نسخة numpy-based (بدون dict نصي) لتوفير
الذاكرة بشكل جذري.

ليش النسخة القديمة كانت تنفجر بالذاكرة؟
-----------------------------------------
النسخة القديمة كانت تبني dict[str, array] — يعني مفتاح الفهرس عبارة
عن string بايثون بطول 25 حرف لكل k-mer فريد. لكروموسوم بشري متوسط
(عشرات/مئات ملايين k-mer فريد)، كل string بايثون بياخد ~50-80 byte
overhead فوق الأحرف نفسها (object header + hash cache...)، فوق overhead
الـ dict نفسه (~50-100 byte لكل entry). النتيجة: عشرات الـ GB ذاكرة
لكروموسوم واحد بس.

الحل هون
--------
- كل k-mer (25 حرف ACGT) بيترمّز كرقم uint64 واحد (2-bit لكل قاعدة:
  A=0, C=1, G=2, T=3 → 25*2 = 50 bit، بيلاقي بـ uint64 بريحة).
- الفهرس كامل بيتخزن بـ 3 مصفوفات numpy بس:
    * unique_kmers  (uint64): كل القيم الفريدة، مرتبة تصاعدياً
    * offsets       (int64) : حدود مجموعة المواقع لكل k-mer فريد
    * positions     (uint32): كل المواقع، مجمّعة حسب k-mer
- البحث عن seed معيّن: نرمّزه لنفس القيمة uint64 ونعمل عليه
  np.searchsorted بدل dict lookup — أبطأ شوي نظرياً (O(log n) بدل
  O(1))، بس الفرق العملي غير محسوس (log2 لـ 200 مليون ≈ 28 مقارنة)،
  مقابل توفير ذاكرة يوصل لعشرات الأضعاف.
- الفهرس يُخزَّن على القرص كـ .npz (numpy compressed) بدل pickle —
  أسرع تحميل وأصغر حجم بكثير من pickle لـ dict نصي.

التوافق مع DNA_locator.py
--------------------------
DNA_locator.py بيستخدم:
    seed_positions = kmer_index.get(seed)
    if not seed_positions: continue
    if len(seed_positions) > MAX_HITS_PER_SEED: ...
    for match_pos in seed_positions: ...

الـ class تحت (KmerIndex) بتوفر بالضبط نفس الواجهة (.get() بيرجع
None أو list عادي، مش numpy array مباشرة، حتى ما تنكسر `if not x`
مع مصفوفات numpy أكتر من عنصر). يعني DNA_locator.py ما بيحتاج أي
تعديل.
====================================================================
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

K = 25  # لازم يطابق SEED_LENGTH بـ DNA_locator.py

_BUILD_CHUNK_SIZE = 10_000_000

# جدول تحويل حرف ASCII -> قيمة 2-bit (255 = حرف غير معروف مثل N)
_LOOKUP = np.full(256, 255, dtype=np.uint8)
for _ch, _val in (("A", 0), ("C", 1), ("G", 2), ("T", 3)):
    _LOOKUP[ord(_ch)] = _val
    _LOOKUP[ord(_ch.lower())] = _val

# مضاعفات الإزاحة لحساب قيمة uint64 لكل k-mer (K*2 bit)
_POWERS = (np.uint64(1) << (2 * np.arange(K - 1, -1, -1, dtype=np.int64).astype(np.uint64)))


def _encode_seed(seed: str) -> Optional[int]:
    """يرمّز seed (نص طوله K) لقيمة uint64. يرجع None لو فيه حرف غير ACGT."""
    if len(seed) != K:
        return None
    codes = _LOOKUP[np.frombuffer(seed.encode("ascii"), dtype=np.uint8)]
    if (codes == 255).any():
        return None
    return int((codes.astype(np.uint64) * _POWERS).sum(dtype=np.uint64))


class KmerIndex:
    """
    فهرس k-mer خفيف الذاكرة، مبني على numpy arrays مرتبة بدل dict نصي.
    بيوفر واجهة .get(seed) متوافقة مع الاستخدام بـ DNA_locator.py.
    """

    __slots__ = ("unique_kmers", "offsets", "positions", "k")

    def __init__(self, unique_kmers: np.ndarray, offsets: np.ndarray, positions: np.ndarray, k: int = K):
        self.unique_kmers = unique_kmers
        self.offsets = offsets
        self.positions = positions
        self.k = k

    def __len__(self) -> int:
        return len(self.unique_kmers)

    def get(self, seed: str) -> Optional[List[int]]:
        """يرجع list من المواقع (int) لو الـ seed موجود بالفهرس، وإلا None."""
        value = _encode_seed(seed)
        if value is None:
            return None
        idx = np.searchsorted(self.unique_kmers, value)
        if idx >= len(self.unique_kmers) or self.unique_kmers[idx] != value:
            return None
        start, end = self.offsets[idx], self.offsets[idx + 1]
        return self.positions[start:end].tolist()

    def save(self, path: Path) -> None:
        np.savez(
            path,
            unique_kmers=self.unique_kmers,
            offsets=self.offsets,
            positions=self.positions,
            k=np.array([self.k]),
        )

    @classmethod
    def load(cls, path: Path) -> "KmerIndex":
        with np.load(path) as data:
            return cls(
                unique_kmers=data["unique_kmers"],
                offsets=data["offsets"],
                positions=data["positions"],
                k=int(data["k"][0]),
            )


def build_kmer_index(chrom_seq: str, k: int = K) -> KmerIndex:
    """
    يبني فهرس k-mer لكروموسوم كامل بذاكرة محدودة (numpy arrays فقط،
    بدون أي dict نصي وسيط). مرة واحدة فقط لكل كروموسوم.
    """
    n = len(chrom_seq)
    if n < k:
        empty = np.array([], dtype=np.uint64)
        return KmerIndex(empty, np.array([0], dtype=np.int64), np.array([], dtype=np.uint32), k)

    seq_bytes = np.frombuffer(chrom_seq.encode("ascii"), dtype=np.uint8)
    powers = (np.uint64(1) << (2 * np.arange(k - 1, -1, -1, dtype=np.int64).astype(np.uint64)))

    kmer_chunks = []
    pos_chunks = []

    chunk_start = 0
    while chunk_start < n - k + 1:
        chunk_end = min(chunk_start + _BUILD_CHUNK_SIZE, n)
        chunk = seq_bytes[chunk_start:chunk_end]

        n_windows = len(chunk) - k + 1
        if n_windows <= 0:
            break

        codes = _LOOKUP[chunk]
        windows = np.lib.stride_tricks.sliding_window_view(codes, k)

        # استبعاد أي نافذة فيها حرف غير معروف (N ...الخ)
        valid_mask = ~(windows == 255).any(axis=1)
        if not valid_mask.any():
            chunk_start += _BUILD_CHUNK_SIZE - (k - 1)
            continue

        valid_windows = windows[valid_mask].astype(np.uint64)
        valid_positions = (np.arange(n_windows, dtype=np.uint32) + chunk_start)[valid_mask]

        kmer_values = (valid_windows * powers).sum(axis=1, dtype=np.uint64)

        kmer_chunks.append(kmer_values)
        pos_chunks.append(valid_positions)

        chunk_start += _BUILD_CHUNK_SIZE - (k - 1)  # overlap بمقدار k-1

    if not kmer_chunks:
        empty = np.array([], dtype=np.uint64)
        return KmerIndex(empty, np.array([0], dtype=np.int64), np.array([], dtype=np.uint32), k)

    all_kmers = np.concatenate(kmer_chunks)
    all_positions = np.concatenate(pos_chunks)
    del kmer_chunks, pos_chunks

    # ترتيب شامل مرة وحدة حسب قيمة الـ k-mer، ثم تجميع المواقع لكل مجموعة
    order = np.argsort(all_kmers, kind="stable")
    sorted_kmers = all_kmers[order]
    sorted_positions = all_positions[order].astype(np.uint32)
    del all_kmers, all_positions, order

    unique_kmers, first_idx = np.unique(sorted_kmers, return_index=True)
    offsets = np.append(first_idx, len(sorted_kmers)).astype(np.int64)
    del sorted_kmers, first_idx

    logger.info(
        "[KmerIndex] تم بناء الفهرس: %d k-mer فريد من أصل %d موقع بطول الكروموسوم (%d bp، k=%d)",
        len(unique_kmers), len(sorted_positions), n, k,
    )
    return KmerIndex(unique_kmers, offsets, sorted_positions, k)


def get_or_build_kmer_index(
    chromosome: str,
    chrom_seq: str,
    genome_fa_path: str,
    cache_dir: str,
    k: int = K,
) -> KmerIndex:
    """
    يرجع فهرس الـ k-mer لكروموسوم معيّن — من الكاش (.npz) لو موجود
    وأحدث من ملف الجينوم المرجعي، وإلا بيبنيه من جديد ويخزّنه.
    """
    cache_path = Path(cache_dir) / f"{chromosome}_k{k}.npz"

    if cache_path.exists() and os.path.getmtime(cache_path) >= os.path.getmtime(genome_fa_path):
        logger.info("[KmerIndex] تحميل الفهرس المخزّن من: %s", cache_path)
        return KmerIndex.load(cache_path)

    logger.info(
        "[KmerIndex] بناء فهرس جديد للكروموسوم '%s' (قد يستغرق وقت حسب طول الكروموسوم)...",
        chromosome,
    )
    index = build_kmer_index(chrom_seq, k=k)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    index.save(cache_path)

    logger.info("[KmerIndex] تم تخزين الفهرس: %s", cache_path)
    return index