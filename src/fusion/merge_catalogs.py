import pandas as pd

solexs = pd.read_csv(
    "outputs/catalogs/solexs_catalog.csv"
)

hel1os = pd.read_csv(
    "outputs/catalogs/hel1os_catalog.csv"
)

print("\n===== SOLEXS =====")
print(solexs.head())

print("\n===== HEL1OS =====")
print(hel1os.head())

print("\n")
print("SOLEXS FLARES :", len(solexs))
print("HEL1OS FLARES :", len(hel1os))