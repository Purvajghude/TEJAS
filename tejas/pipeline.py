"""End-to-end nowcasting pipeline.

Runs: load SoLEXS -> detect flares -> cross-calibrate to GOES -> classify ->
validate -> persist everything the dashboard and report need.

Outputs (under ``outputs/``):
  catalogs/solexs_flares.csv     one row per detected flare, with GOES class
  catalogs/validation.json       calibration params, recovery, class agreement
  processed/lightcurve.parquet   10 s annotated light curve + GOES flux overlay
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import Config, load_config
from .solexs import load_solexs, list_days
from .detection import annotate, detect_events
from .goes import load_goes, download_goes, fetch_donki
from .calibrate import (
    align_minute, fit_calibration, attach_goes_truth,
    fit_peak_calibration, apply_classification, validate_recovery,
)


def _resample_lightcurve(annotated: pd.DataFrame, goes: pd.DataFrame,
                         bin_s: int = 10) -> pd.DataFrame:
    """Downsample the 1 s annotated series to ``bin_s`` and overlay GOES flux."""
    a = annotated[["time", "counts", "background", "significance"]].copy()
    a["bin"] = a["time"].dt.floor(f"{bin_s}s")
    g = a.groupby("bin").agg(
        counts=("counts", "mean"),
        background=("background", "mean"),
        significance=("significance", "max"),
    ).reset_index().rename(columns={"bin": "time"})
    g["time"] = g["time"].astype("datetime64[ns]")

    gg = goes[["time", "xrsb", "xrsa"]].dropna(subset=["xrsb"]).sort_values("time").copy()
    gg["time"] = gg["time"].astype("datetime64[ns]")
    out = pd.merge_asof(g.sort_values("time"), gg, on="time",
                        direction="nearest", tolerance=pd.Timedelta("60s"))
    return out


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    (cfg.paths["outputs"] / "processed").mkdir(parents=True, exist_ok=True)

    days = list_days(cfg)
    if verbose:
        print(f"=== TEJAS nowcasting pipeline — {len(days)} SoLEXS days ===")

    # 1. Load + detect ----------------------------------------------------
    sol = load_solexs(cfg, verbose=False)
    ann = annotate(sol, cfg)
    cat = detect_events(ann, cfg)
    if verbose:
        print(f"Detected {len(cat)} flares")

    # 2. GOES + calibration ----------------------------------------------
    download_goes(days, cfg, verbose=False)
    goes = load_goes(cfg, verbose=False)
    minute_cal = fit_calibration(align_minute(sol, goes))
    cat = attach_goes_truth(cat, goes, cfg)
    peak_cal = fit_peak_calibration(cat)
    cat = apply_classification(cat, peak_cal, cfg)

    # 3. Validate ---------------------------------------------------------
    d0, d1 = days[0], days[-1]
    donki = fetch_donki(f"{d0[:4]}-{d0[4:6]}-{d0[6:]}",
                        f"{d1[:4]}-{d1[4:6]}-{d1[6:]}", cfg)
    rec = validate_recovery(cat, donki, cfg.goes["match_window_s"])
    valid = cat.dropna(subset=["flux_goes"])
    letter_agree = float(
        (valid["class_solexs"].str[0] == valid["class_goes"].str[0]).mean()
    )

    # 4. Persist ----------------------------------------------------------
    cat_out = cat.copy()
    for col in ("start_time", "peak_time", "end_time"):
        cat_out[col] = cat_out[col].astype(str)
    cat_path = cfg.paths["catalogs"] / "solexs_flares.csv"
    cat_out.to_csv(cat_path, index=False)

    lc = _resample_lightcurve(ann, goes)
    lc_path = cfg.paths["outputs"] / "processed" / "lightcurve.parquet"
    lc.to_parquet(lc_path, index=False)

    report = {
        "n_days": len(days),
        "date_range": [str(sol["time"].min()), str(sol["time"].max())],
        "n_flares": int(len(cat)),
        "class_counts": cat["class_solexs"].str[0].value_counts().to_dict(),
        "minute_correlation_r": round(minute_cal.r, 3),
        "peak_calibration": {
            "slope": round(peak_cal.slope, 4),
            "intercept": round(peak_cal.intercept, 4),
            "r": round(peak_cal.r, 4),
            "n": peak_cal.n,
        },
        "goes_letter_class_agreement": round(letter_agree, 3),
        "recovery": {
            "n_reference": rec["n_reference"],
            "n_recovered": rec["n_recovered"],
            "recall_overall": round(rec["recall_overall"], 3),
            "by_class": rec["by_class"],
        },
    }
    val_path = cfg.paths["catalogs"] / "validation.json"
    val_path.write_text(json.dumps(report, indent=2))

    if verbose:
        print(f"\nSaved:\n  {cat_path}\n  {lc_path}\n  {val_path}")
        print("\n=== VALIDATION SUMMARY ===")
        print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
