# src/data_loader/read_solexs.py

from astropy.io import fits

file_path = "data/raw/solexs/solexs_2026Jun12T200024196/AL1_SLX_L1_20260610_v1.0/SDD2/AL1_SOLEXS_20260610_SDD2_L1.lc"

with fits.open(file_path) as hdul:
    print("\n===== FITS INFO =====")
    hdul.info()

    data = hdul[1].data

    print("\n===== COLUMN NAMES =====")
    print(data.columns.names)

    print("\n===== FIRST 5 ROWS =====")
    for row in data[:5]:
        print(row)