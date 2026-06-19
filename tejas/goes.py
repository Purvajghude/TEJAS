"""GOES XRS reference data — fetch, cache, and classify.

We use NOAA NCEI's science-quality 1-minute averaged GOES-16 XRS product as an
independent ground truth:

* ``xrsb_flux`` — 1-8 Angstrom long channel (defines the GOES A/B/C/M/X class)
* ``xrsa_flux`` — 0.5-4 Angstrom short channel (harder X-rays)

This is used to (a) calibrate SoLEXS counts to physical flux, (b) assign real
flare classes, (c) validate our catalogue, and (d) overlay on the dashboard.

NetCDF time epoch is ``seconds since 2000-01-01 12:00:00 UTC``.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import Config, load_config

_NCEI_BASE = (
    "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/"
    "goes/goes{sat}/l2/data/xrsf-l2-avg1m_science"
)
_EPOCH = pd.Timestamp("2000-01-01 12:00:00")
_HREF_RE = re.compile(r'href="(sci_xrsf-l2-avg1m_g\d+_d(\d{8})_v[^"]+\.nc)"')


def _get(url: str, timeout: int = 120, retries: int = 4) -> requests.Response:
    """GET with simple exponential backoff for flaky NOAA connections."""
    import time
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as exc:  # noqa: PERF203
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last


def _month_index(sat: int, year: int, month: int) -> dict[str, str]:
    """Map YYYYMMDD -> filename for a given GOES sat / year / month."""
    url = f"{_NCEI_BASE.format(sat=sat)}/{year:04d}/{month:02d}/"
    resp = _get(url, timeout=60)
    return {m.group(2): m.group(1) for m in _HREF_RE.finditer(resp.text)}


def download_goes(dates: list[str], cfg: Config | None = None,
                  verbose: bool = True) -> list[Path]:
    """Ensure GOES daily netCDF files for ``dates`` (YYYYMMDD) are cached locally."""
    cfg = cfg or load_config()
    sat = cfg.goes["satellite"]
    cache = cfg.paths["external"] / "goes"
    cache.mkdir(parents=True, exist_ok=True)

    # Group requested dates by (year, month) so we list each month only once.
    by_month: dict[tuple, list[str]] = {}
    for d in dates:
        by_month.setdefault((int(d[:4]), int(d[4:6])), []).append(d)

    saved: list[Path] = []
    for (year, month), ds in sorted(by_month.items()):
        index = None
        for d in sorted(ds):
            dest = cache / f"g{sat}_{d}.nc"
            if dest.exists() and dest.stat().st_size > 0:
                saved.append(dest)
                continue
            if index is None:
                index = _month_index(sat, year, month)
            fname = index.get(d)
            if fname is None:
                if verbose:
                    print(f"  GOES: no file for {d}")
                continue
            url = f"{_NCEI_BASE.format(sat=sat)}/{year:04d}/{month:02d}/{fname}"
            r = _get(url, timeout=120)
            dest.write_bytes(r.content)
            saved.append(dest)
            if verbose:
                print(f"  GOES downloaded {d}  ({len(r.content)//1024} KiB)")
    return saved


def load_goes(cfg: Config | None = None, dates: list[str] | None = None,
              verbose: bool = True) -> pd.DataFrame:
    """Load cached GOES flux into a tidy DataFrame.

    Columns: ``time`` (UTC), ``xrsb`` (1-8 A, W/m^2), ``xrsa`` (0.5-4 A, W/m^2).
    Bad-quality samples (non-zero flag) are set to NaN.
    """
    import netCDF4 as nc

    cfg = cfg or load_config()
    sat = cfg.goes["satellite"]
    cache = cfg.paths["external"] / "goes"
    files = sorted(cache.glob(f"g{sat}_*.nc"))
    if dates is not None:
        keep = set(dates)
        files = [f for f in files if f.stem.split("_")[-1] in keep]
    if not files:
        raise FileNotFoundError(
            f"No GOES files in {cache}. Run download_goes() first."
        )

    frames = []
    for f in files:
        ds = nc.Dataset(f)
        t = np.array(ds.variables["time"][:], dtype="float64")
        xrsb = np.array(ds.variables["xrsb_flux"][:], dtype="float64")
        xrsa = np.array(ds.variables["xrsa_flux"][:], dtype="float64")
        bflag = np.array(ds.variables["xrsb_flag"][:], dtype="float64")
        aflag = np.array(ds.variables["xrsa_flag"][:], dtype="float64")
        ds.close()
        xrsb[bflag != 0] = np.nan
        xrsa[aflag != 0] = np.nan
        time = _EPOCH + pd.to_timedelta(t, unit="s")
        frames.append(pd.DataFrame({"time": time, "xrsb": xrsb, "xrsa": xrsa}))

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    if verbose:
        print(f"GOES: {len(files)} days, {len(out):,} minutes, "
              f"peak xrsb={np.nanmax(out['xrsb']):.2e}")
    return out


_DONKI_URL = "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR"


def fetch_donki(start: str, end: str, cfg: Config | None = None) -> pd.DataFrame:
    """Fetch NASA DONKI flare list (authoritative for M/X) for ``start``..``end``.

    Dates are ``YYYY-MM-DD``. Cached as JSON under ``data/external``.
    Returns columns: ``begin``, ``peak``, ``end`` (UTC), ``goes_class``,
    ``flux`` (W/m^2), ``active_region``.
    """
    import json

    cfg = cfg or load_config()
    cache = cfg.paths["external"] / f"donki_{start}_{end}.json"
    if cache.exists():
        records = json.loads(cache.read_text())
    else:
        r = _get(f"{_DONKI_URL}?startDate={start}&endDate={end}", timeout=90)
        records = r.json()
        cache.write_text(json.dumps(records))

    rows = []
    for rec in records:
        cls = rec.get("classType")
        rows.append({
            "begin": pd.to_datetime(rec.get("beginTime")).tz_localize(None)
            if rec.get("beginTime") else pd.NaT,
            "peak": pd.to_datetime(rec.get("peakTime")).tz_localize(None)
            if rec.get("peakTime") else pd.NaT,
            "end": pd.to_datetime(rec.get("endTime")).tz_localize(None)
            if rec.get("endTime") else pd.NaT,
            "goes_class": cls,
            "flux": class_to_flux(cls),
            "active_region": rec.get("activeRegionNum"),
        })
    return pd.DataFrame(rows).dropna(subset=["peak"]).sort_values("peak").reset_index(drop=True)


def class_to_flux(cls: str | None) -> float:
    """Convert a GOES class string like 'X9.0' to flux in W/m^2."""
    if not cls or len(cls) < 2:
        return np.nan
    base = {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}.get(cls[0].upper())
    if base is None:
        return np.nan
    try:
        return base * float(cls[1:])
    except ValueError:
        return base


def flux_to_class(flux: float, classes: dict | None = None) -> str:
    """Convert a 1-8 A flux (W/m^2) to a GOES class string, e.g. 'M2.3'."""
    if not np.isfinite(flux) or flux <= 0:
        return "—"
    bounds = classes or {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}
    for letter, lower in sorted(bounds.items(), key=lambda kv: kv[1], reverse=True):
        if flux >= lower:
            return f"{letter}{flux / lower:.1f}"
    return f"A{flux / 1e-8:.1f}"


if __name__ == "__main__":
    from .solexs import list_days

    cfg = load_config()
    days = list_days(cfg)
    print(f"Ensuring GOES for {len(days)} SoLEXS days...")
    download_goes(days, cfg)
    g = load_goes(cfg)
    print(g.head())
    print("\nSanity — peak class:", flux_to_class(g["xrsb"].max(), cfg.goes["flux_classes"]))
