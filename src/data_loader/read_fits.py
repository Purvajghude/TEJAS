from astropy.io import fits

print("TEJAS FITS Reader")

file_path = "data/raw/sample.fits"

try:
    hdul = fits.open(file_path)

    print("\nFile opened successfully\n")

    hdul.info()

except Exception as e:
    print("Error:", e)