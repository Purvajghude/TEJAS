"""Fetch SDO/HMI SHARP magnetic-complexity parameters from JSOC.

SHARP (Spaceweather HMI Active Region Patch) keywords are the strongest flare
predictors in the literature — total unsigned flux, current helicity, magnetic
shear, etc. — and they're tiny (numbers, not images).  This is the "magnetogram"
supplement ISRO encouraged.

We pull KEYWORDS only (no image segments), so no email/export registration is
needed — just `pip install drms`.  SHARP is per-active-region every 720 s; we
sample at a coarse cadence and aggregate across active regions into one
magnetic-complexity context series alignable with the X-ray grid.

    python tools/fetch_sharp.py --start 2024-06-01 --end 2026-06-15
    python tools/fetch_sharp.py --start 2024-06-01 --end 2026-06-15 --cadence 6h

Output: data/sharp.csv  (time + per-timestamp max/sum of each SHARP keyword)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# The most predictive, commonly-used SHARP keywords.
KEYS = ["T_REC", "NOAA_AR", "USFLUX", "TOTUSJH", "TOTPOT", "MEANPOT",
        "SAVNCPP", "MEANSHR", "SHRGT45", "R_VALUE", "AREA_ACR"]
AGG = ["USFLUX", "TOTUSJH", "TOTPOT", "MEANPOT", "SAVNCPP", "MEANSHR",
       "SHRGT45", "R_VALUE", "AREA_ACR"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--cadence", default="6h", help="sampling cadence (e.g. 1h, 6h)")
    ap.add_argument("--out", type=Path, default=Path("data/sharp.csv"))
    ap.add_argument("--email", default=None, help="JSOC export email (not needed for keywords)")
    args = ap.parse_args()

    try:
        import drms
    except ImportError:
        print("drms not installed. Run:  pip install drms")
        return 1

    # JSOC times out on multi-year queries, so fetch in monthly chunks (keywords
    # only, cadence-sampled) with a couple of retries each, then concatenate.
    client = drms.Client(email=args.email) if args.email else drms.Client()
    print(f"Fetching hmi.sharp_cea_720s @ {args.cadence}, monthly chunks\n"
          f"  keywords: {', '.join(AGG)}")
    parts, cur, end = [], pd.Timestamp(args.start), pd.Timestamp(args.end)
    while cur < end:
        nxt = min(cur + pd.Timedelta(days=31), end)
        q = (f"hmi.sharp_cea_720s[][{cur:%Y.%m.%d}_00:00:00_TAI-"
             f"{nxt:%Y.%m.%d}_00:00:00_TAI@{args.cadence}]")
        d = None
        for attempt in range(3):
            try:
                d = client.query(q, key=", ".join(KEYS))
                break
            except Exception as ex:
                print(f"  {cur:%Y-%m} retry {attempt+1}/3 ({type(ex).__name__})")
        n = 0 if d is None else len(d)
        if n:
            parts.append(d)
        print(f"  {cur:%Y-%m}: {n} records")
        cur = nxt
    if not parts:
        print("No SHARP records returned (check the date range / JSOC availability).")
        return 1
    df = pd.concat(parts, ignore_index=True)
    print(f"  total {len(df):,} active-region records")

    # Parse time and convert TAI -> UTC.  SHARP T_REC is in TAI, while every other
    # TEJAS series (SoLEXS/HEL1OS/GOES) is UTC; TAI has led UTC by 37 leap seconds
    # since 2017 (no leap seconds added 2024-2026), so UTC = TAI - 37 s.
    TAI_MINUS_UTC_S = 37
    df["time"] = (pd.to_datetime(df["T_REC"].str.replace("_TAI", "", regex=False),
                                 format="%Y.%m.%d_%H:%M:%S", errors="coerce")
                  - pd.Timedelta(seconds=TAI_MINUS_UTC_S))
    df = df.dropna(subset=["time"])
    for k in AGG:
        df[k] = pd.to_numeric(df[k], errors="coerce")

    # Aggregate across active regions per timestamp: the most complex AR drives
    # flare risk -> take the max; also keep the sum (whole-disk magnetic budget).
    g = df.groupby("time")
    out = pd.DataFrame({"time": sorted(df["time"].unique())}).set_index("time")
    for k in AGG:
        out[f"sharp_{k.lower()}_max"] = g[k].max()
        out[f"sharp_{k.lower()}_sum"] = g[k].sum()
    out["sharp_n_ar"] = g["NOAA_AR"].nunique()
    out = out.reset_index()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"\nWrote {len(out):,} timestamps -> {args.out}  "
          f"({out['time'].min()} .. {out['time'].max()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
