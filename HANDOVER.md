# ScoutPlatform — session handover, 23 August 2026

Everything below is either done, downloaded and waiting to be committed, or
still open. Read the "STILL OPEN" section first if you just want to know what
is next.

---

## THE PROJECTS

Three GitHub repos under `MilosSavicGit`, all GitHub Pages, all single-file
HTML apps with no build step:

| Repo | What it is | Live at |
|---|---|---|
| `bymilossavic` | The website, bymilossavic.com (CNAME in repo) | bymilossavic.com |
| `BeachScout` | Beach / naturist / dog-beach finder | milossavicgit.github.io/BeachScout/ |
| `EVchargeScout` | EV road-trip charging planner | milossavicgit.github.io/EVchargeScout/ |

Also `ParkingScout`, `HotelScout`, `RoadScout` — not touched this session.

**Important:** every app link uses the `milossavicgit.github.io` address, NOT
`bymilossavic.com/BeachScout/`. Canonical tags now say the same. If that ever
changes, change it in both the app's `index.html` and the website pages.

---

## LOCAL DISK — currently messy, worth tidying

```
C:\ScoutPlatform\
    bymilossavic_repo\            ← the real clone (GitHub Desktop)
    bymilossavic\                 ← stale, delete or rename
    bymilossavic_google_play_ready\  ← stale, delete or rename
    BeachScout\Release_2_0_2\     ← snapshot from 8 Aug, NOT a clone, stale
    EVchargeScout\                ← has build_ev.py (new) + index.html
    ParkingScout\                 ← has the OLD build_ev.py, parking_probe.py,
                                     a second ev\ folder, and EV_OCM_key.png
C:\AndroidStudioProjects\RoadScout\   ← actually the BeachScout Android wrapper
```

GitHub Desktop is now installed with `bymilossavic`, `BeachScout` and
`ParkingScout` cloned. `EVchargeScout` is not yet cloned.

Two things worth doing: delete the stale duplicates, and decide which `ev\`
folder is canonical (EVchargeScout's was the one rebuilt).

---

## DONE AND SHIPPED

### BeachScout — build 2.3.7 (live)
- Fixed: search results and country overviews overwriting each other on the map
- Fixed: country overview vanishing on a basemap switch
- Fixed: a failed `beaches/<cc>.json` fetch was cached like a real answer, so
  going offline once disabled that country for the whole session. Now a 404 is
  cached (real answer) and a thrown fetch is not (learned nothing, retry next
  time). Offline message now says "could not fetch" rather than "not prepared
  yet", which read as "your country is not supported".
- Added: `<title>`, meta description, Open Graph tags, canonical URL. Bing was
  showing the build-version string as the page description because there was no
  meta description to use. Version line now carries `data-nosnippet`.

### BeachScout Android — versionCode 7 / 2.3.5, NOT yet released
- `MainActivity.kt` rewritten with `onReceivedError` handling, a custom offline
  panel in the app's colours, a Try again button, and a `ConnectivityManager`
  callback that reloads automatically when the network returns.
- `ACCESS_NETWORK_STATE` added to the manifest.
- Builds clean, tested on a Samsung SM-A175F as a debug build.
- **Not urgent:** the WebView caches well enough that the offline error path is
  rare, and 2.3.7 fixed the symptom actually observed. The phone currently has
  a debug build on it — reinstall from Play to get back to the signed release.

### EVchargeScout — build 1.0.2 (downloaded, NOT yet committed)
- Added `BUILD_VERSION` and `EV_DATA_VERSION` (there were none at all).
  `EV_DATA_VERSION` cache-busts `ev/*.json` and `ev-cars.json` — they were
  fetched with `cache:'force-cache'` and no version, so returning users would
  have kept stale charger data forever.
- Added a km / miles toggle in the range field's own label. Internals stay km;
  only display and the range box convert. Switching converts what is already
  typed. Persists in localStorage, seeded from locale (US/GB start on miles;
  Canada is metric for driving and correctly stays km).
- Fixed cost handling: OCM's `UsageCost` is free text and a "Free" claim on a
  fast DC charger is not credible — the Tesla site at Herzsprung was listed
  free while Tesla publishes two paid tariffs. A free claim is now believed
  only up to 22 kW; above that the estimate is shown with "OCM lists free —
  unverified". It also used to feed €0 into the trip total, understating a
  Copenhagen–Belgrade trip by roughly €24.
- Fixed `loadCountry`: same failure-caching bug as BeachScout, plus a worse
  consequence. The caller only checked whether the TOTAL charger list was
  empty, so a partial failure was invisible — Germany failing on a
  Copenhagen–Belgrade route gave five countries of chargers and a silent 700 km
  hole. It now names the unreachable country and refuses to plan.

### EVchargeScout data — rebuilt
- Wrote a new `build_ev.py` (the old one lived in ParkingScout; the README
  named a file that did not exist in the EVchargeScout repo).
- **Found and fixed:** `compact=true` returns `OperatorID` as an integer, not
  the nested `OperatorInfo{}` object the old parser read. Operator and usage
  were empty on 100% of records — measured 24,605 of 24,605 blank in de.json.
  That silently degraded the app's "which app to use" feature to matching on
  charger name alone. Now `/referencedata` is fetched once per run and the IDs
  hydrated into names. Germany went from 24,605 blank to 4,652 (those are
  genuinely unrecorded in OCM).
- Records now store the OCM `id`, which makes `--since` deltas possible at all.
- Full rebuild: 47 countries, 0 failed, 256,958 chargers, 7.6 minutes.
- The OCM API key was in plain text in `build_ev_all.bat` and has been rotated.
  The new key is in the `OCM_API_KEY` user environment variable.
  `EV_OCM_key.png` is still sitting in the ParkingScout folder — delete it.

### Website — live
- New page `naturist-beaches-france.html`: 563 mapped locations, 21 officially
  designated, with a section explaining honestly why only 21 (a mapping gap,
  not a legal one) and a "the same works for any country" section pointing at
  Croatia, Spain, Greece, Italy and Germany. Two map screenshots.
- `index.html`: meta description and canonical added (there were none), plus a
  button linking to the France page in the "Naturist places, country by
  country" card. Rendered as a `.btn` because the global link style is red and
  bold with no underline, which did not read as clickable.
- `sitemap.xml` replaced — the old one listed only the homepage, so the four
  legal pages were missing too.
- `country-page-template.html` exists for building the next four countries.

---

## STILL OPEN

**1. Commit EVchargeScout 1.0.2** — downloaded, not yet pushed. The repo is not
   cloned in GitHub Desktop yet.

**2. Commit `build_ev.py` to the EVchargeScout repo.** It exists only on the
   local disk. If that drive dies, the app survives but the ability to refresh
   its data does not.

**3. Set up the weekly data refresh.** `update-ev-data.yml` is written and
   validated; it goes in `.github/workflows/`. Needs two things first:
   - `OCM_API_KEY` added under repo Settings → Secrets and variables → Actions
   - Settings → Actions → General → Workflow permissions → Read and write
   Weekly deltas via `--since auto`, full rebuild on the first Sunday of the
   month (a delta can never see a DELETED charger). OCM explicitly ask callers
   not to re-download everything repeatedly and reserve the right to ban.

**4. EVchargeScout planner rework — parked for "next version".**
   `planStops` currently takes `reachF[reachF.length-1]` — the furthest
   reachable fast charger. That minimises STOP COUNT, not time or cost. Three
   gaps: power is ignored above the 75 kW threshold (a 75 kW charger 380 km out
   beats a 350 kW one at 360 km, which is wrong on time); the detour distance
   `off` is computed and never used to choose between chargers, so an 8 km
   detour costs nothing in the maths; and cost cannot be optimised at all
   because `EUR_PER_KWH` is a flat 0.55 regardless of network. The cheap fix is
   a scoring function — reachable distance, plus a power bonus, minus a detour
   penalty — roughly 20 lines. Real cost optimisation needs per-network pricing,
   which is a much bigger piece of work.

**5. EVchargeScout Android wrapper.** Not started. The BeachScout
   `MainActivity.kt` pattern transfers directly. Decisions to make first:
   whether to bundle `ev/` as assets for genuinely offline planning (the
   "stranded, find alternatives" feature is exactly the offline case), and
   `tel:` links plus external links (Google Maps, HotelScout, seven vignette
   shops) need `shouldOverrideUrlLoading` or they trap the user inside the app.
   Play policy is lighter than BeachScout's — no user-generated content, no
   age-rating friction.

**6. More country pages.** France is live. Croatia, Spain, Greece and Italy to
   follow, using `country-page-template.html`. Read the real counts off the
   app's legend — do not estimate them.

**7. Reply on the OSM forum.** The thread "dog=* on beaches: 1,910 tagged out
   of 381,331" got a substantive answer from Mateusz Konieczny: the seasonal
   values should be `dog=no` + `dog:conditional=yes @ (...)` per the Conditional
   restrictions wiki page, and the `partially` / `0` / `1` tail can just be
   treated as untagged (which the code already does). Worth thanking him and
   saying what will change — parsing `dog:conditional=*` properly so the app
   can say "dogs allowed except 15 March – 15 August" instead of a generic
   seasonal message.

---

## NUMBERS, FOR REFERENCE

- BeachScout Play: 56 device acquisitions in 28 days (+143%), 28 first opens,
  25 monthly active devices, 5.00 rating, zero crashes, install base 92.9% on
  the current release. Zero marketing spend.
- Google now shows an AI Overview for "beachscout", built from the Play listing
  and a LinkedIn post. Bing ranks the app first and bymilossavic.com second.
- The gap worth watching: 56 acquired against 28 opened. Half never launch it.
- France naturist data: 563 total — 333 beaches, 128 campsites, 54 by name
  only, 23 resorts, 21 officially designated, 4 pools.

## THINGS THAT KEEP BITING

- **Two files called `index.html`.** The website one is ~19 KB; BeachScout's is
  ~226 KB; EVchargeScout's is ~87 KB. Mixing them up cost time twice today.
- **Local copies drift from the repos.** Half of today's confusion came from
  working on a file that predated the commits. Always pull, or work in the
  clone.
- **Version constants go stale.** BeachScout reported 2.3.4 while running
  post-MapTiler code because the commit that removed MapTiler never bumped it.
  `build_ev.py` now bumps `EV_DATA_VERSION` automatically; `BUILD_VERSION`
  still needs doing by hand on every release.
