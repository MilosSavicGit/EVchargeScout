#!/usr/bin/env python3
"""
build_merge.py — combine the OCM and OSM charger files into the one file the
app loads.

    ocm/<cc>.json   from build_ev.py   (curated: 98% have power, has price)
    osm/<cc>.json   from build_osm.py  (wider: PL 5.8x, but only 16% have power)
                        |
                   build_merge.py
                        |
    ev/<cc>.json    <-- the only file index.html fetches

Run:
    python build_merge.py --all
    python build_merge.py --country PL

WHY THE OUTPUT HAS TWO ARRAYS

Measured on the real data: OSM supplies a great many pins that say "a charger
exists here" and nothing else. Germany is 42,499 OSM records of which only
16,517 state power - 26,000 carry no kW, no connector, no price. Those cannot be
planned against (you cannot compute a charging time from nothing, and calling an
unknown charger "slow" asserts something you do not know), but they are still
worth drawing: a driver seeing 300 km of empty map assumes the app is ignorant.

So:

  "chargers"  full records, power known. EXACTLY the shape index.html already
              reads, so the planner needs no change at all.

  "pins"      display-only, as compact arrays: [id, lat, lon, name, operator, src]
              Drawn on the map, offered in "chargers near here", never planned on.

Two arrays, not one with a flag, because the size problem is the blocker:
Germany merged as uniform full records is ~15 MB, which nobody loads at a
motorway services on two bars of signal. The pins array costs about a fifth of
that per record.

SOURCE OF TRUTH

ocm/ and osm/ are kept as-is and are never written here. Either can be rebuilt
independently, and a disputed pin can be traced back to the source that supplied
it. Only ev/ is generated.
"""

import argparse, json, os, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_sources import dedupe

ONE_SIDED = []

# Fields the app needs on a full record. Anything else is dropped on the way out.
FULL_FIELDS = ("id", "lat", "lon", "name", "town", "operator", "kw",
               "points", "cost", "usage", "conn", "membership", "src")
# Match keys used during dedup that must not ship.
STRIP = ("evse", "operator_wikidata", "osm_id", "match", "conn_unknown", "geometry")


def has_power(r):
    kw = r.get("kw")
    if kw in ("", None):
        return False
    try:
        return float(kw) > 0
    except (TypeError, ValueError):
        return False


def slim(r):
    """Display-only pin as a compact array. Order is fixed and documented in
    the file header the app reads, so index.html can unpack it positionally."""
    return [r.get("id") or "", round(float(r["lat"]), 5), round(float(r["lon"]), 5),
            r.get("name") or "", r.get("operator") or "", r.get("src") or "osm"]


def full(r):
    out = {k: r[k] for k in FULL_FIELDS if k in r and r[k] not in (None, "")}
    out["lat"], out["lon"] = r["lat"], r["lon"]        # always present
    return out


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_country(cc, ocm_dir, osm_dir, out_dir):
    cc = cc.lower()
    ocm = load(os.path.join(ocm_dir, f"{cc}.json"))
    osm = load(os.path.join(osm_dir, f"{cc}.json"))
    if ocm is None and osm is None:
        raise RuntimeError(f"{cc}: neither {ocm_dir}/ nor {osm_dir}/ has this country")

    ocm_recs = (ocm or {}).get("chargers", [])
    osm_recs = (osm or {}).get("chargers", [])

    # A country present in one source and absent from the other is nearly always
    # a missing file rather than reality. Uruguay merged as "OCM 0 + OSM 32" and
    # shipped 17 plannable records where OCM alone had 203 - the ocm/uy.json file
    # had simply gone. Nothing complained, because zero plus something still
    # looks like a successful merge. Report it; do not fail, because Russia
    # legitimately has no OSM side.
    if not ocm_recs and len(osm_recs) >= 20:
        ONE_SIDED.append(f"{cc}: no OCM data (OSM has {len(osm_recs):,})")
    if not osm_recs and len(ocm_recs) >= 20:
        ONE_SIDED.append(f"{cc}: no OSM data (OCM has {len(ocm_recs):,})")

    merged, stats = dedupe([dict(r) for r in ocm_recs], [dict(r) for r in osm_recs])

    for r in merged:
        for k in STRIP:
            r.pop(k, None)

    plannable = [full(r) for r in merged if has_power(r)]
    pins      = [slim(r) for r in merged if not has_power(r)]

    payload = {
        "area": cc,
        "sources": ["Open Charge Map (CC BY 4.0)", "OpenStreetMap (ODbL)"],
        "generated": time.strftime("%Y-%m-%d"),
        "pin_fields": ["id", "lat", "lon", "name", "operator", "src"],
        "count": len(plannable),
        "pin_count": len(pins),
        "chargers": plannable,
        "pins": pins,
    }

    d = out_dir or "."
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{cc}.json")
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

    kb = os.path.getsize(path) // 1024
    print(f"  [{cc}] OCM {stats['ocm_in']:,} + OSM {stats['osm_in']:,} "
          f"-> merged {stats['merged']:,} dupes removed", flush=True)
    print(f"        {len(plannable):,} plannable · {len(pins):,} pins · {kb} KB",
          flush=True)
    return len(plannable), len(pins), os.path.getsize(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge OCM and OSM charger data.")
    ap.add_argument("--country", help="single ISO code, e.g. PL")
    ap.add_argument("--all", action="store_true", help="every country present in either source")
    ap.add_argument("--ocm", default="ocm", help="OCM input folder (default: ocm)")
    ap.add_argument("--osm", default="osm", help="OSM input folder (default: osm)")
    ap.add_argument("--out", default="ev", help="output folder the app reads (default: ev)")
    args = ap.parse_args(argv)

    if args.all:
        ccs = set()
        for d in (args.ocm, args.osm):
            if os.path.isdir(d):
                ccs |= {f[:-5] for f in os.listdir(d)
                        if f.endswith(".json") and not f.startswith(("ev", "_"))}
        targets = sorted(ccs)
    else:
        targets = [args.country] if args.country else []
    if not targets:
        ap.error("give --country XX or --all")

    tp = tn = tb = 0
    failed = []
    for i, cc in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {cc.upper()}", flush=True)
        try:
            p, n, b = build_country(cc, args.ocm, args.osm, args.out)
            tp += p; tn += n; tb += b
        except Exception as e:                                   # noqa: BLE001
            failed.append(cc)
            print(f"      FAILED: {e}", flush=True)

    print(f"\n{len(targets)-len(failed)} countries · {tp:,} plannable · {tn:,} pins "
          f"· {tb/1048576:.1f} MB total")
    if ONE_SIDED:
        print("\nONE-SIDED - check whether a source file is missing:")
        for line in ONE_SIDED:
            print("   " + line)
    if failed:
        print("Failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
