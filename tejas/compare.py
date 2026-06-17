"""Honest head-to-head: logistic vs RF vs LightGBM vs GOES-pretrained TCN.

All models are evaluated on the **same chronological test set** (Aditya-L1,
Oct 2024) at the **same horizon** (the forecaster's primary, 30 min), so the
table is apples-to-apples. The winner is selected by ROC-AUC (threshold-free
skill); precision / false-alarm rate are reported for the operational view.
"""

from __future__ import annotations

import json

from .config import Config, load_config

_KEYS = ["ROC_AUC", "TSS", "HSS", "precision", "TPR_recall",
         "false_alarm_ratio", "Brier"]


def _pick(m: dict) -> dict:
    return {k: m.get(k) for k in _KEYS}


def run(cfg: Config | None = None, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    fc = json.loads((cfg.paths["forecasting"] / "forecast_metrics.json").read_text())
    rows = [{"model": name, **_pick(mt)}
            for name, mt in fc["model_comparison"].items()]

    tcn_path = cfg.paths["forecasting"] / "tcn_metrics.json"
    if tcn_path.exists():
        tcn = json.loads(tcn_path.read_text())
        rows.append({"model": "tcn_transfer", **_pick(tcn["metrics_test"])})

    rows.sort(key=lambda r: (r["ROC_AUC"] or 0), reverse=True)
    winner = rows[0]["model"] if rows else None
    report = {
        "horizon_min": fc.get("primary_horizon_min"),
        "test_period": fc.get("split_time"),
        "n_test": fc.get("n_test"),
        "ranking": rows,
        "winner_by_auc": winner,
        "note": ("TCN evaluated on 120-min windows over the same test period; "
                 "tree/logistic on per-minute engineered features. Same horizon "
                 "and chronological test set."),
    }
    (cfg.paths["forecasting"] / "model_comparison.json").write_text(
        json.dumps(report, indent=2))

    if verbose:
        print("=== MODEL HEAD-TO-HEAD (same test set, horizon "
              f"{report['horizon_min']} min) ===")
        print(f"{'model':>14} {'AUC':>6} {'TSS':>6} {'HSS':>6} "
              f"{'prec':>6} {'recall':>7} {'FAR':>6} {'Brier':>7}")
        for r in rows:
            print(f"{r['model']:>14} {r['ROC_AUC']!s:>6} {r['TSS']!s:>6} "
                  f"{r['HSS']!s:>6} {r['precision']!s:>6} {r['TPR_recall']!s:>7} "
                  f"{r['false_alarm_ratio']!s:>6} {r['Brier']!s:>7}")
        print(f"\nwinner by ROC-AUC: {winner}")
    return report


if __name__ == "__main__":
    run()
