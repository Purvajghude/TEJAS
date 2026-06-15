import pandas as pd
from pathlib import Path

# ==========================
# CONFIGURATION
# ==========================

MAX_TIME_DIFF = 120  # seconds

# ==========================
# LOAD CATALOGS
# ==========================

solexs = pd.read_csv(
    "outputs/catalogs/solexs_catalog.csv"
)

hel1os = pd.read_csv(
    "outputs/catalogs/hel1os_catalog.csv"
)

# ==========================
# CONVERT TIMES
# ==========================

solexs["peak_time"] = pd.to_datetime(
    solexs["peak_time"]
)

hel1os["peak_time"] = pd.to_datetime(
    hel1os["peak_time"]
)

# ==========================
# EVENT MATCHING
# ==========================

matches = []

used_hel1os = set()

for _, sflare in solexs.iterrows():

    s_time = sflare["peak_time"]

    # Ignore HEL1OS events already matched
    candidates = hel1os[
        ~hel1os["flare_id"].isin(
            used_hel1os
        )
    ].copy()

    if len(candidates) == 0:
        break

    candidates["time_diff"] = (
        candidates["peak_time"] - s_time
    ).abs()

    nearest = candidates.loc[
        candidates["time_diff"].idxmin()
    ]

    diff_seconds = (
        nearest["time_diff"]
        .total_seconds()
    )

    # Match only if within threshold
    if diff_seconds <= MAX_TIME_DIFF:

        matches.append({

            "solexs_id":
                sflare["flare_id"],

            "hel1os_id":
                nearest["flare_id"],

            "solexs_peak":
                s_time,

            "hel1os_peak":
                nearest["peak_time"],

            "time_diff_sec":
                round(diff_seconds, 2)

        })

        used_hel1os.add(
            nearest["flare_id"]
        )

# ==========================
# CREATE DATAFRAME
# ==========================

match_df = pd.DataFrame(matches)

# ==========================
# SAVE RESULTS
# ==========================

Path(
    "outputs/fusion"
).mkdir(
    parents=True,
    exist_ok=True
)

output_file = (
    "outputs/fusion/event_matches.csv"
)

match_df.to_csv(
    output_file,
    index=False
)

# ==========================
# REPORT
# ==========================

print("\n")
print("=" * 60)
print("             EVENT MATCH REPORT")
print("=" * 60)

if len(match_df) > 0:

    print("\nMatched Events:\n")
    print(match_df)

else:

    print(
        "\nNo matching events found "
        f"within {MAX_TIME_DIFF} seconds."
    )

print("\n")
print("Total SoLEXS Events :", len(solexs))
print("Total HEL1OS Events :", len(hel1os))
print("Valid Matches       :", len(match_df))

print("\nSaved :", output_file)
print("=" * 60)