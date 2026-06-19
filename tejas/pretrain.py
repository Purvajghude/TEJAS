"""Transfer-learning support: bulk GOES data for pretraining the temporal model.

We pretrain a temporal CNN on *years* of GOES XRS so it learns flare dynamics
from thousands of events, then fine-tune on Aditya-L1. To keep transfer honest,
pretraining years must NOT overlap the Aditya-L1 test period (Sep-Oct 2024) —
otherwise the model would memorise the very flares we evaluate on.

GOES and Aditya-L1 are mapped onto the same three physical channels:
    soft  ~ GOES xrsb (1-8 A)      hard ~ GOES xrsa (0.5-4 A)
    hardness = hard / soft
so a representation learned on GOES transfers to SoLEXS(soft)+HEL1OS(hard).
"""

from __future__ import annotations

import concurrent.futures as cf

import numpy as np
import pandas as pd

from .config import Config, load_config
from .goes import _NCEI_BASE, _get, _month_index, _EPOCH


def download_pretrain_goes(years: list[int], cfg: Config | None = None,
                           workers: int = 8, verbose: bool = True) -> int:
    """Download GOES-16 1-min flux for whole years into a pretrain cache."""
    cfg = cfg or load_config()
    sat = cfg.goes["satellite"]
    cache = cfg.paths["external"] / "goes_pretrain"
    cache.mkdir(parents=True, exist_ok=True)

    jobs = []  # (url, dest)
    for year in years:
        for month in range(1, 13):
            try:
                index = _month_index(sat, year, month)
            except Exception:
                continue
            for date, fname in index.items():
                dest = cache / f"g{sat}_{date}.nc"
                if dest.exists() and dest.stat().st_size > 0:
                    continue
                url = f"{_NCEI_BASE.format(sat=sat)}/{year:04d}/{month:02d}/{fname}"
                jobs.append((url, dest))
            if verbose:
                print(f"  indexed {year}-{month:02d} ({len(jobs)} queued)")

    def fetch(job):
        url, dest = job
        try:
            dest.write_bytes(_get(url, timeout=120).content)
            return True
        except Exception:
            return False

    ok = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for i, good in enumerate(ex.map(fetch, jobs), 1):
            ok += int(good)
            if verbose and i % 50 == 0:
                print(f"  downloaded {i}/{len(jobs)} ({ok} ok)")
    if verbose:
        n = len(list(cache.glob(f"g{sat}_*.nc")))
        print(f"GOES pretrain cache: {n} daily files in {cache}")
    return ok


def load_pretrain_goes(cfg: Config | None = None) -> pd.DataFrame:
    """Load the cached pretrain GOES years into [time, soft, hard]."""
    import netCDF4 as nc
    cfg = cfg or load_config()
    sat = cfg.goes["satellite"]
    cache = cfg.paths["external"] / "goes_pretrain"
    files = sorted(cache.glob(f"g{sat}_*.nc"))
    frames = []
    for f in files:
        ds = nc.Dataset(f)
        t = np.array(ds.variables["time"][:], dtype="float64")
        xb = np.array(ds.variables["xrsb_flux"][:], dtype="float64")
        xa = np.array(ds.variables["xrsa_flux"][:], dtype="float64")
        bf = np.array(ds.variables["xrsb_flag"][:], dtype="float64")
        ds.close()
        xb[bf != 0] = np.nan
        frames.append(pd.DataFrame({
            "time": _EPOCH + pd.to_timedelta(t, unit="s"),
            "soft": xb, "hard": xa}))
    out = pd.concat(frames, ignore_index=True).dropna(subset=["soft"])
    return out.drop_duplicates("time").sort_values("time").reset_index(drop=True)


# ----------------------------------------------------------------------
# Channel representation shared by GOES (pretrain) and Aditya-L1 (finetune)
#   ch0 = log10(soft)   ch1 = log10(hard)   ch2 = hardness = log(hard/soft)
# Each dataset is standardised to its own stats so the network learns the
# *shape* of pre-flare dynamics, not absolute instrument units.
# ----------------------------------------------------------------------
def to_channels(soft, hard):
    s = np.log10(np.clip(np.asarray(soft, float), 1e-12, None))
    h = np.log10(np.clip(np.asarray(hard, float), 1e-12, None))
    hr = h - s
    return np.vstack([s, h, hr])  # (3, N)


def standardize(ch, stats=None):
    if stats is None:
        mu = np.nanmean(ch, axis=1, keepdims=True)
        sd = np.nanstd(ch, axis=1, keepdims=True) + 1e-6
        stats = (mu, sd)
    mu, sd = stats
    return (ch - mu) / sd, stats


def goes_flare_peaks(df, mclass=1e-5, sep_min=10):
    """Local maxima of GOES soft flux above M1 — pretraining flare peaks."""
    from scipy.signal import find_peaks
    y = df["soft"].to_numpy()
    idx, _ = find_peaks(np.log10(np.clip(y, 1e-12, None)),
                        height=np.log10(mclass), distance=sep_min)
    return df["time"].to_numpy()[idx]


def make_windows(times, ch, peaks, W=120, H=30, cadence_s=60,
                 neg_per_pos=3, seed=42):
    """Sliding windows (3,W) -> label (flare peak within next H min)."""
    rng = np.random.default_rng(seed)
    times = np.asarray(times)
    pk = np.sort(np.asarray(peaks))
    N = ch.shape[1]
    step = np.timedelta64(cadence_s, "s")
    span = np.timedelta64(W * cadence_s, "s")
    horizon = np.timedelta64(H, "m")
    pos, neg = [], []
    for i in range(W, N - 1):
        # require a contiguous window (no data gaps)
        if times[i] - times[i - W] > span * 1.05:
            continue
        j = np.searchsorted(pk, times[i], side="right")
        y = 1 if (j < len(pk) and pk[j] <= times[i] + horizon) else 0
        (pos if y else neg).append(i)
    neg = list(rng.choice(neg, size=min(len(neg), neg_per_pos * max(len(pos), 1)),
                          replace=False)) if neg else []
    idxs = np.array(pos + neg)
    rng.shuffle(idxs)
    X = np.stack([ch[:, i - W:i] for i in idxs]).astype("float32")
    y = np.array([1 if i in set(pos) else 0 for i in idxs], dtype="float32")
    return X, y


if __name__ == "__main__":
    import sys
    yrs = [int(y) for y in sys.argv[1:]] or [2022, 2023]
    download_pretrain_goes(yrs)
