# src/data_loader/read_hel1os.py

from astropy.io import fits

file_path = "data/raw/hel1os/HLS_20260611_114949_43807sec_lev1_V111/2026/06/11/HLS_20260611_114949_43807sec_lev1_V111/cdte/lightcurve_cdte1.fits"

with fits.open(file_path) as hdul:
    print("\n===== FITS INFO =====")
    hdul.info()

    data = hdul[1].data

    print("\n===== COLUMN NAMES =====")
    print(data.columns.names)

    print("\n===== FIRST 5 ROWS =====")
    for row in data[:5]:
        print(row)