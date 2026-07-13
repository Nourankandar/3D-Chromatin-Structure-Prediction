"""
model_loader.py - Basset (FIXED نهائياً بناءً على pretrained_model_reloaded_th.py الأصلي)
====================================================================
اكتشفنا مشكلتين حقيقيتين مقارنة مع المصدر الأصلي (convert_Basset_to_pytorch
+ pretrained_model_reloaded_th.py + model.yaml من Kipoi):

مشكلة 1 (تسمية المفاتيح): طبقتي fc.1 وfc.5 بالملف مخزّنتين كـ '13.1.weight'
و'17.1.weight' مش '13.weight'/'17.weight' — لأنه كل Linear بالأصل ملفوفة
بـ nn.Sequential(Lambda(...), nn.Linear(...)) (شوف pretrained_model_reloaded_th.py
سطر "nn.Sequential(Lambda(...), nn.Linear(2000,1000))"). تم تصحيحها بـ _KEY_MAP.

مشكلة 2 (الأهم - بنية الموديل نفسها): كل الـ Conv2d بالأصل بدون أي padding
إطلاقاً (nn.Conv2d(4,300,(19,1)) بدون معامل padding = padding افتراضي صفر)،
بينما النسخة القديمة من BassetModel كانت حاطة padding=(9,0)/(5,0)/(3,0)
بالغلط. هاد كان عم يخلي طول الـ feature map النهائي 12 بدل 10، فتصير
fc.1 تتوقع 2400 مدخل بدل 2000 الحقيقية -> size mismatch عند التحميل.

تأكيد الحساب اليدوي (600bp input, بدون padding):
  600 --Conv1(k=19)--> 582 --MaxPool(3,3)--> 194
  194 --Conv2(k=11)--> 184 --MaxPool(4,4)--> 46
   46 --Conv3(k=7) -->  40 --MaxPool(4,4)--> 10
  10 * 200 channels = 2000  ✅ يطابق شكل fc.1.weight الحقيقي (1000, 2000)
====================================================================
"""
import os, sys, glob, torch
import torch.nn as nn
from collections import OrderedDict


class BassetModel(nn.Module):
    def __init__(self):
        super().__init__()
        # ── مهم: بدون padding إطلاقاً بكل conv (مطابق تماماً للأصل) ──
        self.conv_net = nn.Sequential(
            nn.Conv2d(4, 300, kernel_size=(19, 1)),                  # 0  (بدون padding)
            nn.BatchNorm2d(300),                                      # 1
            nn.ReLU(),                                                # 2
            nn.MaxPool2d(kernel_size=(3, 1), stride=(3, 1)),         # 3
            nn.Conv2d(300, 200, kernel_size=(11, 1)),                # 4  (بدون padding)
            nn.BatchNorm2d(200),                                      # 5
            nn.ReLU(),                                                # 6
            nn.MaxPool2d(kernel_size=(4, 1), stride=(4, 1)),         # 7
            nn.Conv2d(200, 200, kernel_size=(7, 1)),                 # 8  (بدون padding)
            nn.BatchNorm2d(200),                                      # 9
            nn.ReLU(),                                                # 10
            nn.MaxPool2d(kernel_size=(4, 1), stride=(4, 1)),         # 11
        )
        # 600 -> 582/194 -> 184/46 -> 40/10 = 10 positions, 200 channels -> 2000
        self.fc = nn.Sequential(
            nn.Flatten(),              # 0
            nn.Linear(200 * 10, 1000), # 1  <- "13.1.weight" (2000 مدخل، مش 2400)
            nn.BatchNorm1d(1000),      # 2  <- "14.*"
            nn.ReLU(),                 # 3
            nn.Dropout(0.3),           # 4
            nn.Linear(1000, 1000),     # 5  <- "17.1.weight"
            nn.BatchNorm1d(1000),      # 6  <- "18.*"
            nn.ReLU(),                 # 7
            nn.Dropout(0.3),           # 8
            nn.Sequential(nn.Dropout(0.3), nn.Linear(1000, 164)),  # 9 <- "21.1.*"
            nn.Sigmoid(),              # 10
        )

    def forward(self, x):
        return self.fc(self.conv_net(x))


# Mapping: file prefix -> model path prefix
_KEY_MAP = {
    "0":    "conv_net.0",
    "1":    "conv_net.1",
    "4":    "conv_net.4",
    "5":    "conv_net.5",
    "8":    "conv_net.8",
    "9":    "conv_net.9",
    "13.1": "fc.1",     # ملف: '13.1.weight' (Linear جوا Sequential مع Lambda)
    "14":   "fc.2",
    "17.1": "fc.5",     # ملف: '17.1.weight'
    "18":   "fc.6",
    "21.1": "fc.9.1",
}
_SUFFIXES = (".weight", ".bias", ".running_mean", ".running_var", ".num_batches_tracked")


def _remap(raw: OrderedDict) -> OrderedDict:
    new = OrderedDict()
    unmatched_raw_keys = []

    for raw_key, tensor in raw.items():
        matched = False
        for src, dst in _KEY_MAP.items():
            for suf in _SUFFIXES:
                if raw_key == src + suf:
                    new[dst + suf] = tensor
                    matched = True
                    break
            if matched:
                break
        if not matched:
            unmatched_raw_keys.append(raw_key)

    if unmatched_raw_keys:
        print(f"  [WARNING] {len(unmatched_raw_keys)} مفتاح بالملف ما انطابق مع أي mapping: {unmatched_raw_keys}")

    return new


_model = None

def load_basset_model(weights_path: str = None) -> nn.Module:
    global _model
    if _model is not None:
        return _model

    print("Loading Basset model...")
    basset_dir = r"C:\Users\dell\.kipoi\models\Basset"

    if weights_path is None:
        default = os.path.join(basset_dir, "pretrained_model_reloaded_th.pth")
        if os.path.exists(default):
            weights_path = default
        else:
            found = glob.glob(os.path.join(basset_dir, "**", "*.pth"), recursive=True)
            weights_path = found[0] if found else None

    if not weights_path or not os.path.exists(weights_path):
        raise FileNotFoundError(f"Weights not found in: {basset_dir}")

    print(f"  weights: {os.path.basename(weights_path)}")

    raw_sd = torch.load(weights_path, map_location="cpu")
    new_sd = _remap(raw_sd)

    model  = BassetModel()
    miss, unex = model.load_state_dict(new_sd, strict=False)

    if miss:
        print(f"  missing keys ({len(miss)}): {miss[:5]}")
    else:
        print("  missing keys: 0 ✅")

    if unex:
        print(f"  unexpected  ({len(unex)}): {unex[:5]}")
    else:
        print("  unexpected keys: 0 ✅")

    # sanity check: كل الأوزان لازم تكون محملة فعلياً (صفر missing/unexpected)
    if not miss and not unex:
        w = dict(model.named_parameters())["fc.1.weight"]
        print(f"  fc.1.weight: shape={tuple(w.shape)}  mean={w.data.mean():.4f}  std={w.data.std():.4f}")
        print("  ✅ Weights loaded correctly — كل الـ 32 مفتاح تطابقوا بدون أي نقص.")
    else:
        print("  ⚠️ WARNING: لسا في مفاتيح ناقصة أو زايدة — تحقق من _KEY_MAP أو البنية.")

    model.eval()
    _model = model
    print("Basset ready!")
    return _model