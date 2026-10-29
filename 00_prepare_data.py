"""Step 0: build data/processed/sector_master.csv and maina_rwanda_facilities.csv.

sector_master.csv has one row per sector (416): census 2022 population (NISR, Table D1),
non-monetary poverty (MPI headcount, census thematic report) and the EICV7 monetary
poverty rate of the district. The MPI table is read from the PDF with the tool `pdftotext`
(part of Poppler). If you do not have pdftotext, use the ready-made sector_master.csv that
comes with the project and skip this step.
"""
import re, subprocess, shutil, warnings
warnings.filterwarnings("ignore")
import pandas as pd, geopandas as gpd
import config as cfg

cfg.unzip_all()
sectors = gpd.read_file(cfg.SECTORS)[["province", "district", "district_i", "sector", "sector_id"]]
key = lambda d: d.district.str.lower().str.strip() + "|" + d.sector.str.lower().str.strip()

# 1. population by sector (Table D1)
raw = pd.read_excel(cfg.CENSUS_XLSX, sheet_name="Table D1", header=None)[[0, 1, 4, 7]]
raw.columns = ["name", "pop", "urban_pop", "rural_pop"]
rows, dist = [], None
for _, r in raw.iterrows():
    n = str(r["name"]).strip()
    if pd.isna(r["pop"]) and n != "nan" and "Province" not in n:
        dist = n
    elif n not in ("Total", "Rwanda") and pd.notna(r["pop"]) and not isinstance(r["pop"], str):
        rows.append((dist, n, r["pop"], r["urban_pop"], r["rural_pop"]))
pop = pd.DataFrame(rows, columns=["district", "sector", "pop", "urban_pop", "rural_pop"])
m = sectors.assign(k=key(sectors)).merge(pop.assign(k=key(pop))[["k", "pop", "urban_pop", "rural_pop"]], on="k", how="left")

# 2. MPI by sector (PDF, Annex C.10)
if shutil.which("pdftotext") and cfg.POVERTY_PDF.exists():
    txt = subprocess.run(["pdftotext", "-layout", str(cfg.POVERTY_PDF), "-"], capture_output=True, text=True).stdout.split("\f")
    start = next(i for i, p in enumerate(txt) if i > 100 and "Annex C. 10" in p and "Headcount" in p)
    rows, dist = [], None
    for page in txt[start:start + 10]:
        for line in page.split("\n"):
            toks = line.split()
            if not toks:
                continue
            nums = []
            for x in reversed(toks):
                try: nums.append(float(x.replace(",", "")))
                except ValueError: break
            nums = nums[::-1]
            if len(nums) == 3 and len(toks) > 3:
                rows.append([dist, " ".join(toks[:-3])] + nums)
            elif not nums and len(toks) <= 3 and re.fullmatch(r"[A-Za-z' \-]+", line.strip()) and line.strip() not in ("Sector", "Total"):
                dist = line.strip()
    mpi = pd.DataFrame(rows, columns=["district", "sector", "mpi_headcount", "intensity", "mpi"])
    m = m.merge(mpi.assign(k=key(mpi)).drop_duplicates("k")[["k", "mpi_headcount", "intensity", "mpi"]], on="k", how="left")
    m["mpi_headcount_pct"] = (m.mpi_headcount * 100).round(1)
else:
    print("pdftotext not found: keeping the MPI columns from the existing sector_master.csv")
    old = pd.read_csv(cfg.MASTER)[["sector_id", "mpi_headcount", "intensity", "mpi", "mpi_headcount_pct"]]
    m = m.merge(old, on="sector_id", how="left")

# 3. EICV7 monetary poverty by district (Table A9.23)
e = pd.read_excel(cfg.EICV_XLSX, sheet_name="Table A9.23", header=None).iloc[:, :2].dropna()
e.columns = ["district", "eicv7_poverty_pct"]
e = e[e.district.isin(sectors.district.unique())]
m = m.merge(e, on="district", how="left")
print("sectors:", len(m), "| missing pop:", m["pop"].isna().sum(), "| missing MPI:", m.mpi_headcount.isna().sum(),
      "| missing EICV7:", m.eicv7_poverty_pct.isna().sum())
m.drop(columns="k").to_csv(cfg.MASTER, index=False)

# 4. Maina et al. 2019 public facilities, Rwanda only
mn = pd.read_excel(cfg.MAINA_XLSX)
mn[mn.Country.str.contains("Rwanda", case=False, na=False)].to_csv(cfg.MAINA_RW, index=False)
print("saved", cfg.MASTER.name, "and", cfg.MAINA_RW.name)
