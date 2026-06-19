"""Export pipeline outputs into a single JS payload for the WebGL dashboard.

Writes ``app/web/data/data.js`` defining ``window.TEJAS`` with everything the
command-center UI needs: KPIs, the flare list (with pseudo solar-disk positions
for the 3D Sun), a downsampled light curve, class distribution, recovery, the
calibration scatter, and forecast metrics.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .config import Config, load_config

CLASS_ORDER = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}


def _disk_position(seed: int, letter: str) -> dict:
    """Stable pseudo active-region position on the visible solar disk.

    SoLEXS is a Sun-as-a-star spectrometer (no imaging), so positions are
    illustrative — seeded per flare and clustered into a few 'active regions'.
    """
    rng = np.random.default_rng(seed)
    # Cluster flares into 3 synthetic active regions for a realistic look.
    centers = [(-28, 18), (22, -12), (5, 30)]
    cx, cy = centers[seed % len(centers)]
    lon = cx + rng.normal(0, 12)
    lat = cy + rng.normal(0, 10)
    lon = float(np.clip(lon, -75, 75))
    lat = float(np.clip(lat, -60, 60))
    return {"lon": lon, "lat": lat}


def build_payload(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    cat = pd.read_csv(cfg.paths["catalogs"] / "solexs_flares.csv",
                      parse_dates=["start_time", "peak_time", "end_time"])
    val = json.loads((cfg.paths["catalogs"] / "validation.json").read_text())
    lc = pd.read_parquet(cfg.paths["outputs"] / "processed" / "lightcurve.parquet")

    fc_path = cfg.paths["forecasting"] / "forecast_metrics.json"
    forecast = json.loads(fc_path.read_text()) if fc_path.exists() else None

    fus_path = cfg.paths["fusion"] / "fusion_report.json"
    fusion = json.loads(fus_path.read_text()) if fus_path.exists() else None

    cmp_path = cfg.paths["forecasting"] / "model_comparison.json"
    modelcmp = json.loads(cmp_path.read_text()) if cmp_path.exists() else None

    ens_path = cfg.paths["forecasting"] / "ensemble_metrics.json"
    ensemble = json.loads(ens_path.read_text()) if ens_path.exists() else None

    mc_path = cfg.paths["forecasting"] / "multiclass_metrics.json"
    multiclass = json.loads(mc_path.read_text()) if mc_path.exists() else None
    # Class-resolved probability track (10-min peak) for live C/M/X bars.
    mct_path = cfg.paths["forecasting"] / "multiclass_probability.parquet"
    mc_track = None
    if mct_path.exists():
        mt = pd.read_parquet(mct_path)
        mt["t10"] = mt["time"].dt.floor("10min")
        cols = [c for c in ("p_C", "p_M", "p_X") if c in mt.columns]
        tg = mt.groupby("t10")[cols].max().reset_index()
        mc_track = {"t": [t.isoformat() for t in tg["t10"]]}
        for c in cols:
            mc_track[c] = [round(float(v), 4) for v in tg[c]]

    qpp_path = cfg.paths["catalogs"] / "qpp_report.json"
    qpp = json.loads(qpp_path.read_text()) if qpp_path.exists() else None
    # Ensemble probability track (10-min peak), the live forecast-alert driver.
    tl_path = cfg.paths["forecasting"] / "ensemble_timeline.parquet"
    forecast_track = None
    if tl_path.exists():
        tl = pd.read_parquet(tl_path)
        tl["t10"] = tl["time"].dt.floor("10min")
        tg = tl.groupby("t10")["p_ens"].max().reset_index()
        forecast_track = {"t": [t.isoformat() for t in tg["t10"]],
                          "p": [round(float(p), 4) for p in tg["p_ens"]]}

    # --- Flares ----------------------------------------------------------
    cat = cat.sort_values("peak_time").reset_index(drop=True)
    flares = []
    for i, r in cat.iterrows():
        letter = str(r["class_solexs"])[0]
        pos = _disk_position(i, letter)
        flares.append({
            "id": r["flare_id"],
            "t": r["peak_time"].isoformat(),
            "start": r["start_time"].isoformat(),
            "end": r["end_time"].isoformat(),
            "cls": r["class_solexs"],
            "clsGoes": r["class_goes"] if pd.notna(r["class_goes"]) else None,
            "letter": letter,
            "counts": float(r["peak_counts"]),
            "flux": float(r["flux_pred"]) if pd.notna(r.get("flux_pred")) else None,
            "fluxGoes": float(r["flux_goes"]) if pd.notna(r.get("flux_goes")) else None,
            "sig": float(r["peak_significance"]),
            "durMin": round(float(r["duration_s"]) / 60, 1),
            "lon": pos["lon"], "lat": pos["lat"],
        })

    # --- Downsampled light curve (10-min): soft + GOES + hard X-ray -------
    lc = lc.dropna(subset=["counts"]).copy()
    lc["t10"] = lc["time"].dt.floor("10min")
    g = lc.groupby("t10").agg(counts=("counts", "mean"),
                              xrsb=("xrsb", "mean")).reset_index()
    # overlay HEL1OS hard X-ray on the same 10-min grid, if available
    hel_path = cfg.paths["outputs"] / "processed" / "hel1os_lightcurve.parquet"
    hard_map = {}
    if hel_path.exists():
        hlc = pd.read_parquet(hel_path)
        hlc["t10"] = hlc["time"].dt.floor("10min")
        hg = hlc.groupby("t10").agg(broad=("broad", "mean")).reset_index()
        hard_map = dict(zip(hg["t10"], hg["broad"]))
    light = {
        "t": [t.isoformat() for t in g["t10"]],
        "counts": [round(float(c), 1) for c in g["counts"]],
        "xrsb": [None if not np.isfinite(x) else float(f"{x:.3e}")
                 for x in g["xrsb"]],
        "hard": [None if t not in hard_map or not np.isfinite(hard_map[t])
                 else round(float(hard_map[t]), 1) for t in g["t10"]],
    }

    # --- Distributions / scatter ----------------------------------------
    dist = {k: int((cat["class_solexs"].str[0] == k).sum())
            for k in ["A", "B", "C", "M", "X"]}
    scat = cat.dropna(subset=["flux_goes"])
    scatter = [[float(c), float(f), str(cl)[0]]
               for c, f, cl in zip(scat["peak_counts"], scat["flux_goes"],
                                   scat["class_goes"])]

    payload = {
        "meta": {
            "dateStart": val["date_range"][0][:10],
            "dateEnd": val["date_range"][1][:10],
            "nDays": val["n_days"],
        },
        "kpis": {
            "nFlares": val["n_flares"],
            "nX": dist["X"], "nM": dist["M"], "nC": dist["C"],
            "agreement": val["goes_letter_class_agreement"],
            "calibR": val["peak_calibration"]["r"],
            "xRecovered": val["recovery"]["by_class"].get("X", [0, 0]),
            "recallOverall": val["recovery"]["recall_overall"],
        },
        "flares": flares,
        "light": light,
        "dist": dist,
        "recovery": val["recovery"]["by_class"],
        "scatter": scatter,
        "calib": val["peak_calibration"],
        "fusion": ({
            "nSoft": fusion["n_soft"],
            "nHard": fusion["n_hard"],
            "nDualConfirmed": fusion["n_dual_confirmed"],
            "dualByClass": fusion["dual_confirm_by_class"],
            "neupertLeadMedianS": fusion["neupert"]["median_lead_s"],
            "neupertN": fusion["neupert"]["n_with_lead"],
        } if fusion else None),
        "forecast": ({
            "primaryHorizon": forecast["primary_horizon_min"],
            "skillCurve": [
                {"h": s["horizon_min"],
                 "auc": s["soft_plus_hard"]["ROC_AUC"],
                 "aucSoft": s["soft"]["ROC_AUC"],
                 "tss": s["soft_plus_hard"]["TSS"],
                 "precision": s["soft_plus_hard"]["precision"],
                 "precisionSoft": s["soft"]["precision"],
                 "far": s["soft_plus_hard"]["false_alarm_ratio"],
                 "lead": s["median_lead_min"]}
                for s in forecast["skill_vs_leadtime"]],
            "primary": forecast["primary_soft_plus_hard"],
            "fusionBenefit": forecast["fusion_benefit"],
            "leadMedian": forecast["primary_lead_time"].get("median_lead_min"),
            "eventRecall": forecast["primary_lead_time"].get("event_recall"),
            "bestModel": forecast.get("best_model"),
            "walkForward": forecast.get("walk_forward_cv"),
        } if forecast else None),
        "modelComparison": ({
            "horizon": modelcmp["horizon_min"],
            "winner": modelcmp["winner_by_auc"],
            "ranking": [{"model": r["model"], "auc": r["ROC_AUC"],
                         "tss": r["TSS"], "precision": r["precision"]}
                        for r in modelcmp["ranking"]],
        } if modelcmp else None),
        "ensemble": ({
            "auc": ensemble["test_metrics"]["ensemble"]["ROC_AUC"],
            "prAuc": ensemble["test_metrics"]["ensemble"].get("PR_AUC"),
            "tss": ensemble["test_metrics"]["ensemble"]["TSS"],
            "brier": ensemble["test_metrics"]["ensemble"]["Brier"],
            "horizon": ensemble["primary_horizon_min"],
            "leadMedian": ensemble["lead_time"].get("median_lead_min"),
            "operatingPoints": ensemble.get("operating_points"),
            "lowFarThreshold": (ensemble.get("operating_points", {})
                                .get("low_far_1_per_day", {}).get("threshold")),
            "track": forecast_track,
        } if ensemble else None),
        "multiclass": ({
            "horizon": multiclass["primary_horizon_min"],
            "classes": {c: {"auc": v["metrics"]["ROC_AUC"],
                            "prAuc": v["metrics"]["PR_AUC"],
                            "recall": v["event_recall"],
                            "lead": v["median_lead_min"],
                            "label": v["label"]}
                        for c, v in multiclass["classes"].items()},
            "track": mc_track,
        } if multiclass else None),
        "qpp": ({
            "fraction": qpp["qpp_fraction"],
            "nDetected": qpp["n_qpp_detected"],
            "nAnalysed": qpp["n_flares_analysed"],
            "medianPeriodS": qpp["median_qpp_period_s"],
            "periodRangeS": qpp["period_range_s"],
        } if qpp else None),
    }
    return payload


def export(cfg: Config | None = None, verbose: bool = True) -> None:
    cfg = cfg or load_config()
    payload = build_payload(cfg)
    out = cfg.paths["outputs"].parent / "app" / "web" / "data" / "data.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.TEJAS = " + json.dumps(payload) + ";",
                   encoding="utf-8")
    if verbose:
        size_kb = out.stat().st_size / 1024
        print(f"Exported {len(payload['flares'])} flares, "
              f"{len(payload['light']['t'])} light-curve points "
              f"-> {out}  ({size_kb:.0f} KiB)")


if __name__ == "__main__":
    export()
