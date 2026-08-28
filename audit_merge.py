#!/usr/bin/env python3
"""
audit_merge.py — is the dedup missing real duplicates, or are the two sources
genuinely listing different chargers?

    python audit_merge.py --country PL

Poland merged only 124 of OCM's 501 records against OSM's 2,891. That is either
correct (the sources really do list different sites) or the radius is too tight
and ~280 physical chargers are about to show as two dots each. The difference is
visible in ONE number: how far the unmatched OCM records sit from their nearest
OSM neighbour.

  clustered at 50-150 m  -> the radius is too tight, widen it
  spread over kilometres -> genuinely different chargers, merge is right

Also prints the near misses individually, so a judgement call can be made on
real examples rather than on a histogram.
"""

import argparse, json, os, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_sources import metres, norm_operator, match, _index, _neighbours, centroid

# The grid only searches the 3x3 cells around a point (~360 m). Anything with no
# OSM record in there is reported as such rather than given a made-up distance -
# claiming '5 km' when we never looked past 360 m would be inventing data.
BANDS = [(0,25),(25,50),(50,100),(100,200),(200,360)]
GRID_REACH_M = 360


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("chargers", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", required=True)
    ap.add_argument("--ocm", default="ocm")
    ap.add_argument("--osm", default="osm")
    ap.add_argument("--show", type=int, default=15, help="near misses to list")
    a = ap.parse_args()
    cc = a.country.lower()

    ocm = load(os.path.join(a.ocm, f"{cc}.json"))
    osm = load(os.path.join(a.osm, f"{cc}.json"))
    print(f"{cc.upper()}: OCM {len(ocm):,}  OSM {len(osm):,}\n")

    # index OSM so each OCM record can find its neighbours cheaply
    osm_pts = []
    for o in osm:
        la, lo = centroid(o)
        if la is not None:
            osm_pts.append({**o, "lat": la, "lon": lo})
    grid = _index(osm_pts)

    bands = collections.Counter()
    reasons = collections.Counter()
    near_misses = []
    matched = 0

    for c in ocm:
        if c.get("lat") is None:
            continue
        best_d, best_o, best_why = 1e9, None, ""
        did_match = False
        for cell in _neighbours(c["lat"], c["lon"]):
            for i in grid.get(cell, ()):
                o = osm_pts[i]
                d = metres(c["lat"], c["lon"], o["lat"], o["lon"])
                if d < best_d:
                    best_d, best_o = d, o
                if d <= 100:
                    same, why = match(o, c, d)
                    if same:
                        did_match = True
                    else:
                        best_why = why
        if did_match:
            matched += 1
            continue
        # unmatched: how far is the nearest OSM thing?
        if best_o is None or best_d > GRID_REACH_M:
            bands["far"] += 1
        else:
            for lo_, hi in BANDS:
                if lo_ <= best_d < hi:
                    bands[(lo_, hi)] += 1
                    break
        if best_d <= 200 and best_o is not None:
            reasons[best_why or "outside radius"] += 1
            near_misses.append((best_d, c, best_o, best_why))

    print(f"matched   {matched:,} of {len(ocm):,}  ({100*matched/max(1,len(ocm)):.0f}%)")
    print(f"unmatched {len(ocm)-matched:,}\n")

    print("distance from each UNMATCHED OCM record to its nearest OSM record")
    print("-"*62)
    tot = sum(bands.values()) or 1
    for lo_, hi in BANDS:
        n = bands[(lo_, hi)]
        bar = "#" * int(50 * n / tot)
        print(f"{lo_}-{hi} m".rjust(14) + f" {n:6,d} {100*n/tot:5.1f}%  {bar}")
    n = bands["far"]
    bar = "#" * int(50 * n / tot)
    print(f"{'no OSM near':>14s} {n:6,d} {100*n/tot:5.1f}%  {bar}")
    print("-"*62)
    print(f"('no OSM near' = nothing within ~{GRID_REACH_M} m; not searched beyond that)")

    close = sum(bands[b] for b in BANDS if b[1] <= 200)
    print(f"\nwithin 200 m of an OSM record but NOT merged: {close:,} "
          f"({100*close/tot:.1f}% of unmatched)")
    if reasons:
        print("why they were not merged:")
        for why, n in reasons.most_common():
            print(f"   {why:22s} {n:5,d}")

    if near_misses:
        near_misses.sort(key=lambda x: x[0])
        print(f"\nclosest {min(a.show, len(near_misses))} near misses:")
        print(f"{'dist':>7s}  {'OCM operator':28s} {'OSM operator':28s} reason")
        for d, c, o, why in near_misses[:a.show]:
            co = (c.get("operator") or "")[:27]
            oo = (o.get("operator") or "")[:27]
            print(f"{d:6.0f}m  {co:28s} {oo:28s} {why or 'outside radius'}")
            if norm_operator(co) != norm_operator(oo):
                print(f"{'':9s}normalised: {norm_operator(co)!r} vs {norm_operator(oo)!r}")

    print("\nreading it:")
    print("  a spike at 50-200 m   -> radius too tight, widen R_OPERATOR")
    print("  operator-conflict     -> normalisation is failing on real names")
    print("  mostly over 1 km      -> genuinely different chargers, merge is right")


if __name__ == "__main__":
    main()
