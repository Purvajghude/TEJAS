"""Soft + hard X-ray fusion — the combined SoLEXS x HEL1OS master catalogue.

Three things happen here:

1. **Independent hard X-ray detection** — the same sliding-background + Poisson
   detector, run on the HEL1OS 1.8-90 keV broadband.
2. **Neupert-effect coupling** — the nonthermal hard X-ray (30-60 keV) impulsive
   phase peaks *before* the soft X-ray peak (median ~8 min in this campaign), so
   the hard channel is a genuine *precursor*.  We measure the lead per event.
3. **Dual-channel master catalogue** — soft and hard events are matched in time.
   A flare confirmed in *both* channels is the highest-confidence detection
   (a natural false-alarm filter); the hard channel also tags which flares are
   energetic enough to accelerate nonthermal particles.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import Config, load_config
from .detection import annotate, detect_events
from .hel1os import load_hel1os


def detect_hard(hel: pd.DataFrame, cfg: Config | None = None) -> pd.DataFrame:
    """Detect hard X-ray flares on the HEL1OS 1.8-90 keV broadband."""
    cfg = cfg or load_config()
    bin_s = cfg.hel1os["bin_s"]
    ann = annotate(hel, cfg, count_col="broad", cadence_s=bin_s)
    cat = detect_events(ann, cfg, count_col="broad", cadence_s=bin_s,
                        id_prefix="HLS", payload="HEL1OS")
    return cat


def _nonthermal_lead(hel_idx: pd.DataFrame, soft_peak: pd.Timestamp,
                     pre_min: int = 20, post_min: int = 10,
                     min_counts: float = 20.0):
    """Lead (s) of the nonthermal (30-60 keV) peak over the soft peak."""
    w = hel_idx.loc[soft_peak - pd.Timedelta(minutes=pre_min):
                    soft_peak + pd.Timedelta(minutes=post_min)]
    if len(w) == 0:
        return np.nan, np.nan
    nonth = w.get("b_30_40", 0) + w.get("b_40_60", 0)
    if nonth.max() < min_counts:
        return np.nan, float(nonth.max())
    npk = nonth.idxmax()
    return (soft_peak - npk).total_seconds(), float(nonth.max())


def build_master(soft_cat: pd.DataFrame, hard_cat: pd.DataFrame, hel: pd.DataFrame,
                 cfg: Config | None = None) -> tuple[pd.DataFrame, dict]:
    """Match soft & hard events and build the master catalogue + fusion report."""
    cfg = cfg or load_config()
    window = pd.Timedelta(seconds=cfg.goes["match_window_s"])
    hel_idx = hel.set_index("time").sort_index()

    soft = soft_cat.copy()
    soft["peak_time"] = pd.to_datetime(soft["peak_time"])
    hard = hard_cat.copy()
    if not hard.empty:
        hard["peak_time"] = pd.to_datetime(hard["peak_time"])
    hard_peaks = hard["peak_time"].to_numpy() if not hard.empty else np.array([])

    rows = []
    used_hard = set()
    for i, s in soft.iterrows():
        sp = s["peak_time"]
        # nearest hard event within the match window
        hid, hpk, hcounts, hsig = None, pd.NaT, np.nan, np.nan
        if len(hard_peaks):
            j = int(np.argmin(np.abs(hard_peaks - np.datetime64(sp))))
            if abs(pd.Timestamp(hard_peaks[j]) - sp) <= window:
                hid = hard.iloc[j]["flare_id"]
                hpk = hard.iloc[j]["peak_time"]
                hcounts = float(hard.iloc[j]["peak_counts"])
                hsig = float(hard.iloc[j]["peak_significance"])
                used_hard.add(hid)
        lead, nonth_pk = _nonthermal_lead(hel_idx, sp)
        # hardness at the soft peak (nearest HEL1OS bin)
        try:
            hr = float(hel_idx["hr"].asof(sp))
        except Exception:
            hr = np.nan
        rows.append({
            "event_id": f"EVT-{len(rows)+1:04d}",
            "soft_id": s["flare_id"],
            "soft_peak": sp,
            "class_solexs": s.get("class_solexs"),
            "class_goes": s.get("class_goes"),
            "soft_peak_counts": float(s["peak_counts"]),
            "soft_sig": float(s["peak_significance"]),
            "hard_id": hid,
            "hard_peak": hpk,
            "hard_peak_counts": hcounts,
            "hard_sig": hsig,
            "coincidence": hid is not None,
            "neupert_lead_s": lead,
            "nonthermal_peak_counts": nonth_pk,
            "hardness_ratio": hr,
            "confidence": "DUAL-CONFIRMED" if hid is not None else "SOFT-ONLY",
        })

    # hard-only events (detected in hard X-ray, no soft match)
    for _, h in hard.iterrows():
        if h["flare_id"] in used_hard:
            continue
        rows.append({
            "event_id": f"EVT-{len(rows)+1:04d}",
            "soft_id": None, "soft_peak": pd.NaT,
            "class_solexs": None, "class_goes": None,
            "soft_peak_counts": np.nan, "soft_sig": np.nan,
            "hard_id": h["flare_id"], "hard_peak": h["peak_time"],
            "hard_peak_counts": float(h["peak_counts"]),
            "hard_sig": float(h["peak_significance"]),
            "coincidence": False, "neupert_lead_s": np.nan,
            "nonthermal_peak_counts": np.nan, "hardness_ratio": np.nan,
            "confidence": "HARD-ONLY",
        })

    master = pd.DataFrame(rows)

    # ---- fusion report ----
    soft_letters = soft["class_solexs"].str[0]
    confirmed = master[master["coincidence"]]
    leads = master["neupert_lead_s"].dropna()
    leads = leads[leads > 0]  # Neupert-consistent (hard precedes soft)
    by_class = {}
    for L in ["C", "M", "X"]:
        tot = int((soft_letters == L).sum())
        conf = int(confirmed["class_solexs"].str[0].eq(L).sum())
        by_class[L] = [conf, tot]

    report = {
        "n_soft": int(len(soft)),
        "n_hard": int(len(hard)),
        "n_master": int(len(master)),
        "n_dual_confirmed": int(len(confirmed)),
        "dual_confirm_by_class": by_class,
        "neupert": {
            "n_with_lead": int(len(leads)),
            "median_lead_s": round(float(leads.median()), 1) if len(leads) else None,
            "mean_lead_s": round(float(leads.mean()), 1) if len(leads) else None,
        },
    }
    return master, report


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    (cfg.paths["fusion"]).mkdir(parents=True, exist_ok=True)

    soft = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv")
    hel = load_hel1os(cfg, verbose=False)
    hard = detect_hard(hel, cfg)
    if verbose:
        print(f"Hard X-ray flares detected: {len(hard)}")

    master, report = build_master(soft, hard, hel, cfg)

    # persist
    hard_out = hard.copy()
    for c in ("start_time", "peak_time", "end_time"):
        hard_out[c] = hard_out[c].astype(str)
    hard_out.to_csv(cfg.paths["catalogs"] / "hel1os_flares.csv", index=False)
    m_out = master.copy()
    for c in ("soft_peak", "hard_peak"):
        m_out[c] = m_out[c].astype(str)
    m_out.to_csv(cfg.paths["fusion"] / "master_catalog.csv", index=False)
    (cfg.paths["fusion"] / "fusion_report.json").write_text(json.dumps(report, indent=2))

    # Downsampled hard X-ray light curve for the dashboard (aligns with soft LC).
    proc = cfg.paths["outputs"] / "processed"
    proc.mkdir(parents=True, exist_ok=True)
    hl = hel.set_index("time")
    lc = pd.DataFrame({
        "broad": hl["broad"].resample("10s").sum(),
        "hard": hl["hard"].resample("10s").sum(),
        "hr": hl["hr"].resample("10s").mean(),
    }).reset_index()
    lc.to_parquet(proc / "hel1os_lightcurve.parquet", index=False)

    if verbose:
        print("\n=== FUSION REPORT ===")
        print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
