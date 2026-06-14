from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np

file_path = "data/raw/hel1os/HLS_20260613_120007_43189sec_lev1_V111/2026/06/13/HLS_20260613_120007_43189sec_lev1_V111/cdte/lightcurve_cdte1.fits"

with fits.open(file_path) as hdul:

    print("\n===== FITS INFO =====")
    hdul.info()

    for i in range(1, len(hdul)):

        data = hdul[i].data

        ctr = data["CTR"]

        print("\n===================================")
        print("Band Name :", hdul[i].name)
        print("Records   :", len(ctr))
        print("Max CTR   :", np.max(ctr))
        print("Mean CTR  :", np.mean(ctr))

        plt.figure(figsize=(15, 5))
        plt.plot(ctr)

        plt.title(f"TEJAS - {hdul[i].name}")
        plt.xlabel("Time Index")
        plt.ylabel("Count Rate (CTR)")

        plt.grid(True)
        plt.show()