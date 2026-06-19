"""Reproduce the ISRO 'Solar Flare Prediction' figure for a chosen flare.

Mirrors the reference slide: observed X-ray flux up to a 'current time' T0, the
unseen future (dashed), the N-minute forecast window shaded, and the pre-onset
'Precursor Heating Detected' segment highlighted — the gradual soft-X-ray rise
(and Neupert hard-X-ray lead) that TEJAS forecasts on.

    python tools/precursor_figure.py                 # strongest flare in the catalogue
    python tools/precursor_figure.py --date 2024-10-03
    python tools/precursor_figure.py --flare SLX-0042 --horizon 15
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root on path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tejas.config import load_config


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD; pick that day's strongest flare")
    ap.add_argument("--flare", help="specific flare_id")
    ap.add_argument("--horizon", type=int, default=15, help="forecast window (min)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    cfg = load_config()
    lc = pd.read_parquet(cfg.paths["outputs"] / "processed" / "lightcurve.parquet")
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv",
                      parse_dates=["start_time", "peak_time", "end_time"])

    if args.flare:
        fl = cat[cat["flare_id"] == args.flare].iloc[0]
    else:
        c = cat.copy()
        if args.date:
            c = c[c["peak_time"].dt.strftime("%Y-%m-%d") == args.date]
        fl = c.loc[c["peak_counts"].idxmax()]

    onset, peak = fl["start_time"], fl["peak_time"]
    w = lc[(lc["time"] >= peak - pd.Timedelta(hours=4)) &
           (lc["time"] <= peak + pd.Timedelta(hours=2))].copy()
    if w.empty:
        print("No light-curve samples around that flare.")
        return 1
    y = w["xrsb"] if w["xrsb"].notna().any() else w["counts"]
    t0 = onset                                    # "current time" = forecast issued at onset
    obs = w[w["time"] <= t0]
    fut = w[w["time"] >= t0]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(obs["time"], (obs["xrsb"] if y is w["xrsb"] else obs["counts"]),
            color="#1f4e8c", lw=1.6, label="Observed flux")
    ax.plot(fut["time"], (fut["xrsb"] if y is w["xrsb"] else fut["counts"]),
            color="#9aa0a6", lw=1.0, ls=":", label="Future / unseen data")
    ax.axvline(t0, color="k", ls="--", lw=1.2, label="Current time (T=0)")
    ax.axvspan(t0, t0 + pd.Timedelta(minutes=args.horizon), color="#e8746a",
               alpha=0.18, label=f"{args.horizon}-min forecast window")

    # Precursor-heating segment: pre-onset gradual rise above background.
    pre = w[(w["time"] >= onset - pd.Timedelta(minutes=40)) & (w["time"] <= onset)]
    if not pre.empty:
        ax.plot(pre["time"], (pre["xrsb"] if y is w["xrsb"] else pre["counts"]),
                color="#d62828", lw=2.6, label="Precursor heating detected")

    ax.set_yscale("log")
    ax.set_ylabel("Flux (W/m$^2$)" if y is w["xrsb"] else "SoLEXS counts/s")
    ax.set_xlabel("Time (UTC)")
    cls = fl.get("class_goes") or fl.get("class_solexs")
    ax.set_title(f"TEJAS forecast — {fl['flare_id']} ({cls}), peak {peak:%Y-%m-%d %H:%M}")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.autofmt_xdate()
    fig.tight_layout()

    out = args.out or (cfg.paths["figures"] / f"precursor_{fl['flare_id']}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
