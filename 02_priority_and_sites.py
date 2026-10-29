"""
ServiceReach Rwanda - step 2:
  A. Priority sectors: far from care AND poor ("poor people beyond a 60-minute walk").
     Run on two facility lists (Maina+OSM and Maina only). A sector is "robust" if it is in
     the top 40 of both lists.
  B. Candidate sites for a new facility on a ~2 km grid. For each site: how many people
     gain a walk of 30 / 60 minutes or less. Then a greedy pick of the best 15 sites.
Needs 00_prepare_data.py to have been run. 01_access_grid.py must be in the same folder.
"""
import json, warnings, importlib.util, os
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, rasterio
from skimage.graph import MCP_Geometric

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("g", os.path.join(here, "01_access_grid.py"))
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
OUT = g.CONFIG["out"]
HALF, STRIDE, FAR = 56, 22, 60          # window half-size (cells, ~5 km), candidate spacing (~2 km), minutes


# ---------- A. priority sectors ----------
def sector_table(mode):
    mi, sid, p, fac = g.build(mode=mode, verbose=False)
    res, _ = g.summarise(mi, sid, p)
    res["poor_far"] = res.people_beyond_60 * res.mpi_headcount
    res["rank"] = res.poor_far.rank(ascending=False)
    return res, mi, sid, p, fac


main, minutes, sid, p, fac = sector_table("maina+osm")
alt, *_ = sector_table("maina")
main["rank_public_only"] = main.sector_id.map(alt.set_index("sector_id")["rank"])
main["poor_far_public_only"] = main.sector_id.map(alt.set_index("sector_id").poor_far)
main["robust"] = (main["rank"] <= 40) & (main.rank_public_only <= 40)
main["priority_score"] = (main.poor_far + main.poor_far_public_only) / 2
# second poverty check: EICV7 monetary poverty rate of the district (survey, district level)
main["poor_far_eicv"] = main.people_beyond_60 * main.eicv7_poverty_pct / 100
main["rank_eicv"] = main.poor_far_eicv.rank(ascending=False)
main["agree_eicv"] = (main["rank"] <= 40) & (main.rank_eicv <= 40)
main = main.sort_values("priority_score", ascending=False)
main.to_csv(OUT + "sector_priority.csv", index=False)
fac.assign(x=fac.geometry.x, y=fac.geometry.y).drop(columns="geometry").to_csv(OUT + "facilities_used.csv", index=False)
print(main[["district", "sector", "pop", "people_beyond_60", "mpi_headcount_pct", "poor_far", "rank", "rank_public_only", "robust", "eicv7_poverty_pct", "rank_eicv", "agree_eicv"]]
      .head(20).round(0).to_string(index=False))

# ---------- B. candidate sites ----------
cost, sid, p = g.make_cost(verbose=False)
tr = p.transform
pop = p.read(1).astype(float); pop[(pop == p.nodata) | np.isnan(pop) | (pop < 0)] = 0
secsum = pd.Series(pop.ravel()).groupby(sid.ravel()).sum()
secpop = main.set_index("sector_id")["pop"]; mpi = main.set_index("sector_id")["mpi_headcount"]
scale = np.zeros(int(sid.max()) + 1); idx = secsum.index.values
ok = idx > 0
scale[idx[ok]] = secpop.reindex(idx[ok]).values / secsum.values[ok]
mpi_arr = np.zeros(int(sid.max()) + 1); mpi_arr[mpi.index.values.astype(int)] = mpi.values
ppl = pop * scale[sid]                         # people per cell, scaled to the census
mpi_cell = mpi_arr[sid]
old = np.where(np.isnan(minutes), 999.0, minutes)
R, C = sid.shape


def gains(r, c, old):
    r0, r1, c0, c1 = max(r - HALF, 0), min(r + HALF + 1, R), max(c - HALF, 0), min(c + HALF + 1, C)
    w = cost[r0:r1, c0:c1]
    if not np.isfinite(w[r - r0, c - c0]):
        return None
    secs, _ = MCP_Geometric(w, fully_connected=True).find_costs([(r - r0, c - c0)])
    new = secs / 60.0
    o, pp = old[r0:r1, c0:c1], ppl[r0:r1, c0:c1]
    g60 = pp[(new <= 60) & (o > 60)]
    g30 = pp[(new <= 30) & (o > 30)]
    poor60 = (pp * mpi_cell[r0:r1, c0:c1])[(new <= 60) & (o > 60)]
    saved = (pp * np.clip(np.minimum(o, 120) - np.minimum(new, 120), 0, None)).sum()
    return dict(gain60=g60.sum(), gain30=g30.sum(), poor60=poor60.sum(), saved_hours=saved / 60), new


cands = []
for r in range(STRIDE // 2, R, STRIDE):
    for c in range(STRIDE // 2, C, STRIDE):
        if sid[r, c] > 0 and old[r, c] > 10:
            cands.append((r, c))
print("candidate sites:", len(cands))
rows = []
for r, c in cands:
    out = gains(r, c, old)
    if out and out[0]["gain60"] + out[0]["gain30"] > 0:
        x, y = tr * (c + 0.5, r + 0.5)
        rows.append(dict(r=r, c=c, lon=round(x, 4), lat=round(y, 4), sector_id=int(sid[r, c]),
                         **{k: round(v) for k, v in out[0].items()}))
cd = pd.DataFrame(rows)
print("sites with a gain:", len(cd))

# greedy: pick the site with the most new people within 60 min, update the map, repeat
picked, cur = [], old.copy()
cd["gain60_now"] = cd.gain60.astype(float)
for k in range(15):
    best = cd.loc[cd.gain60_now.idxmax()]
    r, c = int(best.r), int(best.c)
    res_, new = gains(r, c, cur)
    r0, c0 = max(r - HALF, 0), max(c - HALF, 0)
    sub = cur[r0:r0 + new.shape[0], c0:c0 + new.shape[1]]
    cur[r0:r0 + new.shape[0], c0:c0 + new.shape[1]] = np.minimum(sub, new)
    picked.append(dict(order=k + 1, lon=best.lon, lat=best.lat, sector_id=int(best.sector_id), **{kk: round(v) for kk, v in res_.items()}))
    near = (abs(cd.r - r) <= 2 * HALF) & (abs(cd.c - c) <= 2 * HALF)
    for i in cd.index[near]:
        o = gains(int(cd.r[i]), int(cd.c[i]), cur)
        cd.loc[i, "gain60_now"] = o[0]["gain60"] if o else 0
    cd.loc[best.name, "gain60_now"] = 0
pk = pd.DataFrame(picked)
nm = main.set_index("sector_id")[["district", "sector"]]
pk = pk.join(nm, on="sector_id")
pk.to_csv(OUT + "best_new_sites.csv", index=False)
cd.drop(columns=["r", "c", "gain60_now"]).to_csv(OUT + "candidate_sites.csv", index=False)
print(pk.to_string(index=False))
tot = ppl[(old > 60) & (sid > 0)].sum()
print("people beyond 60 min now:", round(tot), "| after 15 greedy sites:", round(ppl[(cur > 60) & (sid > 0)].sum()))
