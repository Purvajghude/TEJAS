from astropy.io import fits
import numpy as np

file_path = "data/raw/solexs/solexs_2026Jun12T200024196/AL1_SLX_L1_20260610_v1.0/SDD2/AL1_SOLEXS_20260610_SDD2_L1.lc"

with fits.open(file_path) as hdul:

    data = hdul[1].data

    counts = data["COUNTS"]
    time = data["TIME"]

    mask = ~np.isnan(counts)

    counts = counts[mask]
    time = time[mask]

    mean_count = np.mean(counts)
    std_count = np.std(counts)

    threshold = mean_count + 3 * std_count

    flare_indices = np.where(counts > threshold)[0]

    print(f"Mean Counts: {mean_count:.2f}")
    print(f"Std Counts : {std_count:.2f}")
    print(f"Threshold  : {threshold:.2f}")
    print(f"Flare Points Detected: {len(flare_indices)}")

    if len(flare_indices) > 0:
        print("\nFirst 10 flare points:")
        for i in flare_indices[:10]:
            print(
                f"Time={time[i]}, Counts={counts[i]}"
            )