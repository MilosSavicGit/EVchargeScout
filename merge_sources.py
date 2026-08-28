#!/usr/bin/env python3
"""
merge_sources.py — fold OSM charging stations into the OCM records that
build_ev.py already produces, without putting two dots on the same charger.

WHY BOTH SOURCES

Neither is complete, and which one wins changes at national borders:

    country   OCM     OSM      better
    PL        501     3,039    OSM  6.1x
    CZ        649     3,053    OSM  4.7x
    DE     24,611    45,733    OSM  1.9x
    LT      1,909       438    OCM  4.4x

Lithuania is strong on OCM because Inbalance Grid submit to it. Poland is
strong on OSM because Polish mappers map GreenWay by hand and GreenWay do not
submit to OCM. Dropping either source loses real chargers somewhere.

WHY DEDUP IS A CASCADE AND NOT ONE RADIUS

Rule 4 below is the one people leave out. Motorway services genuinely have two
operators' chargers 30 m apart. A single "within 50 m = same charger" rule
silently deletes one of them, and nobody can see that it happened. A duplicate
dot is visible and annoying; a deleted charger is invisible and strands people.
Prefer the annoying failure.

GRANULARITY

An OSM charging_station is usually a whole site (one node, capacity=2), and an
OCM POI is also a site with several Connections. So these are site-to-site
matches, not socket-to-socket. Do not read the counts above as charge points.
"""

import math, re, unicodedata

# --- tuning ---------------------------------------------------------------
R_IDENTICAL = 10.0    # m: the SAME SPOT, whatever the two sources call it
R_SURE      = 25.0    # m: same spot unless the operators actively disagree
R_OPERATOR  = 50.0    # m: same spot if the operators agree
R_CONFLICT  = 100.0   # m: within this, a disagreeing operator means KEEP BOTH
CELL_M      = 120.0   # spatial grid cell; must exceed R_CONFLICT

_WS  = re.compile(r"\s+")
_PUN = re.compile(r"[^\w\s]")
# Legal-form noise that makes "GreenWay" and "GreenWay Polska Sp. z o.o." differ.
# OCM stores these in the operator field. They are placeholders meaning "we do
# not know", not company names. Treating them as names made every one of them
# conflict with the real operator OSM had. Four of the fifteen closest near
# misses in Poland were "(Business Owner at Location" against Orlen, Lotos,
# Leroy Merlin and Nissan - all at 2-3 m, all the same physical charger.
PLACEHOLDER_OPERATORS = {
    "businessowneratlocation", "unknownoperator", "unknown", "private",
    "privateindividual", "notapplicable", "na", "none", "other",
}

_NOISE = {"sp","z","o","oo","zoo","sa","spzoo","gmbh","ag","ltd","limited","plc",
          "bv","nv","as","ab","oy","srl","spa","doo","kft","polska","poland",
          "deutschland","group","energy","mobility","charging","emobility",
          "unknown","operator"}

_BRACKETED = re.compile(r"\([^)]*\)?")
# Legal forms, matched as whole patterns rather than by dropping short tokens.
# Dropping every single letter fixed "PKP S.A." but broke "E.ON" -> "on".
_LEGAL = re.compile(
    r"\b(?:s\.?\s*a\.?|sp\.?\s*z\s*o\.?\s*o\.?|s\.?\s*r\.?\s*o\.?"
    r"|a\.?\s*s\.?|d\.?\s*o\.?\s*o\.?|gmbh|ag|ltd|limited|plc|bv|nv|oy|ab)\b",
    re.I)

def norm_operator(s):
    """'GreenWay Polska Sp. z o.o.' -> 'greenway'. Empty means 'not stated'.

    Bracketed text is dropped before anything else. OCM qualifies its operator
    names that way - 'Greenway Polska (PL)', 'Tesla (Tesla-only charging)',
    'Essent (NL)' - and OSM does not, so every one of those was a false conflict.
    The trailing ')?' matters: OCM's own data contains the unclosed string
    '(Business Owner at Location'.
    """
    if not s: return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = _BRACKETED.sub(" ", s)
    s = _LEGAL.sub(" ", s)
    s = _PUN.sub(" ", s)
    toks = [t for t in _WS.split(s)
            if t and t not in _NOISE and not t.isdigit()]
    out = "".join(toks)
    return "" if out in PLACEHOLDER_OPERATORS else out

def same_operator(a, b):
    """Both normalised. Equal, or one a prefix of the other.

    OCM and OSM routinely disagree on how much of a corporate name to record:
      orlen        / orlencharge
      tauron       / tauronnowetechnologie
      pge          / pgenowaenergia
      greenway     / greenwaypolska
    A prefix test catches all of those. Three characters minimum: real operator
    names that short exist (PGE, EDF, EON), and the prefix test only ever runs
    on a pair already within 50 m of each other, so a chance collision would
    also have to be a chance collision in space.
    """
    if not a or not b: return False
    if a == b: return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 3 and long_.startswith(short)


def metres(lat1, lon1, lat2, lon2):
    """Equirectangular — fine at these distances and much cheaper than haversine."""
    mlat = math.radians((lat1 + lat2) / 2.0)
    dx = math.radians(lon2 - lon1) * math.cos(mlat) * 6371008.8
    dy = math.radians(lat2 - lat1) * 6371008.8
    return math.hypot(dx, dy)

def centroid(rec):
    """OSM ways/relations arrive as polygons; nodes already have lat/lon."""
    if rec.get("lat") is not None and rec.get("lon") is not None:
        return rec["lat"], rec["lon"]
    pts = rec.get("geometry") or []
    if not pts: return None, None
    return (sum(p["lat"] for p in pts)/len(pts),
            sum(p["lon"] for p in pts)/len(pts))

# --- spatial index --------------------------------------------------------
def _cell(lat, lon):
    dlat = CELL_M / 111320.0
    dlon = CELL_M / (111320.0 * max(0.2, math.cos(math.radians(lat))))
    return (int(lat / dlat), int(lon / dlon))

def _neighbours(lat, lon):
    r, c = _cell(lat, lon)
    return [(r+dr, c+dc) for dr in (-1,0,1) for dc in (-1,0,1)]

def _index(records):
    """Grid buckets so DE's 45k records cost O(n), not 2 billion comparisons."""
    grid = {}
    for i, r in enumerate(records):
        if r.get("lat") is None: continue
        grid.setdefault(_cell(r["lat"], r["lon"]), []).append(i)
    return grid

# --- the cascade ----------------------------------------------------------
def match(osm, ocm, dist):
    """Is this OSM record the same physical site as this OCM one?

    Returns (is_same, why). `why` is kept so a disputed merge can be explained
    rather than argued about.
    """
    # 1. EVSE ID — unique by EU regulation. Rare (PL 1.9%, DE 9.5%) but certain.
    a = (osm.get("evse") or "").strip().upper()
    b = (ocm.get("evse") or "").strip().upper()
    if a and b:
        return (a == b, "evse-id")          # IDs present and different = NOT same

    # Two DISTINCT charging sites do not exist 10 m apart. At this range a
    # disagreement is two databases naming one thing differently - a subsidiary
    # (Enspirion vs Energa), a placeholder, a bracketed qualifier - not two
    # chargers. Proximity wins, and it must be checked BEFORE the operator
    # rules or those reject it at 2 m.
    if dist <= R_IDENTICAL:
        return True, "same-spot-10m"

    oa, ob = norm_operator(osm.get("operator")), norm_operator(ocm.get("operator"))
    wa, wb = osm.get("operator_wikidata"), ocm.get("operator_wikidata")

    # 2. Wikidata QID beats string matching outright where both have it.
    if wa and wb:
        if wa == wb and dist <= R_OPERATOR: return True,  "wikidata+50m"
        if wa != wb and dist <= R_CONFLICT: return False, "wikidata-conflict"

    # 3. Operators agree, and close enough.
    if oa and ob and same_operator(oa, ob) and dist <= R_OPERATOR:
        return True, "operator+50m"

    # 4. Operators actively disagree — two networks at one services. KEEP BOTH.
    if oa and ob and not same_operator(oa, ob) and dist <= R_CONFLICT:
        return False, "operator-conflict"

    # 5. Nobody contradicts anybody, and it is very close.
    if dist <= R_SURE:
        return True, "proximity-25m"

    return False, "no-match"

def dedupe(ocm_records, osm_records):
    """OCM records stay primary; unmatched OSM records are appended.

    Each survivor gains "src": "ocm" | "osm" | "both". Two independent sources
    agreeing is worth showing a driver, so it is recorded rather than discarded.
    """
    for r in ocm_records:
        r.setdefault("src", "ocm")

    grid, merged, added = _index(ocm_records), 0, []

    for o in osm_records:
        lat, lon = centroid(o)
        if lat is None:
            continue
        best, best_d, best_why = None, 1e9, ""
        for cellkey in _neighbours(lat, lon):
            for i in grid.get(cellkey, ()):
                c = ocm_records[i]
                d = metres(lat, lon, c["lat"], c["lon"])
                if d > R_CONFLICT:
                    continue
                same, why = match({**o, "lat": lat, "lon": lon}, c, d)
                if same and d < best_d:
                    best, best_d, best_why = c, d, why
        if best is not None:
            best["src"] = "both"
            best.setdefault("osm_id", o.get("osm_id"))
            # Fill only what OCM left blank. Never overwrite - OCM's operator and
            # cost fields are curated; OSM's are whatever a mapper typed.
            for k in ("operator", "name", "kw", "points"):
                if not best.get(k) and o.get(k):
                    best[k] = o[k]
            best.setdefault("match", best_why)
            merged += 1
        else:
            n = dict(o)
            n["lat"], n["lon"] = lat, lon
            n["src"] = "osm"
            n.pop("geometry", None)
            added.append(n)

    return ocm_records + added, {
        "ocm_in": len(ocm_records), "osm_in": len(osm_records),
        "merged": merged, "osm_only": len(added),
        "total_out": len(ocm_records) + len(added),
    }
