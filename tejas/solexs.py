"""SoLEXS (soft X-ray) Level-1 light-curve loader.

The PRADAN packages expand to::

    AL1_SLX_L1_<YYYYMMDD>_v<ver>/.../SDD2/AL1_SOLEXS_<YYYYMMDD>_SDD2_L1.lc.gz

Each ``.lc.gz`` is a gzipped FITS file whose HDU 1 (``RATE``) holds a 1 Hz
``TIME`` (Unix UTC seconds) / ``COUNTS`` table for a full UT day.

This module discovers every day, keeps the highest processing version when a
day is present more than once, reads them, and returns one tidy, time-sorted
:class:`pandas.DataFrame` with columns ``time`` (UTC datetime) and ``counts``.
"""

from __future__ import annotations

import gzip
import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

from .config import Config, load_config

_DATE_VER_RE = re.compile(r"AL1_SLX_L1_(\d{8})_v(\d+)\.(\d+)")


@dataclass(frozen=True)
class DayFile:
    date: str          # YYYYMMDD
    version: tuple     # (major, minor)
    path: Path


def _discover_days(cfg: Config) -> list[DayFile]:
    """Find all SDD light-curve files, keeping the newest version per day."""
    root = cfg.paths["raw_solexs"]
    glob = cfg.solexs["lc_glob"]
    excluded = set(cfg.solexs.get("exclude_dates", []) or [])
    found: dict[str, DayFile] = {}
    for path in root.glob(glob):
        m = _DATE_VER_RE.search(str(path))
        if not m:
            continue
        date = m.group(1)
        if date in excluded:
            continue
        version = (int(m.group(2)), int(m.group(3)))
        prev = found.get(date)
        if prev is None or version > prev.version:
            found[date] = DayFile(date=date, version=version, path=path)
    return sorted(found.values(), key=lambda d: d.date)


def _read_one(day: DayFile, cfg: Config) -> pd.DataFrame:
    """Read a single gzipped FITS light curve into a DataFrame."""
    hdu = cfg.solexs["hdu"]
    tcol = cfg.solexs["time_col"]
    ccol = cfg.solexs["count_col"]
    with gzip.open(day.path, "rb") as gz:
        with fits.open(io.BytesIO(gz.read())) as hdul:
            data = hdul[hdu].data
            time = np.asarray(data[tcol], dtype="float64")
            counts = np.asarray(data[ccol], dtype="float64")
    df = pd.DataFrame({"unix": time, "counts": counts})
    # Drop NaN counts and obviously invalid timestamps.
    df = df[np.isfinite(df["unix"]) & np.isfinite(df["counts"])]
    df["time"] = pd.to_datetime(df["unix"], unit="s", utc=True).dt.tz_convert(None)
    df["date"] = day.date
    return df[["time", "counts", "date"]]


def load_solexs(cfg: Config | None = None, verbose: bool = True) -> pd.DataFrame:
    """Load and concatenate every available SoLEXS day.

    Returns a time-sorted DataFrame with columns ``time`` (UTC, tz-naive),
    ``counts`` (per-second), and ``date`` (source YYYYMMDD).
    """
    cfg = cfg or load_config()
    days = _discover_days(cfg)
    if not days:
        raise FileNotFoundError(
            f"No SoLEXS light curves under {cfg.paths['raw_solexs']} "
            f"matching {cfg.solexs['lc_glob']!r}"
        )
    frames = []
    for day in days:
        df = _read_one(day, cfg)
        frames.append(df)
        if verbose:
            print(f"  loaded {day.date} v{day.version[0]}.{day.version[1]}  "
                  f"rows={len(df):>6}  "
                  f"counts[min/med/max]={df['counts'].min():.0f}/"
                  f"{df['counts'].median():.0f}/{df['counts'].max():.0f}")
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
    if verbose:
        print(f"\nSoLEXS: {len(days)} days, {len(out):,} rows, "
              f"{out['time'].min()} -> {out['time'].max()}")
    return out


def list_days(cfg: Config | None = None) -> list[str]:
    """Return the sorted list of available YYYYMMDD dates."""
    cfg = cfg or load_config()
    return [d.date for d in _discover_days(cfg)]


if __name__ == "__main__":
    df = load_solexs()
    print("\nHead:\n", df.head())
