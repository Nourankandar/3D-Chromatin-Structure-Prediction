"""
model_loader.py - Basset with correct key remapping
keys in file: "0.weight", "4.weight" (numbered)
keys in model: "conv_net.0.weight", "fc.1.weight" (named)
"""
import os, sys, glob, torch
import torch.nn as nn
from collections import OrderedDict


class BassetModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_net = nn.Sequential(
            nn.Conv2d(4, 300, kernel_size=(19,1), padding=(9,0)),   # 0
            nn.BatchNorm2d(300),                                      # 1
            nn.ReLU(),                                                # 2
            nn.MaxPool2d(kernel_size=(3,1), stride=(3,1)),           # 3
            nn.Conv2d(300, 200, kernel_size=(11,1), padding=(5,0)), # 4
            nn.BatchNorm2d(200),                                      # 5
            nn.ReLU(),                                                # 6
            nn.MaxPool2d(kernel_size=(4,1), stride=(4,1)),           # 7
            nn.Conv2d(200, 200, kernel_size=(7,1), padding=(3,0)),  # 8
            nn.BatchNorm2d(200),                                      # 9
            nn.ReLU(),                                                # 10
            nn.MaxPool2d(kernel_size=(4,1), stride=(4,1)),           # 11
        )
        # 600 -> /3 -> /4 -> /4 = 12 positions, 200 channels
        self.fc = nn.Sequential(
            nn.Flatten(),            # 0
            nn.Linear(200*12, 1000), # 1  <- "13.weight"
            nn.BatchNorm1d(1000),    # 2  <- "14.*"
            nn.ReLU(),               # 3
            nn.Dropout(0.3),         # 4
            nn.Linear(1000, 1000),   # 5  <- "17.weight"
            nn.BatchNorm1d(1000),    # 6  <- "18.*"
            nn.ReLU(),               # 7
            nn.Dropout(0.3),         # 8
            nn.Sequential(nn.Dropout(0.3), nn.Linear(1000, 164)),  # 9 <- "21.1.*"
            nn.Sigmoid(),            # 10
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
    "13":   "fc.1",
    "14":   "fc.2",
    "17":   "fc.5",
    "18":   "fc.6",
    "21.1": "fc.9.1",
}
_SUFFIXES = (".weight", ".bias", ".running_mean", ".running_var", ".num_batches_tracked")


def _remap(raw: OrderedDict) -> OrderedDict:
    new = OrderedDict()
    for raw_key, tensor in raw.items():
        for src, dst in _KEY_MAP.items():
            for suf in _SUFFIXES:
                if raw_key == src + suf:
                    new[dst + suf] = tensor
                    break
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

    if miss:  print(f"  missing keys ({len(miss)}): {miss[:3]}")
    if unex:  print(f"  unexpected  ({len(unex)}): {unex[:3]}")

    # sanity check
    w = dict(model.named_parameters()).get("fc.1.weight")
    if w is not None:
        print(f"  fc.1.weight: mean={w.data.mean():.4f}  std={w.data.std():.4f}")
        if abs(w.data.std().item() - 0.0) < 1e-6:
            print("  WARNING: weights look random - check mapping")
        else:
            print("  Weights loaded correctly!")
    
    model.eval()
    _model = model
    print("Basset ready!")
    return _model