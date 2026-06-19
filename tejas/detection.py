"""Flare detection on a soft X-ray light curve.

The original pipeline used a single global ``mean + 3*std`` threshold over a whole
day.  That is statistically wrong: flares are huge outliers that inflate both the
mean and the std (raising the threshold and hiding small flares), and a single
global level cannot track a background that drifts over the day.

This module instead uses the standard approach for X-ray flare detection:

1. **Sliding quiescent background** — a causal (trailing) rolling *median*, which
   is robust to flares occupying a minority of the window.
2. **Poisson significance** — ``(counts - background) / sqrt(background)``; the
   noise on a count rate is Poissonian, so this is the physically correct S/N.
3. **Hysteresis event extraction** — a flare *opens* where significance crosses a
   high threshold (default 5 sigma) and its rise/decay are traced out to a lower
   threshold (default 2 sigma), mimicking the GOES start/peak/end convention.

Working per continuous segment (split on time gaps) prevents the background from
smearing across day boundaries and observing gaps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config, load_config


def _split_segments(times: pd.Series, cadence_s: float, max_gap_factor: float = 5.0):
    """Yield (start_idx, stop_idx) slices of contiguously-sampled data."""
    dt = times.diff().dt.total_seconds().to_numpy()
    breaks = np.where(dt > cadence_s * max_gap_factor)[0]
    bounds = [0, *breaks.tolist(), len(times)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b > a:
            yield a, b


def annotate(df: pd.DataFrame, cfg: Config | None = None,
             count_col: str = "counts", cadence_s: float | None = None) -> pd.DataFrame:
    """Return a copy of ``df`` with ``smooth``, ``background`` and ``significance``.

    Works on any count channel (``count_col``) at any ``cadence_s`` — the same
    validated algorithm serves both the SoLEXS soft and HEL1OS hard channels.
    These per-sample series drive event extraction and the dashboard.
    """
    cfg = cfg or load_config()
    d = cfg.detection
    cadence = cadence_s if cadence_s is not None else cfg.solexs["cadence_s"]
    smooth_n = max(1, int(d["smooth_window_s"] / cadence))
    bg_n = max(1, int(d["background_window_s"] / cadence))

    out = df.copy().reset_index(drop=True)
    smooth = np.full(len(out), np.nan)
    background = np.full(len(out), np.nan)

    counts = out[count_col].to_numpy(dtype="float64")
    for a, b in _split_segments(out["time"], cadence):
        seg = pd.Series(counts[a:b])
        sm = seg.rolling(smooth_n, min_periods=1, center=True).mean()
        # Causal rolling-median background, robust to flare outliers.
        bg = seg.rolling(bg_n, min_periods=max(5, bg_n // 6)).median()
        bg = bg.bfill()  # fill the warm-up region at the segment start
        smooth[a:b] = sm.to_numpy()
        background[a:b] = bg.to_numpy()

    out["smooth"] = smooth
    out["background"] = background
    safe_bg = np.clip(background, 1.0, None)
    out["significance"] = (smooth - background) / np.sqrt(safe_bg)
    return out


def detect_events(df: pd.DataFrame, cfg: Config | None = None,
                  count_col: str = "counts", cadence_s: float | None = None,
                  id_prefix: str = "SLX", payload: str = "SoLEXS") -> pd.DataFrame:
    """Detect flares and return one row per event.

    ``df`` must already be annotated by :func:`annotate` (or a raw frame, in
    which case annotation is performed here).
    """
    cfg = cfg or load_config()
    d = cfg.detection
    cadence = cadence_s if cadence_s is not None else cfg.solexs["cadence_s"]

    if "significance" not in df.columns:
        df = annotate(df, cfg, count_col=count_col, cadence_s=cadence)

    hi = d["sigma_threshold"]
    lo = d["end_sigma"]
    min_dur = d["min_duration_s"]
    merge_gap = d["merge_gap_s"]

    sig = df["significance"].to_numpy()
    counts = df[count_col].to_numpy()
    background = df["background"].to_numpy()
    times = df["time"].to_numpy()

    above_lo = sig > lo
    # Contiguous runs of "above low threshold".
    runs = _contiguous_true(above_lo)

    events = []
    for a, b in runs:
        seg_sig = sig[a:b]
        if seg_sig.max() < hi:
            continue  # never reached the high (opening) threshold -> not a flare
        events.append([a, b])

    # Merge events separated by a short gap.
    merged = []
    for a, b in events:
        if merged and (a - merged[-1][1]) * cadence <= merge_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])

    rows = []
    for n, (a, b) in enumerate(merged, start=1):
        seg_counts = counts[a:b]
        peak_off = int(np.argmax(seg_counts))
        peak_idx = a + peak_off
        duration_s = (b - 1 - a) * cadence
        if duration_s < min_dur:
            continue
        rows.append({
            "flare_id": f"{id_prefix}-{n:04d}",
            "payload": payload,
            "start_time": pd.Timestamp(times[a]),
            "peak_time": pd.Timestamp(times[peak_idx]),
            "end_time": pd.Timestamp(times[b - 1]),
            "duration_s": float(duration_s),
            "peak_counts": float(counts[peak_idx]),
            "background_counts": float(background[peak_idx]),
            "peak_significance": float(sig[a:b].max()),
        })

    cat = pd.DataFrame(rows)
    if not cat.empty:
        cat["flare_id"] = [f"{id_prefix}-{i:04d}" for i in range(1, len(cat) + 1)]
    return cat


def _contiguous_true(mask: np.ndarray):
    """Return [start, stop) index pairs for runs of True in a boolean array."""
    if not mask.any():
        return []
    idx = np.flatnonzero(np.diff(np.concatenate(([0], mask.view(np.int8), [0]))))
    return list(zip(idx[0::2], idx[1::2]))


if __name__ == "__main__":
    from .solexs import load_solexs

    cfg = load_config()
    print("Loading SoLEXS...")
    df = load_solexs(cfg, verbose=False)
    print(f"  {len(df):,} samples")
    print("Annotating + detecting...")
    ann = annotate(df, cfg)
    cat = detect_events(ann, cfg)
    print(f"\nDetected {len(cat)} flares")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(cat.head(20).to_string(index=False))
