"""
check_weights.py — افحص keys ملف الأوزان وشوف سبب القيم الصفرية
py check_weights.py
"""
import torch
import sys

WEIGHTS_PATH = r"C:\Users\dell\.kipoi\models\Basset\pretrained_model_reloaded_th.pth"

print("=" * 60)
print("فحص ملف الأوزان")
print("=" * 60)

state = torch.load(WEIGHTS_PATH, map_location="cpu")
print(f"النوع: {type(state)}\n")

if isinstance(state, dict):
    keys = list(state.keys())
    print(f"عدد الـ keys: {len(keys)}")
    print("\nأول 15 key:")
    for k in keys[:15]:
        v     = state[k]
        shape = tuple(v.shape) if hasattr(v, 'shape') else type(v).__name__
        print(f"  {k:55s} {shape}")
    if len(keys) > 15:
        print("\n  ...")
        print("\nآخر 5 keys:")
        for k in keys[-5:]:
            v     = state[k]
            shape = tuple(v.shape) if hasattr(v, 'shape') else type(v).__name__
            print(f"  {k:55s} {shape}")

elif hasattr(state, 'state_dict'):
    print("الملف موديل كامل — نستخرج state_dict")
    sd   = state.state_dict()
    keys = list(sd.keys())
    print(f"عدد الـ keys: {len(keys)}")
    for k in keys[:15]:
        print(f"  {k:55s} {tuple(sd[k].shape)}")

# ── تحقق من القيم: هل هي عشوائية أم حقيقية؟ ─────────────────────────────────
print("\n" + "=" * 60)
print("فحص القيم — هل الأوزان مدرّبة أم عشوائية؟")
print("=" * 60)
sd = state if isinstance(state, dict) else state.state_dict()
for k, v in list(sd.items())[:5]:
    if hasattr(v, 'float'):
        v_f = v.float()
        print(f"  {k[:45]:45s} mean={v_f.mean():.4f}  std={v_f.std():.4f}")