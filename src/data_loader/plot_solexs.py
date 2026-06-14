from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np

file_path = "data/raw/solexs/solexs_2026Jun12T200024196/AL1_SLX_L1_20260610_v1.0/SDD2/AL1_SOLEXS_20260610_SDD2_L1.lc"

with fits.open(file_path) as hdul:
    data = hdul[1].data

    time = data["TIME"]
    counts = data["COUNTS"]

    mask = ~np.isnan(counts)

    time = time[mask]
    counts = counts[mask]

    print(f"Total Records: {len(counts)}")
    print(f"Max Count: {counts.max()}")
    print(f"Min Count: {counts.min()}")

    plt.figure(figsize=(15, 5))
    plt.plot(time[:5000], counts[:5000])

    plt.title("TEJAS - SoLEXS Light Curve")
    plt.xlabel("Time")
    plt.ylabel("Counts")
    plt.grid(True)

    plt.show()