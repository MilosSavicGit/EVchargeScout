#!/usr/bin/env python3
"""
check_sources.py — which countries are missing from ocm/ or osm/?

    python check_sources.py

Uruguay merged as "OCM 0 + OSM 32" and shipped 17 plannable records where OCM
alone held 203, because ocm/uy.json had gone missing. Nothing complained: zero
plus something still looks like a successful merge. This lists both counts side
by side so a gap is visible rather than inferred.
"""
import json, os, sys

def counts(folder):
    out = {}
    if not os.path.isdir(folder):
        print(f"!! no {folder}/ folder here", file=sys.stderr)
        return out
    for f in sorted(os.listdir(folder)):
        if not f.endswith(".json") or f.startswith("_") or f == "ev.json":
            continue
        try:
            d = json.load(open(os.path.join(folder, f), encoding="utf-8"))
            out[f[:-5]] = d.get("count", len(d.get("chargers", [])))
        except Exception as e:                                   # noqa: BLE001
            out[f[:-5]] = f"ERR {e}"
    return out

ocm, osm = counts("ocm"), counts("osm")
allcc = sorted(set(ocm) | set(osm))

print(f"{'cc':5s}{'OCM':>10s}{'OSM':>10s}   note")
print("-" * 52)
missing_ocm, missing_osm, zeros = [], [], []
for cc in allcc:
    o, s = ocm.get(cc), osm.get(cc)
    note = ""
    if o is None:
        note = "<<< MISSING from ocm/"; missing_ocm.append(cc)
    elif s is None:
        note = "missing from osm/";     missing_osm.append(cc)
    elif o == 0 or s == 0:
        note = "zero on one side";      zeros.append(cc)
    print(f"{cc:5s}{str(o if o is not None else '-'):>10s}"
          f"{str(s if s is not None else '-'):>10s}   {note}")

print("-" * 52)
print(f"ocm/ {len(ocm)} files · osm/ {len(osm)} files · {len(allcc)} countries seen")
if missing_ocm:
    print(f"\nMISSING FROM ocm/ : {', '.join(missing_ocm)}")
    print("  rebuild with:  python build_ev.py --country "
          + missing_ocm[0].upper() + " --out ocm")
if missing_osm:
    print(f"\nmissing from osm/ : {', '.join(missing_osm)}")
    print("  (RU is expected - its tiles could not complete)")
if zeros:
    print(f"\nzero on one side  : {', '.join(zeros)}")
if not (missing_ocm or missing_osm or zeros):
    print("\nBoth sources complete for every country.")
