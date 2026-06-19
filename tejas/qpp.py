"""Quasi-Periodic Pulsation (QPP) detection in HEL1OS hard X-rays.

ISRO called out QPPs explicitly as a fine temporal structure worth detecting:
oscillatory variations during the impulsive phase of a flare, typically with
periods of tens of seconds to a few minutes, strongest at high X-ray energies.

For every hard flare in the catalogue we:
  1. take the HEL1OS hard X-ray light curve over the flare interval,
  2. detrend it (subtract a smooth running mean) to isolate oscillations,
  3. run a Lomb-Scargle periodogram over periods 20-600 s,
  4. flag a QPP when the dominant peak is significant (false-alarm prob < 1%).

Output: outputs/catalogs/qpp_catalog.csv (one row per analysed flare) + a summary.
HEL1OS is binned at 10 s, so the shortest resolvable period is ~20 s (Nyquist).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from astropy.timeseries import LombScargle

from .config import Config, load_config
from .hel1os import load_hel1os

P_MIN_S, P_MAX_S = 30.0, 600.0      # QPP period search range (>~3x the 10s bin)
FAP_THRESHOLD = 0.01                # significance to declare a QPP


def _analyse_flare(t_s: np.ndarray, y: np.ndarray) -> dict | None:
    """Lomb-Scargle QPP test on one detrended flare light curve."""
    if len(y) < 12:                 # need enough cycles to be meaningful
        return None
    # Detrend by removing the smooth flare envelope with a low-order polynomial
    # (a rolling mean would absorb the longer-period oscillations we want to keep).
    deg = min(3, len(y) // 4)
    coef = np.polyfit(t_s, y, deg)
    resid = y - np.polyval(coef, t_s)
    if not np.any(resid) or np.std(resid) == 0:
        return None
    # A credible QPP must complete at least ~3 cycles within the flare, so cap the
    # longest searched period at duration/3.  This rejects both the Nyquist-floor
    # pile-up and residual-trend power masquerading as a very long "period".
    dur = float(t_s[-1] - t_s[0])
    p_max_eff = min(P_MAX_S, dur / 3.0)
    if p_max_eff <= P_MIN_S:
        return None
    fmin, fmax = 1.0 / p_max_eff, 1.0 / P_MIN_S
    ls = LombScargle(t_s, resid)
    freq = np.linspace(fmin, fmax, 2000)
    power = ls.power(freq)
    i = int(np.argmax(power))
    peak_f, peak_p = float(freq[i]), float(power[i])
    try:
        fap = float(ls.false_alarm_probability(peak_p, method="baluev"))
    except Exception:
        fap = float("nan")
    period = 1.0 / peak_f
    return {
        "qpp_period_s": round(period, 1),
        "qpp_power": round(peak_p, 4),
        "qpp_fap": round(fap, 5),
        "qpp_detected": bool(np.isfinite(fap) and fap < FAP_THRESHOLD),
        "n_points": int(len(y)),
    }


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    bin_s = cfg.hel1os["bin_s"]
    hel = load_hel1os(cfg, verbose=False).set_index("time").sort_index()
    chan = "hard" if "hard" in hel.columns else "broad"     # >20 keV preferred
    cat = pd.read_csv(cfg.paths["catalogs"] / "hel1os_flares.csv",
                      parse_dates=["start_time", "peak_time", "end_time"])
    if verbose:
        print(f"QPP scan: {len(cat)} hard flares, channel '{chan}', "
              f"periods {P_MIN_S:.0f}-{P_MAX_S:.0f}s")

    rows = []
    for _, fl in cat.iterrows():
        seg = hel.loc[fl["start_time"]:fl["end_time"], chan]
        if len(seg) < 12:
            continue
        t_s = (seg.index - seg.index[0]).total_seconds().to_numpy()
        res = _analyse_flare(t_s, seg.to_numpy(dtype="float64"))
        if res is None:
            continue
        rows.append({"flare_id": fl["flare_id"],
                     "peak_time": fl["peak_time"],
                     "duration_s": float(fl.get("duration_s", t_s[-1])),
                     **res})

    qpp = pd.DataFrame(rows)
    n_det = int(qpp["qpp_detected"].sum()) if len(qpp) else 0
    periods = qpp[qpp["qpp_detected"]]["qpp_period_s"] if len(qpp) else pd.Series([], dtype=float)
    out = qpp.copy()
    out["peak_time"] = out["peak_time"].astype(str)
    out.to_csv(cfg.paths["catalogs"] / "qpp_catalog.csv", index=False)

    report = {
        "channel": chan, "bin_s": bin_s,
        "period_range_s": [P_MIN_S, P_MAX_S], "fap_threshold": FAP_THRESHOLD,
        "n_flares_analysed": int(len(qpp)),
        "n_qpp_detected": n_det,
        "qpp_fraction": round(n_det / len(qpp), 3) if len(qpp) else None,
        "median_qpp_period_s": round(float(periods.median()), 1) if len(periods) else None,
        "period_range_detected_s": [round(float(periods.min()), 1),
                                    round(float(periods.max()), 1)] if len(periods) else None,
    }
    (cfg.paths["catalogs"] / "qpp_report.json").write_text(json.dumps(report, indent=2))
    if verbose:
        print(f"\nQPP detected in {n_det}/{len(qpp)} flares "
              f"({report['qpp_fraction']}); median period "
              f"{report['median_qpp_period_s']} s")
        print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
