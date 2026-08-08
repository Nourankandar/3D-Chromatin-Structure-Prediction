
import argparse
import json
import os
import warnings

import numpy as np
from scipy.interpolate import splev, splprep
from scipy.spatial.distance import pdist, squareform
from sklearn.manifold import MDS
from backend.services.genomics.proteomics.nucleosome_track import build_nucleosome_track
warnings.filterwarnings("ignore")

# ألوان الـ TADs (تُستخدم في العارض)
TAD_COLORS = [
    "#38bdf8", "#818cf8", "#34d399", "#f97316", "#f43f5e",
    "#a78bfa", "#22d3ee", "#facc15", "#fb7185", "#4ade80",
]


# ═══════════════════════════════════════
# 1. قراءة الملف
# ═══════════════════════════════════════

def infer_info_from_name(path, n_bins, resolution=5000):
   
    import re
    base = os.path.basename(path)
    m = re.search(r"(chr[\dXYM]+)[_\-](\d+)", base, re.IGNORECASE)
    chrom = m.group(1).lower() if m else "chr1"
    start = int(m.group(2)) if m else 0
    return {"chrom": chrom, "start": start,
            "end": start + n_bins * resolution, "resolution": resolution}


def load_hic_file(path, verbose=True, resolution=5000):
    """يقرأ ملف Hi-C ويرجع المصفوفة والمعلومات الجينية."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"الملف غير موجود: {path}")

    ext = path.split(".")[-1].lower()

    if ext == "npz":
        data = np.load(path, allow_pickle=True)
        matrix = None
        for key in ["hic_matrix", "hic", "matrix", "contact_matrix"]:
            if key in data:
                matrix = data[key].astype(np.float32)
                break
        if matrix is None:
            for key in data.keys():
                if data[key].ndim == 2:
                    matrix = data[key].astype(np.float32)
                    break
        if matrix is None:
            raise ValueError(f"لم أجد مصفوفة Hi-C. المفاتيح: {list(data.keys())}")

        info = {
            "chrom": str(data["chrom"]) if "chrom" in data else "unknown",
            "start": int(data["start"]) if "start" in data else 0,
            "end": int(data["end"]) if "end" in data else matrix.shape[0] * 5000,
            "resolution": int(data["resolution"]) if "resolution" in data else 5000,
        }

    elif ext == "npy":
        matrix = np.load(path).astype(np.float32)
        info = infer_info_from_name(path, matrix.shape[0], resolution)

    elif ext in ("txt", "csv"):
        sep = "," if ext == "csv" else None
        matrix = np.loadtxt(path, delimiter=sep).astype(np.float32)
        info = {"chrom": "unknown", "start": 0,
                "end": matrix.shape[0] * 5000, "resolution": 5000}
    else:
        raise ValueError(f"صيغة غير مدعومة: {ext} | المدعوم: npz, npy, txt, csv")

    if verbose:
        print(f"[✓] المصفوفة: {matrix.shape} من {path}")
        print(f"    {info['chrom']} | {info['start']:,} → {info['end']:,} "
              f"| دقة {info['resolution']:,} bp")
    return matrix, info


# ═══════════════════════════════════════
# 2. تنظيف المصفوفة
# ═══════════════════════════════════════

def clean_matrix(matrix, verbose=True):
    #تصفير القطر، حذف البينات الفارغة، تطبيع لوغاريتمي.
    mat = matrix.copy().astype(np.float64)
    # بعض النماذج تُخرج قيماً سالبة ضئيلة — نصفّرها (التلامس لا يكون سالباً)
    n_neg = int((mat < 0).sum())
    if n_neg:
        if verbose:
            print(f"[i] صُفِّرت {n_neg} قيمة سالبة (أدناها {mat.min():.2e})")
        mat[mat < 0] = 0
    np.fill_diagonal(mat, 0)

    valid = mat.sum(axis=1) > 0
    removed = int((~valid).sum())
    if removed and verbose:
        print(f"[i] حُذف {removed} bin فارغ")
    mat = mat[valid][:, valid]

    mat = np.log1p(mat)
    mat = (mat + mat.T) / 2
    if verbose:
        print(f"[✓] بعد التنظيف: {mat.shape}")
    return mat, valid


# ═══════════════════════════════════════
# 3. تلامس → مسافات
# ═══════════════════════════════════════

def contact_to_distance(matrix, alpha=0.5, verbose=True):
    #distance = contact^(-alpha) ثم تطبيع للنطاق [0, 100].
    mat = matrix.copy()
    mat[mat == 0] = 1e-10
    dist = 1.0 / (mat ** alpha)
    np.fill_diagonal(dist, 0)
    dist = (dist + dist.T) / 2

    max_d = dist[dist > 0].max()
    dist = dist / max_d * 100
    if verbose:
        print(f"[✓] المسافات — min {dist[dist>0].min():.2f} | max {dist.max():.2f}")
    return dist


# ═══════════════════════════════════════
# 3-ب. أقصر مسار (خطوة ShRec3D)
# ═══════════════════════════════════════

def to_shortest_path(dist_matrix, verbose=True):
    
    from scipy.sparse.csgraph import shortest_path
    out = shortest_path(dist_matrix, method="D", directed=False)

    # قد ينفصل الرسم البياني عند بعض قيم alpha فتظهر مسافات لانهائية.
    # نستبدلها بأكبر مسافة محدودة مضروبة قليلاً — أي «أبعد ما يمكن»
    # دون كسر الحساب.
    finite = np.isfinite(out)
    if not finite.all():
        max_finite = out[finite].max() if finite.any() else 1.0
        n_inf = int((~finite).sum())
        out[~finite] = max_finite * 1.5
        if verbose:
            print(f"[i] الرسم غير متصل — عُوّضت {n_inf:,} مسافة لانهائية")

    if verbose:
        off = ~np.eye(len(out), dtype=bool)
        before = dist_matrix[off].max() / max(dist_matrix[off].min(), 1e-12)
        after = out[off].max() / max(out[off].min(), 1e-12)
        print(f"[✓] أقصر مسار — مدى المسافات {before:,.0f}x → {after:,.0f}x")
    return out


# ═══════════════════════════════════════
# 4. MDS → XYZ  (+ stress مُطبَّع)
# ═══════════════════════════════════════

def normalized_stress(coords, dist_matrix):
   
    proj = pdist(coords)
    target = squareform(dist_matrix, checks=False)
    denom = np.dot(proj, proj)
    if denom == 0:
        return 0.0
    b = np.dot(proj, target) / denom          # معامل القياس الأمثل
    num = np.sum((b * proj - target) ** 2)
    den = np.sum(target ** 2)
    return float(np.sqrt(num / den)) if den > 0 else 0.0


def dscc(coords, contact_matrix):
    
    from scipy.stats import spearmanr
    d3 = pdist(coords)
    upper = np.triu(contact_matrix, 1)
    contacts = squareform(upper + upper.T, checks=False)
    return -float(spearmanr(d3, contacts).correlation)


def run_mds(dist_matrix, n_init=4, max_iter=1000, verbose=True):
    """SMACOF MDS — أدق من Classical MDS لبيانات Hi-C."""
    if verbose:
        print("[i] تشغيل MDS…")
    mds = MDS(
        n_components=3,
        dissimilarity="precomputed",
        random_state=42,          # نتائج قابلة للتكرار
        max_iter=max_iter,
        n_init=n_init,
        normalized_stress="auto",
    )
    coords = mds.fit_transform(dist_matrix).astype(np.float32)
    stress = normalized_stress(coords, dist_matrix)
    if verbose:
        print(f"[✓] MDS تم — stress مُطبَّع {stress:.4f} | نقاط {coords.shape[0]}")
    return coords, stress




# ═══════════════════════════════════════
# 4-ب. التحسين الفيزيائي (اختياري)
# ═══════════════════════════════════════

def physics_refine(coords, dist_matrix, iters=300, lr=0.02,
                   k_restraint=2.0, k_chain=1.0, k_repel=0.4,
                   verbose=True):
   
    from scipy.spatial import cKDTree

    X = coords.astype(np.float64).copy()
    n = len(X)

    # نوحّد المقياس: متوسط خطوة السلسلة = 1، والمسافات المستهدفة بنفس النسبة
    step0 = np.linalg.norm(np.diff(X, axis=0), axis=1).mean()
    if step0 <= 0:
        return coords
    X /= step0
    D = dist_matrix / max(np.median(dist_matrix[dist_matrix > 0]), 1e-12)
    np.fill_diagonal(D, 0)

    contact_radius = 0.8   # نصف قطر «الحجم المستبعد» بوحدات السلسلة

    for _ in range(iters):
        F = np.zeros_like(X)

        # 1) قيود التلامس
        diff = X[:, None, :] - X[None, :, :]
        dist = np.linalg.norm(diff, axis=2) + 1e-9
        err = (dist - D) / dist
        np.fill_diagonal(err, 0.0)
        F -= k_restraint * np.einsum("ij,ijk->ik", err, diff) / n

        # 2) ترابط السلسلة
        d = X[1:] - X[:-1]
        L = np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
        f = k_chain * (L - 1.0) * (d / L)
        F[:-1] += f
        F[1:] -= f

        # 3) تنافر الحجم المستبعد
        pairs = cKDTree(X).query_pairs(r=contact_radius, output_type="ndarray")
        if len(pairs):
            dv = X[pairs[:, 0]] - X[pairs[:, 1]]
            L2 = np.linalg.norm(dv, axis=1, keepdims=True) + 1e-9
            push = k_repel * (contact_radius - L2) * (dv / L2)
            np.add.at(F, pairs[:, 0], push)
            np.add.at(F, pairs[:, 1], -push)

        X += lr * F

    X *= step0   # نعيد المقياس الأصلي
    if verbose:
        before = count_overlaps(coords)
        after = count_overlaps(X)
        print(f"[✓] تحسين فيزيائي — تداخل {before:,} → {after:,} "
              f"({100*(before-after)/max(before,1):.0f}%- )")
    return X.astype(np.float32)


def collapse_ratio(coords):
    
    r = np.linalg.norm(coords - coords.mean(axis=0), axis=1)
    med = np.median(r)
    return float(r.max() / med) if med > 1e-9 else float("inf")


def count_overlaps(coords):
    #عدد أزواج النقاط المتداخلة (أقرب من نصف متوسط خطوة السلسلة
    from scipy.spatial import cKDTree
    step = np.linalg.norm(np.diff(coords, axis=0), axis=1).mean()
    return len(cKDTree(coords).query_pairs(r=step * 0.5))


# ═══════════════════════════════════════
# 5. تنعيم Spline
# ═══════════════════════════════════════

def smooth_spline(coords, num_points=1200, verbose=True):
   # يولّد خيطاً ناعماً للعرض
    try:
        tck, _ = splprep([coords[:, 0], coords[:, 1], coords[:, 2]], s=None, k=3)
        u = np.linspace(0, 1, num_points)
        xs, ys, zs = splev(u, tck)
        smooth = np.column_stack([xs, ys, zs]).astype(np.float32)
        if verbose:
            print(f"[✓] Spline — {num_points} نقطة")
        return smooth
    except Exception as e:
        if verbose:
            print(f"[!] تعذّر Spline ({e}) — سنستخدم النقاط الأصلية")
        return coords


# ═══════════════════════════════════════
# 6. كثافة + حدود TADs
# ═══════════════════════════════════════

def compute_density(coords, k=8):
    """كثافة محلية لكل نقطة (0–1): كم النقاط مزدحمة حولها."""
    from scipy.spatial import cKDTree
    tree = cKDTree(coords)
    k_eff = min(k + 1, len(coords))
    d, _ = tree.query(coords, k=k_eff)
    mean_d = d[:, 1:].mean(axis=1) if k_eff > 1 else np.ones(len(coords))
    dens = 1.0 / (mean_d + 1e-9)
    lo, hi = dens.min(), dens.max()
    return ((dens - lo) / (hi - lo)) if hi > lo else np.full(len(coords), 0.5)


def detect_tads(dist_matrix, min_size=8):
    
    n = dist_matrix.shape[0]
    w = max(3, min_size // 2)
    ins = np.zeros(n)
    for i in range(w, n - w):
        left = dist_matrix[i - w:i, i - w:i].mean()
        right = dist_matrix[i:i + w, i:i + w].mean()
        across = dist_matrix[i - w:i, i:i + w].mean()
        ins[i] = across - (left + right) / 2

    boundaries, last = [], -min_size
    thr = ins.mean() + ins.std()
    for i in range(w, n - w):
        if ins[i] > thr and i - last >= min_size:
            boundaries.append(int(i))
            last = i

    tad_id = np.zeros(n, dtype=int)
    for b_i, b in enumerate(boundaries):
        tad_id[b:] = b_i + 1
    return boundaries, tad_id


# ═══════════════════════════════════════
# 7. بناء كائن البنية (شكل العارض)
# ═══════════════════════════════════════

def build_structure(path, alpha=0.5, smooth_points=1200, verbose=True,
                    physics=False, resolution=5000, auto_alpha=False,
                    dnase_signal=None):
    matrix, info = load_hic_file(path, verbose, resolution)
    clean, valid = clean_matrix(matrix, verbose)

    if auto_alpha:
        # نختار alpha بمقياس dSCC وليس stress.
        # السبب: تغيير alpha يغيّر المسافات المستهدفة نفسها، فاختياره
        # حسب stress استدلال دَوري (نختار الهدف الأسهل لا الأصحّ).
        # أما dSCC فيُقاس مقابل مصفوفة التلامس الخام، وهي ثابتة.
        best = None
        for a in (0.1, 0.25, 0.5, 1.0, 2.0):
            d_try = to_shortest_path(contact_to_distance(clean, a, verbose=False),
                                     verbose=False)
            # نستخدم نفس إعدادات التشغيل النهائي حتى لا يتغيّر الترتيب لاحقاً
            c_try, s_try = run_mds(d_try, verbose=False)
            q = dscc(c_try, clean)
            if best is None or q > best[1]:
                best = (a, q, d_try, c_try, s_try)
        alpha = best[0]
        if verbose:
            print(f"[✓] alpha تلقائي = {alpha} (dSCC {best[1]:.4f})")
        dist = best[2]
        coords, stress = best[3], best[4]   # نحتفظ بالمجسّم الأفضل مباشرة
    else:
        dist = to_shortest_path(contact_to_distance(clean, alpha, verbose), verbose)
        coords, stress = run_mds(dist, verbose=verbose)

    cr = collapse_ratio(coords)
    if cr > 20 and verbose:
        print(f"[!] تحذير: مؤشّر الانهيار {cr:.0f} (الطبيعي 2–5) — "
              f"معظم النقاط متكدّسة؛ المجسّم غير موثوق للعرض")

    if physics:
        ov_before = count_overlaps(coords)
        # لا فائدة من التحسين إن كان المجسّم نظيفاً أصلاً
        if ov_before < len(coords) * 0.5:
            if verbose:
                print(f"[i] المجسّم نظيف أصلاً (تداخل {ov_before}) — تخطّي التحسين الفيزيائي")
        else:
            refined = physics_refine(coords, dist, verbose=False)
            ov_after = count_overlaps(refined)
            s_after = normalized_stress(refined, dist)
            # نقبل التحسين فقط إن قلّل التداخل فعلاً دون إفساد الـ stress
            if ov_after < ov_before and s_after < stress * 1.15:
                coords, stress = refined, s_after
                if verbose:
                    print(f"[✓] تحسين فيزيائي — تداخل {ov_before:,} → {ov_after:,} "
                          f"| stress {stress:.4f}")
            elif verbose:
                print(f"[i] التحسين لم يُفد (تداخل {ov_before:,} → {ov_after:,}) — أُبقي على MDS")
    smooth = smooth_spline(coords, smooth_points, verbose)

    # توحيد المقياس: MDS يُنتج إحداثيات بمقاييس متفاوتة جداً
    # (نصف قطر 0.0025 مقابل 2.8) والعارض لا يستطيع عرض بنية بالغة الصغر.
    # نطبّع كل مجسّم إلى نصف قطر 10 وحدات — لا يؤثر على الدقة إطلاقاً
    # لأن كل المقاييس (dSCC، stress) نسبية لا مطلقة.
    _r = np.linalg.norm(coords - coords.mean(axis=0), axis=1).max()
    if _r > 0:
        _scale = 10.0 / _r
        coords = (coords - coords.mean(axis=0)) * _scale
        smooth = (smooth - smooth.mean(axis=0)) * _scale
        if verbose:
            print(f"[✓] توحيد المقياس — نصف القطر {_r:.4f} → 10.0")

    density = compute_density(coords)
    boundaries, tad_id = detect_tads(dist)
    n_tads = int(tad_id.max()) + 1

    # انحراف كل نقطة عن الشكل الناعم (مؤشر «تباين» للعرض)
    idx_map = np.linspace(0, len(smooth) - 1, len(coords)).astype(int)
    dev = np.linalg.norm(coords - smooth[idx_map], axis=1)
    dev = dev / dev.max() if dev.max() > 0 else dev

    bin_idx = np.where(valid)[0]
    res, start = info["resolution"], info["start"]

    coords_raw = []
    for i, c in enumerate(coords):
        b = int(bin_idx[i]) if i < len(bin_idx) else i
        bp0 = start + b * res
        coords_raw.append({
            "x": round(float(c[0]), 4),
            "y": round(float(c[1]), 4),
            "z": round(float(c[2]), 4),
            "region": f"{bp0//1000}kb-{(bp0+res)//1000}kb",
            "density": round(float(density[i]), 4),
            "deviation": round(float(dev[i]), 4),
            "tad_id": int(tad_id[i]),
            "is_boundary": bool(i in boundaries),
        })

    coords_smooth = []
    for j, c in enumerate(smooth):
        i = min(int(j / max(len(smooth) - 1, 1) * (len(coords) - 1)), len(coords) - 1)
        coords_smooth.append({
            "x": round(float(c[0]), 4),
            "y": round(float(c[1]), 4),
            "z": round(float(c[2]), 4),
            "density": round(float(density[i]), 4),
            "deviation": round(float(dev[i]), 4),
            "tad_id": int(tad_id[i]),
        })

    steps = np.linalg.norm(np.diff(coords, axis=0), axis=1)
    quality = dscc(coords, clean)
    if verbose:
        print(f"[✓] dSCC = {quality:.4f} (المقياس المرجعي — الأعلى أفضل)")
    nucleosome_track = []
    if dnase_signal is not None:
        nucleosome_track = build_nucleosome_track(
            dnase_signal=dnase_signal,
            coords_smooth=coords_smooth,   # القائمة يلي بنيناها فوق (list of dicts)
            genomic_start=info["start"],
            n_original_bins=len(coords_raw),
            resolution=info["resolution"],
        )
        if verbose:
            print(f"[✓] Nucleosome track — {len(nucleosome_track)} وحدة (200bp لكل وحدة)")

    return {
        "chrom": info["chrom"],
        "start": info["start"],
        "end": info["end"],
        "resolution": info["resolution"],
        "stress": round(stress, 4),
        "dscc": round(quality, 4),
        "collapse_ratio": round(collapse_ratio(coords), 2),
        "n_tads": n_tads,
        "tad_colors": TAD_COLORS[:max(n_tads, 1)],
        "tad_boundaries": boundaries,
        "coords_raw": coords_raw,
        "coords_smooth": coords_smooth,
        "nucleosome_track": nucleosome_track,   # ← جديد
        "stats": {
            "mean_step": round(float(steps.mean()), 4) if len(steps) else 0.0,
            "std_step": round(float(steps.std()), 4) if len(steps) else 0.0,
            "max_density": round(float(density.max()), 4),
            "n_bins": int(len(coords)),
            "n_boundaries": int(len(boundaries)),
        },
    }


# ═══════════════════════════════════════
# 8. نقطة الدخول
# ═══════════════════════════════════════

def run(input_path, control_path=None, alpha=0.5, smooth_points=1200,
        output=None, physics=False, resolution=5000, auto_alpha=False,
        dnase_patient=None, dnase_control=None):
    print("\n" + "=" * 52)
    print("  Hi-C → 3D Coordinates (v2)")
    print("=" * 52)

    print("\n— المريض —")
    patient = build_structure(input_path, alpha, smooth_points,
                              physics=physics, resolution=resolution,
                              auto_alpha=auto_alpha, dnase_signal=dnase_patient)

    payload = {"patient": patient}
    if control_path:
        print("\n— السليم —")
        payload["control"] = build_structure(control_path, alpha, smooth_points,
                                            physics=physics, resolution=resolution,
                                            auto_alpha=auto_alpha, dnase_signal=dnase_control)
    if output is None:
        output = os.path.splitext(os.path.basename(input_path))[0] + "_coords.json"

    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    size_kb = os.path.getsize(output) / 1024
    print(f"\n[✓] حُفظ: {output} ({size_kb:.1f} KB)")
    print(f"    stress المريض: {patient['stress']:.4f} "
          f"(0 = مثالي · أقل من 0.15 ممتاز · أكثر من 0.4 ضعيف)")
    if control_path:
        print(f"    stress السليم: {payload['control']['stress']:.4f}")
    print("    الملف جاهز للاستيراد مباشرة في عارض الكروماتين.")
    return output


# ═══════════════════════════════════════
# 9. الجسر مع الـ pipeline (Django) — هاي اللي بينادي عليها pipeline_manager
# ═══════════════════════════════════════

def convert_hic_to_3d_coords(
    hic_relative_path: str,
    alpha: float = 0.5,
    output_name_hint: str = "sample",
) -> str:
    """
    بتفتح ملف Hi-C المحفوظ (.npz، طالع من HI_C/predictorHIC.py)، بتشغّل عليه
    نفس محرك build_structure() (MDS + spline + TADs) الموجود فوق، وبتحفظ
    الناتج كملف .json تحت MEDIA_ROOT/genomics/coordinates_3d/json/.

    ملاحظة مهمة: منحفظ نتيجة build_structure() مباشرة بجذر ملف الـ JSON
    (مش تحت مفتاح "patient"/"control")، لأنه _step_motifs بـ
    pipeline_manager.py عم يقرأ payload.get("coords_raw", []) من المستوى
    الأعلى مباشرة — هاد الجسر بيُستدعى مرة لكل واحد (مريض / سليم) لحاله.

    Parameters
    ----------
    hic_relative_path : المسار النسبي لملف .npz (نسبة لـ MEDIA_ROOT) — هو
                         نفس القيمة يلي بترجعها generate_hic_matrices()
    alpha : أس تحويل التفاعل إلى مسافة
    output_name_hint : اسم مميز لملف الإخراج (مثلاً "input_17_patient")

    Returns
    -------
    str: المسار النسبي (نسبة لـ MEDIA_ROOT) لملف الإحداثيات JSON
    """
    from django.conf import settings

    absolute_hic_path = os.path.join(settings.MEDIA_ROOT, hic_relative_path)
    if not os.path.exists(absolute_hic_path):
        raise FileNotFoundError(f"Hi-C matrix file not found at: {absolute_hic_path}")

    result_dict = build_structure(
        absolute_hic_path,
        alpha=alpha,
        verbose=False,
    )

    relative_folder = "genomics/coordinates_3d/json/"
    absolute_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(absolute_folder, exist_ok=True)

    output_filename = f"{output_name_hint}_coords.json"
    absolute_output_path = os.path.join(absolute_folder, output_filename)

    with open(absolute_output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False)

    print(
        f"[✓] 3D coordinates saved: {absolute_output_path} "
        f"(n_bins={result_dict['stats']['n_bins']}, stress={result_dict['stress']:.4f})"
    )

    return os.path.join(relative_folder, output_filename)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Hi-C → 3D coordinates JSON (v2)")
    ap.add_argument("--input", required=True, help="ملف Hi-C للمريض (npz/npy/txt/csv)")
    ap.add_argument("--control", default=None, help="ملف Hi-C للسليم (اختياري — للمقارنة)")
    ap.add_argument("--alpha", type=float, default=0.5, help="أس التحويل (افتراضي 0.5)")
    ap.add_argument("--points", type=int, default=1200, help="نقاط Spline (افتراضي 1200)")
    ap.add_argument("--output", default=None, help="اسم ملف JSON الناتج")
    ap.add_argument("--physics", action="store_true",
                    help="تحسين فيزيائي بعد MDS (يقلّل التداخل ~80%%)")
    ap.add_argument("--auto-alpha", action="store_true", dest="auto_alpha",
                    help="اختيار alpha تلقائياً (يجرّب عدة قيم ويختار الأدق)")
    ap.add_argument("--resolution", type=int, default=5000,
                    help="حجم البين بالـ bp (يُستخدم مع ملفات .npy)")
    a = ap.parse_args()
    run(a.input, a.control, a.alpha, a.points, a.output, a.physics,
        a.resolution, a.auto_alpha)