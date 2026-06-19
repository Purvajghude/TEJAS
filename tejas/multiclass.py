"""Multi-class flare forecasting — ISRO Forecasting Milestone 2.

Milestone 1 (single probability "is a flare coming?") is the binary M+ model in
forecast.py / ensemble.py.  Milestone 2 asks for *class-resolved* probabilities:

    P(C-class+ in next N min)   "low"
    P(M-class+ in next N min)   "medium"
    P(X-class+ in next N min)   "high"

We implement this as three calibrated classifiers on cumulative thresholds (C+, M+,
X+), sharing the exact same leak-free pipeline as the rest of TEJAS:

  * causal soft+hard precursor features (forecast.FEATURES + HARD_FEATURES)
  * in-flare samples excluded (genuine pre-onset forecasting, not nowcasting)
  * chronological train/test split, time-aware isotonic calibration
  * per-class skill: ROC-AUC, PR-AUC, event recall, false alarms/day, median lead

Cumulative thresholds (P(>=C) >= P(>=M) >= P(>=X)) are the operationally natural
form: an operator reads "70% chance of at least M, 12% chance of X in 30 min".
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import Config, load_config
from . import forecast as F
from . import models

CLASS_ORDER = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}
TARGETS = ["C", "M", "X"]           # cumulative: C+ (low), M+ (medium), X+ (high)
LABELS = {"C": "low (C+)", "M": "medium (M+)", "X": "high (X+)"}


def _class_peaks(cfg: Config, letter: str) -> pd.Series:
    """Peak times of flares of GOES class >= ``letter``."""
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv",
                      parse_dates=["peak_time"])
    cutoff = CLASS_ORDER[letter]
    L = cat["class_goes"].fillna(cat["class_solexs"]).str[0]
    return cat[L.map(lambda c: CLASS_ORDER.get(c, 0)) >= cutoff][
        "peak_time"].astype("datetime64[ns]")


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    primary = cfg.forecast.get("primary_horizon_min", 30)
    test_frac = cfg.forecast["test_fraction"]
    feats = F.FEATURES + F.HARD_FEATURES

    # Build the shared leak-free panel once (same as the binary forecaster).
    m = F.minute_series(cfg)
    m = F.make_features(m)
    m = F.add_time_since_flare(m, _class_peaks(cfg, "C"))   # time-since-any-flare
    hard = F.hel1os_minute_features(cfg)
    m = m.merge(hard[["time"] + F.HARD_FEATURES], on="time", how="left")
    m[F.HARD_FEATURES] = m[F.HARD_FEATURES].fillna(0.0)
    m = m.dropna(subset=F.FEATURES).reset_index(drop=True)
    st, en = F.flare_intervals(cfg)
    m = m[~F.in_flare_mask(m["time"].to_numpy(), st, en)].reset_index(drop=True)
    split = m["time"].quantile(1 - test_frac)
    if verbose:
        print(f"Multi-class @ {primary} min | {len(m):,} quiescent samples | "
              f"test after {split.date()}")

    keep = ["ROC_AUC", "PR_AUC", "TSS", "precision", "TPR_recall", "Brier"]
    per_class, prob_cols = {}, {}
    for letter in TARGETS:
        peaks = _class_peaks(cfg, letter)
        m["target"] = F.make_labels(m, peaks, primary)
        tr, te = m[m["time"] <= split], m[m["time"] > split]
        if tr["target"].nunique() < 2 or te["target"].nunique() < 2:
            if verbose:
                print(f"  {letter}+: too few events, skipped")
            continue
        r = models.fit_eval("lgbm", tr, te, feats)
        thr = r["thr"]
        lead = F.lead_times(te, r["prob_test"], peaks, thr, primary)
        ev = F.event_skill(te["time"].to_numpy(), r["prob_test"], peaks, thr, primary)
        per_class[letter] = {
            "label": LABELS[letter],
            "n_target_peaks": int(len(peaks)),
            "metrics": {k: r["metrics"][k] for k in keep},
            "threshold": round(thr, 4),
            "event_recall": lead["event_recall"],
            "median_lead_min": lead["median_lead_min"],
            "false_alarms_per_day": ev.get("false_alarms_per_day"),
        }
        prob_cols[f"p_{letter}"] = r["prob_test"]
        if verbose:
            mt = per_class[letter]["metrics"]
            print(f"  {letter}+ ({LABELS[letter]:>11}): AUC {mt['ROC_AUC']}  "
                  f"PR-AUC {mt['PR_AUC']}  recall {lead['event_recall']}  "
                  f"lead {lead['median_lead_min']}m  FA/day {ev.get('false_alarms_per_day')}")

    # Save aligned class-probability series over the test set for the dashboard.
    te_times = m[m["time"] > split]["time"].reset_index(drop=True)
    prob_df = pd.DataFrame({"time": te_times})
    for c, v in prob_cols.items():
        prob_df[c] = v
    prob_df.to_parquet(cfg.paths["forecasting"] / "multiclass_probability.parquet",
                       index=False)

    report = {
        "milestone": "Forecasting M2 — multi-class (low/medium/high) probabilities",
        "primary_horizon_min": primary,
        "split_time": str(split),
        "classes": per_class,
    }
    (cfg.paths["forecasting"] / "multiclass_metrics.json").write_text(
        json.dumps(report, indent=2))
    if verbose:
        print(f"\nSaved multiclass_metrics.json + multiclass_probability.parquet")
    return report


if __name__ == "__main__":
    run()
