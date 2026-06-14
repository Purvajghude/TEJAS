from astropy.io import fits
import numpy as np

file_path = "data/raw/hel1os/HLS_20260613_120007_43189sec_lev1_V111/2026/06/13/HLS_20260613_120007_43189sec_lev1_V111/cdte/lightcurve_cdte1.fits"

with fits.open(file_path) as hdul:

    # Using Band 5 = 1.8–90 keV
    data = hdul[5].data

    ctr = data["CTR"]
    time = data["ISOT"]

    mean_ctr = np.mean(ctr)
    std_ctr = np.std(ctr)

    threshold = mean_ctr + 3 * std_ctr

    flare_mask = ctr > threshold

    flare_count = np.sum(flare_mask)

    print("\n===== TEJAS HEL1OS FLARE DETECTION =====\n")

    print(f"Mean CTR : {mean_ctr:.4f}")
    print(f"Std CTR  : {std_ctr:.4f}")
    print(f"Threshold: {threshold:.4f}")

    print(f"\nFlare Points Detected: {flare_count}")

    print("\nFirst 20 Flare Points:\n")

    flare_indices = np.where(flare_mask)[0]

    for idx in flare_indices[:20]:
        print(
            f"Time={time[idx]} | CTR={ctr[idx]}"
        )