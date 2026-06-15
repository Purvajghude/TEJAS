import pandas as pd
from pathlib import Path

# =========================
# LOAD MATCHED EVENTS
# =========================

matches = pd.read_csv(
    "outputs/fusion/event_matches.csv"
)

solexs = pd.read_csv(
    "outputs/catalogs/solexs_catalog.csv"
)

hel1os = pd.read_csv(
    "outputs/catalogs/hel1os_catalog.csv"
)

# =========================
# BUILD MASTER CATALOG
# =========================

master_catalog = []

for _, match in matches.iterrows():

    sflare = solexs[
        solexs["flare_id"] ==
        match["solexs_id"]
    ].iloc[0]

    hflare = hel1os[
        hel1os["flare_id"] ==
        match["hel1os_id"]
    ].iloc[0]

    master_catalog.append({

        "event_id":
        f"EVT-{len(master_catalog)+1:03d}",

        "solexs_id":
        sflare["flare_id"],

        "hel1os_id":
        hflare["flare_id"],

        "solexs_peak":
        match["solexs_peak"],

        "hel1os_peak":
        match["hel1os_peak"],

        "time_difference_sec":
        match["time_diff_sec"],

        "solexs_severity":
        sflare["severity"],

        "hel1os_severity":
        hflare["severity"],

        "solexs_peak_count":
        sflare["peak_count"],

        "hel1os_peak_ctr":
        hflare["peak_ctr"]

    })

# =========================
# SAVE
# =========================

master_df = pd.DataFrame(
    master_catalog
)

Path(
    "outputs/fusion"
).mkdir(
    parents=True,
    exist_ok=True
)

output_file = (
    "outputs/fusion/master_catalog.csv"
)

master_df.to_csv(
    output_file,
    index=False
)

# =========================
# REPORT
# =========================

print("\n")
print("=" * 70)
print("           TEJAS MASTER FLARE CATALOG")
print("=" * 70)

if len(master_df):

    print("\n")
    print(master_df)

else:

    print("\nNo matched events found.")

print("\n")
print("Total Master Events :", len(master_df))
print("Saved :", output_file)

print("=" * 70)