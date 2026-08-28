"""Each case is a real tagging pattern found on OSM charging stations."""
from osm_tags import to_record, power_kw, connectors, cost, usage, _kw

fails = []
def check(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label:46s} {got!r}")
    if not ok:
        fails.append(f"{label}: got {got!r} want {want!r}")

print("--- power parsing (OSM is wildly inconsistent here) ---")
check("'150 kW'",            _kw("150 kW"), 150.0)
check("'22000' (watts)",     _kw("22000"), 22.0)
check("'11,5' (comma)",      _kw("11,5"), 11.5)
check("'50000 W'",           _kw("50000 W"), 50.0)
check("'0'",                 _kw("0"), None)
check("junk",                _kw("fast"), None)

print("\n--- power_kw prefers the highest per-socket output ---")
check("socket outputs beat maxpower",
      power_kw({"socket:type2:output":"22 kW","socket:type2_combo:output":"150 kW",
                "maxpower":"11"}), 150.0)
check("falls back to charging_station:output",
      power_kw({"charging_station:output":"50 kW"}), 50.0)
check("nothing recorded", power_kw({"amenity":"charging_station"}), None)

print("\n--- connectors ---")
check("type2 + CCS",
      connectors({"socket:type2":"2","socket:type2_combo":"1"})[0], ["TYPE2","CCS2"])
check(":output is not a socket count",
      connectors({"socket:type2":"2","socket:type2:output":"22 kW"})[0], ["TYPE2"])
check("socket:type2=no is absent",
      connectors({"socket:type2":"no","socket:chademo":"1"})[0], ["CHADEMO"])
check("unrecognised socket counted unknown",
      connectors({"socket:wibble":"1"})[1], 1)
check("supercharger -> NACS",
      connectors({"socket:tesla_supercharger":"8"})[0], ["NACS"])

print("\n--- cost: never invent a number ---")
check("fee=no",              cost({"fee":"no"}), "Free")
check("fee=yes no amount",   cost({"fee":"yes"}), "Paid")
check("fee=yes with charge", cost({"fee":"yes","charge":"0.79 PLN/kWh"}), "0.79 PLN/kWh")
check("nothing said",        cost({}), "")

print("\n--- access maps onto OCM's own vocabulary ---")
check("access=yes",       usage({"access":"yes"}), "Public")
check("access=customers", usage({"access":"customers"}),
      "Private - For Staff, Visitors or Customers")
check("access=private",   usage({"access":"private"}), "Private - Restricted Access")
check("unstated",         usage({}), "")

print("\n--- whole records ---")
r = to_record("n", 123, 52.2297, 21.0122, {
    "amenity":"charging_station", "operator":"GreenWay Polska",
    "operator:wikidata":"Q1234", "capacity":"4", "fee":"yes",
    "access":"yes", "socket:type2":"2", "socket:type2_combo":"2",
    "socket:type2_combo:output":"150 kW", "ref:EU:EVSE":"PL*GRW*E1001",
    "addr:city":"Warszawa"})
check("full record: kw",       r["kw"], 150.0)
check("full record: points",   r["points"], 4)
check("full record: conn",     r["conn"], ["TYPE2","CCS2"])
check("full record: id",       r["id"], "osm:n123")
check("full record: evse",     r["evse"], "PL*GRW*E1001")
check("full record: wikidata", r["operator_wikidata"], "Q1234")

check("bicycle-only station rejected",
      to_record("n", 9, 1, 1, {"amenity":"charging_station","bicycle":"yes"}), None)
check("motorcar=no rejected",
      to_record("n", 9, 1, 1, {"amenity":"charging_station","motorcar":"no",
                               "socket:type2":"1"}), None)
check("not a charging station",
      to_record("n", 9, 1, 1, {"amenity":"parking"}), None)

bare = to_record("n", 7, 50.0, 8.0, {"amenity":"charging_station"})
check("bare station still yields a record", bare is not None, True)
check("  ...with blank kw, not zero", bare["kw"], "")
check("  ...with empty conn", bare["conn"], [])

print()
print("ALL PASS" if not fails else "FAILURES:\n  " + "\n  ".join(fails))
