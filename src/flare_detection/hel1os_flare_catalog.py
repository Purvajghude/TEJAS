from astropy.io import fits
import numpy as np

file_path = "data/raw/hel1os/HLS_20260613_120007_43189sec_lev1_V111/2026/06/13/HLS_20260613_120007_43189sec_lev1_V111/cdte/lightcurve_cdte1.fits"

with fits.open(file_path) as hdul:

    data = hdul[5].data

    ctr = data["CTR"]
    time = data["ISOT"]

    threshold = np.mean(ctr) + 3 * np.std(ctr)

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

    for i, group in enumerate(groups):

        start_idx = group[0]
        end_idx = group[-1]

        peak_idx = group[np.argmax(ctr[group])]

        duration = end_idx - start_idx

        peak_ctr = ctr[peak_idx]

        if peak_ctr >= 15:
            severity = "VERY STRONG 🔴"
        elif peak_ctr >= 10:
            severity = "STRONG 🟠"
        elif peak_ctr >= 5:
            severity = "MODERATE 🟡"
        else:
            severity = "WEAK 🟢"

        print("\n" + "=" * 60)

        print(f"Flare ID     : HLS-{i+1:03d}")
        print(f"Payload      : HEL1OS")
        print(f"Energy Band  : 1.8–90 keV")

        print()
        print(f"Start Time   : {time[start_idx]}")
        print(f"Peak Time    : {time[peak_idx]}")
        print(f"End Time     : {time[end_idx]}")

        print()
        print(f"Peak CTR     : {peak_ctr}")
        print(f"Duration     : {duration} sec")

        print()
        print(f"Severity     : {severity}")

    print("\n")
    print("=" * 60)
    print(f"Total HEL1OS Flares Detected : {len(groups)}")
    print("=" * 60)