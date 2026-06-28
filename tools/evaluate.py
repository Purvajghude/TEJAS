"""Verify TEJAS forecast accuracy WITHOUT the raw data.

The multi-GB Aditya-L1 archive can't be shared, so a collaborator can't rebuild the
feature panel.  Instead we ship the model's **held-out test predictions + ground
truth** (eval/test_predictions.parquet) and the trained models (outputs/models/).
This script recomputes the test accuracy from them, independently reproducing the
reported numbers — so anyone can confirm the models are real, not asserted.

Also prints:
  - 95 % bootstrap CI on ROC-AUC (critical for X+ where n_pos ≈ 14 events)
  - Baseline comparison table (if eval/benchmark.json exists)

    python main.py evaluate
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score)

REPO = Path(__file__).resolve().parent.parent
CLASSES = [("C", "low"), ("M", "medium"), ("X", "high")]


def _bootstrap_auc_ci(y, p, n_boot=1000, ci=0.95, seed=42):
    rng = np.random.default_rng(seed)
    n = len(y)
    boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yb, pb = y[idx], p[idx]
        if len(np.unique(yb)) < 2:
            continue
        try:
            boot.append(float(roc_auc_score(yb, pb)))
        except Exception:
            pass
    if not boot:
        return None, None
    alpha = (1 - ci) / 2
    return (round(float(np.percentile(boot, 100 * alpha)), 3),
            round(float(np.percentile(boot, 100 * (1 - alpha))), 3))


def main() -> int:
    pq = REPO / "eval" / "test_predictions.parquet"
    if not pq.exists():
        print(f"missing {pq}\n(generate with tools/build_eval_bundle.py on a data machine)")
        return 1
    df = pd.read_parquet(pq)
    rep_path = REPO / "eval" / "multiclass_metrics.json"
    reported = json.loads(rep_path.read_text())["classes"] if rep_path.exists() else {}

    print("=" * 72)
    print("  TEJAS — held-out test accuracy (eval/ bundle, no raw data needed)")
    print("=" * 72)
    print(f"  test set: {len(df):,} quiescent samples "
          f"({df['time'].min()} → {df['time'].max()})\n")
    print(f"  {'class':>5} {'n_pos':>6} {'AUC':>7} {'95% CI':^15} "
          f"{'PR-AUC':>7} {'Brier':>7}   reported")
    print("  " + "-" * 68)

    for c, _ in CLASSES:
        y = df[f"y_{c}"].to_numpy()
        p = df[f"p_{c}"].to_numpy()
        n_pos = int(y.sum())
        if len(np.unique(y)) < 2:
            print(f"  {c+'+':>5} {n_pos:>6}  (single class in test — metrics not computable)")
            continue
        auc = roc_auc_score(y, p)
        prauc = average_precision_score(y, p)
        brier = brier_score_loss(y, p)
        ci_lo, ci_hi = _bootstrap_auc_ci(y, p)
        ci_str = f"[{ci_lo:.3f}, {ci_hi:.3f}]" if ci_lo else "  n/a         "
        rep_auc = reported.get(c, {}).get("metrics", {}).get("ROC_AUC")
        small = " ⚠  small sample" if n_pos < 30 else ""
        print(f"  {c+'+':>5} {n_pos:>6} {auc:>7.3f} {ci_str:^15} "
              f"{prauc:>7.4f} {brier:>7.4f}   ({rep_auc}){small}")

    print(
        "\n  ⚠  X+ n_pos is small — the CI is wide and the point AUC is unreliable.\n"
        "  Report the CI alongside the point estimate in any presentation.\n"
    )

    # Ensemble summary from committed JSON (no parquet needed for these).
    ens_path = REPO / "eval" / "ensemble_metrics.json"
    if ens_path.exists():
        ens = json.loads(ens_path.read_text())
        em = ens["test_metrics"]["ensemble"]
        op = ens.get("operating_points", {})
        prec_op = op.get("low_far_1_per_day", {})
        rec_op = op.get("recall_max", {})
        lt = ens.get("lead_time", {})
        lt_prec = ens.get("lead_time_precision_op", {})
        print("  " + "=" * 68)
        print("  TCN + LightGBM ENSEMBLE (M+, 30-min, untouched test set)")
        print("  " + "-" * 68)
        print(f"  AUC {em['ROC_AUC']}  |  TSS {em['TSS']}  |  Brier {em['Brier']}  "
              f"|  PR-AUC {em.get('PR_AUC', 'n/a')}")
        print()
        print(f"  Operating point A — precision  (≤ 1 FA/day):  "
              f"recall {prec_op.get('event_recall', 'n/a')}  "
              f"FA/day {prec_op.get('false_alarms_per_day', 'n/a')}  "
              f"ep_prec {prec_op.get('episode_precision', 'n/a')}")
        if lt_prec:
            print(f"    lead to peak   median {lt_prec.get('median_lead_to_peak_min', lt_prec.get('median_lead_min', 'n/a'))} min")
            if lt_prec.get("median_lead_to_onset_min") is not None:
                print(f"    lead to onset  median {lt_prec.get('median_lead_to_onset_min')} min  "
                      f"({100*lt_prec.get('pct_alerts_before_onset',0):.0f}% before flare starts)")
        print()
        print(f"  Operating point B — recall-max (~8 FA/day):   "
              f"recall {rec_op.get('event_recall', 'n/a')}  "
              f"FA/day {rec_op.get('false_alarms_per_day', 'n/a')}  "
              f"ep_prec {rec_op.get('episode_precision', 'n/a')}")
        if lt:
            print(f"    lead to peak   median {lt.get('median_lead_to_peak_min', lt.get('median_lead_min', 'n/a'))} min")
            if lt.get("median_lead_to_onset_min") is not None:
                print(f"    lead to onset  median {lt.get('median_lead_to_onset_min')} min  "
                      f"({100*lt.get('pct_alerts_before_onset',0):.0f}% before flare starts)")
        tcn_gain = ens.get("tcn_calibration_gain", {})
        if tcn_gain:
            print(f"\n  TCN contribution: Brier improved by {tcn_gain.get('brier_improvement_pct')} %  |  "
                  f"AUC gain vs LightGBM alone: {tcn_gain.get('auc_gain_vs_lgbm')}")
            print(f"  → {tcn_gain.get('interpretation')}")

    # Benchmark comparison table (if benchmark.json exists).
    bench_path = REPO / "eval" / "benchmark.json"
    if bench_path.exists():
        bench = json.loads(bench_path.read_text())
        print("\n  " + "=" * 68)
        print("  BASELINE COMPARISON  (same test set, 30-min M+ horizon)")
        print("  " + "-" * 68)
        print(f"  {'Model / Baseline':<42} {'TSS':>6} {'AUC':>6}")
        print("  " + "-" * 68)
        for r in bench["baselines"]:
            tss_s = f"{r['tss']:.3f}" if r.get("tss") is not None else "  n/a"
            auc_s = f"{r['auc']:.3f}" if r.get("auc") is not None else "  n/a"
            print(f"  {r['label']:<42} {tss_s:>6} {auc_s:>6}")
        print("  " + "-" * 68)
        print()
        print("  LITERATURE CONTEXT  (⚠ 24-hour horizon, magnetogram input — different task)")
        print("  " + "-" * 68)
        for L in bench.get("literature", []):
            tss_s = f"{L['tss']:.3f}" if L.get("tss") is not None else "  n/a"
            print(f"  {L['system']:<32} {L['horizon']:>8}  TSS {tss_s}  [{L['reference']}]")
        print()
        print(f"  {bench['literature_caveat']}")
    else:
        print("\n  (Run `python main.py benchmark` to generate baseline comparison table)")

    print("\n  Full retraining: Aditya-L1 data from ISSDC PRADAN → README for steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
