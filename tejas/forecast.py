"""Soft X-ray flare forecasting — precursor-based, leakage-free.

The original forecaster had three fatal flaws: a *random* train/test split on a
time series (test rows sit seconds from train rows → leakage → fake accuracy),
labels derived from only 3 events, and no lead-time metric at all.

This rebuild fixes all three:

* **Causal features only** — every feature is a trailing-window statistic, so the
  model never sees the future.
* **Chronological split** — train on the earlier part of the campaign, test on
  the later part. No temporal leakage.
* **Operational metrics** — TSS (True Skill Statistic) and Brier score, plus a
  **lead-time distribution**: for every real flare in the test set, how many
  minutes before the peak did the alert first fire.

Target: probability that a flare *peak* occurs within the next ``horizon`` minutes.
Features are built on the 1-minute SoLEXS series; labels come from the validated
flare catalogue.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from joblib import dump

from .config import Config, load_config
from .solexs import load_solexs
from .hel1os import load_hel1os
from .detection import annotate
from . import models

# Soft X-ray (SoLEXS) precursor features.
FEATURES = [
    "counts", "log_counts", "excess", "ratio",
    "mean_5", "mean_15", "mean_30",
    "std_5", "std_15", "std_30",
    "slope_5", "slope_15", "slope_30",
    "delta_5", "delta_15",
    "sig_max_15", "sig_max_30",
    "mins_since_flare",
]

# Hard X-ray (HEL1OS) precursor features — the Neupert/nonthermal channel.
HARD_FEATURES = [
    "h_broad", "h_hard", "h_nonth", "h_hr",
    "h_hard_d5", "h_hard_d15", "h_nonth_max15",
    "h_hr_mean15", "h_broad_slope15",
]


def minute_series(cfg: Config | None = None) -> pd.DataFrame:
    """1-minute SoLEXS series with counts, background and significance."""
    cfg = cfg or load_config()
    ann = annotate(load_solexs(cfg, verbose=False), cfg)
    ann = ann.set_index("time")
    out = pd.DataFrame({
        "counts": ann["counts"].resample("1min").mean(),
        "background": ann["background"].resample("1min").mean(),
        "significance": ann["significance"].resample("1min").max(),
    }).dropna(subset=["counts"]).reset_index()
    return out


def hel1os_minute_features(cfg: Config | None = None) -> pd.DataFrame:
    """1-minute HEL1OS hard X-ray precursor features (all causal)."""
    cfg = cfg or load_config()
    hel = load_hel1os(cfg, verbose=False).set_index("time")
    nonth = hel.get("b_30_40", 0) + hel.get("b_40_60", 0)
    res = pd.DataFrame({
        "h_broad": hel["broad"].resample("1min").sum(),
        "h_soft": hel["soft"].resample("1min").sum(),
        "h_hard": hel["hard"].resample("1min").sum(),
        "h_nonth": nonth.resample("1min").sum(),
    }).fillna(0.0)
    res["h_hr"] = res["h_hard"] / np.clip(res["h_soft"], 1, None)
    res["h_hard_d5"] = res["h_hard"] - res["h_hard"].shift(5)
    res["h_hard_d15"] = res["h_hard"] - res["h_hard"].shift(15)
    res["h_nonth_max15"] = res["h_nonth"].rolling("15min").max()
    res["h_hr_mean15"] = res["h_hr"].rolling("15min").mean()
    res["h_broad_slope15"] = (res["h_broad"] - res["h_broad"].shift(15)) / 15
    return res.reset_index()


def make_features(m: pd.DataFrame) -> pd.DataFrame:
    """Build causal (trailing-window) precursor features on a 1-min series."""
    df = m.copy().set_index("time")
    c = df["counts"]
    df["log_counts"] = np.log10(np.clip(c, 1, None))
    df["excess"] = c - df["background"]
    df["ratio"] = c / np.clip(df["background"], 1, None)
    for w in (5, 15, 30):
        win = f"{w}min"
        df[f"mean_{w}"] = c.rolling(win).mean()
        df[f"std_{w}"] = c.rolling(win).std()
        # slope ≈ (now − value w minutes ago) / w, a causal trend estimate
        df[f"slope_{w}"] = (c - c.shift(w)) / w
    df["delta_5"] = c - c.shift(5)
    df["delta_15"] = c - c.shift(15)
    df["sig_max_15"] = df["significance"].rolling("15min").max()
    df["sig_max_30"] = df["significance"].rolling("30min").max()
    return df.reset_index()


def make_labels(m: pd.DataFrame, peaks: pd.Series, horizon_min: int) -> np.ndarray:
    """y(t)=1 if a flare peak occurs in (t, t+horizon]  (vectorised)."""
    times = m["time"].to_numpy()
    pk = np.sort(peaks.to_numpy())
    y = np.zeros(len(times), dtype=int)
    if len(pk) == 0:
        return y
    horizon = np.timedelta64(horizon_min, "m")
    # For each t, the first peak strictly after t is pk[lo]; it counts iff it
    # falls within the horizon.  searchsorted over all t at once -> no Python loop.
    lo = np.searchsorted(pk, times, side="right")
    valid = lo < len(pk)
    nxt = pk[np.where(valid, lo, 0)]              # 0 is a safe dummy where invalid
    y[valid & (nxt <= times + horizon)] = 1
    return y


def flare_intervals(cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """(start, end) datetime arrays of every detected soft flare (any class)."""
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv",
                      parse_dates=["start_time", "end_time"])
    return cat["start_time"].to_numpy(), cat["end_time"].to_numpy()


def in_flare_mask(times: np.ndarray, starts: np.ndarray,
                  ends: np.ndarray) -> np.ndarray:
    """Boolean: is t inside any [start, end] flare interval (a flare in progress).

    Detected flares are disjoint and we sort by start, so the candidate interval
    for t is the one with the greatest start <= t; t is in-flare iff its end >= t.
    Excluding these samples is what turns nowcasting into genuine forecasting:
    the model may only predict from a quiescent state, never mid-flare.
    """
    if len(starts) == 0:
        return np.zeros(len(times), dtype=bool)
    order = np.argsort(starts)
    starts, ends = starts[order], ends[order]
    idx = np.searchsorted(starts, times, side="right") - 1
    out = np.zeros(len(times), dtype=bool)
    v = idx >= 0
    out[v] = times[v] <= ends[idx[v]]
    return out


def add_time_since_flare(m: pd.DataFrame, peaks: pd.Series) -> pd.DataFrame:
    """Minutes since the most recent *past* flare peak (causal)."""
    times = m["time"].to_numpy()
    pk = np.sort(peaks.to_numpy())
    mins = np.full(len(times), 1e4)
    idx = np.searchsorted(pk, times, side="right") - 1
    valid = idx >= 0
    mins[valid] = (times[valid] - pk[idx[valid]]) / np.timedelta64(1, "m")
    m = m.copy()
    m["mins_since_flare"] = np.clip(mins, 0, 1e4)
    return m


def lead_times(test: pd.DataFrame, prob: np.ndarray, peaks: pd.Series,
               threshold: float, horizon_min: int,
               starts: pd.Series | None = None) -> dict:
    """For each test-set flare, minutes between first alert and the flare peak
    (and optionally the flare onset/start, which is the stricter metric).

    Lead-to-peak: time from first alert to peak.  Upper-bounded by horizon_min
    because labels only cover [t, t+horizon].  Max = horizon means the model
    fired at the very start of the prediction window.

    Lead-to-onset: time from first alert to flare START.  Always positive for
    quiescent-only prediction points (by construction), and is the operationally
    correct metric — it tells you how early the alert fired before the flare
    was visible in any channel.  Requires `starts` (flare start times).
    """
    t = test["time"].to_numpy()
    horizon = np.timedelta64(horizon_min, "m")
    in_test = (peaks >= test["time"].min()) & (peaks <= test["time"].max())
    leads_peak, leads_onset, caught = [], [], 0
    pk_list = np.sort(peaks[in_test].to_numpy())

    # Build start-time lookup: for each caught peak p, find the last flare
    # start time that precedes p by ≤ 3 h (this must be the start of that flare).
    # We do NOT assume starts and peaks are co-indexed — we just need a sorted
    # array of all start times from the catalog.
    st_arr: np.ndarray | None = None
    if starts is not None and len(starts) > 0:
        st_arr = np.sort(starts.to_numpy().astype("datetime64[ns]"))

    for p in pk_list:
        window = (t >= p - horizon) & (t <= p)
        if not window.any():
            continue
        fired = window & (prob >= threshold)
        if fired.any():
            first = t[fired][0]
            leads_peak.append((p - first) / np.timedelta64(1, "m"))
            if st_arr is not None:
                # Last start at or before p (= start of this flare).
                idx = int(np.searchsorted(st_arr, p, side="right")) - 1
                if idx >= 0:
                    s = st_arr[idx]
                    gap_h = (p - s) / np.timedelta64(1, "h")
                    if 0.0 <= float(gap_h) <= 3.0:
                        leads_onset.append(
                            float((s - first) / np.timedelta64(1, "m")))
            caught += 1

    leads_peak = np.array(leads_peak)
    leads_onset = np.array(leads_onset) if leads_onset else None
    result = {
        "n_flares": int(len(pk_list)),
        "n_caught": int(caught),
        "event_recall": round(caught / len(pk_list), 3) if len(pk_list) else None,
        "median_lead_to_peak_min": round(float(np.median(leads_peak)), 1) if len(leads_peak) else None,
        "mean_lead_to_peak_min": round(float(np.mean(leads_peak)), 1) if len(leads_peak) else None,
        "max_lead_to_peak_min": round(float(np.max(leads_peak)), 1) if len(leads_peak) else None,
        # Legacy key kept for dashboard compatibility.
        "median_lead_min": round(float(np.median(leads_peak)), 1) if len(leads_peak) else None,
        "leads": leads_peak.tolist(),
    }
    if leads_onset is not None and len(leads_onset) > 0:
        result.update({
            "median_lead_to_onset_min": round(float(np.median(leads_onset)), 1),
            "mean_lead_to_onset_min": round(float(np.mean(leads_onset)), 1),
            "pct_alerts_before_onset": round(float((leads_onset > 0).mean()), 3),
            "leads_onset": leads_onset.tolist(),
        })
    return result


def alarm_episodes(times: np.ndarray, fire: np.ndarray,
                   merge_gap_min: int = 10) -> list[tuple]:
    """Contiguous 'alert firing' runs, merged across short gaps -> (start, end)."""
    if not fire.any():
        return []
    edges = np.flatnonzero(np.diff(np.concatenate(([0], fire.view(np.int8), [0]))))
    runs = [[a, b] for a, b in zip(edges[0::2], edges[1::2])]
    gap = np.timedelta64(merge_gap_min, "m")
    merged = [runs[0]]
    for a, b in runs[1:]:
        if times[a] - times[merged[-1][1] - 1] <= gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(times[a], times[b - 1]) for a, b in merged]


def event_skill(times: np.ndarray, prob: np.ndarray, peaks, threshold: float,
                horizon_min: int, merge_gap_min: int = 10) -> dict:
    """Operational, *event-based* skill — what the ISRO rubric means by TPR/FAR.

    * a flare is *caught* if any alert fires in [peak-horizon, peak]
    * an alert *episode* is a *false alarm* if no flare peak follows it within the
      horizon; we report those per day (the operationally standard FAR), not the
      per-minute ratio that looks catastrophic for rare events.
    """
    times = np.asarray(times)
    if len(times) == 0:
        return {}
    horizon = np.timedelta64(horizon_min, "m")
    fire = prob >= threshold
    lo, hi = times.min(), times.max()
    pk = np.sort(np.asarray(peaks))
    pk = pk[(pk >= lo) & (pk <= hi)]

    caught = sum(bool(((times >= p - horizon) & (times <= p) & fire).any()) for p in pk)
    episodes = alarm_episodes(times, fire, merge_gap_min)
    n_false = sum(0 if np.any((pk >= s) & (pk <= e + horizon)) else 1
                  for s, e in episodes)
    n_days = max(float((hi - lo) / np.timedelta64(1, "D")), 1e-9)
    return {
        "n_flares": int(len(pk)), "n_caught": int(caught),
        "event_recall": round(caught / len(pk), 3) if len(pk) else None,
        "n_alarms": len(episodes), "n_false_alarms": int(n_false),
        "false_alarms_per_day": round(n_false / n_days, 2),
        "episode_precision": round(1 - n_false / len(episodes), 3) if episodes else None,
    }


def _evaluate(name, tr, te, features, peaks, horizon, m_full):
    """models.fit_eval + lead-time + full-series probabilities."""
    r = models.fit_eval(name, tr, te, features)
    lead = lead_times(te, r["prob_test"], peaks, r["thr"], horizon)
    r["lead"] = {k: v for k, v in lead.items() if k != "leads"}
    r["lead_raw"] = lead["leads"]
    r["prob_full"] = r["model"].predict_proba(m_full[features])[:, 1]
    return r


def _importances(name, train, features):
    """Feature importances (tree) or |coef| (logistic) from a raw fit."""
    raw = models.make_model(name)
    raw.fit(train[features], train["target"])
    if hasattr(raw, "named_steps"):                    # logistic pipeline
        lr = raw.named_steps.get("logisticregression")
        vals = np.abs(lr.coef_[0]) if lr is not None else np.zeros(len(features))
    elif hasattr(raw, "feature_importances_"):
        vals = raw.feature_importances_
    else:
        vals = np.zeros(len(features))
    vals = np.asarray(vals, dtype=float)
    if vals.sum() > 0:
        vals = vals / vals.sum()
    order = np.argsort(vals)[::-1]
    return [{"feature": features[i], "importance": round(float(vals[i]), 3)}
            for i in order[:8]]


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    cfg.ensure_dirs()
    horizons = cfg.forecast.get("horizons_min", [15, 30, 60, 120])
    primary = cfg.forecast.get("primary_horizon_min", horizons[0])
    test_frac = cfg.forecast["test_fraction"]
    target_class = cfg.forecast.get("target_class", "M")
    candidates = cfg.forecast.get("models", ["logistic", "rf", "lgbm"])

    # Labels from the validated catalogue, restricted to the target class+.
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv",
                      parse_dates=["peak_time"])
    order = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}
    cutoff = order.get(target_class, 2)
    letter = cat["class_goes"].fillna(cat["class_solexs"]).str[0]
    peaks = cat[letter.map(lambda c: order.get(c, 0)) >= cutoff][
        "peak_time"].astype("datetime64[ns]")
    if verbose:
        print(f"Forecasting {target_class}+ flares: {len(peaks)} target events")

    # Build the feature matrix once (soft + hard).
    m = minute_series(cfg)
    m = make_features(m)
    m = add_time_since_flare(m, peaks)
    hard = hel1os_minute_features(cfg)
    m = m.merge(hard[["time"] + HARD_FEATURES], on="time", how="left")
    m[HARD_FEATURES] = m[HARD_FEATURES].fillna(0.0)
    m = m.dropna(subset=FEATURES).reset_index(drop=True)
    # Forecasting discipline: keep only quiescent samples (no flare in progress),
    # so the model predicts onset rather than nowcasting a flare already underway.
    st, en = flare_intervals(cfg)
    quiescent = ~in_flare_mask(m["time"].to_numpy(), st, en)
    m = m[quiescent].reset_index(drop=True)
    if verbose:
        print(f"Quiescent samples (in-flare excluded): {len(m):,} "
              f"({100*quiescent.mean():.1f}% kept)")
    split = m["time"].quantile(1 - test_frac)
    feats_both = FEATURES + HARD_FEATURES

    # 1) Model comparison at the primary horizon (soft+hard, calibrated).
    m["target"] = make_labels(m, peaks, primary)
    tr, te = m[m["time"] <= split], m[m["time"] > split]
    model_comparison = {}
    for name in candidates:
        try:
            model_comparison[name] = models.fit_eval(name, tr, te, feats_both)["metrics"]
        except Exception as exc:                       # e.g. lightgbm missing
            if verbose:
                print(f"  model {name} skipped: {exc}")
    best = max(model_comparison,
              key=lambda n: model_comparison[n]["ROC_AUC"] or 0.0)

    # 2) Skill vs lead-time with the best model: soft vs soft+hard.
    keep = ["TSS", "HSS", "ROC_AUC", "precision", "TPR_recall", "false_alarm_ratio"]
    sweep, primary_soft, primary_both = [], None, None
    for hz in horizons:
        m["target"] = make_labels(m, peaks, hz)
        tr, te = m[m["time"] <= split], m[m["time"] > split]
        s = _evaluate(best, tr, te, FEATURES, peaks, hz, m)
        b = _evaluate(best, tr, te, feats_both, peaks, hz, m)
        sweep.append({"horizon_min": hz,
                      "soft": {k: s["metrics"][k] for k in keep},
                      "soft_plus_hard": {k: b["metrics"][k] for k in keep},
                      "median_lead_min": b["lead"]["median_lead_min"],
                      "event_recall": b["lead"]["event_recall"]})
        if hz == primary:
            primary_soft, primary_both = s, b

    # 3) Walk-forward (expanding-window) CV for the best model at primary.
    m["target"] = make_labels(m, peaks, primary)
    walkfwd = models.walk_forward(best, m, feats_both, n_splits=5)

    report = {
        "target_class": f"{target_class}+",
        "split_time": str(split),
        "n_train": int((m["time"] <= split).sum()),
        "n_test": int((m["time"] > split).sum()),
        "primary_horizon_min": primary,
        "best_model": best,
        "model_comparison": model_comparison,
        "walk_forward_cv": walkfwd,
        "skill_vs_leadtime": sweep,
        "primary_soft_only": primary_soft["metrics"],
        "primary_soft_plus_hard": primary_both["metrics"],
        "fusion_benefit": {
            "precision_gain": round((primary_both["metrics"]["precision"] or 0)
                                    - (primary_soft["metrics"]["precision"] or 0), 3),
            "false_alarm_drop": round(primary_soft["metrics"]["false_alarm_ratio"]
                                      - primary_both["metrics"]["false_alarm_ratio"], 3),
        },
        "primary_lead_time": primary_both["lead"],
        "top_features": _importances(best, m[m["time"] <= split], feats_both),
    }

    # Persist best model + probability series + lead times.
    dump({"model": primary_both["model"], "features": feats_both,
          "threshold": primary_both["thr"], "horizon_min": primary,
          "model_name": best}, cfg.paths["models"] / "flare_forecaster.joblib")
    out_dir = cfg.paths["forecasting"]
    (out_dir / "forecast_metrics.json").write_text(json.dumps(report, indent=2))
    prob_series = m[["time"]].copy()
    prob_series["prob"] = primary_both["prob_full"]
    prob_series["in_test"] = prob_series["time"] > split
    prob_series.to_parquet(out_dir / "forecast_probability.parquet", index=False)
    pd.DataFrame({"lead_min": primary_both["lead_raw"]}).to_csv(
        out_dir / "lead_times.csv", index=False)

    if verbose:
        print("=== FORECAST (chronological, leakage-free) ===")
        print(f"{target_class}+ | primary {primary} min | best model: {best}")
        print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
