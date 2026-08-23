#!/usr/bin/env python3
"""
build_ev.py — build EV charger data per country from Open Charge Map.

Writes ev/<cc>.json in the compact shape EVchargeScout reads directly, so the
app stays static with no runtime API call and no key in the browser.

    python build_ev.py --country DE
    python build_ev.py --all                 # every country in COUNTRIES
    python build_ev.py --all --since 2026-08-01   # only what changed
    python build_ev.py --all --since auto          # since each file was built

Set OCM_API_KEY in the environment. Never pass the key on the command line on a
shared machine and never commit it.

Data (c) Open Charge Map contributors, CC BY 4.0.

------------------------------------------------------------------------------
WHY THIS REPLACED THE OLD SCRIPT

1. compact=true returns OperatorID / UsageTypeID as integers, NOT the nested
   OperatorInfo{} and UsageType{} objects. The old parser read the nested form,
   so operator and usage were empty on 100% of records - measured on de.json:
   24,605 of 24,605 blank. That silently degraded the app's "which app to use"
   feature to matching on charger name alone. We now fetch /referencedata once
   and hydrate the IDs into names ourselves, which keeps the small payload AND
   gets the names back.

2. Records carried no OCM ID, so there was no key to merge an update against.
   Every refresh had to be a full re-download of every country. OCM is a
   non-profit on donated infrastructure and asks callers not to do that. Each
   record now stores "id", which makes --since deltas possible.

3. The key travelled in the query string. OCM asks for the X-API-Key header;
   query strings leak into proxy and server logs.

4. Paging: a single request relied on one response carrying an entire country.
   We now page on greaterthanid with sortby=id_asc, so a country that outgrows
   any single response still completes.
------------------------------------------------------------------------------
"""

import argparse, json, os, sys, tempfile, time
import urllib.parse, urllib.request, urllib.error

OCM_POI = "https://api.openchargemap.io/v3/poi/"
OCM_REF = "https://api.openchargemap.io/v3/referencedata/"

# OCM asks callers to identify themselves so they can tell apps apart from
# anonymous scraping, and contact you rather than ban you if something is wrong.
UA = "EVchargeScout/1.0 (+https://milossavicgit.github.io/EVchargeScout/; contact@bymilossavic.com)"

PAGE_SIZE = 5000          # per request; OCM pages fine at this size
SLEEP_BETWEEN_PAGES = 2.0
SLEEP_BETWEEN_COUNTRIES = 5.0

# Matches build_ev_all.bat. Order is roughly by expected coverage.
COUNTRIES = [
    "IT","FR","DE","NL","BE","LU","AT","CH","GB","IE","DK","SE","NO","FI","IS",
    "EE","LV","LT","ES","PT","GR","SI","HR","MT","CY","PL","CZ","SK","HU","RO","BG",
    "RU","BY","UA","RS","TR","MK","MD","BA","AL","ME","XK",
    "US","CA","MX","AU","NZ",
]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def get_json(url, key=None, timeout=180):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if key:
        headers["X-API-Key"] = key        # header, not query string
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def get_json_retry(url, key=None, timeout=180, attempts=5):
    last = None
    for i in range(attempts):
        try:
            return get_json(url, key, timeout)
        except urllib.error.HTTPError as e:
            # A bad key or malformed request will never succeed on retry.
            if e.code in (400, 401, 403):
                raise RuntimeError(
                    f"Open Charge Map rejected the request (HTTP {e.code}). Check OCM_API_KEY "
                    f"at https://openchargemap.org/site/profile/applications")
            last = e
            wait = 15 * (i + 1)
            print(f"      HTTP {e.code}; retry in {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:                                   # noqa: BLE001
            last = e
            wait = 15 * (i + 1)
            print(f"      {type(e).__name__}; retry in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Open Charge Map unreachable: {last}")


# ---------------------------------------------------------------------------
# Reference data - this is what restores the operator and usage names.
# ---------------------------------------------------------------------------

def load_reference(key):
    """id -> title maps for operators and usage types.

    Fetched ONCE per run, not per country. compact=true gives us IDs; these maps
    turn them back into the names the app displays and matches roaming apps on.
    """
    print("Fetching reference data...", flush=True)
    ref = get_json_retry(OCM_REF, key)
    ops = {o["ID"]: (o.get("Title") or "").strip()
           for o in ref.get("Operators", []) if o.get("ID") is not None}
    usage = {}
    for u in ref.get("UsageTypes", []):
        if u.get("ID") is None:
            continue
        usage[u["ID"]] = {
            "title": (u.get("Title") or "").strip(),
            "membership": bool(u.get("IsMembershipRequired")),
            "payAtLocation": bool(u.get("IsPayAtLocation")),
        }
    print(f"  {len(ops)} operators, {len(usage)} usage types", flush=True)
    return ops, usage


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_charger(poi, ops, usage):
    """One OCM POI -> the compact record the app consumes.

    Handles BOTH shapes: compact mode (OperatorID int) and verbose mode
    (OperatorInfo{} object), so the script keeps working if the output mode is
    ever changed.
    """
    ai = poi.get("AddressInfo") or {}
    lat, lon = ai.get("Latitude"), ai.get("Longitude")
    if lat is None or lon is None:
        return None

    conns = poi.get("Connections") or []
    kws = [c.get("PowerKW") for c in conns if c.get("PowerKW")]
    qty = sum((c.get("Quantity") or 0) for c in conns)

    # Operator: prefer the nested object if present, else look the ID up.
    op = ""
    oi = poi.get("OperatorInfo")
    if isinstance(oi, dict):
        op = (oi.get("Title") or "").strip()
    if not op and poi.get("OperatorID") is not None:
        op = ops.get(poi["OperatorID"], "")

    # Usage type: same two shapes.
    ut_title, membership, pay_at = "", False, False
    ut = poi.get("UsageType")
    if isinstance(ut, dict):
        ut_title = (ut.get("Title") or "").strip()
        membership = bool(ut.get("IsMembershipRequired"))
        pay_at = bool(ut.get("IsPayAtLocation"))
    elif poi.get("UsageTypeID") is not None:
        u = usage.get(poi["UsageTypeID"])
        if u:
            ut_title, membership, pay_at = u["title"], u["membership"], u["payAtLocation"]

    rec = {
        # The OCM ID is what makes incremental updates possible. Without it
        # every refresh has to re-download the world.
        "id": poi.get("ID"),
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "name": ai.get("Title") or "",
        "town": (ai.get("Town") or ai.get("StateOrProvince") or "").strip(),
        "operator": op,
        "kw": max(kws) if kws else "",
        "points": poi.get("NumberOfPoints") or qty or "",
        "cost": (poi.get("UsageCost") or "").strip(),
        "usage": ut_title,
    }
    if membership: rec["membership"] = 1
    if pay_at:     rec["payAtLocation"] = 1
    return rec


# ---------------------------------------------------------------------------
# Fetching a country, with paging
# ---------------------------------------------------------------------------

def fetch_country(cc, key, since=None):
    """Every POI for a country, paged. Returns a list of raw POIs.

    Paging uses greaterthanid + sortby=id_asc rather than an offset, so a record
    being added mid-run cannot cause a page to be skipped or repeated.
    """
    out, last_id, page = [], 0, 0
    while True:
        params = {
            "output": "json",
            "compact": "true",
            "verbose": "false",
            "countrycode": cc.upper(),
            "maxresults": str(PAGE_SIZE),
            "sortby": "id_asc",
        }
        if last_id:
            params["greaterthanid"] = str(last_id)
        if since:
            params["modifiedsince"] = since

        url = OCM_POI + "?" + urllib.parse.urlencode(params)
        batch = get_json_retry(url, key)
        if not batch:
            break

        out.extend(batch)
        page += 1
        ids = [p.get("ID") for p in batch if p.get("ID") is not None]
        if not ids:
            break                       # nothing to page on - stop rather than loop
        new_last = max(ids)
        if new_last <= last_id:
            break                       # no forward progress; guard against a loop
        last_id = new_last
        print(f"      page {page}: {len(batch)} (id<={last_id})", flush=True)

        if len(batch) < PAGE_SIZE:
            break                       # short page = last page
        time.sleep(SLEEP_BETWEEN_PAGES)
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_json_atomic(path, obj):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def load_existing(path):
    if not os.path.exists(path):
        return None
    try:
        # encoding is not optional: Windows defaults to cp1252 and these files
        # are full of non-ASCII place names.
        return json.load(open(path, encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return None


def merge(existing, fresh):
    """Merge fresh records over existing ones, keyed on OCM id.

    NOTE what this cannot do: a POI DELETED at OCM simply stops being returned,
    it does not come back flagged. A delta run therefore never removes anything.
    Run a full rebuild (no --since) periodically to pick up removals.
    """
    by_id = {}
    for r in (existing or {}).get("chargers", []):
        if r.get("id") is not None:
            by_id[r["id"]] = r
    added = updated = 0
    for r in fresh:
        if r.get("id") is None:
            continue
        if r["id"] in by_id: updated += 1
        else:                added += 1
        by_id[r["id"]] = r
    return list(by_id.values()), added, updated


def build_country(cc, key, out_dir, ops, usage, since=None):
    cc = cc.lower()
    path = os.path.join(out_dir, f"{cc}.json")
    existing = load_existing(path)

    eff_since = since
    if since == "auto":
        eff_since = (existing or {}).get("generated")
        if not eff_since:
            eff_since = None            # never built - must do a full pull

    mode = f"since {eff_since}" if eff_since else "full"
    print(f"  [{cc}] {mode}", flush=True)

    pois = fetch_country(cc, key, eff_since)
    fresh = [c for c in (parse_charger(p, ops, usage) for p in pois) if c]

    if eff_since and existing:
        chargers, added, updated = merge(existing, fresh)
        note = f"{added} new, {updated} updated"
    else:
        chargers, note = fresh, f"{len(fresh)} total"

    save_json_atomic(path, {
        "area": cc,
        "source": "Open Charge Map",
        "generated": time.strftime("%Y-%m-%d"),
        "count": len(chargers),
        "chargers": chargers,
    })
    blank_op = sum(1 for c in chargers if not c["operator"])
    kb = os.path.getsize(path) // 1024
    print(f"      {len(chargers):,} chargers · {kb} KB · {note} · "
          f"{blank_op} without operator", flush=True)
    return len(chargers)


def update_manifest(out_dir):
    """ev/ev.json - the index of built areas."""
    rows = []
    for fn in sorted(os.listdir(out_dir)):
        if not fn.endswith(".json") or fn == "ev.json":
            continue
        d = load_existing(os.path.join(out_dir, fn))
        if not d:
            continue
        rows.append({"area": d.get("area", fn[:-5]),
                     "file": f"{out_dir}/{fn}",
                     "count": d.get("count", 0),
                     "generated": d.get("generated", "")})
    rows.sort(key=lambda r: -r["count"])
    save_json_atomic(os.path.join(out_dir, "ev.json"), rows)
    return len(rows)


def bump_data_version(index_path):
    """Rewrite EV_DATA_VERSION in index.html to today.

    This is the step that is easy to forget and impossible to notice: the app
    fetches ev/<cc>.json with cache:'force-cache' and a ?v= built from this
    constant. New files without a new version means every returning user keeps
    serving the copy their browser already has - silently, forever.
    """
    if not os.path.exists(index_path):
        print(f"  (no {index_path} here - skipping version bump)")
        return False
    today = time.strftime("%Y-%m-%d")
    src = open(index_path, encoding="utf-8").read()
    import re
    new, n = re.subn(r'(const EV_DATA_VERSION\s*=\s*")[^"]*(")',
                     rf'\g<1>{today}\g<2>', src, count=1)
    if not n:
        print("  WARNING: EV_DATA_VERSION not found in index.html - not bumped")
        return False
    if new == src:
        print(f"  EV_DATA_VERSION already {today}")
        return False
    open(index_path, "w", encoding="utf-8").write(new)
    print(f"  EV_DATA_VERSION -> {today}")
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build EV charger data from Open Charge Map.")
    ap.add_argument("--country", help="single ISO country code, e.g. DE")
    ap.add_argument("--all", action="store_true", help="build every country in COUNTRIES")
    ap.add_argument("--since", help='YYYY-MM-DD for a delta, or "auto" to use each '
                                    'file\'s own generated date')
    ap.add_argument("--out", default="ev", help="output folder (default: ev)")
    ap.add_argument("--index", default="index.html", help="index.html to bump EV_DATA_VERSION in")
    ap.add_argument("--no-bump", action="store_true", help="do not touch index.html")
    args = ap.parse_args(argv)

    key = os.environ.get("OCM_API_KEY", "")
    if not key:
        print("OCM_API_KEY is not set. Get a free key at "
              "https://openchargemap.org/site/profile/applications", file=sys.stderr)
        return 1

    targets = COUNTRIES if args.all else ([args.country] if args.country else [])
    if not targets:
        ap.error("give --country XX or --all")

    os.makedirs(args.out, exist_ok=True)
    ops, usage = load_reference(key)

    total = ok = failed = 0
    t0 = time.time()
    for i, cc in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {cc}", flush=True)
        try:
            total += build_country(cc, key, args.out, ops, usage, args.since)
            ok += 1
        except KeyboardInterrupt:
            print("\nInterrupted - files already written are kept.")
            break
        except Exception as e:                                   # noqa: BLE001
            failed += 1
            print(f"      FAILED: {e}", flush=True)
        if i < len(targets):
            time.sleep(SLEEP_BETWEEN_COUNTRIES)

    n = update_manifest(args.out)
    if not args.no_bump:
        bump_data_version(args.index)

    mins = (time.time() - t0) / 60
    print(f"\nDone in {mins:.1f} min: {ok} countries, {failed} failed, "
          f"{total:,} chargers, manifest lists {n}.")
    print("Data (c) Open Charge Map contributors (CC BY 4.0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
