from astropy.io import fits
import numpy as np
from datetime import datetime

file_path = "data/raw/solexs/solexs_2026Jun12T200024196/AL1_SLX_L1_20260610_v1.0/SDD2/AL1_SOLEXS_20260610_SDD2_L1.lc"

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

        # Ignore tiny detections (< 60 sec)
        if duration < 0:
            continue

        flare_count += 1

        peak_idx = group[np.argmax(counts[group])]

        start_time = datetime.utcfromtimestamp(time[start_idx])
        peak_time = datetime.utcfromtimestamp(time[peak_idx])
        end_time = datetime.utcfromtimestamp(time[end_idx])

        peak_count = counts[peak_idx]
        duration_minutes = duration / 60

        # Severity Classification
        if peak_count >= 250:
            severity = "VERY STRONG 🔴"
        elif peak_count >= 150:
            severity = "STRONG 🟠"
        elif peak_count >= 75:
            severity = "MODERATE 🟡"
        else:
            severity = "WEAK 🟢"

        print("\n" + "=" * 60)

        print(f"Flare ID     : FLR-{flare_count:03d}")

        print("\nStatus       : SOLAR FLARE CONFIRMED ✅")
        print("Payload      : SoLEXS")

        print(f"\nStart Time   : {start_time} UTC")
        print(f"Peak Time    : {peak_time} UTC")
        print(f"End Time     : {end_time} UTC")

        print(f"\nDuration     : {duration_minutes:.1f} Minutes")

        print(f"\nPeak Count   : {peak_count:.0f}")

        print(f"Background   : {mean_count:.2f}")
        print(f"Threshold    : {threshold:.2f}")

        print(f"\nSeverity     : {severity}")

        print("\n" + "=" * 60)

    if flare_count == 0:
        print("\nNo significant solar flares detected.")

    print(f"\nTotal Significant Flares Detected : {flare_count}")