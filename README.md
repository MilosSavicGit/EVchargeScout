# EVchargeScout

An EV road-trip **charging planner** — part of the [ScoutPlatform](https://bymilossavic.com)
family. Tell it where you're driving and your car's range; it traces the real road route
(ferries included), plans the charging stops so you never run flat, and shows driving +
charging + total time. A static web app: no build step, no API keys.

## What it does

- **Route + range → charging stops.** Enter start, destination, optional stops, and pick your
  car; it plans fast-charger stops with an 80% range safety margin.
- **Real road routing, ferry-aware.** Uses the free community Valhalla server; long multi-stop
  trips are routed leg-by-leg so ferries survive at any distance. OSRM is the fallback.
- **Charger tiers at a glance.** Slow AC (small green), fast DC 75 kW+ (dark green), ultra-rapid
  300 kW+ (black).
- **Click any charger → add it to your route.** Re-routes and renumbers instantly.
- **Multi-day splits.** Set "max hours/day" and it breaks the trip into Day 1 / Day 2 with a
  🌙 overnight stop at a charger — plus a link to **HotelScout** to find a bed.
- **156-car specs** (incl. Chinese EVs), operator + which app to use per stop, English place names.

## Data & services (all keyless)

- **Chargers:** prepared per country into `ev/<cc>.json` by `build_ev.py` — **© Open Charge Map**.
- **Car specs:** `ev-cars.json` (nominal WLTP figures, editable).
- **Routing:** Valhalla / OSRM via FOSSGIS (free community servers, fair-use).
- **Places & tiles:** Nominatim + OpenStreetMap raster tiles.

Nothing needs an API key. For a busier future, point routing at a self-hosted engine — a
one-line change — with no key ever required from users.

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

## Honesty

Charging times are estimates (real charging tapers). Ferry times are rough — check the
operator's timetable. Distances/times follow the routing engine's road route. Charger
coverage is best across Europe, North America and Australia (where Open Charge Map is dense).
Always verify a charger and your real range before you rely on it.
