from astropy.io import fits
import numpy as np
import pandas as pd
from datetime import datetime, UTC
from pathlib import Path

file_path = list(Path("data/raw/solexs").rglob("*.lc"))[0]
print("Using:", file_path)

catalog = []

with fits.open(file_path) as hdul:

    data = hdul[1].data

    counts = data["COUNTS"]
    time = data["TIME"]

    # Remove NaN values
    mask = ~np.isnan(counts)

    counts = counts[mask]
    time = time[mask]

    # Detection Threshold
    mean_count = np.mean(counts)
    std_count = np.std(counts)
    threshold = mean_count + (3 * std_count)

    flare_mask = counts > threshold

    indices = np.where(flare_mask)[0]

    groups = np.split(
        indices,
        np.where(np.diff(indices) > 1)[0] + 1
    )

    print("\n")
    print("=" * 60)
    print("                TEJAS SOLAR FLARE REPORT")
    print("=" * 60)

    flare_count = 0

    for group in groups:

        start_idx = group[0]
        end_idx = group[-1]

        duration = time[end_idx] - time[start_idx]

        # Skip invalid detections
        if duration < 0:
            continue

        flare_count += 1

        peak_idx = group[np.argmax(counts[group])]

        start_time = datetime.fromtimestamp(
            time[start_idx],
            UTC
        )

        peak_time = datetime.fromtimestamp(
            time[peak_idx],
            UTC
        )

        end_time = datetime.fromtimestamp(
            time[end_idx],
            UTC
        )

        peak_count = float(counts[peak_idx])

        duration_minutes = duration / 60

        # Severity Classification
        if peak_count >= 250:
            severity = "VERY STRONG"
            icon = "🔴"

        elif peak_count >= 150:
            severity = "STRONG"
            icon = "🟠"

        elif peak_count >= 75:
            severity = "MODERATE"
            icon = "🟡"

        else:
            severity = "WEAK"
            icon = "🟢"

        # Save to catalog
        catalog.append({
            "flare_id": f"FLR-{flare_count:03d}",
            "payload": "SoLEXS",
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "peak_time": peak_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_minutes": round(duration_minutes, 2),
            "peak_count": peak_count,
            "background": round(mean_count, 2),
            "threshold": round(threshold, 2),
            "severity": severity
        })

        print("\n" + "=" * 60)

        print(f"Flare ID     : FLR-{flare_count:03d}")

        print("\nStatus       : SOLAR FLARE CONFIRMED ✅")
        print("Payload      : SoLEXS")

        print(f"\nStart Time   : {start_time}")
        print(f"Peak Time    : {peak_time}")
        print(f"End Time     : {end_time}")

        print(f"\nDuration     : {duration_minutes:.1f} Minutes")

        print(f"\nPeak Count   : {peak_count:.0f}")

        print(f"Background   : {mean_count:.2f}")
        print(f"Threshold    : {threshold:.2f}")

        print(f"\nSeverity     : {severity} {icon}")

        print("\n" + "=" * 60)

    if flare_count == 0:
        print("\nNo significant solar flares detected.")

# ==========================
# SAVE CSV CATALOG
# ==========================

Path("outputs/catalogs").mkdir(
    parents=True,
    exist_ok=True
)

df = pd.DataFrame(catalog)

csv_path = "outputs/catalogs/solexs_catalog.csv"

df.to_csv(
    csv_path,
    index=False
)

print("\n")
print("=" * 60)
print(f"Total Significant Flares Detected : {flare_count}")
print(f"Catalog Saved : {csv_path}")
print("=" * 60)