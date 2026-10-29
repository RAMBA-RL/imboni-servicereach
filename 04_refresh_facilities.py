"""Step 4 (optional): add newly mapped health facilities from OpenStreetMap.

Needs an internet connection. It asks OpenStreetMap (Overpass API) for hospitals, clinics and
health centres in Rwanda, keeps only points that are more than 300 m from every facility the
analysis already uses, and adds them to data/new_facilities.csv (name,lat,lon).
After that, rerun 02_priority_and_sites.py and 03_build_app.py.

    python 04_refresh_facilities.py --dry-run     # only print what would be added
    python 04_refresh_facilities.py               # add them to data/new_facilities.csv

NOTE: the matching logic was tested with sample data. The live download was not tested in the
place where this script was written (no internet there), so test it once on your computer.
This uses OpenStreetMap (free, ODbL). It does not use Google Maps.
"""
import json, sys, urllib.parse, urllib.request
import numpy as np, pandas as pd
import config as cfg

URL = "https://overpass-api.de/api/interpreter"
QUERY = """[out:json][timeout:120];
area["ISO3166-1"="RW"][admin_level=2]->.a;
(nwr["amenity"~"^(hospital|clinic|doctors)$"](area.a);
 nwr["healthcare"~"^(hospital|clinic|centre|doctor)$"](area.a););
out center tags;"""
BAD = ("pharmac", "drugstore", "dentist", "dental", "laborator", "optic", "veterin")


def fetch():
    req = urllib.request.Request(URL, data=urllib.parse.urlencode({"data": QUERY}).encode(),
                                 headers={"User-Agent": "IMBONI-ServiceReach-hackathon"})
    return json.load(urllib.request.urlopen(req, timeout=180))["elements"]


def to_rows(elements):
    rows = []
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name", "(unnamed facility)")
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None or lon is None or any(b in name.lower() for b in BAD):
            continue
        if tags.get("amenity") == "pharmacy" or tags.get("healthcare") == "pharmacy":
            continue
        rows.append({"name": name, "lat": float(lat), "lon": float(lon)})
    return pd.DataFrame(rows, columns=["name", "lat", "lon"])


def metres(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742000 * np.arcsin(np.sqrt(a))


def new_only(osm, known, dedup_m=300):
    """osm: name,lat,lon. known: lat,lon of facilities already used."""
    if osm.empty:
        return osm
    d = metres(osm.lat.values[:, None], osm.lon.values[:, None], known.lat.values[None, :], known.lon.values[None, :]).min(axis=1)
    return osm[d > dedup_m].drop_duplicates(["name", "lat", "lon"])


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    used = pd.read_csv(cfg.OUT / "facilities_used.csv").rename(columns={"y": "lat", "x": "lon"})
    new = new_only(to_rows(fetch()), used[["lat", "lon"]])
    print(f"{len(new)} newly mapped facilities found")
    print(new.head(20).to_string(index=False))
    if not dry and len(new):
        old = pd.read_csv(cfg.NEW_FAC) if cfg.NEW_FAC.exists() else pd.DataFrame(columns=["name", "lat", "lon"])
        pd.concat([old, new]).drop_duplicates(["name", "lat", "lon"]).to_csv(cfg.NEW_FAC, index=False)
        print("added to", cfg.NEW_FAC, "- now rerun 02_priority_and_sites.py and 03_build_app.py")
