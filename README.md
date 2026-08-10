# EVchargeScout

An EV road-trip **charging planner** — part of the [ScoutPlatform](https://bymilossavic.com)
family. Tell it where you're driving and your car's range; it traces the real road route
(ferries included), plans the charging stops so you never run flat, and shows driving +
charging + total time. When a charger turns out to be dead or busy, it shows the working
alternatives around you. A static web app: no build step, no API keys, no sign-in.

**Live:** https://milossavicgit.github.io/EVchargeScout/

---

## What it does

### Plan a trip
- **Route + range → charging stops.** Enter a start, a destination, optional stops along the
  way, and pick your car. It plans fast-charger stops with an **80% range safety margin**, so
  the numbers hold up when it's cold, hilly, or you're driving fast.
- **Real road routing, ferry-aware.** Uses the free community **Valhalla** server; long
  multi-stop trips are routed leg-by-leg so ferries survive at any distance. **OSRM** is the
  fallback, and a straight-line estimate is the last resort so you always get *something*.
- **Alternative routes.** Where a genuine ferry option exists, it's offered as a selectable
  alternative alongside the all-road route, each with its own time and ferry estimate.
- **Location-aware place search.** Type-ahead suggestions come from **Photon**, biased to your
  location, so a couple of letters is enough and nearby places come first (Nominatim is the
  fallback). Place names are shown in English.

### Read the map
- **Chargers in three tiers at a glance.** Slow AC (small soft-green dot), fast DC 75 kW+
  (dark-green dot), ultra-rapid 300 kW+ (black dot).
- **Numbered stop markers** for the planned charging stops, A/B markers for the endpoints, and
  a route line following the real road geometry.
- **Every stop is explained:** nearest town, distance in, charger power, estimated charge time,
  operator, and **which app to use** (operator app plus roaming apps), with a **ballpark cost**.

### When a charger is down
- **Tap any charger — or any empty spot on the map — to find alternatives** within a chosen
  **5 / 10 / 20 km** radius. Results open as a full page with a **← Back to map** button and a
  distance-sorted list; press *Back* and they appear on the map as **miniature ⚡ lightning
  markers** (ring colour = power tier) inside the search radius, with an orange dot marking your
  reference point.
- **Same-network options are flagged** — if one Ionity is down the next Ionity often is too, so
  a different network nearby is the more useful suggestion.
- **Works offline.** Alternatives are drawn from the charger data already loaded for your trip,
  so there's no network call — handy exactly when you're stranded with patchy signal.

### Stay the night
- **Accommodation within 3 km of any charger.** Tap a charger → *Accommodation*, and it opens a
  list of hotels, guest houses, B&Bs, apartments and more (via OpenStreetMap / Overpass, tried
  across several mirrors for reliability). Press *Back to map* to see them as **dark-purple
  dots**. Each has a **Google Maps directions** link.
- **Multi-day splits.** Set *max hours/day* and it breaks the trip into Day 1 / Day 2 with a 🌙
  overnight stop at a charger — plus a link to **HotelScout** to find a bed near that town.

### Before you go
- **Vignette / road-toll warnings.** If your route crosses a country that requires an e-vignette
  (Austria, Switzerland, Czechia, Slovakia, Slovenia, Hungary, Romania, Bulgaria), it warns you
  and links to the **official** shop — buy before the border, not from a reseller.

### Cars
- **156 EV models**, grouped by brand, including Chinese brands (BYD, Nio, XPeng, Zeekr, Xiaomi,
  Leapmotor, MG, and more). Picking a model fills in battery, range and max charge rate; there's
  a *Custom* option for anything not listed.

---

## Data & services (all keyless)

- **Chargers:** prepared per country into `ev/<cc>.json` by `build_ev.py` — **© Open Charge Map**.
- **Car specs:** `ev-cars.json` (nominal WLTP figures, editable).
- **Routing:** Valhalla / OSRM via FOSSGIS (free community servers, fair-use).
- **Place search:** Photon (komoot) with Nominatim fallback.
- **Accommodation & alternatives search:** OpenStreetMap via Overpass (multiple mirrors).
- **Map tiles:** OpenStreetMap raster tiles.

Nothing needs an API key. For a busier future, point routing at a self-hosted engine — a
one-line change — with no key ever required from users.

---

## Repository layout

```
EVchargeScout/
├── index.html        the whole app (no build step, no keys)
├── ev-cars.json      EV specs for the car dropdown
└── ev/               prepared EV chargers per country (it.json, fr.json, us.json, …)
    └── ev.json       index of built areas
```

## Run it locally

```
python -m http.server
# open http://localhost:8000
```

## Deploy (GitHub Pages)

Push `index.html`, `ev-cars.json`, and the `ev/` folder; then repo → Settings → Pages →
deploy from branch → / (root). It uses only relative paths, so it works at any URL.

---

## Notes on the mobile build

Every form control is 16px so iOS Safari doesn't auto-zoom on focus (that was the old
"window too big" bug), long names wrap instead of forcing horizontal scroll, and the search,
accommodation and alternatives pages are full-screen overlays with a Back button so it behaves
like an app on a phone. Verified on iOS and Android.

## Honesty

Charging times are estimates (real charging tapers). Ferry times are rough — check the
operator's timetable. Distances/times follow the routing engine's road route. Charger and
accommodation coverage comes from open data and is best across Europe, North America and
Australia. **Open Charge Map tells you a charger exists, not that it's working right now** —
live availability lives in your charging app. Always verify a charger and your real range
before you rely on it.
