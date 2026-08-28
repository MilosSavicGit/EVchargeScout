# EVchargeScout — session handover, 25 August 2026

Supersedes the 24 August handover. Items 1, 2, 3 and 7 from the original
23 August ScoutPlatform document are CLOSED.

---

## STATE NOW

| Thing | State |
|---|---|
| `BUILD_VERSION` | `1.0.3 (2026-08-25)` — bumped by hand only |
| `EV_DATA_VERSION` | bumped automatically by `build_ev.py` |
| Countries | **56** (was 47) |
| Connector data | Captured per charger as `conn` |
| Weekly refresh | Live, Sundays 03:00 UTC. Deltas weekly, full rebuild first Sunday of month |
| Live at | milossavicgit.github.io/EVchargeScout/ |

Local clone: `C:\ScoutPlatform\EVchargeScout\EVchargeScout\` (note the nesting —
GitHub Desktop appended the repo name). The OUTER folder is the pre-clone
original and is stale.

**Actions commits to this repo weekly. PULL before touching anything.**

---

## WHAT CHANGED TODAY

### Coverage: 47 → 56 countries
Added `JP KR MY ID BR UY CL AR CO` after an OCM coverage survey
(`ocm_survey.ps1`, kept in `Asia_tests/`).

Excluded ON EVIDENCE — do not re-add without re-surveying:
- **CN 15 POIs** against a real network of 300,000+. Domestic operators do not
  publish to OCM. Also GB/T connectors, OSM mapping restrictions, and the
  GCJ-02 coordinate offset. Showing 15 chargers would be worse than none.
- **TH 35**, **SG 15**, **PE 9** (zero DC), **VN 8** (55% unknown connectors)
- **IN** capped at 200, but 31.8% of connectors unrecorded — compatibility
  filtering could not be trusted there

The survey method: `maxresults=200`. If a country returns 200 it is CAPPED and
worth pulling properly; anything well under 200 IS the whole country.

### Connector capture in `build_ev.py`
`compact=true` DOES return `Connections[]` — verified, so no need to drop
compact. Records now carry:

```json
"conn": ["NACS","CHADEMO"], "connUnknown": 1, "dc": 1
```

`connector_family()` collapses OCM's ~40 connection types into families:
CCS2, CCS1, CHADEMO, NACS, GBT_DC, GBT_AC, TYPE1, TYPE2, TYPE3, DOMESTIC,
TESLA_OTHER, OTHER. Names come from `/referencedata` — the same call already
made for operator hydration — not hardcoded IDs.

Post-rebuild coverage: DE 24,515/24,611 · JP 1,639/1,660 · BR 1,613/1,647 ·
KR 161/161.

### Connector awareness in the app (1.0.3)
- New **"Charging socket on your car"** dropdown. Seeded from the car
  (Tesla → NACS, everything else → CCS2), editable, stops overriding once
  touched.
- `planStops` plans from `fits` (compatible + unknown), not `corridor`.
  Incompatible chargers still DRAW on the map and are marked in the popup.
- Route-level warning when >25% of corridor chargers do not fit.

**The rule that matters: UNKNOWN IS NOT INCOMPATIBLE.** OCM leaves ~16% of
German connections unrecorded. Treating blanks as unusable would delete a
sixth of Europe. Three states, deliberately: usable / unknown / incompatible.

### FIXED: transit countries were never loaded
`COUNTRY_BBOX` had 36 entries while `ev/` shipped 47 countries. Missing:
`ru by ua rs tr mk md ba al me xk`.

Transit countries are found ONLY through `COUNTRY_BBOX`; endpoints come from
the geocoder separately. So **Moscow → Belgrade never fetched `by.json` at
all** — Belarus was pure transit. The empty stretch across Belarus was partly
this bug, not only the infrastructure gap. Now 56 entries.

---

## VERIFIED TODAY

**Japan has ZERO CCS2.** 1,490 CHAdeMO, 126 NACS, 19 Tesla, 6 Type 1. A
European car planned through Japan used to be routed stop-to-stop through
sockets it cannot physically enter. Now: one stop found and a clear warning.
Switching the socket to CHAdeMO makes Japan usable.

**Korea returns 161 and only 161** — not capped, that is all OCM has. Thin for
a country with real EV infrastructure. Korean routes will plan poorly.

---

## STILL OPEN

**`ev-cars.json` has no connector field.** The profile is inferred (Tesla →
NACS, else CCS2) and the user can override. A Japanese-market Leaf in the car
list would default to CCS2 when it is really CHAdeMO. Adding a `conn` field
per car would make the default right rather than merely overridable.

**`main()` returns 0 even when countries fail.** Per-country failures are
caught, counted, printed — then the run exits green. Under Actions a green
tick means "the script finished", not "the data is good". One line:
`return 1 if failed else 0`. Until then a silent weekly failure is possible.
The manifest and `EV_DATA_VERSION` bump also run regardless of failures.

**`bump_data_version()` matches `const EV_DATA_VERSION = "..."` exactly.**
Change that to `let` or single quotes and the regex misses. It warns and
returns False — but the run still exits 0.

**Version-line patch** (`Asia_tests/ev_status_line.html`) still unapplied.
Adds charger count and date read from `ev/ev.json`, flags countries >14 days
behind, adds `data-nosnippet`, and deletes a duplicated
`window.addEventListener('load')` block (two byte-identical copies).

**Planner rework (original item 4).** `planStops` still takes
`reachF[reachF.length-1]` — minimises stop COUNT, not time or cost. Power
above the 75 kW threshold ignored; detour distance `off` computed and never
used; `EUR_PER_KWH` flat at 0.55. Cheap fix is a scoring function
(reachable distance + power bonus − detour penalty), ~20 lines.

**Cost strings are not uniform.** OCM `cost` is free text: `17 ₽/kwt`,
`0.49 BYN/kWh`, bare `0.56`, or empty. Non-euro handling unverified.

**Operator country label.** A Belarusian charger showed operator
`РусГидро (Russia)` — the label appears to come from the operator's home
country, not the charger's location.

**Node 20 deprecation** on `actions/checkout@v4` / `actions/setup-python@v5`.
Cosmetic.

**Repo grows every week.** `build_country` rewrites the whole country file even
when a delta found nothing, because `generated` is set to today regardless.

---

## KNOWN DATA GAPS — NOT BUGS

**Norway blank operators: 87.5%.** Regional, not a parser fault (IS 81.8,
FI 78.8, SE 74.4, DK 72.2, then LT 48.9, FR 33.4). Matters because **468 of
Norway's blank-operator chargers are ≥75 kW** against 143 with an operator —
so ~77% of the chargers the planner would pick have no network name.

Title-based fallback was evaluated and **REJECTED**: sampling the ≥75 kW blanks
showed ~half carry the network in the name (`Valdresporten Supercharger`,
`Circle K Sandvika`, `YX 7-Eleven Håvik`, `Fortum hurtigladestasjon`) and half
do not (`Vestby`, `Hjerkinn`, `Bjorli`, `Gol`). A ~50% guess is worse than a
blank. Note `Åsane superlader` — Norwegian for Supercharger, so an English
keyword list would miss it.

**Belarus: 42 chargers, 9 at ≥75 kW.** Between Brest (lon 23.71) and Minsk
(27.41) there is NOTHING on the M1. Effectively one-directional for an EV:
Moscow → Minsk plans fine (stops at `Malanka 391 km`, 120 kW); westbound from
Poland cannot cross. Same "loads fine, has almost nothing" shape applies to
`md mk xk al` and now `kr`.

**Russia: 2,567 chargers, 0 blank operators.** Cleanest in the set.

---

## GOTCHAS

**PowerShell corrupts Cyrillic on READ.** `Get-Content` without
`-Encoding UTF8` reads UTF-8 as ANSI. The JSON is fine — `build_ev.py` writes
`encoding="utf-8"` with `ensure_ascii=False`. Setting `[Console]::OutputEncoding`
afterwards does NOT fix an object already read wrong.

**Charger record shape:** `{id, lat, lon, name, town, operator, kw, points,
cost, usage, conn, connUnknown, dc}`. Power is `kw`, NOT `power`.

**Four files called `index.html`**: website ~19 KB, ParkingScout ~50 KB,
EVchargeScout ~93 KB, BeachScout ~224 KB. Size is the fastest way to tell them
apart. On 24 Aug ParkingScout's was uploaded to BeachScout's repo and went
live for ~25 minutes.

**Browser upload has a batch size ceiling.** The full `ev/` folder fails via
the web UI; use the GitHub Desktop clone.

---

## SECURITY — OUTSTANDING

The OCM API key was printed to a console and appeared in a shared screenshot
on 23 Aug. Still live in the GitHub secret and the Windows user environment
variable. Rotation is ~2 minutes: new key at openchargemap.org, update the env
var, update the repo secret. Nothing else references it.

Read it without displaying it:
`[Environment]::GetEnvironmentVariable('OCM_API_KEY','User') | Set-Clipboard`

---

## ANDROID PORT — DECIDED, PARKED

Staying a web app. Works on a Samsung A17 and an iPhone including multi-country
routes. One transient failure after a cold cache resolved on retry — mobile
fetch reliability, not a code bug.

Decisions worth keeping:
- **Bundle all countries as assets** (~47 MB at 47 countries; re-measure at 56).
  Offline is the differentiator, so it is the default, not a fallback. Also
  removes the mobile-fetch failure mode.
- Check `ev/ev.json` on launch when online, compare `generated` per country.
- **Refresh route-relevant countries at PLAN time, while still connected** —
  not at the border, by which point the signal is gone.
- One centralised "freshest copy" function: internal storage if newer, else
  bundled asset. Do not duplicate that logic.

Requirements: `WebViewAssetLoader` over `https://appassets.androidplatform.net/`
(`fetch()` against `file://` is CORS-blocked); `domStorageEnabled = true` or the
km/miles toggle resets each launch; explicit `Charsets.UTF_8` on asset reads;
`shouldOverrideUrlLoading` for `tel:`, Google Maps, HotelScout, vignette shops;
geolocation needs BOTH the runtime permission and
`onGeolocationPermissionsShowPrompt`; target **API 36** (required for new apps
from 31 Aug 2026); `noCompress += listOf("json")`.

Play closed testing is **per app**: 12 testers, 14 continuous days. Same people
can be reused from BeachScout. Exempt if the account predates 13 Nov 2023 or is
an organisation account. Rejections are now usually for low tester engagement,
not headcount.

---

## OTHER APPS — CARRIED OVER

**BeachScout** live and correct. `BUILD_VERSION` still reads **2.3.6 while
running 2.3.7 code** — the version line describes the 2.3.7 offline fix. Beach
data `2026-07-13`; agreed cadence is **annual** (beaches do not move; only OSM
tagging improves). Worth a README line stating that so it does not read as
staleness.

**ParkingScout** — fixed `index.html` produced but NOT yet deployed. Two real
bugs: (1) `circle-radius` / `circle-stroke-width` had two `interpolate`
subexpressions inside a `case`, which MapLibre rejects — `addLayer('pts')`
threw and every later `setFilter('pts')` failed, so point-mapped parking never
rendered anywhere; (2) `force-cache` on the country EV fetch cached failures.
Also: the live site was running an EU-only build, so Belarus was missing from
`COUNTRY_CC` — the batch-2 country map existed on disk but was never deployed.
`chargers/` is EMPTY for all 1,506 cities, so every city relies on the
country-wide fallback.
