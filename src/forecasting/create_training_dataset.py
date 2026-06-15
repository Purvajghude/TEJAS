from astropy.io import fits
import pandas as pd
import numpy as np
from pathlib import Path

# =====================================
# CONFIGURATION
# =====================================

FORECAST_WINDOW = 3600   # 1 hour

# =====================================
# LOAD SOLEXS
# =====================================

solexs_file = (
    "data/raw/solexs/"
    "AL1_SLX_L1_20260612_v1.0/"
    "SDD2/"
    "AL1_SOLEXS_20260612_SDD2_L1.lc"
)

with fits.open(solexs_file) as hdul:

    data = hdul[1].data

    time = np.array(
        data["TIME"],
        dtype=np.float64
    )

    counts = np.array(
        data["COUNTS"],
        dtype=np.float64
    )

solexs = pd.DataFrame({

    "time": pd.to_datetime(
        time,
        unit="s",
        utc=True
    ).tz_localize(None),

    "solexs_count": counts

})

solexs = solexs.dropna()

# =====================================
# LOAD HEL1OS
# =====================================

hel1os_file = (
    "data/raw/hel1os/"
    "HLS_20260612_000011_43177sec_lev1_V111/"
    "2026/06/12/"
    "HLS_20260612_000011_43177sec_lev1_V111/"
    "cdte/lightcurve_cdte1.fits"
)

with fits.open(hel1os_file) as hdul:

    data = hdul[5].data

    isot = np.array(
        data["ISOT"],
        dtype=str
    )

    ctr = np.array(
        data["CTR"],
        dtype=np.float64
    )

hel1os = pd.DataFrame({

    "time": pd.to_datetime(
        isot
    ),

    "hel1os_ctr": ctr

})

hel1os = hel1os.dropna()

# =====================================
# SORT FOR MERGE
# =====================================

solexs = solexs.sort_values(
    "time"
)

hel1os = hel1os.sort_values(
    "time"
)

# =====================================
# MERGE LIGHT CURVES
# =====================================
# Force same datetime precision

solexs["time"] = pd.to_datetime(
    solexs["time"]
).astype("datetime64[ns]")

hel1os["time"] = pd.to_datetime(
    hel1os["time"]
).astype("datetime64[ns]")

print(
    "SoLEXS dtype:",
    solexs["time"].dtype
)

print(
    "HEL1OS dtype:",
    hel1os["time"].dtype
)
df = pd.merge_asof(

    solexs,

    hel1os,

    on="time",

    direction="nearest",

    tolerance=pd.Timedelta("5s")

)

df = df.dropna()

if len(df) == 0:

    raise ValueError(
        "Merge produced 0 rows. "
        "Increase tolerance or check timestamps."
    )

print("\nMerged rows:", len(df))
print("Start:", df["time"].min())
print("End  :", df["time"].max())

# =====================================
# FEATURE ENGINEERING
# =====================================

df["solexs_mean_60"] = (
    df["solexs_count"]
    .rolling(60)
    .mean()
)

df["solexs_std_60"] = (
    df["solexs_count"]
    .rolling(60)
    .std()
)

df["hel1os_mean_60"] = (
    df["hel1os_ctr"]
    .rolling(60)
    .mean()
)

df["hel1os_std_60"] = (
    df["hel1os_ctr"]
    .rolling(60)
    .std()
)

df = df.dropna()

# =====================================
# LOAD MASTER CATALOG
# =====================================

master = pd.read_csv(
    "outputs/fusion/master_catalog.csv"
)

flare_times = pd.to_datetime(
    master["solexs_peak"]
)

# =====================================
# TARGET CREATION
# =====================================

targets = []

for current_time in df["time"]:

    future_flares = flare_times[
        flare_times > pd.Timestamp(
            current_time
        )
    ]

    if len(future_flares) == 0:

        targets.append(0)
        continue

    next_flare = future_flares.min()

    diff = (
        next_flare - current_time
    ).total_seconds()

    if diff <= FORECAST_WINDOW:

        targets.append(1)

    else:

        targets.append(0)

df["target"] = targets

# =====================================
# FINAL CLEANUP
# =====================================

df = df.dropna()

# =====================================
# SAVE DATASET
# =====================================

Path(
    "outputs/forecasting"
).mkdir(
    parents=True,
    exist_ok=True
)

output_file = (
    "outputs/forecasting/"
    "training_dataset.csv"
)

df.to_csv(
    output_file,
    index=False
)

# =====================================
# REPORT
# =====================================

print("\n")
print("=" * 60)
print("      TRAINING DATASET CREATED")
print("=" * 60)

print("\nRows :", len(df))

print(
    "\nPositive Samples :",
    (df["target"] == 1).sum()
)

print(
    "Negative Samples :",
    (df["target"] == 0).sum()
)

print("\nSaved :", output_file)

print("\nDataset Columns:\n")
print(df.columns.tolist())

print("\nSample:\n")
print(df.head())

print("\n")
print("=" * 60)