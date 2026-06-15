import joblib
import pandas as pd

# =====================================
# LOAD MODEL
# =====================================

model = joblib.load(
    "outputs/models/flare_forecast_rf.joblib"
)

# =====================================
# LOAD DATASET
# =====================================

df = pd.read_csv(
    "outputs/forecasting/training_dataset.csv"
)

latest = df.iloc[-1]

# =====================================
# FEATURES USED DURING TRAINING
# =====================================

feature_columns = [

    "solexs_count",
    "hel1os_ctr",
    "solexs_mean_60",
    "solexs_std_60",
    "hel1os_mean_60",
    "hel1os_std_60"

]

# Create dataframe with column names
feature_df = pd.DataFrame(
    [latest[feature_columns]]
)

# =====================================
# PREDICTION
# =====================================

prediction = model.predict(
    feature_df
)[0]

probability = model.predict_proba(
    feature_df
)[0][1]

# =====================================
# RISK LEVEL
# =====================================

if probability >= 0.80:

    risk = "VERY HIGH 🔴"

elif probability >= 0.60:

    risk = "HIGH 🟠"

elif probability >= 0.40:

    risk = "MODERATE 🟡"

else:

    risk = "LOW 🟢"

# =====================================
# REPORT
# =====================================

print("\n")
print("=" * 60)
print("         TEJAS FLARE FORECAST")
print("=" * 60)

print(
    "\nLatest Time :",
    latest["time"]
)

print(
    "\nFlare Probability :",
    f"{probability * 100:.2f}%"
)

print(
    "Prediction :",
    "FLARE LIKELY"
    if prediction == 1
    else "NO FLARE"
)

print(
    "Risk Level :",
    risk
)

print("\nFeature Values Used:\n")
print(feature_df)

print("\n")
print("=" * 60)