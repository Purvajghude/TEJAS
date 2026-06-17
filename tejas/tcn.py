"""Temporal CNN with GOES → Aditya-L1 transfer learning (the deep-model track).

A dilated 1-D CNN reads a 120-minute window of three physical channels
(log soft, log hard, hardness) and predicts whether a flare peaks in the next
H minutes.  It is **pretrained on years of GOES** (thousands of flares) and then
**fine-tuned on Aditya-L1** soft+hard data.  Pretraining years (2022-2023) do not
overlap the Aditya-L1 test period (Sep-Oct 2024), so there is no leakage.

Evaluated on the *same* chronological test set as the tree/logistic models, so the
head-to-head in `tejas.compare` is honest.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score

from .config import Config, load_config
from . import pretrain as P
from . import models

W, H, CADENCE = 120, 30, 60          # window mins, horizon mins, seconds/bin
torch.manual_seed(42)


class TCNNet(nn.Module):
    def __init__(self, in_ch=3, hidden=32, levels=4, k=3, p=0.2):
        super().__init__()
        blocks, ch = [], in_ch
        for l in range(levels):
            d = 2 ** l
            blocks += [nn.Conv1d(ch, hidden, k, padding=d, dilation=d),
                       nn.BatchNorm1d(hidden), nn.ReLU(), nn.Dropout(p)]
            ch = hidden
        self.body = nn.Sequential(*blocks)
        self.head = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(),
                                  nn.Linear(hidden, 1))

    def forward(self, x):
        return self.head(self.body(x)).squeeze(-1)


def _train(model, Xtr, ytr, Xva, yva, epochs=25, lr=1e-3, bs=256, verbose=False):
    Xtr = torch.tensor(Xtr); ytr = torch.tensor(ytr)
    Xva = torch.tensor(Xva); yva = torch.tensor(yva)
    pos = float(ytr.sum()); neg = float(len(ytr) - pos)
    pw = torch.tensor([neg / max(pos, 1)])
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pw)
    best_auc, best_state = -1, None
    n = len(Xtr)
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n)
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            opt.zero_grad()
            loss = lossf(model(Xtr[idx]), ytr[idx])
            loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            pv = torch.sigmoid(model(Xva)).numpy()
        auc = roc_auc_score(yva, pv) if len(np.unique(yva)) > 1 else 0.5
        if auc > best_auc:
            best_auc, best_state = auc, {k: v.clone() for k, v in model.state_dict().items()}
        if verbose:
            print(f"  epoch {ep+1:02d}  val_AUC={auc:.3f}")
    if best_state:
        model.load_state_dict(best_state)
    return best_auc


def pretrain_on_goes(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    g = P.load_pretrain_goes(cfg)
    ch = P.to_channels(g["soft"], g["hard"])
    ch, stats = P.standardize(ch)
    peaks = P.goes_flare_peaks(g)
    X, y = P.make_windows(g["time"].to_numpy(), ch, peaks, W=W, H=H, cadence_s=CADENCE)
    if verbose:
        print(f"GOES pretrain windows: {len(y)}  positives={int(y.sum())}  "
              f"flare peaks={len(peaks)}")
    cut = int(len(X) * 0.85)
    model = TCNNet()
    auc = _train(model, X[:cut], y[:cut], X[cut:], y[cut:], epochs=25, verbose=verbose)
    torch.save({"state": model.state_dict(),
                "stats": (stats[0].tolist(), stats[1].tolist()),
                "goes_holdout_auc": round(float(auc), 3)},
               cfg.paths["models"] / "tcn_pretrained.pt")
    if verbose:
        print(f"GOES pretrain holdout AUC = {auc:.3f}")
    return {"goes_windows": int(len(y)), "goes_positives": int(y.sum()),
            "goes_holdout_auc": round(float(auc), 3)}


def _aditya_channels(cfg):
    """1-minute [time, soft(SoLEXS counts), hard(HEL1OS >20keV)] for Aditya-L1."""
    from .solexs import load_solexs
    from .hel1os import load_hel1os
    s = load_solexs(cfg, verbose=False).set_index("time")["counts"].resample("1min").mean()
    h = load_hel1os(cfg, verbose=False).set_index("time")["hard"].resample("1min").sum()
    df = pd.concat({"soft": s, "hard": h}, axis=1).dropna(subset=["soft"]).reset_index()
    df["hard"] = df["hard"].fillna(0.0)
    return df


def _aditya_windows(cfg, split_q=0.75):
    df = _aditya_channels(cfg)
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv", parse_dates=["peak_time"])
    order = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}
    letter = cat["class_goes"].fillna(cat["class_solexs"]).str[0]
    peaks = np.sort(cat[letter.map(lambda c: order.get(c, 0)) >= 3]["peak_time"]
                    .astype("datetime64[ns]").to_numpy())
    ch_raw = P.to_channels(df["soft"], df["hard"])
    times = df["time"].to_numpy()
    split = pd.Series(times).quantile(split_q)
    # standardize on the training portion only
    train_mask_full = times <= np.datetime64(split)
    _, stats = P.standardize(ch_raw[:, train_mask_full])
    ch, _ = P.standardize(ch_raw, stats)

    span = np.timedelta64(W * CADENCE, "s"); horizon = np.timedelta64(H, "m")
    Xtr, ytr, Xte, yte, te_times = [], [], [], [], []
    for i in range(W, len(times) - 1):
        if times[i] - times[i - W] > span * 1.05:
            continue
        j = np.searchsorted(peaks, times[i], side="right")
        y = 1.0 if (j < len(peaks) and peaks[j] <= times[i] + horizon) else 0.0
        win = ch[:, i - W:i].astype("float32")
        if times[i] <= np.datetime64(split):
            Xtr.append(win); ytr.append(y)
        else:
            Xte.append(win); yte.append(y); te_times.append(times[i])
    return (np.stack(Xtr), np.array(ytr, "float32"),
            np.stack(Xte), np.array(yte, "float32"), np.array(te_times), str(split))


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    pre_path = cfg.paths["models"] / "tcn_pretrained.pt"

    # 1) Pretrain on GOES (reuse cached weights if present).
    if pre_path.exists():
        _blob = torch.load(pre_path, weights_only=False)
        pre = {"goes_holdout_auc": _blob.get("goes_holdout_auc"), "reused": True}
        if verbose:
            print("Using cached GOES-pretrained weights.")
    else:
        pre = pretrain_on_goes(cfg, verbose=verbose)

    # 2) Fine-tune on Aditya-L1 (same chronological test set as other models).
    Xtr, ytr, Xte, yte, te_times, split = _aditya_windows(cfg)
    if verbose:
        print(f"Aditya windows: train={len(ytr)} (pos {int(ytr.sum())}), "
              f"test={len(yte)} (pos {int(yte.sum())})")

    model = TCNNet()
    blob = torch.load(pre_path, weights_only=False)
    model.load_state_dict(blob["state"])
    # carve a small chronological val slice from train for early stopping
    cut = int(len(Xtr) * 0.85)
    _train(model, Xtr[:cut], ytr[:cut], Xtr[cut:], ytr[cut:],
           epochs=20, lr=3e-4, verbose=False)

    model.eval()
    with torch.no_grad():
        pte = torch.sigmoid(model(torch.tensor(Xte))).numpy()
    thr, _ = models.best_threshold(ytr, torch.sigmoid(
        model(torch.tensor(Xtr))).detach().numpy())
    metrics = models.score(yte, pte, thr)

    report = {
        "model": "tcn_transfer",
        "pretrain": pre,
        "horizon_min": H, "window_min": W,
        "split_time": split,
        "n_test": int(len(yte)), "test_positive_rate": round(float(yte.mean()), 3),
        "metrics_test": metrics,
    }
    (cfg.paths["forecasting"] / "tcn_metrics.json").write_text(json.dumps(report, indent=2))
    if verbose:
        print("\n=== TCN (GOES→Aditya transfer) TEST METRICS ===")
        print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
