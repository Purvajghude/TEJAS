"""Clean a downloaded HEL1OS tree down to just the light curves we train on.

A PRADAN HEL1OS package expands to::

    HLS_<date>_<hhmmss>_<dur>sec_lev1_V<ver>/.../<date>/cdte/lightcurve_cdte1.fits
                                            .../<date>/cdte/lightcurve_cdte2.fits
                                            .../<date>/cdte/hel1os_cdte_spectra_*.fits
                                            .../<date>/czt/lightcurve_czt1.fits
                                            .../<date>/czt/lightcurve_czt2.fits
                                            .../<date>/czt/hel1os_czt_spectra_*.fits
                                            .../<date>/events/evt.fits          <-- huge
                                            .../<date>/_aux/...                  <-- gti/hk

TEJAS' forecasting pipeline only ever reads the *light curves*.  The spectra,
event photon-lists and _aux housekeeping are ~90% of the download and are never
touched, so this tool keeps only::

    lightcurve_cdte*.fits   (required by tejas/hel1os.py)
    lightcurve_czt*.fits    (extra >60 keV bands for the "best data" model)

and deletes everything else.  Any still-zipped packages have their light curves
extracted first (so no day is lost), then the zip itself is removed.

SAFETY: dry-run by default.  Nothing is created, extracted or deleted unless you
pass --apply.  Run it once without --apply, read the report, then re-run with it.

    python tools/clean_hel1os.py                       # dry run (default root)
    python tools/clean_hel1os.py --root "D:/Helios"    # dry run, other location
    python tools/clean_hel1os.py --apply               # actually clean
    python tools/clean_hel1os.py --apply --cdte-only   # drop czt too (10 GB less)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

DEFAULT_ROOT = Path(r"C:\Users\Rover\Downloads\Helios")

# Filenames we keep.  Everything else under the tree is removable.
KEEP_CDTE = re.compile(r"lightcurve_cdte\d*\.fits$", re.IGNORECASE)
KEEP_CZT = re.compile(r"lightcurve_czt\d*\.fits$", re.IGNORECASE)


def _gb(n: int) -> float:
    return n / 1024 ** 3


def _is_keeper(name: str, cdte_only: bool) -> bool:
    if KEEP_CDTE.search(name):
        return True
    if not cdte_only and KEEP_CZT.search(name):
        return True
    return False


def _extract_from_zips(root: Path, cdte_only: bool, apply: bool) -> tuple[int, int, int]:
    """Pull light curves out of every .zip, then mark the zip for deletion.

    Returns (n_zips, bytes_extracted, bytes_zip_reclaimed).
    """
    zips = sorted(root.rglob("*.zip"))
    n_extracted_bytes = 0
    n_zip_bytes = 0
    for z in zips:
        n_zip_bytes += z.stat().st_size
        try:
            with zipfile.ZipFile(z) as zf:
                members = [m for m in zf.infolist()
                           if not m.is_dir() and _is_keeper(m.filename, cdte_only)]
                target = z.with_name(z.stem + "_lc")  # sibling dir, light curves only
                for m in members:
                    n_extracted_bytes += m.file_size
                    if apply:
                        zf.extract(m, target)
        except zipfile.BadZipFile:
            print(f"  !! corrupt zip, leaving in place: {z}")
            n_zip_bytes -= z.stat().st_size
            continue
        if apply:
            z.unlink()
    return len(zips), n_extracted_bytes, n_zip_bytes


def _sweep_junk(root: Path, cdte_only: bool, apply: bool) -> tuple[int, int, int]:
    """Delete every file that is not a kept light curve.

    Returns (kept_files, kept_bytes, deleted_bytes).
    """
    kept_files = kept_bytes = deleted_bytes = 0
    by_type: dict[str, list[int]] = {}
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if p.suffix == ".zip":
            continue  # handled (and counted) by the zip-extraction pass
        size = p.stat().st_size
        if _is_keeper(p.name, cdte_only):
            kept_files += 1
            kept_bytes += size
            continue
        # bucket for the report
        if "spectra" in p.name:
            key = "spectra"
        elif p.name == "evt.fits":
            key = "events"
        elif "_aux" in p.parts[-2:][0] or p.suffix == ".txt" or p.name.startswith("gti") \
                or p.name == "hk.fits":
            key = "_aux/housekeeping"
        elif KEEP_CZT.search(p.name):  # cdte_only mode dropping czt
            key = "czt lightcurve (dropped)"
        else:
            key = "other"
        bucket = by_type.setdefault(key, [0, 0])
        bucket[0] += 1
        bucket[1] += size
        deleted_bytes += size
        if apply:
            try:
                p.unlink()
            except OSError as e:
                print(f"  !! could not delete {p}: {e}")

    if by_type:
        print("\n  Removable, by category:")
        for key, (cnt, b) in sorted(by_type.items(), key=lambda kv: -kv[1][1]):
            print(f"    {key:28s} {_gb(b):8.2f} GB  ({cnt} files)")
    return kept_files, kept_bytes, deleted_bytes


def _prune_empty_dirs(root: Path, apply: bool) -> int:
    removed = 0
    # walk bottom-up so children are gone before parents are tested
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        d = Path(dirpath)
        if d == root:
            continue
        if not any(d.iterdir()):
            removed += 1
            if apply:
                try:
                    d.rmdir()
                except OSError:
                    pass
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                    help=f"HEL1OS tree to clean (default: {DEFAULT_ROOT})")
    ap.add_argument("--apply", action="store_true",
                    help="actually extract/delete (otherwise dry run)")
    ap.add_argument("--cdte-only", action="store_true",
                    help="keep only CdTe light curves, drop CZT too")
    args = ap.parse_args()

    root: Path = args.root
    if not root.is_dir():
        print(f"error: not a directory: {root}")
        return 1

    mode = "APPLY (deleting)" if args.apply else "DRY RUN (no changes)"
    keep = "CdTe only" if args.cdte_only else "CdTe + CZT light curves"
    print(f"\nHEL1OS cleanup  -  {mode}")
    print(f"  root : {root}")
    print(f"  keep : {keep}\n")

    print("[1/3] Extracting light curves from zipped packages ...")
    nz, ext_b, zip_b = _extract_from_zips(root, args.cdte_only, args.apply)
    print(f"  {nz} zips ({_gb(zip_b):.2f} GB); light curves inside ~{_gb(ext_b):.2f} GB "
          f"{'extracted' if args.apply else 'would be extracted'}, "
          f"then zips {'deleted' if args.apply else 'would be deleted'}.")

    print("\n[2/3] Sweeping non-light-curve files ...")
    kf, kb, db = _sweep_junk(root, args.cdte_only, args.apply)

    print("\n[3/3] Pruning empty folders ...")
    ne = _prune_empty_dirs(root, args.apply)
    print(f"  {ne} empty folders {'removed' if args.apply else 'would be removed'}.")

    print("\n" + "=" * 56)
    print(f"  KEEP    : {kf} light curves   {_gb(kb):8.2f} GB")
    print(f"  RECLAIM : files + zips        {_gb(db + zip_b):8.2f} GB")
    print("=" * 56)
    if not args.apply:
        print("\nThis was a DRY RUN. Re-run with --apply to perform the cleanup.")
    else:
        print("\nDone. Point config.yaml paths.raw_hel1os at this folder to load it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
