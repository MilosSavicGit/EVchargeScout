# ScoutPlatform — session handover, 25–27 Aug 2026

Two separate workstreams ran in this session. Part 1 shipped. Part 2 is built and
tested but not yet wired in.

---

# PART 1 — Name / identity SEO (DONE, live)

## The original question

"Connect my name to ScoutPlatform to improve visibility."

## What was found at the start

- No structured data anywhere on bymilossavic.com
- No Open Graph tags
- No About page — your name existed only as footer text, unresolvable
- Two app pages were publicly showing development titles:
  RoadScout "clean 200 debugged map version", HotelScout "v0.14 reverse address fallback"
- Four of five app pages had no meta description
- BeachScout repo held three duplicate copies of index.html

## What shipped

**All six repos updated and live.**

- JSON-LD entity graph on every page: Person + Organization + WebSite + WebPage
  + one SoftwareApplication per app. Every page reuses the same two `@id`s
  (`#milos-savic`, `#scoutplatform`) so crawlers merge them into one entity each.
- `about.html` created — the canonical page for you as a person, styled to match
  the site. Linked from the homepage body text twice (your name is the anchor
  text) plus the footer.
- App pages: new titles, meta descriptions, canonicals, OG tags, author schema.
- `contact.html` had no meta description and no canonical. Both added.
- Legal pages got canonicals and descriptions.
- Three duplicate BeachScout files deleted.
- sitemap.xml updated.

**Google Play developer name changed** from `bymilossavic` to
**"ScoutPlatform by Miloš Savić"** — the single most valuable change of the day,
because it is a Google-verified page carrying both your name and your brand.
Developer page: https://play.google.com/store/apps/dev?id=4627318307378995391
That URL is now in the `sameAs` list on every page.

## Verified

- validator.schema.org: 0 errors, 0 warnings on about.html
- Search Console is a Domain property, already set up
- Indexing report: "duplicate without canonical" was `/index.html` vs `/` —
  already fixed by the canonical added 23 Aug; Google had last crawled 21 Aug.
  Validation was started 26 Aug and should clear on its own.

## Still to do (not files — profiles)

1. **GitHub profile** — still "MilosSavicGit", no bio. Set name to `Miloš Savić`,
   bio "Creator of ScoutPlatform — free map tools built on open geographic data",
   website bymilossavic.com, and add LinkedIn + Play dev page as social links.
2. **LinkedIn** — still says Militho Ltd, never mentions ScoutPlatform. Needs:
   name to Miloš Savić, headline, About section, and — most important — an
   **Experience entry** (Founder & Developer, ScoutPlatform), because that is
   structured data rather than free text. Draft copy was written in the chat.
3. **Repo descriptions** have typos: ParkingScout "gavigate", EVchargeScout
   "planing". HotelScout has none.
4. **README.md** for bymilossavic was rewritten (ParkingScout and EVchargeScout
   were missing entirely, BeachScout listed as 1.0 when it is 2.3) — rewritten
   file was delivered but NOT yet uploaded.
   - It still says "Belgrade, Serbia" while your Play account says UK. Decide.
   - Planned apps list disagrees with the website (README has 5, site has 2).

## Realistic expectations

Your name alone is not winnable — a footballer with a Wikipedia page, a handball
player, and 100+ LinkedIn profiles share it. The winnable query is the pairing:
"Milos Savic ScoutPlatform", "who made BeachScout". A US-weighted search already
returns bymilossavic.com third for "ScoutPlatform BeachScout naturist beaches app".

Baseline to compare against in late September: **48 clicks over 3 months** in
Search Console.

---

# PART 2 — EVchargeScout dual-source charger data (BUILT, NOT WIRED IN)

## Why this started

Riga → Warsaw showed dense chargers through Lithuania and nothing across Poland.
It looked like a bug at the border.

## What it actually was

Not a bug. Open Charge Map genuinely holds only ~501 chargers for Poland because
GreenWay and Orlen do not submit to it. Lithuania has 1,909 because Inbalance
Grid does. The data has a border.

**I was wrong twice on the way to this** — first diagnosing a paging bug in
build_ev.py that did not exist, then blaming a truncated fetch. Poland really is
501 in OCM. The build_ev.py guards added along the way are still worth keeping,
but they fixed nothing.

## The finding that settles the architecture

Across 37 countries where both sources have data:

    OSM ahead in 18 countries · OCM ahead in 18 · similar in 1

    Latvia    OCM     96   OSM    386   OSM 4.0x
    Lithuania OCM  1,909   OSM    439   OCM 4.3x    <- neighbours, opposite winners
    Poland    OCM    501   OSM  2,891   OSM 5.8x
    Germany   OCM 24,611   OSM 42,499   OSM 1.7x
    NL        OCM  8,172   OSM 21,258   OSM 2.6x
    USA       OCM 87,116   OSM 17,751   OCM 4.9x    <- OSM-only would lose 69k

Neither source can be dropped. Merge both.

## Data fetched

`osm/` — 55 countries, ~191,600 chargers, built with build_osm.py.
Russia failed (5 tiles, could not complete) and was left out deliberately: Play
is marginal there, Yandex is the default nav app, and any map app distributed in
Russia hits the Crimea rendering requirement.

## The critical caveat

**OSM has coverage but not detail.**

    Poland   OCM 501:    98% have power    OSM 2,891:  16% have power
    Germany  OSM 42,499: 39% have power

Power is needed to compute charge time and to call a stop fast or slow. A pin
with no kW cannot be planned against — and labelling it "slow" asserts something
unknown.

## The design agreed

Merged file has TWO arrays:

    "chargers"  full records, power known — EXACTLY the shape index.html
                already reads, so the planner needs no change
    "pins"      display-only, compact arrays [id, lat, lon, name, operator, src]
                drawn on the map, never planned against

Tier by DATA, not by source: an OSM record that has power is as plannable as an
OCM one.

Measured on Germany-scale data: 13.5 MB naive -> 7.7 MB merged -> **1.34 MB
gzipped**, which is what actually crosses the wire since GitHub Pages compresses.

## Files built (all tested)

| File | Purpose | State |
|---|---|---|
| `build_osm.py` | fetch OSM per country via Overpass | run, worked |
| `osm_tags.py` | OSM tags -> record shape | 30 tests pass |
| `overpass_pool.py` | mirror rotation, busy vs broken | 10 tests pass |
| `merge_sources.py` | dedup cascade | 9 tests pass |
| `build_merge.py` | writes the merged ev/<cc>.json | run on PL |
| `audit_merge.py` | checks the dedup is not under-merging | NOT YET RUN |
| `test_*.py` | the test suites | all pass |

## WHERE WE STOPPED

Poland merged: OCM 501 + OSM 2,891, 124 duplicates removed,
**911 plannable (up from 490) + 2,357 pins, 322 KB.**

Open question: only **124 of OCM's 501 matched** — 25%. Either the two sources
genuinely list different chargers, or the dedup radius is too tight and ~280
chargers will show as two dots each.

**NEXT COMMAND:**

    python audit_merge.py --country PL

It reports how far each unmatched OCM record sits from its nearest OSM neighbour.
  - spike at 50-200 m       -> radius too tight, widen R_OPERATOR in merge_sources.py
  - many operator-conflict  -> name normalisation failing on real Polish names
  - mostly "no OSM near"    -> genuinely different chargers, merge is correct

Settle that BEFORE running `build_merge.py --all`. A duplicate-pin problem is
cheap to fix now and expensive after 55 countries have shipped.

## Then, in order

1. `python build_merge.py --all`
2. **Apply the planner gate** in index.html — currently a record with no kW
   passes `connState` as 'unknown', lands in `fits`, and can be chosen as a
   fallback stop labelled "slow only". That asserts something unknown. Change:

       const hasKw = c => c.kw !== '' && c.kw != null && +c.kw > 0;
       const fits = corridor.filter(c => c._cs !== 'incompatible' && hasKw(c));
       const fast = fits.filter(c => +c.kw >= FAST_KW);

   `corridor` is untouched, so pins still draw. Display and planning are already
   separated in your code — this just puts power on the planning side.
3. Draw the `pins` array on the map, visually distinct (hollow/grey), with a
   popup saying "Listed in OpenStreetMap. Power and connector not recorded."
4. Update the weekly workflow to run build_osm.py and build_merge.py too.

---

# GOTCHAS — things that cost time today

**Hyphens are stripped from filenames on download from the chat.**
`data-deletion.html` arrived as `datadeletion.html`, uploaded as a NEW file,
and left the original unfixed. Rename before uploading anything hyphenated.

**overpass.osm.ch is the SWISS Overpass API**, not a planet-wide one. It returns
HTTP 200 with zero elements for anything outside Switzerland — indistinguishable
from success. It silently emptied 61 of 56 countries on the first full run.
Any mirror added must be verified planet-wide first.

**Two of three Overpass mirrors never succeeded once.** Across two full runs:

    overpass-api.de     ok=59  busy=21  broken=0
    overpass.kumi       ok=0   busy=4   broken=4
    private.coffee      ok=0   busy=5   broken=4

There is effectively no fallback. Must be solved before this becomes a weekly
GitHub Action, or a busy Sunday kills the refresh outright.

**Guards that compare against history are blind on first run.** The 80% shrink
guard did not catch the Swiss-mirror disaster because every file was new. The
zero-result guard added afterwards is what catches it.

**ParkingScout has its own stale copy of `ev/`** dated 10 August, and no workflow
refreshes it. Either give it the same workflow, or point it at EVchargeScout's
Pages URL so there is one copy instead of two.

---

# BeachScout baseline (for comparing later)

    Device impressions   2,940   (up >999% — Play is surfacing it)
    Device acquisitions     61
    Device first opens      38
    Monthly active          27
    Install base         90.2%   (unusually good)
    Rating                5.00   (few ratings — count is a strong Play ranking factor)
    Listing conversion     55%

Read: discovery on Play is working; the loss is at the search-result stage, where
only the icon, title and first screenshot are visible. **Store listing
experiments: 0 running** — free A/B testing you now have enough impressions to
use. That is a bigger lever on installs than anything on the website.
