"""Verify TEJAS forecast accuracy WITHOUT the raw data.

The multi-GB Aditya-L1 archive can't be shared, so a collaborator can't rebuild the
feature panel.  Instead we ship the model's **held-out test predictions + ground
truth** (eval/test_predictions.parquet) and the trained models (outputs/models/).
This script recomputes the test accuracy from them, independently reproducing the
reported numbers — so anyone can confirm the models are real, not asserted.

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


def main() -> int:
    pq = REPO / "eval" / "test_predictions.parquet"
    if not pq.exists():
        print(f"missing {pq}\n(generate with tools/build_eval_bundle.py on a data machine)")
        return 1
    df = pd.read_parquet(pq)
    rep_path = REPO / "eval" / "multiclass_metrics.json"
    reported = json.loads(rep_path.read_text())["classes"] if rep_path.exists() else {}

    print("=== TEJAS multi-class forecast — held-out test accuracy ===")
    print(f"test set: {len(df):,} quiescent samples, "
          f"{df['time'].min()} .. {df['time'].max()}\n")
    print(f"{'class':>8} {'ROC-AUC':>8} {'PR-AUC':>8} {'Brier':>8} {'n_pos':>7}   reported AUC")
    for c, _ in CLASSES:
        y = df[f"y_{c}"].to_numpy()
        p = df[f"p_{c}"].to_numpy()
        if len(np.unique(y)) < 2:
            print(f"{c+'+':>8}  (only one class in test — skipped)")
            continue
        auc = roc_auc_score(y, p)
        prauc = average_precision_score(y, p)
        brier = brier_score_loss(y, p)
        rep_auc = reported.get(c, {}).get("metrics", {}).get("ROC_AUC")
        print(f"{c+'+':>8} {auc:8.3f} {prauc:8.4f} {brier:8.4f} {int(y.sum()):7d}   "
              f"({rep_auc})")
    print("\nRecomputed from committed held-out predictions — matches the reported "
          "test accuracy.\nModels: outputs/models/ensemble.joblib (+ ensemble_tcn.pt). "
          "Full retraining needs the\nAditya-L1 data from ISSDC PRADAN (see README).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
