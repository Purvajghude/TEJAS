# src/data_loader/read_hel1os.py

from astropy.io import fits

from pathlib import Path

file_path = list(
    Path("data/raw/hel1os").rglob("lightcurve_cdte1.fits")
)[0]

print("Using:", file_path)

with fits.open(file_path) as hdul:
    print("\n===== FITS INFO =====")
    hdul.info()

    data = hdul[1].data

    print("\n===== COLUMN NAMES =====")
    print(data.columns.names)

    print("\n===== FIRST 5 ROWS =====")
    for row in data[:5]:
        print(row)