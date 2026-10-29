"""
ServiceReach Rwanda - step 1: our own walking-time grid to the nearest health facility.

Inputs (paths are set in config.py):
  - OSM health facilities (HOT export)         health_facilities.gpkg
  - OSM roads (HOT export)                     roads.gpkg
  - Sector boundaries 2022 (NISR)              Sector_Boundary_(Open_Data).shp
  - WorldPop 2020 population, 100 m            rwa_pop_2020_CN_100m_R2025A_v1.tif
  - sector_master.csv (NISR census population + MPI poverty)

Method (simple on purpose, so it can be explained):
  1. Make a cost grid on the WorldPop grid (about 92 m cells).
  2. Cells on a road or path: walk at ROAD_KMH. Other land: walk at OFFROAD_KMH.
     Cells outside every sector (lakes, other countries): cannot walk.
  3. Least-cost path (Dijkstra-type) from every facility to every cell -> minutes.
  4. Scale WorldPop so each sector equals the NISR 2022 census total.
  5. Per sector: people-weighted mean walking time, % of people within 30 and 60 min.

Known limits (say them in the pitch):
  - No slope (no DEM used), so hilly areas are probably UNDER-estimated.
  - Health posts are not mapped well in OSM, so access is for health centres + hospitals.
"""
import sys, os, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio import features
from skimage.graph import MCP_Geometric

import config as cfg
cfg_mod = cfg
cfg.unzip_all()
CONFIG = dict(facilities=str(cfg.FACILITIES), roads=str(cfg.ROADS), sectors=str(cfg.SECTORS), pop=str(cfg.POP_TIF),
              master=str(cfg.MASTER), maina=str(cfg.MAINA_RW), out=str(cfg.OUT) + "/")
ROAD_KMH, OFFROAD_KMH = cfg.ROAD_KMH, cfg.OFFROAD_KMH   # assumptions (see sensitivity run)

WALKABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
            "service", "track", "path", "footway", "living_street", "pedestrian", "steps", "cycleway",
            "bridleway", "road"}


def clean_facilities(path):
    h = gpd.read_file(path)
    bad_name = h.name.fillna("").str.contains("pharmac|drugstore|dentist|dental|laborator|optic|veterin",
                                              case=False, regex=True)
    ok_amenity = h.amenity.isin(["hospital", "clinic", "doctors"])
    ok_health = h.healthcare.isin(["hospital", "clinic", "centre", "doctor"])
    h = h[(ok_amenity | ok_health) & ~bad_name & (h.amenity != "pharmacy") & (h.healthcare != "pharmacy")].copy()
    h["geometry"] = h.geometry.representative_point()
    return h


def load_facilities(mode="maina+osm", cfg=CONFIG, dedup_m=300):
    """Base list (see _base_facilities) plus any rows in data/new_facilities.csv (name,lat,lon)."""
    fac = _base_facilities(mode, cfg, dedup_m)
    if cfg_mod.NEW_FAC.exists():
        extra = pd.read_csv(cfg_mod.NEW_FAC)
        if len(extra):
            new = gpd.GeoDataFrame(extra[["name"]], geometry=gpd.points_from_xy(extra.lon, extra.lat), crs=4326).assign(src="new")
            fac = pd.concat([fac, new], ignore_index=True)
    return fac


def _base_facilities(mode="maina+osm", cfg=CONFIG, dedup_m=300):
    """mode: 'osm', 'maina' (public list, Maina et al. 2019) or 'maina+osm'
    (Maina first; OSM points are added only if farther than dedup_m from every Maina point)."""
    osm = clean_facilities(cfg["facilities"])[["name", "geometry"]].assign(src="osm")
    if mode == "osm":
        return osm
    mn = pd.read_csv(cfg["maina"])
    mn = gpd.GeoDataFrame(mn[["Facility_n", "Facility_t"]].rename(columns={"Facility_n": "name"}),
                          geometry=gpd.points_from_xy(mn.Long, mn.Lat), crs=4326).assign(src="maina")
    if mode == "maina":
        return mn
    a, b = mn.to_crs(32735), osm.to_crs(32735)
    dist = b.geometry.apply(lambda g: a.distance(g).min())
    keep = osm[(dist > dedup_m).values]
    return pd.concat([mn, keep], ignore_index=True)


def make_cost(road_kmh=ROAD_KMH, offroad_kmh=OFFROAD_KMH, cfg=CONFIG, verbose=True):
    """Cost grid in seconds to cross one cell. Returns cost, sector-id grid, population raster."""
    p = rasterio.open(cfg["pop"])
    shape, tr = p.shape, p.transform
    sec = gpd.read_file(cfg["sectors"])[["sector_id", "geometry"]]
    sec["sector_id"] = sec.sector_id.astype(int)
    sid = features.rasterize(((g, i) for g, i in zip(sec.geometry, sec.sector_id)),
                             out_shape=shape, transform=tr, fill=0, dtype="int32")
    cell_m = 0.00083333333 * 111_320          # about 92.8 m
    sec_per_cell = lambda kmh: cell_m / (kmh / 3.6)
    cost = np.full(shape, sec_per_cell(offroad_kmh), dtype="float64")
    roads = gpd.read_file(cfg["roads"], columns=["highway"])
    roads = roads[roads.geometry.geom_type.isin(["LineString", "MultiLineString"]) & roads.highway.isin(WALKABLE)]
    road_mask = features.rasterize(((g, 1) for g in roads.geometry), out_shape=shape, transform=tr,
                                   fill=0, dtype="uint8", all_touched=True).astype(bool)
    cost[road_mask] = sec_per_cell(road_kmh)
    cost[sid == 0] = np.inf                     # outside Rwanda / lakes
    if verbose:
        print(f"road cells: {road_mask.sum():,}")
    return cost, sid, p


def build(road_kmh=ROAD_KMH, offroad_kmh=OFFROAD_KMH, cfg=CONFIG, verbose=True, mode="maina+osm"):
    cost, sid, p = make_cost(road_kmh, offroad_kmh, cfg, verbose)
    shape, tr = p.shape, p.transform
    fac = load_facilities(mode, cfg)
    rows, cols = rasterio.transform.rowcol(tr, fac.geometry.x.values, fac.geometry.y.values)
    rc = {(r, c) for r, c in zip(rows, cols) if 0 <= r < shape[0] and 0 <= c < shape[1] and sid[r, c] > 0}
    if verbose:
        print(f"facilities used: {len(fac)} (unique grid cells inside Rwanda: {len(rc)})")
    mcp = MCP_Geometric(cost, fully_connected=True)
    secs, _ = mcp.find_costs(list(rc))
    minutes = secs / 60.0
    minutes[~np.isfinite(minutes)] = np.nan
    return minutes, sid, p, fac


def summarise(minutes, sid, p, cfg=CONFIG):
    pop = p.read(1).astype(float)
    pop[(pop == p.nodata) | np.isnan(pop) | (pop < 0)] = 0
    m = pd.read_csv(cfg["master"])
    m["sector_id"] = m.sector_id.astype(int)
    df = pd.DataFrame({"sid": sid.ravel(), "wp": pop.ravel(), "t": minutes.ravel()})
    df = df[(df.sid > 0) & (df.wp > 0) & df.t.notna()]
    s = df.groupby("sid").wp.sum().rename("wp_sum")
    df = df.merge(s, left_on="sid", right_index=True).merge(m[["sector_id", "pop"]], left_on="sid", right_on="sector_id")
    df["ppl"] = df.wp * df["pop"] / df.wp_sum
    g = df.groupby("sid")
    out = pd.DataFrame({
        "walk_mean_min": g.apply(lambda d: np.average(d.t, weights=d.ppl)),
        "pct_within_30": g.apply(lambda d: 100 * d.ppl[d.t <= 30].sum() / d.ppl.sum()),
        "pct_within_60": g.apply(lambda d: 100 * d.ppl[d.t <= 60].sum() / d.ppl.sum()),
    })
    out["people_beyond_60"] = g.apply(lambda d: d.ppl[d.t > 60].sum())
    res = m.merge(out, left_on="sector_id", right_index=True, how="left")
    return res, df


if __name__ == "__main__":
    minutes, sid, p, fac = build()
    res, df = summarise(minutes, sid, p)
    np.save(CONFIG["out"] + "walk_minutes_grid.npy", minutes.astype("float32"))
    res.to_csv(CONFIG["out"] + "sector_access_own.csv", index=False)
    tot = df.ppl.sum()
    print("national mean walk (min):", round(np.average(df.t, weights=df.ppl), 1), "| survey 31.7")
    print("people within 30 / 60 min (%):", round(100 * df.ppl[df.t <= 30].sum() / tot, 1),
          round(100 * df.ppl[df.t <= 60].sum() / tot, 1))
