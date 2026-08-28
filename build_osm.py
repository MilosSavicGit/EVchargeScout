#!/usr/bin/env python3
"""
build_osm.py — build EV charger data per country from OpenStreetMap.

Writes osm/<cc>.json in the same envelope as build_ev.py's ev/<cc>.json, so
merge_sources.py can fold the two together without either side knowing which
came first.

    python build_osm.py --country PL
    python build_osm.py --all

WHY OVERPASS AND NOT A GEOFABRIK PBF EXTRACT

A country query for one tag returns a small result - Germany, the largest, is
about 46,000 objects. Geofabrik's Germany extract is ~4 GB. Pulling tens of
gigabytes a week to lift a few thousand nodes out is far heavier on donated
infrastructure than the queries are, and it would need pyosmium and disk in CI.
Overpass is the right size of tool for this particular job.

We are still a guest: one country at a time, a real User-Agent, a long pause
between countries, and the mirror list rotated on failure.

WHY OSM AT ALL - the coverage is not uniform and neither source wins:

    country   OCM     OSM      better
    PL        501     3,039    OSM  6.1x
    CZ        649     3,053    OSM  4.7x
    DE     24,611    45,733    OSM  1.9x
    LT      1,909       438    OCM  4.4x

Lithuania is strong on OCM because Inbalance Grid submit to it; Poland is strong
on OSM because Polish mappers map GreenWay by hand and GreenWay do not submit to
OCM. Dropping either source loses real chargers somewhere.

Data (c) OpenStreetMap contributors, ODbL.
"""

import argparse, json, os, sys, tempfile, time
import urllib.parse, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from osm_tags import to_record
from overpass_pool import OverpassPool

# Same mirrors index.html falls back through, so a mirror that dies is one
# problem to fix, not two. Order matters: kumi first, it is the most tolerant
# of long queries.
# ONLY GENERAL-PURPOSE, PLANET-WIDE INSTANCES BELONG HERE.
#
# overpass.osm.ch was in this list and had to be removed. It is the *Swiss*
# Overpass API - a regional extract. Ask it for Brazil and it returns HTTP 200
# with zero elements, which is indistinguishable from success. It served 61 of
# 55 countries on the first full run and silently wrote empty files for all of
# them. Any mirror added here must be verified as planet-wide first; the
# zero-result guard below is the backstop, not the check.
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

UA = ("EVchargeScout/1.0 (+https://milossavicgit.github.io/EVchargeScout/; "
      "contact@bymilossavic.com)")

QUERY_TIMEOUT = 300           # seconds, inside the Overpass query itself
HTTP_TIMEOUT  = 360
SLEEP_BETWEEN_COUNTRIES = 20  # be a guest, not a scraper
RETRIES_PER_MIRROR = 2
MIN_KEEP_RATIO = 0.80         # same guard as build_ev.py

COUNTRIES = [
    "IT","FR","DE","NL","BE","LU","AT","CH","GB","IE","DK","SE","NO","FI","IS",
    "EE","LV","LT","ES","PT","GR","SI","HR","MT","CY","PL","CZ","SK","HU","RO","BG",
    "RU","BY","UA","RS","TR","MK","MD","BA","AL","ME","XK",
    "US","CA","MX","AU","NZ","JP","KR","MY","ID","BR","UY","CL","AR","CO",
]

# Countries whose area query is too large for one request; split by bbox.
# (lat_s, lon_w, lat_n, lon_e) tiles covering the country.
BIG = {
    "RU": [(41,19,60,60),(41,60,60,110),(41,110,78,180),(60,19,78,60),(60,60,78,110)],
    "US": [(24,-125,50,-104),(24,-104,50,-83),(24,-83,50,-66)],
    "CA": [(41,-141,70,-100),(41,-100,70,-52)],
    "AU": [(-44,112,-10,133),(-44,133,-10,154)],
    "BR": [(-34,-74,5,-54),(-34,-54,5,-34)],
}


def q_area(cc):
    return (f"[out:json][timeout:{QUERY_TIMEOUT}];"
            f'area["ISO3166-1"="{cc.upper()}"][admin_level=2]->.a;'
            f'nwr["amenity"="charging_station"](area.a);'
            f"out center tags;")

def q_bbox(box):
    s, w, n, e = box
    return (f"[out:json][timeout:{QUERY_TIMEOUT}];"
            f'nwr["amenity"="charging_station"]({s},{w},{n},{e});'
            f"out center tags;")


POOL = None

def run_query(q):
    """Delegates to the mirror pool: busy hosts are skipped at once, broken ones
    are put in a long cooldown that is remembered across countries."""
    return POOL.query(q)


def elements_to_records(elements):
    """Overpass elements -> our record shape. 'out center' gives ways/relations
    a .center, so no polygon maths is needed here."""
    out, skipped = [], 0
    for el in elements:
        tags = el.get("tags") or {}
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            skipped += 1
            continue
        rec = to_record(el["type"][0], el["id"], lat, lon, tags)
        if rec: out.append(rec)
        else:   skipped += 1
    return out, skipped


def build_country(cc, out_dir, force=False):
    cc = cc.lower()
    path = os.path.join(out_dir, f"{cc}.json")

    if cc.upper() in BIG:
        boxes = BIG[cc.upper()]
        print(f"  [{cc}] large country - {len(boxes)} tiles", flush=True)
        seen, records = set(), []
        for i, box in enumerate(boxes, 1):
            data = run_query(q_bbox(box))
            recs, skipped = elements_to_records(data.get("elements", []))
            new = [r for r in recs if r["id"] not in seen]
            seen.update(r["id"] for r in new)
            records.extend(new)
            print(f"      tile {i}/{len(boxes)}: +{len(new)} (dropped {skipped})", flush=True)
            if i < len(boxes): time.sleep(10)
    else:
        print(f"  [{cc}] area query", flush=True)
        data = run_query(q_area(cc))
        records, skipped = elements_to_records(data.get("elements", []))
        print(f"      {len(records)} usable (dropped {skipped})", flush=True)

    # An empty result is never right. Every country in COUNTRIES has chargers;
    # zero means the query went somewhere that could not answer it - a regional
    # mirror, a truncated response, a bad area id. Fail loudly and write nothing,
    # so the country lands in _failed.txt and --resume does not skip it later.
    if not records:
        raise RuntimeError(
            f"{cc}: zero chargers returned. That is a fetch failure, not data. "
            f"Check the mirror is planet-wide.")

    # Cross-check against the OCM file for the same country where we have one.
    # The two sources disagree a lot, but not by two orders of magnitude - if
    # OSM comes back under 5% of OCM, something fetched wrong.
    ocm_path = os.path.join("ev", f"{cc}.json")
    if os.path.exists(ocm_path) and not force:
        try:
            ocm_n = json.load(open(ocm_path, encoding="utf-8")).get("count", 0)
        except Exception:                                        # noqa: BLE001
            ocm_n = 0
        if ocm_n >= 100 and len(records) < ocm_n * 0.05:
            raise RuntimeError(
                f"{cc}: OSM {len(records):,} against OCM {ocm_n:,} "
                f"({100.0*len(records)/ocm_n:.1f}%) - implausible, treating as a "
                f"failed fetch. Pass --force if this country really is that thin.")

    # Same protection as the OCM side: a country does not lose most of its
    # chargers overnight, so a big fall is a failed fetch, not real data.
    if os.path.exists(path) and not force:
        try:
            had = len(json.load(open(path, encoding="utf-8")).get("chargers", []))
        except Exception:                                        # noqa: BLE001
            had = 0
        if had and len(records) < had * MIN_KEEP_RATIO:
            raise RuntimeError(
                f"{cc}: {len(records):,} vs {had:,} on disk "
                f"({100.0*len(records)/had:.0f}%) - refusing to overwrite. "
                f"Re-run, or pass --force if the drop is real.")

    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({
            "area": cc,
            "source": "OpenStreetMap",
            "licence": "ODbL",
            "generated": time.strftime("%Y-%m-%d"),
            "count": len(records),
            "chargers": records,
        }, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)

    kb = os.path.getsize(path) // 1024
    withop = sum(1 for r in records if r["operator"])
    withkw = sum(1 for r in records if r["kw"] != "")
    print(f"      wrote {len(records):,} · {kb} KB · {withop} with operator · "
          f"{withkw} with power", flush=True)
    return len(records)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build EV charger data from OpenStreetMap.")
    ap.add_argument("--country", help="single ISO country code, e.g. PL")
    ap.add_argument("--all", action="store_true", help="every country in COUNTRIES")
    ap.add_argument("--out", default="osm", help="output folder (default: osm)")
    ap.add_argument("--force", action="store_true",
                    help="write even if the result is much smaller than what is on disk")
    ap.add_argument("--resume", action="store_true",
                    help="skip countries whose file was already built today")
    ap.add_argument("--only-failed", metavar="FILE", default=None,
                    help="re-run just the countries listed in a previous failures file")
    args = ap.parse_args(argv)

    if args.only_failed:
        targets = [l.strip().upper() for l in open(args.only_failed) if l.strip()]
    else:
        targets = COUNTRIES if args.all else ([args.country] if args.country else [])
    if not targets:
        ap.error("give --country XX, --all, or --only-failed FILE")

    os.makedirs(args.out, exist_ok=True)

    if args.resume:
        today, keep = time.strftime("%Y-%m-%d"), []
        for cc in targets:
            fp = os.path.join(args.out, f"{cc.lower()}.json")
            try:
                if json.load(open(fp, encoding="utf-8")).get("generated") == today:
                    continue
            except Exception:                                    # noqa: BLE001
                pass
            keep.append(cc)
        skipped = len(targets) - len(keep)
        if skipped:
            print(f"--resume: {skipped} already built today, {len(keep)} to go\n")
        targets = keep
        if not targets:
            print("Nothing left to do.")
            return 0

    global POOL
    POOL = OverpassPool(MIRRORS, UA, HTTP_TIMEOUT)
    total = ok = 0
    failed_ccs = []
    t0 = time.time()
    for i, cc in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {cc}", flush=True)
        try:
            total += build_country(cc, args.out, args.force)
            ok += 1
        except KeyboardInterrupt:
            print("\nInterrupted - files already written are kept.")
            break
        except Exception as e:                                   # noqa: BLE001
            failed_ccs.append(cc)
            print(f"      FAILED: {e}", flush=True)
        if i < len(targets):
            time.sleep(SLEEP_BETWEEN_COUNTRIES)

    mins = (time.time() - t0) / 60
    print(f"\nDone in {mins:.1f} min: {ok} countries, {len(failed_ccs)} failed, "
          f"{total:,} chargers.")
    print("mirrors:", POOL.report())
    if failed_ccs:
        fp = os.path.join(args.out, "_failed.txt")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(failed_ccs) + "\n")
        print(f"\nFailed: {', '.join(failed_ccs)}")
        print(f"Re-run just those with:  python build_osm.py --only-failed {fp}")
    print("Data (c) OpenStreetMap contributors (ODbL).")
    return 1 if failed_ccs else 0


if __name__ == "__main__":
    sys.exit(main())
