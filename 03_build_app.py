"""Step 3: build the one-file web app (app/index.html) from the CSV results.
Template: app/app_template.html (colors and text are edited there)."""
import json, warnings, os
import config as cfg
import pandas as pd, geopandas as gpd
import collections
warnings.filterwarnings("ignore")

H = os.path.dirname(os.path.abspath(__file__)); DT = str(cfg.OUT) + "/"
pri = pd.read_csv(DT + "sector_priority.csv")
cand = pd.read_csv(DT + "candidate_sites.csv")
best = pd.read_csv(DT + "best_new_sites.csv").head(5)
fac = pd.read_csv(DT + "facilities_used.csv")

# Load your authoritative sector master mapping table from your desktop folder
master_df = pd.read_csv(os.path.join(H, "data", "processed", "sector_master.csv"))

if cfg.SHAPES.exists():                      # ready-made simplified map: no raw data needed
    sec = gpd.read_file(cfg.SHAPES)
else:                                        # first time: make it from the NISR sector boundary zip
    cfg.unzip_all([cfg.ZIP_SECTORS])
    sec = gpd.read_file(cfg.SECTORS)[["sector_id", "geometry"]]
    sec["geometry"] = sec.geometry.simplify(0.004)
    sec.assign(sector_id=sec.sector_id.astype(int)).to_file(cfg.SHAPES, driver="GeoJSON")

# Coordinate conversion scaling functions for the dashboard canvas
X = lambda lon: round((lon - 28.8) * 1000); Y = lambda lat: round((-lat - 1.0) * 1000)

def path(g):
    if g is None or pd.isna(g):
        return ""
    out = []
    for poly in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
        for ring in [poly.exterior, *poly.interiors]:
            out.append("M" + "L".join(f"{X(x)} {Y(y)}" for x, y in ring.coords) + "Z")
    return "".join(out)

# Clean string text formatting helper function
def clean_txt(s):
    return str(s).lower().replace(" sector", "").replace(" district", "").replace("-", " ").strip()

pri["sector_match"] = pri["sector"].apply(clean_txt)
pri["district_match"] = pri["district"].apply(clean_txt)
master_df["sector_match"] = master_df["sector"].apply(clean_txt)
master_df["district_match"] = master_df["district"].apply(clean_txt)

# Build a dictionary to map official clean string pairs to the correct code keys
master_lookup = {}
for r in master_df.itertuples():
    master_lookup[f"{r.sector_match}_{r.district_match}"] = int(r.sector_id)

# Harmonize the geoBoundaries dataset: every one of the 416 sectors must get its own shape.
# Many sector names repeat in different districts (Remera, Murundi, Karama ...), so a name alone is not enough.
# Step 1: unique names (with small spelling fixes)  Step 2: vote using candidate_sites points (they carry the true sector_id)
# Step 3: for the rest, pick the same-name sector whose district lies next to the shape.
import difflib
from shapely.strtree import STRtree
from shapely.geometry import Point
from shapely.ops import unary_union

if "shapeName" in sec.columns:
    sec = sec.reset_index(drop=True)
    sec["sector_match"] = sec["shapeName"].apply(clean_txt)
    all_names = sorted(set(pri["sector_match"]))
    def fixname(n):                               # e.g. "Shyrongi" -> "shyorongi"
        if n in all_names: return n
        m = difflib.get_close_matches(n, all_names, n=1, cutoff=0.8)
        return m[0] if m else n
    sec["sector_match"] = sec["sector_match"].apply(fixname)

    assign = {}                                   # shape index -> row index in pri
    by_name = collections.defaultdict(list)
    for idx, r in pri.iterrows(): by_name[r["sector_match"]].append(idx)
    shp_by_name = collections.defaultdict(list)
    for j, n in enumerate(sec["sector_match"]): shp_by_name[n].append(j)

    # 1) names that occur once on both sides
    for n, rows in by_name.items():
        if len(rows) == 1 and len(shp_by_name[n]) == 1:
            assign[shp_by_name[n][0]] = rows[0]

    # 2) vote with candidate points
    geoms = list(sec.geometry); tree = STRtree(geoms)
    id2row = {int(r.sector_id): idx for idx, r in pri.iterrows()}
    votes = collections.defaultdict(collections.Counter)
    for r in cand.itertuples():
        p = Point(r.lon, r.lat)
        for j in tree.query(p):
            if geoms[j].contains(p): votes[j][int(r.sector_id)] += 1
    used = set(assign.values())
    for j in range(len(sec)):
        if j in assign or not votes[j]: continue
        for sid, _ in votes[j].most_common():
            row = id2row.get(sid)
            if row is not None and row not in used and pri.at[row, "sector_match"] == sec.at[j, "sector_match"]:
                assign[j] = row; used.add(row); break

    # 3) rest: nearest district made from shapes already placed
    for _ in range(5):
        dist_geom = collections.defaultdict(list)
        for j, row in assign.items(): dist_geom[pri.at[row, "district"]].append(geoms[j])
        dist_geom = {d: unary_union(g) for d, g in dist_geom.items()}
        progress = False
        for j in range(len(sec)):
            if j in assign: continue
            free = [r for r in by_name.get(sec.at[j, "sector_match"], []) if r not in used]
            if not free: continue
            pick_r = min(free, key=lambda r: geoms[j].distance(dist_geom[pri.at[r, "district"]]) if pri.at[r, "district"] in dist_geom else 9e9)
            if len(free) == 1 or geoms[j].distance(dist_geom.get(pri.at[pick_r, "district"], geoms[j])) < 0.02:
                assign[j] = pick_r; used.add(pick_r); progress = True
        if not progress: break

    geometry_list = [None] * len(pri)
    for j, row in assign.items(): geometry_list[row] = geoms[j]
    pri["geometry"] = geometry_list
    missing = pri[pri["geometry"].isna()]
    print(f"Sectors with a map shape: {len(pri) - len(missing)} of {len(pri)}")
    if len(missing): print("STILL MISSING:", list(zip(missing.sector, missing.district)))
else:
    sec["sector_id"] = sec["sector_id"].astype(int)
    pri["sector_id"] = pri["sector_id"].astype(int)
    pri = pri.merge(sec[["sector_id", "geometry"]], on="sector_id")

# Sort descending by priority metrics so the sidebar links stay clean
pri = pri.sort_values(by="poor_far", ascending=False).reset_index(drop=True)

# Build a positional coordinate index to protect candidate points from breaking
sidx = {}
for i, r in enumerate(pri.itertuples()):
    sidx[int(r.sector_id)] = i
sidx = collections.defaultdict(int, sidx)

D = {"sec": [dict(n=r.sector, d=r.district, pv=r.province.replace(" Province", ""), w=round(r.walk_mean_min, 1),
                  b60=round(r.people_beyond_60), pf=round(r.poor_far), rb=bool(r.robust), ae=bool(r.agree_eicv),
                  path=path(r.geometry)) for _, r in pri.iterrows()],
     "fac": [[X(r.x), Y(r.y)] for r in fac.itertuples()],
     "cand": [[X(r.lon), Y(r.lat), int(r.gain60), sidx[int(r.sector_id)]] for r in cand.itertuples()],
     "best": [dict(x=X(r.lon), y=Y(r.lat), o=int(r.order), s=r.sector, d=r.district, g=int(r.gain60), p=int(r.poor60)) for r in best.itertuples()],
     "tot": dict(poor=round(pri.poor_far.sum()), poor_eicv=round(pri.poor_far_eicv.sum()), far=round(pri.people_beyond_60.sum()))}

import base64
logo = "data:image/webp;base64," + base64.b64encode(open(H + "/app/logo.webp", "rb").read()).decode()
html = open(H + "/app/app_template.html").read().replace("/*DATA*/", json.dumps(D, separators=(",", ":"))).replace("/*LOGO*/", logo)
open(H + "/app/index.html", "w").write(html); print(len(html) // 1024, "KB;", D["tot"])
