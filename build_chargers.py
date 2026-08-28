#!/usr/bin/env python3
"""
build_chargers.py — build an EV-charging layer per city from Open Charge Map.

OSM only tags a handful of chargers (via capacity:charging on parking). Open
Charge Map (openchargemap.org) is the open global registry built for exactly
this — far denser, refreshed monthly, free, CC BY 4.0. This script fetches the
chargers inside each city's bounding box and writes chargers/<slug>.json in a
compact format the app reads directly (so the app stays static — no runtime API).

  python build_chargers.py --key YOURKEY                 # every city in cities/
  python build_chargers.py cities/copenhagen-2192363.json --key YOURKEY
  python build_chargers.py --key YOURKEY --status
  python build_chargers.py --key YOURKEY --refresh        # re-fetch existing

Get a free API key at  https://openchargemap.org/site/develop/  (or set the
OCM_API_KEY environment variable instead of passing --key).

Resumable and safe to interrupt: each city is written atomically and already-built
ones are skipped. Attribution: the app credits "© Open Charge Map contributors".
Requires parking_probe.py alongside (reused for the polite HTTP helper).
"""

import argparse, glob, json, os, sys, time, tempfile
import urllib.parse, urllib.error

import parking_probe as pp   # reuse get_json (User-Agent, JSON) — be a good citizen

OCM_API = "https://api.openchargemap.io/v3/poi/"


def bbox_of(parking_path, pad=0.01):
    """Bounding box (minlat, minlon, maxlat, maxlon) + city name from a parking file."""
    d = json.load(open(parking_path, encoding="utf-8"))
    els = d.get("elements") or []
    lats = [e["lat"] for e in els if "lat" in e]
    lons = [e["lon"] for e in els if "lon" in e]
    city = d.get("city") or os.path.basename(parking_path)
    if lats and lons:
        return min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad, city
    c = d.get("centre") or {}
    if "lat" in c:
        return c["lat"] - pad, c["lon"] - pad, c["lat"] + pad, c["lon"] + pad, city
    return None


def fetch_chargers(minlat, minlon, maxlat, maxlon, key, maxresults=5000):
    params = {
        "output": "json", "compact": "true",   # expanded titles (operator, usage, cost)
        # OCM bounding box is (lat,lng),(lat,lng) — two opposite corners.
        "boundingbox": f"({maxlat},{minlon}),({minlat},{maxlon})",
        "maxresults": str(maxresults),
    }
    if key:
        params["key"] = key   # a wrong key is worse than none — omit if not supplied
    url = OCM_API + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(5):
        try:
            return pp.get_json(url, timeout=120)
        except urllib.error.HTTPError as e:
            # A bad or placeholder API key returns 401/403 — retrying won't help.
            if e.code in (400, 401, 403):
                raise RuntimeError(
                    f"Open Charge Map rejected the request (HTTP {e.code}). Your API key "
                    f"looks wrong — replace the placeholder with your real key from "
                    f"https://openchargemap.org/site/profile/applications (or set OCM_API_KEY).")
            last = e
            wait = 15 * (attempt + 1)
            print(f"    OCM HTTP {e.code}; retry in {wait}s")
            time.sleep(wait)
        except Exception as e:                                  # noqa: BLE001
            last = e
            wait = 15 * (attempt + 1)
            print(f"    OCM request failed ({type(e).__name__}); retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Open Charge Map unreachable: {last}")


def parse_charger(poi):
    ai = poi.get("AddressInfo") or {}
    lat, lon = ai.get("Latitude"), ai.get("Longitude")
    if lat is None or lon is None:
        return None
    conns = poi.get("Connections") or []
    kws = [c.get("PowerKW") for c in conns if c.get("PowerKW")]
    qty = sum((c.get("Quantity") or 0) for c in conns)
    op = (poi.get("OperatorInfo") or {}).get("Title") or ""
    ut = poi.get("UsageType") or {}
    rec = {
        "lat": round(float(lat), 6), "lon": round(float(lon), 6),
        "name": ai.get("Title") or "",
        "town": (ai.get("Town") or ai.get("StateOrProvince") or "").strip(),
        "operator": op,
        "kw": max(kws) if kws else "",
        "points": poi.get("NumberOfPoints") or qty or "",
        "cost": (poi.get("UsageCost") or "").strip(),   # "Free", "0.45 EUR/kWh", etc.
        "usage": (ut.get("Title") or "").strip(),        # "Public", "Public - Membership Required"
    }
    if ut.get("IsMembershipRequired"): rec["membership"] = 1
    if ut.get("IsPayAtLocation"):      rec["payAtLocation"] = 1
    return rec


def save_json_atomic(path, obj):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def build_one(parking_path, out_dir, key, pad, refresh):
    slug = os.path.basename(parking_path)
    out_path = os.path.join(out_dir, slug)
    if os.path.exists(out_path) and not refresh:
        return "exists", out_path
    bb = bbox_of(parking_path, pad)
    if not bb:
        return "skip", "no bounds"
    minlat, minlon, maxlat, maxlon, city = bb
    pois = fetch_chargers(minlat, minlon, maxlat, maxlon, key)      # may raise
    chargers = [c for c in (parse_charger(p) for p in pois) if c]
    save_json_atomic(out_path, {
        "city": city, "source": "Open Charge Map",
        "generated": time.strftime("%Y-%m-%d"),
        "count": len(chargers), "chargers": chargers,
    })
    return "saved", {"path": out_path, "count": len(chargers),
                     "kb": os.path.getsize(out_path) // 1024}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build EV charger layers from Open Charge Map.")
    ap.add_argument("files", nargs="*", help="specific cities/<slug>.json files (default: all in --dir)")
    ap.add_argument("--dir", default="cities", help="folder of parking JSONs to match (default: cities)")
    ap.add_argument("--out", default="chargers", help="output folder (default: chargers)")
    ap.add_argument("--key", default=os.environ.get("OCM_API_KEY", ""),
                    help="Open Charge Map API key (or set OCM_API_KEY)")
    ap.add_argument("--pad", type=float, default=0.01, help="bbox padding in degrees")
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between cities")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if already saved")
    ap.add_argument("--status", action="store_true", help="print progress and exit")
    args = ap.parse_args(argv)

    targets = args.files or sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if not targets:
        print(f"No parking JSONs found in {args.dir}/ — build cities first.")
        return

    if args.status:
        done = sum(1 for t in targets if os.path.exists(os.path.join(args.out, os.path.basename(t))))
        print(f"Cities: {len(targets)}   charger layers built: {done}   remaining: {len(targets) - done}")
        return

    if not args.key:
        print("No API key given — trying Open Charge Map anonymously. If this 403s, get a "
              "free key at https://openchargemap.org/site/profile/applications and pass --key.\n")

    os.makedirs(args.out, exist_ok=True)
    saved = skipped = failed = 0
    try:
        for i, path in enumerate(targets, 1):
            name = os.path.basename(path)
            print(f"[{i}/{len(targets)}] {name}")
            try:
                status, detail = build_one(path, args.out, args.key, args.pad, args.refresh)
                if status == "exists":
                    skipped += 1; print("    already built — skipping"); continue
                if status == "skip":
                    failed += 1; print(f"    {detail} — skipping"); continue
                saved += 1
                print(f"    {detail['count']:>5} chargers · {detail['kb']} KB")
            except KeyboardInterrupt:
                raise
            except Exception as e:                              # noqa: BLE001
                failed += 1; print(f"    FAILED: {e}")
            time.sleep(args.sleep)
    except KeyboardInterrupt:
        print("\nInterrupted — progress saved. Rerun to continue.")

    print(f"\nDone: {saved} saved, {skipped} already had, {failed} failed. "
          f"Chargers in {args.out}/  (data © Open Charge Map contributors).")


if __name__ == "__main__":
    main()
