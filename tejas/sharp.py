"""SDO/HMI SHARP magnetic-complexity features — the encouraged magnetogram supplement.

X-ray instruments see the flare's *radiative onset*; photospheric magnetic complexity
(SHARP) is the *cause* and is the strongest predictor in the flare-forecasting
literature.  This module folds SHARP into the X-ray forecaster and runs a clean
ablation — X-ray-only vs X-ray+SHARP — to measure whether the magnetogram channel
adds genuine forecasting skill.

SHARP is sampled at 6 h and forward-filled onto the 1-minute grid (magnetic
complexity evolves over hours-days).  T_REC is TAI (~37 s vs UTC) — negligible here.
Run `python tools/fetch_sharp.py ...` first to create data/sharp.csv.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import Config, load_config
from . import forecast as F
from . import models

CLASS_ORDER = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}

# Max-aggregated complexity drivers (the most complex AR dominates flare risk).
SHARP_KEYS = ["sharp_usflux_max", "sharp_totusjh_max", "sharp_totpot_max",
              "sharp_savncpp_max", "sharp_meanshr_max", "sharp_r_value_max",
              "sharp_area_acr_max", "sharp_n_ar"]
# Missing SHARP is kept NaN (LightGBM treats it as missing, not as a low value);
# a binary flag tells the model when magnetogram context is actually present.
SHARP_FEATURES = SHARP_KEYS + ["sharp_available"]


def load_sharp(path: str | Path = "data/sharp.csv") -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Fetch it first:\n"
            f"  python tools/fetch_sharp.py --start 2024-06-01 --end 2026-06-15")
    return pd.read_csv(p, parse_dates=["time"])


def merge_sharp(m: pd.DataFrame, sharp: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill the 6 h SHARP series onto the 1-min panel (backward as-of).

    Uncovered samples keep NaN (LightGBM-native missing); ``sharp_available`` flags
    where real magnetogram context exists.  A 12 h tolerance bounds the forward-fill.
    """
    cols = ["time"] + [c for c in SHARP_KEYS if c in sharp.columns]
    s = sharp[cols].sort_values("time").copy()
    s["time"] = s["time"].astype("datetime64[ns]")
    mm = m.sort_values("time").copy()
    mm["time"] = mm["time"].astype("datetime64[ns]")
    out = pd.merge_asof(mm, s, on="time",
                        direction="backward", tolerance=pd.Timedelta("12h"))
    present = [c for c in SHARP_KEYS if c in out.columns]
    out["sharp_available"] = out[present[0]].notna().astype(int) if present else 0
    return out.reset_index(drop=True)


def validate(cfg: Config, sharp: pd.DataFrame) -> dict:
    """Sanity-check timeline alignment + accuracy: magnetic complexity should be
    elevated in the hours *before* M+ flares versus the quiet-Sun baseline.  If the
    timeline were misaligned (or the data wrong), this signal would vanish."""
    key = "sharp_totusjh_max"
    s = sharp.dropna(subset=[key]).sort_values("time")
    base = float(s[key].median())
    sidx = s.set_index("time")[key]
    peaks = _peaks(cfg, "M")
    peaks = peaks[(peaks >= s["time"].min()) & (peaks <= s["time"].max())]
    vals = []
    for p in peaks:
        v = sidx.asof(p - pd.Timedelta(hours=6))     # complexity 6 h before onset
        if pd.notna(v):
            vals.append(float(v))
    vals = pd.Series(vals)
    return {
        "quiet_median_totusjh": round(base, 1),
        "n_mplus_checked": int(len(vals)),
        "median_totusjh_6h_pre_mplus": round(float(vals.median()), 1) if len(vals) else None,
        "fraction_above_quiet_median": round(float((vals > base).mean()), 3) if len(vals) else None,
        "elevation_ratio": round(float(vals.median() / base), 2) if len(vals) and base else None,
    }


def _peaks(cfg: Config, letter: str) -> pd.Series:
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv",
                      parse_dates=["peak_time"])
    cut = CLASS_ORDER[letter]
    L = cat["class_goes"].fillna(cat["class_solexs"]).str[0]
    return cat[L.map(lambda c: CLASS_ORDER.get(c, 0)) >= cut][
        "peak_time"].astype("datetime64[ns]")


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    primary = cfg.forecast.get("primary_horizon_min", 30)
    test_frac = cfg.forecast["test_fraction"]
    xray = F.FEATURES + F.HARD_FEATURES

    # Same leak-free panel as the rest of TEJAS.
    m = F.minute_series(cfg)
    m = F.make_features(m)
    m = F.add_time_since_flare(m, _peaks(cfg, "C"))
    hard = F.hel1os_minute_features(cfg)
    m = m.merge(hard[["time"] + F.HARD_FEATURES], on="time", how="left")
    m[F.HARD_FEATURES] = m[F.HARD_FEATURES].fillna(0.0)
    m = m.dropna(subset=F.FEATURES).reset_index(drop=True)
    st, en = F.flare_intervals(cfg)
    m = m[~F.in_flare_mask(m["time"].to_numpy(), st, en)].reset_index(drop=True)

    sharp = load_sharp()
    m = merge_sharp(m, sharp)
    cov = float(m["sharp_available"].mean())
    valid = validate(cfg, sharp)
    if verbose:
        print(f"SHARP merged: {cov*100:.0f}% coverage (starts {sharp['time'].min().date()})")
        print(f"Timeline/accuracy check: TOTUSJH 6h pre-M+ = "
              f"{valid['median_totusjh_6h_pre_mplus']} vs quiet {valid['quiet_median_totusjh']} "
              f"({valid['elevation_ratio']}x, {valid['fraction_above_quiet_median']} above baseline)")

    split = m["time"].quantile(1 - test_frac)
    peaksM = _peaks(cfg, "M")
    m["target"] = F.make_labels(m, peaksM, primary)
    tr, te = m[m["time"] <= split], m[m["time"] > split]

    keep = ["ROC_AUC", "PR_AUC", "TSS", "precision", "Brier"]
    variants = {"xray_only": xray, "xray_plus_sharp": xray + SHARP_FEATURES}
    out = {}
    for name, feats in variants.items():
        r = models.fit_eval("lgbm", tr, te, feats)
        lead = F.lead_times(te, r["prob_test"], peaksM, r["thr"], primary)
        ev = F.event_skill(te["time"].to_numpy(), r["prob_test"], peaksM, r["thr"], primary)
        out[name] = {"metrics": {k: r["metrics"][k] for k in keep},
                     "event_recall": lead["event_recall"],
                     "median_lead_min": lead["median_lead_min"],
                     "false_alarms_per_day": ev.get("false_alarms_per_day")}

    a, b = out["xray_only"]["metrics"], out["xray_plus_sharp"]["metrics"]
    benefit = {k: round((b[k] or 0) - (a[k] or 0), 4) for k in ("ROC_AUC", "PR_AUC", "TSS")}

    # Which SHARP features mattered (importance in the combined model).
    imp = F._importances("lgbm", tr, xray + SHARP_FEATURES)
    sharp_imp = [d for d in imp if d["feature"] in SHARP_FEATURES]

    report = {
        "target": "M+ flares", "primary_horizon_min": primary,
        "sharp_coverage_frac": round(cov, 3),
        "timeline_validation": valid,
        "split_time": str(split),
        "xray_only": out["xray_only"], "xray_plus_sharp": out["xray_plus_sharp"],
        "sharp_benefit": benefit,
        "top_sharp_features": sharp_imp[:5],
    }
    (cfg.paths["forecasting"] / "sharp_ablation.json").write_text(json.dumps(report, indent=2))
    if verbose:
        print("\n=== SHARP ABLATION (M+ @ %d min, untouched test) ===" % primary)
        print(f"{'variant':>16} {'AUC':>6} {'PR-AUC':>7} {'TSS':>6} {'recall':>7} {'lead':>6}")
        for n in ("xray_only", "xray_plus_sharp"):
            mt, o = out[n]["metrics"], out[n]
            print(f"{n:>16} {mt['ROC_AUC']!s:>6} {mt['PR_AUC']!s:>7} {mt['TSS']!s:>6} "
                  f"{o['event_recall']!s:>7} {o['median_lead_min']!s:>6}")
        print(f"\nSHARP benefit: AUC {benefit['ROC_AUC']:+}, PR-AUC {benefit['PR_AUC']:+}, "
              f"TSS {benefit['TSS']:+}")
        if sharp_imp:
            print("top SHARP features:", ", ".join(d["feature"] for d in sharp_imp[:3]))
    return report


if __name__ == "__main__":
    run()
