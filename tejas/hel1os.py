"""HEL1OS (hard X-ray) Level-1 light-curve loader.

Each PRADAN package expands to ``HLS_<date>_<hhmmss>_<dur>sec_lev1_V<ver>`` and
contains, per CdTe detector, a ``lightcurve_cdteN.fits`` whose HDUs are the five
energy bands:

    HDU1  5-20 keV     HDU2 20-30 keV     HDU3 30-40 keV
    HDU4 40-60 keV     HDU5 1.8-90 keV (broadband)

Columns per band: ``MJD``, ``ISOT``, ``CTR`` (counts per ~1 s bin), ``STAT_ERR``
(Poisson error, already provided).  Data arrive as two ~12 h chunks per UT day.

This loader discovers all chunks, keeps the highest processing version per
(date, half-day), bins the irregular ~1 s samples onto a regular grid, sums the
two CdTe detectors, and returns one tidy multi-band hard X-ray series with a
hardness ratio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

from .config import Config, load_config

_MJD_EPOCH = pd.Timestamp("1858-11-17")
_CHUNK_RE = re.compile(r"HLS_(\d{8})_(\d{2})\d{4}_\d+sec_lev1_V(\d+)")


@dataclass(frozen=True)
class Chunk:
    date: str       # YYYYMMDD
    half: int       # 0 = AM, 1 = PM
    version: int
    cdte_files: tuple  # (Path, ...) one per detector present


def _discover_chunks(cfg: Config) -> list[Chunk]:
    """Find CdTe light curves, keeping the newest version per (date, half-day)."""
    root = cfg.paths["raw_hel1os"]
    excluded = set(cfg.hel1os.get("exclude_dates", []) or [])
    # group cdte files by their parent chunk folder
    by_chunkdir: dict[Path, list[Path]] = {}
    for f in root.glob(cfg.hel1os["lc_glob"]):
        by_chunkdir.setdefault(f.parent.parent, []).append(f)

    best: dict[tuple, Chunk] = {}
    for chunkdir, files in by_chunkdir.items():
        m = _CHUNK_RE.search(chunkdir.name)
        if not m:
            continue
        date, hour, ver = m.group(1), int(m.group(2)), int(m.group(3))
        if date in excluded:
            continue
        half = 0 if hour < 12 else 1
        key = (date, half)
        prev = best.get(key)
        if prev is None or ver > prev.version:
            best[key] = Chunk(date=date, half=half, version=ver,
                              cdte_files=tuple(sorted(files)))
    return sorted(best.values(), key=lambda c: (c.date, c.half))


def _read_band(path: Path, hdu: int) -> pd.DataFrame:
    with fits.open(path, memmap=False) as h:
        d = h[hdu].data
        mjd = np.asarray(d["MJD"], dtype="float64")
        ctr = np.asarray(d["CTR"], dtype="float64")
    ok = np.isfinite(mjd) & np.isfinite(ctr)
    return pd.DataFrame({"mjd": mjd[ok], "ctr": ctr[ok]})


def _bin_series(df: pd.DataFrame, bin_s: int) -> pd.Series:
    """Floor MJD times to ``bin_s`` and sum counts per bin -> counts/bin Series."""
    t = _MJD_EPOCH + pd.to_timedelta(df["mjd"].to_numpy(), unit="D")
    s = pd.Series(df["ctr"].to_numpy(), index=t)
    return s.resample(f"{bin_s}s").sum()


def load_hel1os(cfg: Config | None = None, verbose: bool = True) -> pd.DataFrame:
    """Return a tidy hard X-ray series at ``bin_s`` cadence.

    Columns: ``time``, ``broad`` (1.8-90 keV counts/bin, both detectors),
    ``soft`` (5-20 keV), ``hard`` (>20 keV = 20-30+30-40+40-60), the individual
    high bands, ``broad_err`` (Poisson), and ``hr`` (hardness = hard/soft).
    """
    cfg = cfg or load_config()
    bands = cfg.hel1os["bands"]
    bin_s = cfg.hel1os["bin_s"]
    chunks = _discover_chunks(cfg)
    if not chunks:
        raise FileNotFoundError(
            f"No HEL1OS CdTe light curves under {cfg.paths['raw_hel1os']}")

    frames = []
    for c in chunks:
        # sum each band over the available CdTe detectors
        band_series: dict[str, pd.Series] = {}
        for name, hdu in bands.items():
            parts = []
            for f in c.cdte_files:
                try:
                    parts.append(_bin_series(_read_band(f, hdu), bin_s))
                except Exception:
                    continue
            if parts:
                band_series[name] = pd.concat(parts, axis=1).sum(axis=1)
        if "broad" not in band_series:
            continue
        df = pd.DataFrame(band_series).reset_index().rename(columns={"index": "time"})
        df["date"] = c.date
        frames.append(df)
        if verbose:
            pk = df["broad"].max()
            print(f"  HEL1OS {c.date} half{c.half} v{c.version}  "
                  f"bins={len(df):>5}  broad_peak={pk:.0f}")

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates("time").sort_values("time").reset_index(drop=True)

    # A bin with no recorded counts in a band means zero counts, not missing.
    band_cols = [c for c in ("broad", "b_5_20", "b_20_30", "b_30_40", "b_40_60")
                 if c in out.columns]
    out[band_cols] = out[band_cols].fillna(0.0)

    # derived channels
    out["hard"] = out.get("b_20_30", 0) + out.get("b_30_40", 0) + out.get("b_40_60", 0)
    out["soft"] = out.get("b_5_20", 0)
    out["broad_err"] = np.sqrt(np.clip(out["broad"], 0, None))
    out["hr"] = out["hard"] / np.clip(out["soft"], 1, None)
    if verbose:
        print(f"\nHEL1OS: {len(chunks)} chunks, {len(out):,} bins @ {bin_s}s, "
              f"{out['time'].min()} -> {out['time'].max()}, "
              f"broad_peak={out['broad'].max():.0f}")
    return out


def list_chunks(cfg: Config | None = None) -> list[Chunk]:
    return _discover_chunks(cfg or load_config())


if __name__ == "__main__":
    df = load_hel1os()
    print("\nHead:\n", df.head())
    print("\nPeak hard X-ray day (broadband):")
    idx = df["broad"].idxmax()
    print(df.loc[idx])
