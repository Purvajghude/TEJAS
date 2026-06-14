from astropy.io import fits
import numpy as np

# =========================
# SOLEXS CHECK
# =========================

solexs_file = list(__import__("pathlib").Path("data/raw/solexs").rglob("*.lc*"))[0]

with fits.open(solexs_file) as hdul:

    data = hdul[1].data

    counts = data["COUNTS"]

    mask = ~np.isnan(counts)

    counts = counts[mask]

    solexs_threshold = np.mean(counts) + 3*np.std(counts)

    solexs_flares = np.sum(counts > solexs_threshold)

# =========================
# HEL1OS CHECK
# =========================

hel1os_file = list(__import__("pathlib").Path("data/raw/hel1os").rglob("lightcurve_cdte1.fits"))[0]

with fits.open(hel1os_file) as hdul:

    data = hdul[5].data

    ctr = data["CTR"]

    hel1os_threshold = np.mean(ctr) + 3*np.std(ctr)

    hel1os_flares = np.sum(ctr > hel1os_threshold)

# =========================
# TEJAS FUSION ENGINE
# =========================

print("\n")
print("="*60)
print("            TEJAS FUSION ENGINE")
print("="*60)

print(f"\nSoLEXS Flare Points : {solexs_flares}")
print(f"HEL1OS Flare Points : {hel1os_flares}")

if solexs_flares > 0 and hel1os_flares > 0:

    confidence = min(
        100,
        round((solexs_flares + hel1os_flares)/20)
    )

    print("\nSTATUS      : CONFIRMED SOLAR ACTIVITY 🔥")
    print(f"CONFIDENCE  : {confidence}%")

elif solexs_flares > 0:

    print("\nSTATUS      : SOLEXS ONLY DETECTION 🟡")
    print("CONFIDENCE  : 50%")

elif hel1os_flares > 0:

    print("\nSTATUS      : HEL1OS ONLY DETECTION 🟡")
    print("CONFIDENCE  : 50%")

else:

    print("\nSTATUS      : NO FLARE DETECTED 🟢")
    print("CONFIDENCE  : 0%")

print("\n" + "="*60)