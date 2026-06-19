"""Cross-calibrate SoLEXS counts to GOES flux, classify flares, and validate.

Why this matters: the original pipeline invented a ``WEAK/STRONG`` scale from raw
counts that maps to nothing.  Real solar flares are classified A/B/C/M/X from the
GOES 1-8 A peak flux.  Here we learn an empirical SoLEXS-counts -> GOES-flux
relation, so SoLEXS can assign *real* classes on its own, and we validate that
against GOES ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config, load_config
from .goes import flux_to_class


@dataclass
class Calibration:
    slope: float
    intercept: float
    r: float
    n: int

    def predict_flux(self, counts) -> np.ndarray:
        counts = np.clip(np.asarray(counts, dtype="float64"), 1e-6, None)
        return 10.0 ** (self.intercept + self.slope * np.log10(counts))


def align_minute(solexs: pd.DataFrame, goes: pd.DataFrame) -> pd.DataFrame:
    """Resample SoLEXS counts to 1-minute means and join to GOES on the minute."""
    s = solexs[["time", "counts"]].copy()
    s["minute"] = s["time"].dt.floor("min")
    s = s.groupby("minute", as_index=False)["counts"].mean().rename(
        columns={"minute": "time"})
    return s.merge(goes[["time", "xrsb", "xrsa"]], on="time", how="inner")


def fit_calibration(aligned: pd.DataFrame) -> Calibration:
    """Minute-level log-log correlation of GOES flux vs SoLEXS counts.

    This is an instrument cross-check (does SoLEXS track GOES over all time?),
    reported via the correlation ``r``. Classification uses the peak fit below.
    """
    m = (
        np.isfinite(aligned["counts"]) & (aligned["counts"] > 0)
        & np.isfinite(aligned["xrsb"]) & (aligned["xrsb"] > 0)
    )
    x = np.log10(aligned.loc[m, "counts"].to_numpy())
    y = np.log10(aligned.loc[m, "xrsb"].to_numpy())
    slope, intercept = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1])
    return Calibration(slope=float(slope), intercept=float(intercept), r=r, n=int(m.sum()))


def attach_goes_truth(catalog: pd.DataFrame, goes: pd.DataFrame,
                      cfg: Config | None = None) -> pd.DataFrame:
    """Look up the GOES 1-8 A flux/class at each flare peak (ground truth)."""
    cfg = cfg or load_config()
    classes = cfg.goes["flux_classes"]
    g = goes[["time", "xrsb"]].dropna().sort_values("time").copy()
    g["time"] = g["time"].astype("datetime64[ns]")
    cat = catalog.sort_values("peak_time").copy()
    cat["peak_time"] = cat["peak_time"].astype("datetime64[ns]")
    matched = pd.merge_asof(
        cat, g, left_on="peak_time", right_on="time",
        direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("", "_g"),
    )
    cat["flux_goes"] = matched["xrsb"].to_numpy()
    cat["class_goes"] = [flux_to_class(f, classes) for f in cat["flux_goes"]]
    return cat.reset_index(drop=True)


def fit_peak_calibration(catalog: pd.DataFrame) -> Calibration:
    """Calibrate SoLEXS peak counts -> GOES peak flux using detected flares.

    This is the relation used for classification: it is anchored on the actual
    flare peaks (C through X), so it does not get dragged shallow by the millions
    of quiescent samples the way a whole-mission fit does.
    """
    m = (
        np.isfinite(catalog["peak_counts"]) & (catalog["peak_counts"] > 0)
        & np.isfinite(catalog["flux_goes"]) & (catalog["flux_goes"] > 0)
    )
    x = np.log10(catalog.loc[m, "peak_counts"].to_numpy())
    y = np.log10(catalog.loc[m, "flux_goes"].to_numpy())
    slope, intercept = np.polyfit(x, y, 1)
    r = float(np.corrcoef(x, y)[0, 1])
    return Calibration(slope=float(slope), intercept=float(intercept), r=r, n=int(m.sum()))


def apply_classification(catalog: pd.DataFrame, calib: Calibration,
                         cfg: Config | None = None) -> pd.DataFrame:
    """Add SoLEXS-only predicted flux/class from the peak calibration."""
    cfg = cfg or load_config()
    classes = cfg.goes["flux_classes"]
    cat = catalog.copy()
    cat["flux_pred"] = calib.predict_flux(cat["peak_counts"].to_numpy())
    cat["class_solexs"] = [flux_to_class(f, classes) for f in cat["flux_pred"]]
    return cat


def validate_recovery(catalog: pd.DataFrame, donki: pd.DataFrame,
                      window_s: int = 600) -> dict:
    """How many catalogued GOES (DONKI) flares did SoLEXS recover?"""
    win = pd.Timedelta(seconds=window_s)
    det_peaks = catalog["peak_time"].sort_values().to_numpy()

    def is_recovered(t):
        if len(det_peaks) == 0:
            return False
        idx = np.searchsorted(det_peaks, np.datetime64(t))
        for j in (idx - 1, idx):
            if 0 <= j < len(det_peaks):
                if abs(pd.Timestamp(det_peaks[j]) - t) <= win:
                    return True
        return False

    d = donki.copy()
    d["letter"] = d["goes_class"].str[0]
    d["recovered"] = d["peak"].apply(is_recovered)

    by_class = d.groupby("letter")["recovered"].agg(["sum", "count"]).to_dict("index")
    summary = {
        "n_reference": int(len(d)),
        "n_recovered": int(d["recovered"].sum()),
        "recall_overall": float(d["recovered"].mean()) if len(d) else float("nan"),
        "by_class": {k: (int(v["sum"]), int(v["count"])) for k, v in by_class.items()},
        "matched_table": d,
    }
    return summary


if __name__ == "__main__":
    from .solexs import load_solexs, list_days
    from .detection import annotate, detect_events
    from .goes import load_goes, fetch_donki

    cfg = load_config()
    sol = load_solexs(cfg, verbose=False)
    goes = load_goes(cfg, verbose=False)
    cat = detect_events(annotate(sol, cfg), cfg)

    aligned = align_minute(sol, goes)
    mcal = fit_calibration(aligned)
    print(f"Minute-level cross-correlation (SoLEXS vs GOES): r={mcal.r:.3f}  n={mcal.n:,}")

    cat = attach_goes_truth(cat, goes, cfg)
    calib = fit_peak_calibration(cat)
    print(f"Peak calibration: log10(flux) = {calib.intercept:.3f} + "
          f"{calib.slope:.3f}*log10(counts)   r={calib.r:.3f}  n={calib.n}")
    cat = apply_classification(cat, calib, cfg)
    days = list_days(cfg)
    donki = fetch_donki(f"{days[0][:4]}-{days[0][4:6]}-{days[0][6:]}",
                        f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}", cfg)
    rec = validate_recovery(cat, donki)
    print(f"\nRecovery of DONKI flares: {rec['n_recovered']}/{rec['n_reference']} "
          f"({rec['recall_overall']*100:.0f}%)")
    print("By class (recovered/total):", rec["by_class"])

    # Class-agreement between SoLEXS-predicted and GOES-truth (letter level).
    ok = cat.dropna(subset=["flux_goes"])
    agree = (ok["class_solexs"].str[0] == ok["class_goes"].str[0]).mean()
    print(f"\nSoLEXS vs GOES letter-class agreement: {agree*100:.0f}% (n={len(ok)})")
    print("\nStrongest flares:")
    cols = ["peak_time", "peak_counts", "class_solexs", "class_goes", "peak_significance"]
    print(cat.sort_values("peak_counts", ascending=False).head(12)[cols].to_string(index=False))
