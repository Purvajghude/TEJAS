"""Forecasting models, calibration, and time-aware evaluation.

Candidate models for the (small, tabular, imbalanced) forecasting task:
  * ``logistic`` — interpretable linear baseline (the bar to beat)
  * ``rf``       — random forest
  * ``lgbm``     — gradient-boosted trees (usually best on tabular)

Probabilities are calibrated with **time-aware isotonic regression** (fit the base
model on the earlier part of train, calibrate on the later part) so the output
probabilities are trustworthy — essential for a reliability diagram and Brier score.
Skill is also estimated with **walk-forward (expanding-window) CV**, not a single split.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score, roc_curve)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class CalibratedModel:
    """A fitted base classifier with an isotonic probability calibrator.

    Version-proof replacement for ``CalibratedClassifierCV(cv='prefit')``:
    the base is fit on the earlier part of train, the isotonic map on a later
    held-out slice — time-aware calibration. Picklable for joblib.
    """

    def __init__(self, base, iso: IsotonicRegression):
        self.base = base
        self.iso = iso

    def predict_proba(self, X):
        p = self.base.predict_proba(X)[:, 1]
        pc = np.clip(self.iso.predict(p), 0.0, 1.0)
        return np.column_stack([1.0 - pc, pc])


def make_model(name: str):
    if name == "logistic":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0))
    if name == "rf":
        return RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=50,
            class_weight="balanced", n_jobs=-1, random_state=42)
    if name == "lgbm":
        import lightgbm as lgb
        return lgb.LGBMClassifier(
            n_estimators=500, learning_rate=0.03, num_leaves=31,
            subsample=0.8, colsample_bytree=0.8, min_child_samples=40,
            class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1)
    raise ValueError(f"unknown model {name!r}")


def best_threshold(y_true: np.ndarray, prob: np.ndarray) -> tuple[float, float]:
    """Decision threshold maximising TSS = TPR - FPR."""
    fpr, tpr, thr = roc_curve(y_true, prob)
    tss = tpr - fpr
    i = int(np.argmax(tss))
    return float(thr[i]), float(tss[i])


def score(y_true: np.ndarray, prob: np.ndarray, thr: float) -> dict:
    """Full skill-score panel at a given decision threshold."""
    y_true = np.asarray(y_true)
    yhat = (prob >= thr).astype(int)
    tp = int(((yhat == 1) & (y_true == 1)).sum())
    fp = int(((yhat == 1) & (y_true == 0)).sum())
    tn = int(((yhat == 0) & (y_true == 0)).sum())
    fn = int(((yhat == 0) & (y_true == 1)).sum())
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    far = fp / (tp + fp) if (tp + fp) else 0.0
    n = tp + fp + tn + fn
    exp = ((tp + fn) * (tp + fp) + (tn + fn) * (tn + fp)) / n if n else 0.0
    hss = (tp + tn - exp) / (n - exp) if (n - exp) else 0.0
    two_class = len(np.unique(y_true)) > 1
    auc = roc_auc_score(y_true, prob) if two_class else float("nan")
    # PR-AUC (average precision): the threshold-free metric that actually reflects
    # skill on a rare positive class — far more informative than ROC-AUC here.
    pr_auc = average_precision_score(y_true, prob) if two_class else float("nan")
    return {
        "TSS": round(tpr - fpr, 3), "HSS": round(hss, 3),
        "ROC_AUC": round(float(auc), 3), "PR_AUC": round(float(pr_auc), 4),
        "Brier": round(float(brier_score_loss(y_true, prob)), 4),
        "precision": round(1 - far, 3) if (tp + fp) else None,
        "TPR_recall": round(tpr, 3), "FPR": round(fpr, 3),
        "false_alarm_ratio": round(far, 3),
        "confusion": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
    }


def fit_eval(name: str, train: pd.DataFrame, test: pd.DataFrame,
             features: list[str], calibrate: bool = True):
    """Fit ``name`` on train (time-aware isotonic calibration), score on test."""
    train = train.sort_values("time")
    n = len(train)
    cut = int(n * 0.8)
    core, calib = train.iloc[:cut], train.iloc[cut:]
    base = make_model(name)

    if calibrate and len(calib) > 50 and calib["target"].nunique() > 1:
        base.fit(core[features], core["target"])
        pcal_raw = base.predict_proba(calib[features])[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(pcal_raw, calib["target"].to_numpy())
        model = CalibratedModel(base, iso)
        # threshold from the calibration slice (still in-sample, not test)
        pcal = model.predict_proba(calib[features])[:, 1]
        thr, _ = best_threshold(calib["target"].to_numpy(), pcal)
    else:
        model = base
        model.fit(train[features], train["target"])
        ptr = model.predict_proba(train[features])[:, 1]
        thr, _ = best_threshold(train["target"].to_numpy(), ptr)

    pte = model.predict_proba(test[features])[:, 1]
    metrics = score(test["target"].to_numpy(), pte, thr)
    return {"name": name, "metrics": metrics, "model": model,
            "thr": float(thr), "prob_test": pte}


def walk_forward(name: str, data: pd.DataFrame, features: list[str],
                 n_splits: int = 5) -> dict:
    """Expanding-window CV: robust mean+/-std skill across time."""
    data = data.sort_values("time").reset_index(drop=True)
    tss_split = TimeSeriesSplit(n_splits=n_splits)
    aucs, tsss = [], []
    for tr_idx, te_idx in tss_split.split(data):
        tr, te = data.iloc[tr_idx], data.iloc[te_idx]
        if tr["target"].nunique() < 2 or te["target"].nunique() < 2:
            continue
        m = make_model(name)
        m.fit(tr[features], tr["target"])
        p = m.predict_proba(te[features])[:, 1]
        aucs.append(roc_auc_score(te["target"], p))
        thr, _ = best_threshold(tr["target"].to_numpy(),
                                m.predict_proba(tr[features])[:, 1])
        s = score(te["target"].to_numpy(), p, thr)
        tsss.append(s["TSS"])
    return {
        "n_folds": len(aucs),
        "ROC_AUC_mean": round(float(np.mean(aucs)), 3) if aucs else None,
        "ROC_AUC_std": round(float(np.std(aucs)), 3) if aucs else None,
        "TSS_mean": round(float(np.mean(tsss)), 3) if tsss else None,
        "TSS_std": round(float(np.std(tsss)), 3) if tsss else None,
    }
