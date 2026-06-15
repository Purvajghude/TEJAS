import pandas as pd

from pathlib import Path

from sklearn.model_selection import (
    train_test_split
)

from sklearn.ensemble import (
    RandomForestClassifier
)

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score
)

from joblib import dump

# =====================================
# LOAD DATASET
# =====================================

dataset = pd.read_csv(
    "outputs/forecasting/training_dataset.csv"
)

print("\nDataset Loaded")
print("Rows :", len(dataset))

# =====================================
# FEATURES
# =====================================

features = [

    "solexs_count",
    "hel1os_ctr",

    "solexs_mean_60",
    "solexs_std_60",

    "hel1os_mean_60",
    "hel1os_std_60"

]

X = dataset[features]

y = dataset["target"]

# =====================================
# TRAIN TEST SPLIT
# =====================================

X_train, X_test, y_train, y_test = (
    train_test_split(

        X,
        y,

        test_size=0.2,

        random_state=42,

        stratify=y
    )
)

print("\nTraining Samples :", len(X_train))
print("Testing Samples  :", len(X_test))

# =====================================
# MODEL
# =====================================

model = RandomForestClassifier(

    n_estimators=200,

    max_depth=10,

    random_state=42,

    class_weight="balanced"
)

print("\nTraining Model...")

model.fit(
    X_train,
    y_train
)

# =====================================
# PREDICTION
# =====================================

predictions = model.predict(
    X_test
)

# =====================================
# METRICS
# =====================================

print("\n")
print("=" * 60)
print("MODEL PERFORMANCE")
print("=" * 60)

print(
    "\nAccuracy :",
    round(
        accuracy_score(
            y_test,
            predictions
        ),
        4
    )
)

print("\nConfusion Matrix\n")

print(
    confusion_matrix(
        y_test,
        predictions
    )
)

print("\nClassification Report\n")

print(
    classification_report(
        y_test,
        predictions
    )
)

# =====================================
# FEATURE IMPORTANCE
# =====================================

importance = pd.DataFrame({

    "feature":
    features,

    "importance":
    model.feature_importances_

})

importance = importance.sort_values(
    by="importance",
    ascending=False
)

print("\nFeature Importance\n")

print(importance)

# =====================================
# SAVE MODEL
# =====================================

Path(
    "outputs/models"
).mkdir(

    parents=True,
    exist_ok=True
)

model_file = (
    "outputs/models/"
    "flare_forecast_rf.joblib"
)

dump(
    model,
    model_file
)

print("\nModel Saved:")
print(model_file)

print("\n")
print("=" * 60)