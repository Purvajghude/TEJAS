"""Benchmark TEJAS against standard baselines and published literature.

Computes — on the SAME test set, same ground truth:
  (a) TEJAS multiclass M+ model  (from eval/test_predictions.parquet)
  (b) TEJAS ensemble M+          (metrics from eval/ensemble_metrics.json)
  (c) Persistence model           (M+ occurred in last 30 min → alert)
  (d) Climatological baseline     (constant base-rate → TSS = 0)

Then prints a literature-context table (DIFFERENT horizon / inputs — flagged).

Usage:
    python tools/benchmark.py          # full (needs outputs/catalogs/solexs_flares.csv)
    python main.py benchmark

Output: eval/benchmark.json  +  formatted console table.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

REPO = Path(__file__).resolve().parent.parent
HORIZON_MIN = 30

# ---------------------------------------------------------------------------
# Literature reference table.  ALL entries are from peer-reviewed publications
# using DIFFERENT horizons and/or inputs than ours — stated explicitly.
# DO NOT interpret this as a direct performance comparison.
# ---------------------------------------------------------------------------
LITERATURE = [
    {
        "system": "NOAA SWPC operational",
        "reference": "Crown (2012), Space Weather 10",
        "horizon": "24 h",
        "inputs": "Human+magnetogram",
        "tss": 0.39,
        "auc": None,
        "note": "Evaluated on 2000-2010 GOES events; operational expert forecast",
    },
    {
        "system": "Bobra & Couvidat SVM",
        "reference": "Bobra & Couvidat (2015), ApJ 798",
        "horizon": "24 h",
        "inputs": "SDO/HMI SHARP",
        "tss": 0.769,
        "auc": None,
        "note": "SVM on SHARP vector magnetogram parameters; M+X class ≥24 h",
    },
    {
        "system": "DeFN (deep CNN)",
        "reference": "Nishizuka et al. (2018), ApJ 858",
        "horizon": "24 h",
        "inputs": "SDO/HMI image + SHARP",
        "tss": 0.80,
        "auc": None,
        "note": "Deep Flare Net; best M+ result in original paper",
    },
    {
        "system": "FLARECAST ensemble (best)",
        "reference": "Leka et al. (2019), ApJS 243",
        "horizon": "24 h",
        "inputs": "SHARP features",
        "tss": 0.55,
        "auc": None,
        "note": "Best single method in 7-algorithm comparison; M+ class",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tss_at_best_thr(y, p):
    """TSS at the threshold that maximises TSS (same as our model convention)."""
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y, p)
    best = np.argmax(tpr - fpr)
    return float(tpr[best] - fpr[best])


def _score(y, p, label="model"):
    if len(np.unique(y)) < 2:
        return {"label": label, "tss": None, "auc": None, "brier": None,
                "n_pos": int(y.sum()), "note": "single class — not computable"}
    auc = float(roc_auc_score(y, p))
    tss = _tss_at_best_thr(y, p)
    brier = float(brier_score_loss(y, p))
    return {"label": label, "tss": round(tss, 3), "auc": round(auc, 3),
            "brier": round(brier, 4), "n_pos": int(y.sum())}


def _persistence_probs(df: pd.DataFrame, peaks: np.ndarray | None,
                       horizon_min: int = HORIZON_MIN) -> np.ndarray:
    """Binary persistence: 1 if any M+ peak occurred in the last `horizon_min` min.

    If actual peak times are provided (from the flare catalog), uses them for
    an exact computation.  Otherwise falls back to a label-based approximation
    (assumes each y=1 run corresponds to an imminent flare).
    """
    times = df["time"].to_numpy()
    delta = np.timedelta64(horizon_min, "m")

    if peaks is not None and len(peaks) > 0:
        # Vectorised: for each test minute t, check if any peak in (t-delta, t].
        # searchsorted gives the first peak > t-delta; check if it's <= t.
        pk = np.sort(peaks)
        lo = np.searchsorted(pk, times - delta, side="right")
        hi_idx = np.searchsorted(pk, times, side="right")
        persist = (lo < hi_idx).astype(float)
    else:
        # Fallback: treat previous positive label as a proxy for a past flare.
        # Shift the y_M column forward by horizon_min rows (≈ horizon_min minutes
        # since 1 row ≈ 1 minute after resampling to minute grid).
        y = df["y_M"].to_numpy(dtype=float)
        # Rolling max over past window — any positive in last horizon_min rows.
        s = pd.Series(y, index=pd.to_datetime(times))
        persist = (s.rolling(f"{horizon_min}min", closed="left").max()
                   .fillna(0).to_numpy())
    return persist


def _climatological_prob(y: np.ndarray) -> np.ndarray:
    """Constant probability = training base rate; TSS = 0 by construction."""
    return np.full(len(y), float(y.mean()))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(verbose: bool = True) -> dict:
    pq = REPO / "eval" / "test_predictions.parquet"
    if not pq.exists():
        raise FileNotFoundError(
            f"Missing {pq}.\n"
            "Generate with tools/build_eval_bundle.py on a machine with Aditya-L1 data."
        )
    df = pd.read_parquet(pq)

    # Actual M+ flare peak times in the test period (for exact persistence model).
    cat_path = REPO / "outputs" / "catalogs" / "solexs_flares.csv"
    peaks_M = None
    if cat_path.exists():
        cat = pd.read_csv(cat_path, parse_dates=["peak_time"])
        order = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}
        letter = cat["class_goes"].fillna(cat["class_solexs"]).str[0]
        cat_M = cat[letter.map(lambda c: order.get(c, 0)) >= 3]
        test_lo = df["time"].min()
        test_hi = df["time"].max()
        in_test = (cat_M["peak_time"] >= test_lo) & (cat_M["peak_time"] <= test_hi)
        peaks_M = cat_M.loc[in_test, "peak_time"].to_numpy()

    y = df["y_M"].to_numpy()
    p_tejas = df["p_M"].to_numpy()      # multiclass M+ probabilities
    p_persist = _persistence_probs(df, peaks_M)
    p_climo = _climatological_prob(y)

    # Load ensemble metrics (from committed eval/ JSON — no raw data needed).
    ens_path = REPO / "eval" / "ensemble_metrics.json"
    ens_report = json.loads(ens_path.read_text()) if ens_path.exists() else {}
    ens_m = ens_report.get("test_metrics", {}).get("ensemble", {})

    rows = [
        _score(y, p_tejas, "TEJAS multiclass M+ (LightGBM, 30 min)"),
        {
            "label": "TEJAS ensemble M+ (TCN+LGBM, 30 min)",
            "tss": ens_m.get("TSS"),
            "auc": ens_m.get("ROC_AUC"),
            "brier": ens_m.get("Brier"),
            "n_pos": None,
            "note": "From ensemble_metrics.json — TCN+LightGBM stacked meta-learner",
        },
        _score(y, p_persist, f"Persistence ({HORIZON_MIN}-min, same test set)"),
        {**_score(y, p_climo, "Climatological (base-rate)"),
         "note": "TSS=0 by construction; non-trivial AUC from base-rate averaging"},
    ]

    if verbose:
        _print_table(rows, peaks_M)

    result = {
        "horizon_min": HORIZON_MIN,
        "test_n": int(len(df)),
        "test_n_pos_M": int(y.sum()),
        "base_rate_M": round(float(y.mean()), 5),
        "catalog_available": peaks_M is not None,
        "baselines": rows,
        "literature": LITERATURE,
        "literature_caveat": (
            "All literature entries use 24-hour forecast horizons and SDO/HMI "
            "magnetogram inputs. TEJAS uses 30-minute horizons and real-time "
            "Aditya-L1 X-ray data. These are DIFFERENT TASKS — not directly "
            "comparable. The table is provided for calibration context only."
        ),
    }

    out = REPO / "eval" / "benchmark.json"
    out.write_text(json.dumps(result, indent=2))
    if verbose:
        print(f"\nSaved → {out}")
    return result


def _print_table(rows: list[dict], peaks_M) -> None:
    divider = "-" * 80
    print("\n" + "=" * 80)
    print("  TEJAS — BASELINE COMPARISON  (same test set, same ground truth)")
    print("  Horizon: 30 min  |  Target: M+ class  |  Eval: Jan–Jun 2026")
    print("=" * 80)
    print(f"{'Model / Baseline':<42} {'TSS':>6} {'AUC':>6} {'Brier':>7}")
    print(divider)
    for r in rows:
        tss_s = f"{r['tss']:.3f}" if r.get("tss") is not None else "  n/a"
        auc_s = f"{r['auc']:.3f}" if r.get("auc") is not None else "  n/a"
        brier_s = f"{r['brier']:.4f}" if r.get("brier") is not None else "    n/a"
        print(f"  {r['label']:<40} {tss_s:>6} {auc_s:>6} {brier_s:>7}")
    print(divider)
    print(f"  * Persistence uses {'actual flare catalog' if peaks_M is not None else 'label-based approximation'}")
    print()
    print("  LITERATURE CONTEXT  (** DIFFERENT horizon/inputs -- see caveat)")
    print(divider)
    print(f"  {'System':<32} {'Horizon':>8} {'Inputs':<18} {'TSS':>6}")
    print(divider)
    for L in LITERATURE:
        tss_s = f"{L['tss']:.3f}" if L.get("tss") is not None else "  n/a"
        print(f"  {L['system']:<32} {L['horizon']:>8} {L['inputs']:<18} {tss_s:>6}")
    print(divider)
    print(
        "\n  **  All literature entries: 24-hour horizon, SDO/HMI magnetogram input.\n"
        "  Our TSS at 30-min X-ray-only is context-dependent: we operate at a\n"
        "  shorter horizon (easier) but with radiative data only (harder to beat\n"
        "  magnetogram-based systems that see the magnetic cause, not the effect).\n"
        "  The persistence comparison (same horizon, same data) is the fair one.\n"
    )
    print("=" * 80)


if __name__ == "__main__":
    run()
