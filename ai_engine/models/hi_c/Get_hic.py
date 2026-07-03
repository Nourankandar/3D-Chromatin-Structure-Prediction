import os
import torch
import torch.nn as nn
import torch.nn.functional as F

# ══════════════════════════════════════════════════════════════
# الهيكل البرمجي المأخوذ من كود التدريب لتركيب الأوزان مباشرة بيب
# ══════════════════════════════════════════════════════════════

class ConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch, kernel=3, dilation=1):
        super().__init__()
        pad = dilation * (kernel - 1) // 2
        self.net = nn.Sequential(
            nn.Conv1d(in_ch, out_ch, kernel, padding=pad, dilation=dilation, bias=False),
            nn.BatchNorm1d(out_ch),
            nn.GELU(),
        )
    def forward(self, x): return self.net(x)

class ResBlock(nn.Module):
    def __init__(self, channels, dilation=1):
        super().__init__()
        pad = dilation
        self.net = nn.Sequential(
            nn.Conv1d(channels, channels, 3, padding=pad, dilation=dilation, bias=False),
            nn.BatchNorm1d(channels),
            nn.GELU(),
            nn.Conv1d(channels, channels, 3, padding=pad, dilation=dilation, bias=False),
            nn.BatchNorm1d(channels),
        )
        self.act = nn.GELU()
    def forward(self, x): return self.act(x + self.net(x))

class DNAEncoder(nn.Module):
    def __init__(self, d_model=128, num_bins=256, window_size=1_280_000):
        super().__init__()
        self.stem = nn.Sequential(ConvBlock(4, 64, kernel=15), nn.MaxPool1d(5))
        self.tower = nn.Sequential(
            ResBlock(64, dilation=1), ConvBlock(64, 96, kernel=5), nn.MaxPool1d(5),
            ResBlock(96, dilation=2), ConvBlock(96, 128, kernel=5), nn.MaxPool1d(4),
            ResBlock(128, dilation=4), ConvBlock(128, 128, kernel=5), nn.MaxPool1d(5),
            ResBlock(128, dilation=8), ConvBlock(128, d_model - 1, kernel=3), nn.MaxPool1d(10),
        )
        self.out_norm = nn.GroupNorm(1, d_model)
    def forward(self, dna, dnase):
        x = self.tower(self.stem(dna))
        dnase_ch = dnase.unsqueeze(1).float()
        return self.out_norm(torch.cat([x, dnase_ch], dim=1))

def _build_rope_cache(seq_len, head_dim, device):
    inv_freq = 1.0 / (10000 ** (torch.arange(0, head_dim, 2, device=device).float() / head_dim))
    t = torch.arange(seq_len, device=device).float()
    freqs = torch.outer(t, inv_freq)
    return torch.cat([freqs, freqs], dim=-1).cos(), torch.cat([freqs, freqs], dim=-1).sin()

def _apply_rope(q, k, cos, sin):
    def rotate_half(x): return torch.cat([-x[..., x.shape[-1] // 2:], x[..., :x.shape[-1] // 2]], dim=-1)
    return q * cos.unsqueeze(0).unsqueeze(0) + rotate_half(q) * sin.unsqueeze(0).unsqueeze(0), k * cos.unsqueeze(0).unsqueeze(0) + rotate_half(k) * sin.unsqueeze(0).unsqueeze(0)

class FlashRoPEAttention(nn.Module):
    def __init__(self, d_model, n_heads, max_len=512, dropout=0.1):
        super().__init__()
        self.n_heads, self.head_dim = n_heads, d_model // n_heads
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)
        cos, sin = _build_rope_cache(max_len, self.head_dim, torch.device("cpu"))
        self.register_buffer("rope_cos", cos)
        self.register_buffer("rope_sin", sin)
    def forward(self, x):
        B, N, D = x.shape
        Q = self.q_proj(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        Q, K = _apply_rope(Q, K, self.rope_cos[:N], self.rope_sin[:N])
        out = F.scaled_dot_product_attention(Q, K, V, is_causal=False)
        return self.out(out.transpose(1, 2).contiguous().view(B, N, D))

class RoPETransformerLayer(nn.Module):
    def __init__(self, d_model, n_heads, max_len=512, dropout=0.1):
        super().__init__()
        self.norm1, self.norm2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
        self.attn = FlashRoPEAttention(d_model, n_heads, max_len, dropout)
        self.ff = nn.Sequential(nn.Linear(d_model, d_model * 4), nn.GELU(), nn.Dropout(dropout), nn.Linear(d_model * 4, d_model), nn.Dropout(dropout))
    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        return x + self.ff(self.norm2(x))

class RoPETransformerEncoder(nn.Module):
    def __init__(self, d_model, n_heads, num_layers, max_len=512, dropout=0.1):
        super().__init__()
        self.layers = nn.ModuleList([RoPETransformerLayer(d_model, n_heads, max_len, dropout) for _ in range(num_layers)])
        self.norm = nn.LayerNorm(d_model)
    def forward(self, x):
        for layer in self.layers: x = layer(x)
        return self.norm(x)

class ChromogenModel(nn.Module):
    def __init__(self, d_model=128, nhead=8, num_layers=4, num_bins=256, window_size=1_280_000, dropout=0.1):
        super().__init__()
        self.encoder = DNAEncoder(d_model, num_bins, window_size)
        self.transformer = RoPETransformerEncoder(d_model, nhead, num_layers, num_bins, dropout)
        self.pair_proj_i = nn.Linear(d_model, d_model, bias=False)
        self.pair_proj_j = nn.Linear(d_model, d_model, bias=False)
        self.pair_norm_act = nn.Sequential(nn.GELU(), nn.LayerNorm(d_model))
        self.decoder = nn.Sequential(nn.Conv2d(d_model, 64, 3, padding=1), nn.GELU(), nn.Conv2d(64, 32, 3, padding=1), nn.GELU(), nn.Conv2d(32, 16, 3, padding=1), nn.GELU(), nn.Conv2d(16, 1, 1))
    def forward(self, dna, dnase):
        z = self.transformer(self.encoder(dna, dnase).permute(0, 2, 1))
        zi, zj = self.pair_proj_i(z).unsqueeze(2), self.pair_proj_j(z).unsqueeze(1)
        pair = self.pair_norm_act(zi + zj)
        pair = pair / (pair.norm(dim=-1, keepdim=True) + 1e-6)
        out = self.decoder(pair.permute(0, 3, 1, 2)).squeeze(1)
        return (out + out.transpose(-1, -2)) * 0.5

# ══════════════════════════════════════════════════════════════
# تابع الاستدعاء المباشر للأوزان
# ══════════════════════════════════════════════════════════════

def predict_hic(dna_features, dnase_profile, model_path=None):
    if model_path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, 'best_model.pt')
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    model = ChromogenModel() 
    checkpoint = torch.load(model_path, map_location=device)
    
    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
        model.load_state_dict(checkpoint['state_dict'])
    else:
        model.load_state_dict(checkpoint)
        
    model.to(device)
    model.eval()
    
    # تابعي هنا كود التنبؤ وتمرير الـ Features وتوليد المصفوفة...
    
    # تحويل المدخلات إلى Tensors
    if not isinstance(dna_features, torch.Tensor):
        dna_features = torch.tensor(dna_features, dtype=torch.float32)
    if not isinstance(dnase_profile, torch.Tensor):
        dnase_profile = torch.tensor(dnase_profile, dtype=torch.float32)
        
    # ضبط الأبعاد لتناسب الـ Batch (تعدل حسب معماريتك)
    if dna_features.ndim == 1:
        dna_features = dna_features.unsqueeze(0)
    if dnase_profile.ndim == 1:
        dnase_profile = dnase_profile.unsqueeze(0)

    # نقل المدخلات للـ Device
    dna_features = dna_features.to(device)
    dnase_profile = dnase_profile.to(device)
    
    with torch.no_grad():
        # استدعاء المودل بالمدخلات
        hic_output = model(dna_features, dnase_profile)
        hic_matrix = hic_output.squeeze().cpu().numpy()
        
    return hic_matrix