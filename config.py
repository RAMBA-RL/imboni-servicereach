"""Settings used by all scripts. Edit the file names here if yours are different.
Put your downloaded files in data/raw/ (zip files can stay zipped)."""
from pathlib import Path
import os, zipfile

ROOT = Path(__file__).parent
# SR_RAW / SR_UNZIP are optional environment variables (used only for testing)
RAW = Path(os.environ.get("SR_RAW", ROOT / "data" / "raw"))
UNZIPPED = Path(os.environ.get("SR_UNZIP", ROOT / "data" / "raw" / "_unzipped"))
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# --- raw files (names as downloaded) ---
ZIP_SECTORS = RAW / "Sector_Boundary_2022_-811353069855661475.zip"
ZIP_ROADS = RAW / "hotosm_rwa_roads_osm_gpkg.zip"
ZIP_FACILITIES = RAW / "hotosm_rwa_health_facilities_osm_gpkg.zip"
POP_TIF = RAW / "rwa_pop_2020_CN_100m_R2025A_v1.tif"
CENSUS_XLSX = RAW / "Population_size_structure_and_spatial_Distribution_Thematic_Report.xlsx"  # sheet 'Table D1'
POVERTY_PDF = RAW / "RPHC5_Thematic_Report_Non_Monetary_Poverty.pdf"
EICV_XLSX = RAW / "EICV7_Tables_MainIndicatorReport.xlsx"                                     # sheet 'Table A9.23'
MAINA_XLSX = RAW / "sub-saharan_health_facilities.xlsx"

# --- unzipped files (made automatically) ---
SECTORS = UNZIPPED / "Sector_Boundary_(Open_Data).shp"
ROADS = UNZIPPED / "roads.gpkg"
FACILITIES = UNZIPPED / "health_facilities.gpkg"

# --- files we create ---
MASTER = OUT / "sector_master.csv"
MAINA_RW = OUT / "maina_rwanda_facilities.csv"
NEW_FAC = ROOT / "data" / "new_facilities.csv"   # add new or planned facilities here (name,lat,lon)
SHAPES = OUT / "sector_shapes.geojson"           # simplified sector map used by the app

# --- model settings ---
ROAD_KMH, OFFROAD_KMH = 5.0, 2.5      # walking speeds (assumptions)


def unzip_all(zips=None):
    for z in (zips or (ZIP_SECTORS, ZIP_ROADS, ZIP_FACILITIES)):
        if not z.exists():
            raise FileNotFoundError(f"Missing {z}. Put it in data/raw/")
        marker = UNZIPPED / (z.stem + ".done")
        if not marker.exists():
            UNZIPPED.mkdir(parents=True, exist_ok=True)
            zipfile.ZipFile(z).extractall(UNZIPPED)
            marker.write_text("ok")
