from astropy.io import fits
import matplotlib.pyplot as plt

file_path = "data/raw/hel1os/HLS_20260611_114949_43807sec_lev1_V111/2026/06/11/HLS_20260611_114949_43807sec_lev1_V111/cdte/lightcurve_cdte1.fits"

with fits.open(file_path) as hdul:

    print(hdul.info())

    data = hdul[1].data

    counts = data["CTR"]

    plt.figure(figsize=(15,5))
    plt.plot(counts)

    plt.title("HEL1OS CDTE1 Light Curve")
    plt.xlabel("Time Index")
    plt.ylabel("Counts")

    plt.grid(True)

    plt.show()

    print(f"Records : {len(counts)}")
    print(f"Max CTR : {counts.max()}")
    print(f"Min CTR : {counts.min()}")