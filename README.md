# IMBONI (ServiceReach Rwanda)

**Identifying communities with the greatest health access gaps.**  
*NISR 2026 Big Data Hackathon | Track 3: Open Innovation*

* **Team:** `RAMBA RWIBUTSO Leonore` and `RUDASINGWA Allan` (`University of Rwanda`)
* **Live app:** `https://imboni-servicereach.netlify.app/`
* **Demo Video (Max 3 min):** `demo/demo.webm`

---

## Project Overview

Many Rwandans live far from a health facility. Simply counting facilities per district does not reveal *who* is far or *how* far they must walk. **IMBONI (ServiceReach)** combines four core datasets across all 416 sectors to map physical barriers to care:

1. **Population Distribution:** 2022 Census data mapped onto a high-resolution 100-meter grid.
2. **Walking Time Metrics:** Exact pathing calculations to the nearest health facility utilizing actual roads and paths.
3. **Poverty Mapping:** Sector-level poverty indexes cross-checked against the EICV7 survey.
4. **Spatial Optimization Planning:** Algorithmic simulation testing where a single new facility would maximize population coverage.

### Headline Impact Estimate
Approximately **367,000 poor people** live more than a 60-minute walk from a health facility (adjusting to 298,000 if using EICV7 district poverty rates). The most acute accessibility gaps are concentrated in the Eastern Province, specifically within **Karangazi, Rwimiyaga, Murundi, Mpanga, and Ngeruka**.

---

## Dashboard Interface & Usage

| Screen | Core Functionality |
| :--- | :--- |
| **Overview** | View the headline access figures. Click a top-5 priority card or any map sector for deep-dive metrics. Search sectors/districts by name, filter by province, and toggle active health facilities. |
| **Test a New Site** | Click anywhere on the map grid to simulate a potential facility. The system instantly calculates how many more residents move within a 60-minute threshold. The "Show the 5 Best Sites" feature runs a greedy sequence to find the top placement choices. |
| **Method & Limits** | Explains the underlying spatial models, data limits, verification thresholds, and pipeline sync frequencies. |

---

## Data Sources

NISR data forms the authoritative core of this project.

* **Population (Census 2022):** NISR (Table D1). Controls total population size constraints per sector.
* **Non-Monetary Poverty (Census 2022):** NISR Thematic Report. Sets the baseline sector multidimensional poverty rate.
* **EICV7 Tables:** NISR Microdata. Used for secondary poverty checks and to validate walking models against the survey average (31.7 mins).
* **Administrative Boundaries:** NISR Open Data. Provides the 2022 sector geographic shapes.
* **Population Grid (100 m):** WorldPop (CC BY 4.0). Used to distribute sector-level population counts across the landscape.
* **Public Health Facilities:** Maina et al. 2019 via HDX. Primary baseline repository containing 572 public facilities.
* **Road Network & Infrastructure:** OpenStreetMap via HOT exports on HDX (ODbL). Provides 438 additional facilities and the walking network paths.
* **National Priorities:** National Strategy for Transformation (NST2 2024-2029). Guides the socio-economic alignment metrics.

> **Note on Repository Data:** Processed data is stored in `data/processed/` as lightweight CSV and GeoJSON files. Large raw source files are **not** committed to this repository. Download them using the links above and place them into `data/raw/` (refer to `config.py` for exact file names).
Large raw datasets are not included; download them from the links above.

---
## Data Sources

NISR data forms the authoritative core of this project.

| Data | Source and link | Used for |
|---|---|---|
| Population by sector, Census 2022 (Table D1) | NISR: https://www.statistics.gov.rw | Total people in each sector |
| Non-monetary poverty by sector, Census 2022 | NISR thematic report: https://www.statistics.gov.rw | Sector poverty rate (main measure) |
| EICV7 tables (poverty by district, time on foot to a health facility) | NISR Microdata: https://microdata.statistics.gov.rw/index.php/catalog | Second poverty check, and validating walking time (survey average 31.7 min) |
| Sector boundaries 2022 | NISR Open Data: https://www.statistics.gov.rw | Map and sector areas |
| Population grid 2020, 100 m (`rwa_pop_2020_CN_100m_R2025A_v1.tif`) | WorldPop (CC BY 4.0): https://www.worldpop.org | Spreading sector totals over the map |
| Public health facility list (572 facilities in Rwanda) | Maina et al. 2019, HDX: https://data.humdata.org/dataset/health-facilities-in-sub-saharan-africa | Main facility list |
| Hospitals, health centres, clinics, roads and paths | OpenStreetMap (ODbL), HOT exports on HDX: https://data.humdata.org | 438 extra facilities and the walking network |
| National priorities | NST2 2024-2029: https://www.environment.gov.rw/fileadmin/user_upload/Moe/Publications/Strategies/NST2_DOCUMENT.pdf | Alignment |

> **Note on repository data:** Processed data used by the app is in `data/processed/` (small CSV and GeoJSON files). Large raw source files are **not** in this repository because of their size. Download them from the links above and place them in `data/raw/` (exact file names are in `config.py`).

## Methodology Breakdown

1. **Facility Consolidation:** Merges the baseline public list with OpenStreetMap points (filtering out duplicates within 300 m) to index 1,010 total health infrastructure nodes.
2. **Cost-Distance Matrix:** Implements a cost grid over the 100-meter pixel population surface. Walking speed is modeled at 5 km/h on established roads/paths and 2.5 km/h over open terrain to isolate travel times.
3. **Population Scaling:** Adjusts WorldPop grids using a scaling factor to guarantee pixel sums perfectly match the official 2022 NISR census totals for each sector.
4. **Priority Ranking:** Multiplies the unserved population (>60 mins walk) by the local poverty rate to calculate the "poor and far" metric. Sectors are ranked based on this volume.
5. **Optimization Testing:** Evaluates a 2 km grid system across the country. The engine isolates the pixel location that maximizes coverage, updates the map surface, and iterates to select the next best site.

### Model Validation
Our model calculates a national average walking time of **29.8 minutes**, highly consistent with the official **31.7 minutes** reported in the EICV7 survey. Additionally, 17 of our top 20 priority sectors remain highly ranked when swapping baseline census poverty indexes for monetary EICV7 indicators.

---

## Environment Setup & Execution

This pipeline requires **Python 3.10** or newer.

### Quick Start (Using Included Processed Data)
```bash
# Set up virtual environment
python -m venv .venv
source .venv/bin/activate      # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Compile and view the web application
python 03_build_app.py
```
After compilation finishes, open `app/index.html` inside any standard web browser to explore the dashboard.
python app.py   # opens the app at http://localhost:8000

### Full Reproduction Pipeline (From Raw Data)
To re-run the complete spatial analysis, download the external source layers, place them inside `data/raw/`, and execute the pipeline steps sequentially:

```bash
python 00_prepare_data.py         # Formats population and poverty matrix files
python 02_priority_and_sites.py   # Computes walking matrices, rankings, and site optimization (~5-10 mins)
python 03_build_app.py            # Generates the final application deployment files
```

> **Windows Installation Note:** If `pip install geopandas rasterio` encounters compiler errors, use a Conda environment instead:  
> `conda install -c conda-forge geopandas rasterio scikit-image`

---

## Data Lifecycle & Upgrades

* **Adding New Health Facilities:** When new facilities are built, append a row to `data/new_facilities.csv` (`name,lat,lon`). Alternatively, run `python 04_refresh_facilities.py` to automatically harvest newly mapped medical infrastructure endpoints directly from OpenStreetMap via Overpass API. Once appended, re-run scripts `02` and `03`.
* **Updating Demographic Data:** When new census reports or national surveys are released by NISR, drop the replacement sheets into `data/raw/` and execute the pipeline from script `00` onward.

---

## Scope & Operational Limits

* **Infrastructure Gaps:** Local village-level health posts are only partially mapped on public repositories; certain local regions may show artificial coverage gaps.
* **Topography Constraints:** Elevation terrain changes and slope-induced walking friction are modeled as flat surface speed averages. Actual physical travel times in mountainous areas will be higher.
* **Granularity Bias:** Poverty indexes are assumed uniform across the internal boundaries of an individual sector.
* **Strategic Intent:** The isolated "Best Sites" demonstrate theoretical coverage optimization; they do not account for local building zoning, land rights, or medical staffing capacities. This is a strategic macro-planning tool rather than a real-time routing device.

---

## Originality, AI Assistance, and Credits

We declare that this submission is our own work and all external datasets have been properly cited.

The core research questions, architectural layout, and validation workflows were designed and directed by the human team. Portions of the data-wrangling pipeline scripts and the dashboard front-end interface layout were optimized with the assistance of an AI companion. The team fully understands, maintains, and accepts engineering responsibility for the codebase.

### References & Attribution
* **NISR:** Census 2022, EICV7 microdata, and administrative boundary files.
* **WorldPop:** High-resolution spatial population grids (CC BY 4.0).
* **OpenStreetMap & HOT:** Public transit networks and supplemental health node registries (ODbL).
* **Maina et al. 2019:** Sub-Saharan African public health facility inventory baseline dataset via HDX.
