"""Cases that matter. Each one is a real failure mode, not a synthetic edge."""
from merge_sources import dedupe, norm_operator, metres

def offset(lat, lon, m_north, m_east):
    return lat + m_north/111320.0, lon + m_east/(111320.0*0.6)   # ~53N

BASE_LAT, BASE_LON = 52.2297, 21.0122   # Warsaw

def case(name, ocm, osm, expect_total, expect_merged):
    out, st = dedupe([dict(r) for r in ocm], [dict(r) for r in osm])
    ok = (st["total_out"] == expect_total and st["merged"] == expect_merged)
    print(f"{'PASS' if ok else 'FAIL'}  {name:44s} out={st['total_out']} merged={st['merged']} "
          f"(want {expect_total}/{expect_merged})")
    if not ok:
        for r in out: print("      ", {k:r.get(k) for k in ('name','operator','src','match')})
    return ok

allok = True

# 1. Same charger, same operator, 12 m apart — the ordinary duplicate.
la, lo = offset(BASE_LAT, BASE_LON, 12, 0)
allok &= case("same operator, 12m apart -> merge",
  [{"id":1,"lat":BASE_LAT,"lon":BASE_LON,"operator":"GreenWay Polska Sp. z o.o."}],
  [{"osm_id":"n1","lat":la,"lon":lo,"operator":"GreenWay"}], 1, 1)

# 2. Two operators 30 m apart at a services — MUST stay two dots.
la, lo = offset(BASE_LAT, BASE_LON, 30, 0)
allok &= case("different operators, 30m -> keep both",
  [{"id":2,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Orlen Charge"}],
  [{"osm_id":"n2","lat":la,"lon":lo,"operator":"GreenWay"}], 2, 0)

# 3. Neither states an operator, 15 m apart — assume same.
la, lo = offset(BASE_LAT, BASE_LON, 15, 0)
allok &= case("no operator either side, 15m -> merge",
  [{"id":3,"lat":BASE_LAT,"lon":BASE_LON,"operator":""}],
  [{"osm_id":"n3","lat":la,"lon":lo}], 1, 1)

# 4. Same operator but 80 m apart — beyond the operator radius, keep both.
la, lo = offset(BASE_LAT, BASE_LON, 80, 0)
allok &= case("same operator, 80m -> keep both",
  [{"id":4,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Ionity"}],
  [{"osm_id":"n4","lat":la,"lon":lo,"operator":"Ionity"}], 2, 0)

# 5. EVSE IDs disagree at 10 m — the ID wins over proximity.
la, lo = offset(BASE_LAT, BASE_LON, 10, 0)
allok &= case("EVSE ids differ, 10m -> keep both",
  [{"id":5,"lat":BASE_LAT,"lon":BASE_LON,"evse":"PL*GRW*E1001"}],
  [{"osm_id":"n5","lat":la,"lon":lo,"evse":"PL*GRW*E1002"}], 2, 0)

# 6. EVSE IDs agree at 90 m — mapper put the node across the car park.
la, lo = offset(BASE_LAT, BASE_LON, 90, 0)
allok &= case("EVSE ids match, 90m -> merge",
  [{"id":6,"lat":BASE_LAT,"lon":BASE_LON,"evse":"PL*GRW*E1003"}],
  [{"osm_id":"n6","lat":la,"lon":lo,"evse":"PL*GRW*E1003"}], 1, 1)

# 7. Wikidata QIDs disagree at 20 m — beats the 25 m proximity rule.
la, lo = offset(BASE_LAT, BASE_LON, 20, 0)
allok &= case("wikidata conflict, 20m -> keep both",
  [{"id":7,"lat":BASE_LAT,"lon":BASE_LON,"operator_wikidata":"Q111"}],
  [{"osm_id":"n7","lat":la,"lon":lo,"operator_wikidata":"Q222"}], 2, 0)

# 8. OSM way with no lat/lon — centroid from geometry.
allok &= case("OSM way polygon -> centroid then merge",
  [{"id":8,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Energa"}],
  [{"osm_id":"w8","operator":"Energa","geometry":[
      {"lat":BASE_LAT-0.00005,"lon":BASE_LON-0.00005},
      {"lat":BASE_LAT+0.00005,"lon":BASE_LON+0.00005}]}], 1, 1)

# 9. Far apart — untouched.
allok &= case("2 km apart -> both kept",
  [{"id":9,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Ionity"}],
  [{"osm_id":"n9","lat":BASE_LAT+0.018,"lon":BASE_LON,"operator":"Ionity"}], 2, 0)

print()
print("operator normalisation:")
for a,b in [("GreenWay Polska Sp. z o.o.","GreenWay"),
            ("ORLEN Charge","Orlen charge"),
            ("(Unknown Operator)",""),
            ("E.ON Drive","EON Drive")]:
    print(f"   {a!r:34s} -> {norm_operator(a)!r:14s} | {b!r:22s} -> {norm_operator(b)!r}")

print()
print("ALL PASS" if allok else "SOME FAILED")

# ---------------------------------------------------------------------------
# Cases added after auditing real Polish data. Every one of these was a genuine
# near miss that the first version rejected as an operator conflict at 1-3 m.
# ---------------------------------------------------------------------------
print("\n--- regressions found in real PL data ---")

la, lo = offset(BASE_LAT, BASE_LON, 2, 0)
allok &= case("OCM placeholder operator, 2m -> merge",
  [{"id":20,"lat":BASE_LAT,"lon":BASE_LON,"operator":"(Business Owner at Location"}],
  [{"osm_id":"n20","lat":la,"lon":lo,"operator":"Orlen"}], 1, 1)

la, lo = offset(BASE_LAT, BASE_LON, 3, 0)
allok &= case("bracketed country suffix, 3m -> merge",
  [{"id":21,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Greenway Polska (PL)"}],
  [{"osm_id":"n21","lat":la,"lon":lo,"operator":"GreenWay"}], 1, 1)

la, lo = offset(BASE_LAT, BASE_LON, 1, 0)
allok &= case("Tesla qualifier, 1m -> merge",
  [{"id":22,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Tesla (Tesla-only charging)"}],
  [{"osm_id":"n22","lat":la,"lon":lo,"operator":"Tesla"}], 1, 1)

la, lo = offset(BASE_LAT, BASE_LON, 3, 0)
allok &= case("PKP Mobility vs PKP S.A., 3m -> merge",
  [{"id":23,"lat":BASE_LAT,"lon":BASE_LON,"operator":"PKP Mobility"}],
  [{"osm_id":"n23","lat":la,"lon":lo,"operator":"PKP S.A."}], 1, 1)

la, lo = offset(BASE_LAT, BASE_LON, 3, 0)
allok &= case("subsidiary (Enspirion/Energa), 3m -> merge on proximity",
  [{"id":24,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Enspirion"}],
  [{"osm_id":"n24","lat":la,"lon":lo,"operator":"Energa"}], 1, 1)

# and the floor must NOT swallow genuinely separate sites
la, lo = offset(BASE_LAT, BASE_LON, 30, 0)
allok &= case("STILL two networks 30m apart -> keep both",
  [{"id":25,"lat":BASE_LAT,"lon":BASE_LON,"operator":"Orlen Charge"}],
  [{"osm_id":"n25","lat":la,"lon":lo,"operator":"GreenWay"}], 2, 0)

la, lo = offset(BASE_LAT, BASE_LON, 8, 0)
allok &= case("STILL separate when EVSE ids differ at 8m",
  [{"id":26,"lat":BASE_LAT,"lon":BASE_LON,"evse":"PL*A*E1"}],
  [{"osm_id":"n26","lat":la,"lon":lo,"evse":"PL*A*E2"}], 2, 0)

print("\n" + ("ALL PASS" if allok else "SOME FAILED"))
