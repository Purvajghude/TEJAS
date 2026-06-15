from astropy.io import fits
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

from pathlib import Path

file_path = list(
    Path("data/raw/hel1os").rglob("lightcurve_cdte1.fits")
)[0]

print("Using:", file_path)

catalog = []

with fits.open(file_path) as hdul:

    data = hdul[5].data

    ctr = np.array(data["CTR"], dtype=float)
    time = np.array(data["ISOT"])

    # Remove invalid CTR values
    mask = ~np.isnan(ctr)
    ctr = ctr[mask]
    time = time[mask]

    # Thresholding
    mean_ctr = np.mean(ctr)
    std_ctr = np.std(ctr)
    threshold = mean_ctr + (3 * std_ctr)

    flare_mask = ctr > threshold

    indices = np.where(flare_mask)[0]

    groups = np.split(
        indices,
        np.where(np.diff(indices) > 30)[0] + 1
    )

    print("\n")
    print("=" * 60)
    print("          TEJAS HEL1OS FLARE CATALOG")
    print("=" * 60)

    flare_count = 0

    for i, group in enumerate(groups):

        if len(group) == 0:
            continue

        start_idx = group[0]
        end_idx = group[-1]

        peak_idx = group[np.argmax(ctr[group])]

        # Convert ISO strings → datetime (IMPORTANT FIX)
        start_time = datetime.fromisoformat(time[start_idx])
        peak_time = datetime.fromisoformat(time[peak_idx])
        end_time = datetime.fromisoformat(time[end_idx])

        # FIXED duration (real physics-based duration)
        duration = (end_time - start_time).total_seconds()

        peak_ctr = float(ctr[peak_idx])

        flare_count += 1

        # Severity mapping
        if peak_ctr >= 15:
            severity = "VERY STRONG"
            icon = "🔴"
        elif peak_ctr >= 10:
            severity = "STRONG"
            icon = "🟠"
        elif peak_ctr >= 5:
            severity = "MODERATE"
            icon = "🟡"
        else:
            severity = "WEAK"
            icon = "🟢"

        # Store structured record (fusion-ready)
        catalog.append({
            "flare_id": f"HLS-{flare_count:03d}",
            "payload": "HEL1OS",
            "energy_band": "1.8–90 keV",
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "peak_time": peak_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(duration, 2),
            "peak_ctr": peak_ctr,
            "threshold": round(threshold, 3),
            "severity": severity
        })

        # Terminal output
        print("\n" + "=" * 60)
        print(f"Flare ID     : HLS-{flare_count:03d}")
        print(f"Payload      : HEL1OS")
        print(f"Energy Band  : 1.8–90 keV")

        print(f"\nStart Time   : {start_time}")
        print(f"Peak Time    : {peak_time}")
        print(f"End Time     : {end_time}")

        print(f"\nPeak CTR     : {peak_ctr:.3f}")
        print(f"Duration     : {duration:.2f} sec")
        print(f"Threshold    : {threshold:.3f}")

        print(f"\nSeverity     : {severity} {icon}")
        print("=" * 60)

# ==========================
# SAVE CSV
# ==========================

Path("outputs/catalogs").mkdir(parents=True, exist_ok=True)

df = pd.DataFrame(catalog)

csv_path = "outputs/catalogs/hel1os_catalog.csv"

df.to_csv(csv_path, index=False)

print("\n")
print("=" * 60)
print(f"Total HEL1OS Flares Detected : {flare_count}")
print(f"Catalog Saved : {csv_path}")
print("=" * 60)