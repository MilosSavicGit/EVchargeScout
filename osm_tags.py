#!/usr/bin/env python3
"""
osm_tags.py — turn one OSM charging_station's tags into the record shape
build_ev.py already emits, so OSM and OCM entries are interchangeable
downstream.

Kept separate from any osmium import on purpose: this is pure tag logic, so it
can be unit-tested without a PBF, and the tests are the documentation of what
each OSM tag was taken to mean.

CONNECTOR FAMILIES match connector_family() in build_ev.py exactly. If that
function gains a family, add it here too or OSM records will silently classify
as OTHER and drop out of compatibility filtering.

WHAT OSM DOES NOT GIVE YOU
  - No usage vocabulary matching OCM's. access=* is coarser; we map it to the
    nearest OCM phrasing rather than inventing new strings the app cannot show.
  - No reliable price. fee=yes means "costs money", not how much. We never
    fabricate a number - blank is honest, "0" would not be.
"""

import re

# OSM socket:* key -> the family build_ev.py's connector_family() produces.
SOCKET_FAMILY = {
    "type2":              "TYPE2",
    "type2_cable":        "TYPE2",
    "type2_combo":        "CCS2",
    "type1":              "TYPE1",
    "type1_cable":        "TYPE1",
    "type1_combo":        "CCS1",
    "chademo":            "CHADEMO",
    "tesla_supercharger": "NACS",
    "nacs":               "NACS",
    "tesla_supercharger_ccs": "CCS2",
    "tesla_destination":  "TESLA_OTHER",
    "tesla_standard":     "TESLA_OTHER",
    "schuko":             "DOMESTIC",
    "cee_blue":           "DOMESTIC",
    "cee_red_16a":        "DOMESTIC",
    "cee_red_32a":        "DOMESTIC",
    "domestic":           "DOMESTIC",
    "bs1363":             "DOMESTIC",
    "gb_dc":              "GBT_DC",
    "gb_ac":              "GBT_AC",
    "type3":              "TYPE3",
    "type3c":             "TYPE3",
}

_NUM = re.compile(r"(\d+(?:[.,]\d+)?)")

def _kw(val):
    """'150 kW' / '22000' / '11,5' -> float kW. Watts are converted."""
    if val is None: return None
    m = _NUM.search(str(val))
    if not m: return None
    try: n = float(m.group(1).replace(",", "."))
    except ValueError: return None
    if n <= 0: return None
    s = str(val).lower()
    if "kw" in s: return n
    if "w" in s and "kw" not in s: return n / 1000.0
    return n / 1000.0 if n > 400 else n     # bare number: >400 must be watts

def _int(val):
    if val is None: return None
    m = re.search(r"\d+", str(val))
    return int(m.group(0)) if m else None

def connectors(tags):
    """Families present, and how many sockets had no recognised type.

    'unknown' is not 'incompatible' - the app must be able to say a connector
    was not recorded rather than wrongly ruling a stop out. Same contract as
    the OCM side.
    """
    fams, unknown = [], 0
    for k, v in tags.items():
        if not k.startswith("socket:"):
            continue
        rest = k[len("socket:"):]
        if ":" in rest:                  # socket:type2:output etc - not a count
            continue
        if str(v).strip().lower() in ("no", "0", "none"):
            continue
        fam = SOCKET_FAMILY.get(rest.lower())
        if fam is None:
            unknown += 1
        elif fam not in fams:
            fams.append(fam)
    return fams, unknown

def power_kw(tags):
    """Highest per-socket output, else the station-wide figure."""
    best = None
    for k, v in tags.items():
        if k.startswith("socket:") and k.endswith(":output"):
            n = _kw(v)
            if n and (best is None or n > best): best = n
    if best is not None: return best
    for k in ("charging_station:output", "maxpower", "power", "output"):
        n = _kw(tags.get(k))
        if n: return n
    return None

def cost(tags):
    """OCM's 'cost' is free text. Match its vocabulary; never invent a price."""
    fee = (tags.get("fee") or "").strip().lower()
    charge = (tags.get("charge") or "").strip()
    if fee in ("no", "false"):   return "Free"
    if fee in ("yes", "true"):   return charge or "Paid"
    if charge:                   return charge
    return ""

def usage(tags):
    """access=* -> the nearest phrase OCM already uses, so the UI needs no new strings."""
    a = (tags.get("access") or "").strip().lower()
    return {
        "yes":         "Public",
        "public":      "Public",
        "permissive":  "Public",
        "customers":   "Private - For Staff, Visitors or Customers",
        "customer":    "Private - For Staff, Visitors or Customers",
        "private":     "Private - Restricted Access",
        "no":          "Private - Restricted Access",
        "permit":      "Privately Owned - Notice Required",
        "destination": "Private - For Staff, Visitors or Customers",
    }.get(a, "")

def to_record(osm_type, osm_id, lat, lon, tags):
    """One OSM object -> one record in build_ev.py's shape, plus match keys."""
    if tags.get("amenity") != "charging_station":
        return None
    # Bicycle-only stations are not car chargers. motorcar=no is explicit.
    if (tags.get("motorcar") or "").lower() == "no":
        return None
    if (tags.get("bicycle") or "").lower() == "yes" and not any(
            k.startswith("socket:") for k in tags):
        return None

    fams, unknown = connectors(tags)
    kw = power_kw(tags)
    rec = {
        "id":       f"osm:{osm_type}{osm_id}",
        "lat":      round(lat, 6),
        "lon":      round(lon, 6),
        "name":     tags.get("name") or tags.get("brand") or tags.get("operator") or "",
        "town":     tags.get("addr:city") or "",
        "operator": tags.get("operator") or tags.get("brand") or "",
        "kw":       kw if kw is not None else "",
        "points":   _int(tags.get("capacity")) or 0,
        "cost":     cost(tags),
        "usage":    usage(tags),
        "conn":     fams,
        # match keys - consumed by merge_sources.py, stripped before shipping
        "evse":               tags.get("ref:EU:EVSE") or "",
        "operator_wikidata":  tags.get("operator:wikidata") or "",
        "osm_id":             f"{osm_type}{osm_id}",
    }
    if unknown: rec["conn_unknown"] = unknown
    return rec
