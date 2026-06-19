"""Turn SUIT full-disk NUV images into a compact UV light curve.

SUIT NB03 full-frame images are ~64 MB each at ~2-hour cadence, so we never keep
them: each FITS is reduced to a few numbers (disk-integrated brightness), appended
to a CSV, and the image is optionally deleted.  The CSV is the SUIT "light curve"
that accompanies the SoLEXS/HEL1OS series as a chromospheric UV channel.

Per frame we record (all within the solar disk, masked from CRPIX1/CRPIX2/R_SUN):

    disk_sum     total counts on the visible disk
    disk_mean    mean counts/pixel  (robust to the disk being partly off-frame)
    disk_p99     99th-percentile counts  (tracks bright active-region / flare UV)
    *_per_s      the above normalised by exposure (MEAS_EXP), so frames compare
    visible_frac fraction of the full disk actually on the detector (off-pointing
                 clips the southern/western limb in some frames — flag/curate on this)

Usage:
    python tools/suit_flux.py --src "C:/Users/Rover/Downloads/Suit data"
    python tools/suit_flux.py --src <dir> --delete          # process then remove FITS
    python tools/suit_flux.py --src <dir> --out data/suit_uv.csv
"""

from __future__ import annotations

import argparse
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits


def _disk_summary(path: Path) -> dict | None:
    """Reduce one SUIT FITS to disk-integrated UV brightness numbers."""
    with fits.open(path, memmap=True) as h:
        hdr = h[0].header
        data = np.asarray(h[0].data, dtype="float64")
    H, W = data.shape
    cx = float(hdr.get("CRPIX1", W / 2)) - 1.0      # FITS is 1-based -> 0-based
    cy = float(hdr.get("CRPIX2", H / 2)) - 1.0
    rsun = float(hdr.get("R_SUN", 0) or 0)
    if rsun <= 0:
        return None
    yy, xx = np.ogrid[:H, :W]
    disk = (xx - cx) ** 2 + (yy - cy) ** 2 <= rsun ** 2
    n = int(disk.sum())
    if n == 0:
        return None
    vals = data[disk]
    exp_s = float(hdr.get("MEAS_EXP", 0) or hdr.get("CMD_EXPT", 0) or 0) / 1000.0
    disk_sum = float(vals.sum())
    disk_mean = float(vals.mean())
    disk_p99 = float(np.percentile(vals, 99))
    full_disk_px = math.pi * rsun ** 2
    rec = {
        "time": pd.to_datetime(hdr.get("DATE-OBS") or hdr.get("T_OBS")),
        "filter": hdr.get("FTR_NAME"),
        "img_type": hdr.get("IMG_TYPE"),
        "exposure_s": round(exp_s, 4),
        "visible_frac": round(n / full_disk_px, 3),
        "disk_sum": disk_sum,
        "disk_mean": round(disk_mean, 3),
        "disk_p99": round(disk_p99, 3),
        "qval": float(hdr.get("QVAL", float("nan"))),
        # external flare flags SUIT recorded onboard (free cross-validation)
        "helios_trig": int(hdr.get("HELIOSTR", 0) or 0),
        "solex_trig": int((hdr.get("SOLX1TR", 0) or 0) or (hdr.get("SOLX2TR", 0) or 0)),
        "file": path.name,
    }
    if exp_s > 0:
        rec["sum_per_s"] = round(disk_sum / exp_s, 3)
        rec["p99_per_s"] = round(disk_p99 / exp_s, 3)
    return rec


def _gather_fits(src: Path) -> list[Path]:
    """All .fits under src, extracting any .zip archives first."""
    for z in src.rglob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            for m in zf.namelist():
                if m.lower().endswith(".fits") and not (z.parent / Path(m).name).exists():
                    zf.extract(m, z.parent)
    return sorted(src.rglob("*.fits"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True, help="folder of SUIT FITS/zips")
    ap.add_argument("--out", type=Path, default=Path("data/suit_uv.csv"))
    ap.add_argument("--delete", action="store_true", help="delete each FITS after reducing it")
    args = ap.parse_args()

    files = _gather_fits(args.src)
    if not files:
        print(f"No FITS under {args.src}")
        return 1

    existing = pd.read_csv(args.out) if args.out.exists() else None
    done = set(existing["file"]) if existing is not None else set()

    rows, removed = [], 0
    for f in files:
        if f.name in done:
            continue
        try:
            rec = _disk_summary(f)
        except Exception as e:
            print(f"  !! skip {f.name}: {e}")
            continue
        if rec is None:
            continue
        rows.append(rec)
        print(f"  {rec['time']}  {rec['filter']}  mean={rec['disk_mean']:.1f}  "
              f"p99/s={rec.get('p99_per_s')}  vis={rec['visible_frac']}")
        if args.delete:
            f.unlink()
            removed += 1

    if not rows:
        print("Nothing new to add.")
        return 0
    out = pd.DataFrame(rows)
    if existing is not None:
        out = pd.concat([existing, out], ignore_index=True)
    out = out.sort_values("time").drop_duplicates("file").reset_index(drop=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"\n{len(rows)} new frame(s) -> {args.out}  (total {len(out)})"
          + (f"; deleted {removed} FITS" if args.delete else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
