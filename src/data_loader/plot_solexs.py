from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np

from pathlib import Path

file_path = list(Path("data/raw/solexs").rglob("*.lc"))[0]
print("Using:", file_path)

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