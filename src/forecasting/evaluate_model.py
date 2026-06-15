import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    classification_report,
    roc_auc_score
)

# =====================================
# LOAD DATA
# =====================================

df = pd.read_csv(
    "outputs/forecasting/training_dataset.csv"
)

X = df[[
    "solexs_count",
    "hel1os_ctr",
    "solexs_mean_60",
    "solexs_std_60",
    "hel1os_mean_60",
    "hel1os_std_60"
]]

y = df["target"]

# =====================================
# TRAIN TEST SPLIT
# =====================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

# =====================================
# LOAD MODEL
# =====================================

model = joblib.load(
    "outputs/models/flare_forecast_rf.joblib"
)

# =====================================
# PREDICTIONS
# =====================================

y_pred = model.predict(X_test)

y_prob = model.predict_proba(
    X_test
)[:, 1]

# =====================================
# METRICS
# =====================================

accuracy = accuracy_score(
    y_test,
    y_pred
)

auc = roc_auc_score(
    y_test,
    y_prob
)

# =====================================
# REPORT
# =====================================

print("\n")
print("=" * 60)
print("       MODEL EVALUATION REPORT")
print("=" * 60)

print(
    "\nAccuracy :",
    round(accuracy, 4)
)

print(
    "ROC-AUC  :",
    round(auc, 4)
)

print("\nConfusion Matrix\n")
print(
    confusion_matrix(
        y_test,
        y_pred
    )
)

print("\nClassification Report\n")
print(
    classification_report(
        y_test,
        y_pred
    )
)

print("\n")
print("=" * 60)