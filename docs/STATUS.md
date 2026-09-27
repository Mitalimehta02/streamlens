# StreamLens — status

Written for: the judges and anyone picking this repository up mid-build.

Last updated: 27 September 2026.

Phase 1 delivered the **Observe** vertical slice. Phase 1.5 measured the vision
prompt against real photographs. Phase 2 built **Understand & Act**. Phase 3 built **Return & Standards**. Phase 4 deployed it. This document says exactly which is
which, because a demo that hides its seams wastes a reviewer's time.

**Live:** <https://streamlens-ten.vercel.app> (API:
<https://streamlens-api.onrender.com>). The hosted demo does not behave
identically to a local checkout, and [the differences are listed
below](#the-hosted-demo-versus-a-local-checkout) rather than left for a reviewer
to discover.

---

## What works

### The loop, end to end
Pick a site → take upstream and downstream photos → get AI suggestion chips →
confirm, change or reject each one → give your own overall rating and emotions →
consent → send. Verified against the running stack, not only in tests: a
submission stored with two photos, three answers and a measured AI agreement
rate of 0.5 (one suggestion kept, one overridden).

### AI suggests, humans decide — enforced in three places
- **The prompt** (`api/app/ai/prompts/assess_v3.md`, loaded from disk at call
  time) tells the model the `overall` question does not exist for it.
- **The API** drops any suggestion for a question marked `ai_suggestable: false`,
  even at confidence 1.0. There is a test that tries exactly that and asserts it
  is refused.
- **The web app** starts every chip as `pending`, holding no answer. A chip the
  citizen never touched is not submitted. Silence is not consent.

Each stored answer keeps the citizen's choice *and* the AI's suggestion, so
disagreement is measurable rather than invisible.

### Answer validation
Every code a provider returns is checked against `data/questions.json` before a
citizen can see it. Unknown questions, invented codes, duplicates, and multiple
codes on a single-answer question are all discarded into a `dropped` list that
the UI surfaces. A failing prompt shows up as visible drops, not silent nonsense.

### The mock provider, honestly labelled
With no `GEMINI_API_KEY`, StreamLens runs a deterministic colour heuristic. The
API returns `is_mock: true`, and the UI shows a **"demo AI (mock)"** badge plus a
full explanatory notice. The demo works with no key, no network and no cost, and
never pretends to be a vision model.

### Photo handling
EXIF orientation is applied, then *all* metadata — including any GPS the camera
embedded — is destroyed by rebuilding the image from raw pixels. Images are
downscaled to 1600 px. Blur is measured as the variance of the Laplacian and
brightness as mean luma; blurry, dark and overexposed photos produce warnings,
and bad photo quality flags every suggestion for extra review.

### Offline
The site list and question set are cached in IndexedDB, so a cold start with no
signal works. Submissions queue with their photos and flush on reconnect. A
network failure keeps an item queued; a 4xx marks it permanently failed instead
of retrying a bad payload forever. Photos are stored as `ArrayBuffer`, not
`Blob`, because Safari has shipped IndexedDB versions that lose Blobs.

### Data provenance
- **106 real research sites** fetched once from the public ENORA endpoint into
  `data/sites.json` and served locally. Attributed in the file, the API response
  and the UI.
- **24 questions** in `data/questions.json`. The app's own question endpoint
  requires authentication, so ids and answer codes come from a public draft FHIR
  CodeSystem, marked `source: "streamcheck-fhir-docs"` per question and option.
  Our explanations, glossary and translations are marked `source: "manual"`.
  Nothing is presented as an official OneAquaHealth artefact.
- Non-English strings are flagged `machine_translated`, and the UI says so.

### Accessibility
44 px minimum tap targets, visible focus rings, WCAG AA contrast pairings
documented in `web/src/index.css`, labelled controls, and a glossary built as a
tappable popover rather than a hover tooltip — hover does not exist on a phone.

### Tests
- **279 pytest tests**, none touching the network. `pytest.ini` lives at the
  repository root: when it lived in `api/`, running `pytest` from the root
  picked up no configuration and seven async tests skipped themselves while
  the run still reported success.
- **22 vitest tests** covering the answer state machine and the offline outbox.
- TypeScript compiles clean under `strict`.

---

## What is stubbed or missing

| Area | State | Why |
|---|---|---|
| **Gemini provider** | Verified against the live API | Runs on `gemini-3.5-flash-lite`. `gemini-2.5-flash` is retired for new keys and `gemini-3.6-flash` returned 503 on every one of 29 sequential calls, so it is unusable under load. |
| **Question translations** | All six languages carry question labels, explanations, option labels, section headings and the glossary; per-option explanations are English everywhere | Machine-translated and **not yet reviewed by native speakers**, flagged `machine_translated` in the data and warned about in the app. Ecology terms were translated to the established term in each language - riffle/raschio/radier/stroomversnelling/stryk, weir/briglia/seuil/stuw/terskel - rather than literally. |
| **All translations** | Ours, not the consortium's | Flagged `machine_translated` in the data and warned about in the UI. A native speaker should review before field use. |
| **Photo storage** | Files on local disk when running locally; **nothing stored at all on the hosted demo** | `STORE_PHOTOS=false` in production keeps the quality measurements and discards the image, which is why nothing can be served publicly. A real deployment that wanted to keep photographs would need object storage: Render's free disk is wiped on every deploy. Locally, stored files are deleted after `PHOTO_RETENTION_DAYS` (14). |
| **Authentication** | None | Anyone who can reach the API can post an observation. Acceptable for a hackathon demo, not for production. |
| **`GET /observations`** | Unpaginated, capped at 200 | Demo convenience endpoint, not a real query API. |
| **PWA install** | Manifest and service worker build and serve over HTTPS on the live site | Not tested on a physical phone. |
| **"Answer contradicts the photo" check** | Not built | Blur, brightness, GPS distance and the watercourse gate exist. Cross-answer consistency does not. |


---

## The hosted demo versus a local checkout

Six things behave differently in production. All six are configuration, not
different code paths, and each is set in [`render.yaml`](../render.yaml).

| | Local | Hosted |
|---|---|---|
| **Database** | SQLite file in `api/` | Postgres on Neon. The provider's URL is rewritten to the installed driver, and pooled connections are pre-pinged because Neon suspends its compute when idle and drops them with it. |
| **Photographs** | Stored, deleted after 14 days | `STORE_PHOTOS=false`: measured, then discarded. Nothing is written to disk, so nothing can be shown publicly and there is nothing left to delete. |
| **Demo data** | Seeded when you run `python scripts/seed_demo.py` | Seeded on first start, because `SEED_DEMO=true`, and only when the database is empty, so a redeploy neither duplicates it nor touches real submissions. |
| **AI provider** | `mock` unless you supply a key | Gemini, capped at 10 calls per device per hour and 300 a day. Past either cap an assessment still succeeds, on the labelled mock, with a visible notice — never an error. |
| **CORS** | localhost only | The Vercel origin, plus localhost so a developer can point a local web app at the hosted API. A wildcard would let any site on the internet spend the Gemini quota. The list is committed in `render.yaml` rather than typed into the dashboard, because a dashboard value against a `sync: false` key never reached the process, and `/health` now reports the list so that failure is visible from outside. |
| **Cold start** | None | A free Render instance sleeps after about fifteen minutes idle; waking it was measured at 42.7 s, against 0.56 s warm. A cron-job.org schedule requests `/health` every ten minutes to prevent it. `/health` opens no database connection, so the ping keeps Render awake without spending Neon's free compute hours. The GitHub Actions workflow in this repository would do the same job, but GitHub does not run scheduled workflows in a fork, and this repository is one. |

### Two things a reviewer should know about the demo data

**Planted forecasts.** Two of the three weather-driven alert rules need rain to
fire. Rather than wait for rain in Coimbra, the seed plants a forecast at one
site per rule. Those rows are labelled, the API reports the label, and the UI
shows **DEMO FORECAST** wherever the number appears. They are rebased onto the
current clock rather than expiring, so the rule still demonstrates itself weeks
later; delete the row (`python scripts/seed_demo.py --reset`) to get the real
forecast back. The third rule, mosquito breeding conditions, needs no help:
warm weather is common enough to fire on its own.

**The synthetic flag is the boundary.** Every seeded record carries
`synthetic: true`, and the *Showing* toggle on Explore and Community switches
between all data, real only and demo only. Anything a reviewer submits
themselves is real, and appears under "real only".

### Verified against the live deployment, 27 September 2026

Server-side, with a device id that had never been seen before:

- a real Gemini assessment of the bundled Benevento pair — 10 suggestions, no
  degradation, `is_watercourse: true`;
- the watercourse gate refusing the photograph with no water in it, with a
  reason and zero suggestions;
- an assessment submitted with both photographs, both passing the quality
  checks, EXIF stripped;
- 46 points, of which 20 for completing the `after_rain` quest;
- a health card built only from citizen-confirmed answers;
- both rain-driven alerts firing on their planted forecasts, badged
  DEMO FORECAST;
- a six-resource FHIR bundle for one assessment, and a 25-entry bundle for
  Coimbra.

Then through a real browser, from a clean profile, driven over the Chrome
DevTools Protocol: the catalogue loaded, the quick tour opened, a site was
chosen, AI help was accepted, both photo slots were filled from the bundled
samples, the real model returned suggestions in about ten seconds, the citizen's
own rating was set on a screen that says "The AI has no opinion here, by
design", the assessment was sent, and the confirmation showed 26 points with the
breakdown. **Zero console errors and zero failed requests.**

Lighthouse 12, mobile preset, against the live site, two consecutive runs:
performance 84 then 90, accessibility 100 in both, best practices 100 in both,
SEO 100 then 92. Both are recorded rather than the better one. The performance
spread is the first screen waiting on `/sites` (1.7 s) and `/questions` (1.5 s)
from a free instance, plus OpenStreetMap tiles at about 1.2 s each; the same
build scores 91 with the API on localhost, so the gap is the network rather than
the bundle. The SEO dip was a failed `robots.txt` fetch during the audit - the
file serves 200 with valid content.

An earlier measurement of 95 / 100 / 96 / 100 is not comparable and is recorded
here only so the drop is not mistaken for a regression: it was taken while the
API was still refusing the Vercel origin, so the app rendered its error state
and did almost no work.

---

## Phase 2 — Understand & Act (built)

### The watercourse gate
`assess_v3` returns `is_watercourse` in the same structured response as the
suggestions, so it costs no extra call. When it is false the API returns no
chips at all and the review screen asks for a different photo. Measured on the
same 29 evaluation photographs, silence on the 13 images that show no
watercourse went from **10/13 to 13/13**.

### Stream health card
Built only from citizen-confirmed answers. Sections graded by how many of their
answered questions match a known problem in the measures catalogue — a rule a
reader can check. Carries **"indicator view, not a validated ecological index"**
in the payload and on screen. Includes rating history, visit count, last visit,
a data-completeness meter and averaged emotions.

### 48-hour alerts
Three rules in `data/alert_rules.json`, executed by `app/alerts.py`:

| Rule | Fires when |
|---|---|
| `sewage_overflow_risk` | ≥20 mm forecast rain **and** a sewage or polluted-pipe report within 14 days |
| `mosquito_breeding_conditions` | ≥20 °C forecast **and** standing or dry water reported within 21 days |
| `debris_blockage_watch` | ≥25 mm forecast rain **and** a barrier or fallen wood reported within 60 days |

Every threshold carries its own source. The 72-hour advice figure is quoted from
Directive 2006/7/EC Article 2; the mosquito temperature reasoning cites published
Culex development rates. **The rainfall triggers say `project judgement`** and
explain why: no pan-European figure defines when a combined sewer spills, and the
UK Met Office dropped fixed millimetre thresholds in 2011. Nothing borrows an
unrelated citation to look authoritative.

No rule fires on weather alone — weather is not a property of a stream, so each
also needs a citizen observation. Every alert shows the numbers that triggered
it, and a test asserts no alert ever uses a banned word or omits "Check official
local advice."

### Measures
`data/measures.json`: 25 measures across 10 observable problems, from the
OneAquaHealth D2.4 catalogue (DOI 10.5281/zenodo.20040211, CC-BY-4.0).
`scripts/build_measures.py` opens the PDF and confirms each cited page still
names the measure cited against it — **25 of 25 confirmed**. The mapping,
plain-language text, health co-benefit tags and effort estimates are ours and
marked `project judgement (StreamLens)`, because the catalogue links health at
p.132 in general terms rather than measure by measure.

### Weather
Open-Meteo, cached one hour per site, stale cache served offline **with its
timestamp and a stale flag**. With neither forecast nor cache, the engine
produces no weather-based alerts rather than failing the page.

### Demo data
`scripts/seed_demo.py` writes 101 observations across 12 sites in all five
cities over 90 days, every one `synthetic: true`. A scope toggle (all / real /
demo) sits on every view and is passed to the API. Two sites get **planted
forecasts** so the rain-driven rules can be shown on a dry day; these are flagged
`_streamlens_synthetic`, reported by the API and badged "demo forecast" on
screen. `--no-demo-weather` turns that off.

### Screens
Site page (alerts, health card, measures), Home "alerts near you", and a
sortable city table with CSV export for municipal users.

---

## What Phase 2 did NOT do

| Area | State |
|---|---|
| **Litter** | Inferred from `waterAspect: CO` rather than asked directly. It needs its own question; `measures.json` says so in `detection_note`. |
| **City page polish** | Functional sortable table with CSV, but no charts or map view. |
| **Alert delivery** | Alerts are shown when you open a site. No push, no email, no subscriptions. |
| **Thresholds** | Rainfall triggers are our judgement, not calibrated to any real catchment. A municipality must replace them. |
| **Health card weighting** | Every question counts equally within a section. A real index would weight them. |
| **Measures** | 25 of roughly 60 in the catalogue, chosen for the problems StreamLens can observe. |
| **Phase 3** | Not started: quests, leaderboard, wellbeing mirror, FHIR export. |

---

## Phase 3 — Return & Standards (built)

### Litter as its own question
`litter` (NONE / SOME / LOTS / NS) replaces the old inference from
`waterAspect: CO`. It is **not** a OneAquaHealth code and is marked
`source: manual` throughout. questions.json 1.2.0.

**Measured, and the honest answer is "not measured".** Wikimedia Commons had
litter photographs but not litter-in-a-stream photographs — the two that came
back were a beach and an urban courtyard, kept as negative controls. Across the
existing set the model was asked about litter on 5 photographs and only **2 had
labels**; both matched, at 0.82 mean confidence. Two comparisons is an anecdote,
not a result, and it is reported here as one.

### Identity, without accounts
A nickname and an optional team code live in `localStorage`. The nickname never
leaves the phone. The server receives a random `client_id` generated on the
device and, if the citizen typed one, the team code. No name, no email, no
password, no account.

### Quests
`data/quest_rules.json` + `app/quests.py`. Four kinds of real gap:

| Quest | Fires when |
|---|---|
| `stale_site` | Visited before, but not in 30+ days |
| `after_rain` | ≥15 mm has **already fallen** in 48 h at a site with prior sewage reports |
| `missing_season` | Visited before, but never in the current meteorological season |
| `second_opinion` | A visit in the last 14 days by exactly one person |

Each states the fact behind it — the date, the millimetres, the season. The list
shows one quest per site so a volunteer gets one clear reason to go; the site
page shows all of them. The weather cache now carries the last 48 h of observed
rain as well as the forecast, so one Open-Meteo response serves alerts and
quests alike.

### Points, and what they refuse to reward
`data/points_rules.json` awards photo quality, both photos, completing a quest,
and agreeing with an independent visitor at the same site within 14 days.

**Nothing is awarded for volume** — not answers given, not observations
submitted, not streaks, not speed. The file says why at length: paying per
submission pays for rubbish. A 60-point daily cap per person stops the agreement
rule being farmed across many sites in one afternoon, and disagreement never
costs anything.

### Teams only
Individuals are never ranked. A team of fewer than 2 people is withheld from the
board — a team of one is an individual ranking by another name — and the
response says how many were withheld rather than dropping them silently.

The **coverage map** shows which of the 106 sites got a visit in the last 30 days.

### Wellbeing mirror
Splits recorded emotions by the rating the person themselves gave. The personal
view always works; the community view needs **at least 10 people**, enforced in
`app/points.py` and stated in the interface. Wording is descriptive: it reports
what people recorded feeling, states it is not a health measurement, and says
explicitly that it does not show a stream caused a feeling.

### FHIR R4
`GET /observations/{id}/fhir` and `GET /cities/{city}/fhir`.

**Validated with the official HL7 validator: 0 errors, 0 warnings against the
OneAquaHealth IG profiles.** The published IG was unavailable (every URL 404 on
24 September, re-checked once), so it was compiled from its own FSH source with
SUSHI. A deliberately broken bundle was re-validated as a negative control and
produced exactly the profile's constraints, proving the pass is real. Full
reasoning, every modelling decision and every check with its date:
[`docs/fhir/validation-report.md`](fhir/validation-report.md).

---

## What Phase 3 did NOT do

| Area | State |
|---|---|
| **Litter evaluation** | 2 labelled comparisons. Needs litter-in-a-stream photographs, which Commons did not provide. |
| **Quest completion** | The API accepts `completed_quest` on an observation, but the web app does not yet set it automatically when you assess a quested site — so the quest-completion points are reachable by API and not yet by tapping through the app. |
| **Nickname** | Stored and displayed, but there is no settings screen to change it after the first prompt. |
| **Leaderboard filtering** | Works per city via the API; the UI shows the overall board only. |
| **FHIR** | One bundle validated, not a corpus. `Bundle.type` is `collection`; nothing is designed to be POSTed to a server. |
| **Points UI** | Shows the total and the reasoning; no per-award breakdown screen. |

---

## Suggested next steps

### Phase 2 — Understand & Act

1. **Stream health card.** A read model over stored observations for one site:
   latest rating, trend, which pressures were reported and how often, when it was
   last visited. Needs an aggregation endpoint; the data is already shaped for it
   since answers are stored per question with codes.
2. **48-hour alert.** A rules engine, not a model, so every alert can show its
   reasons. Inputs: Open-Meteo rain and temperature forecast for the site
   coordinates, plus recent `sewage`, `pollutedPipes` and `waterFlow: STA`
   reports. Output: a level plus the list of rules that fired, each with the
   number that triggered it. Rules belong in a JSON file, not in Python, so a
   scientist can read and change them.
   **Keep the no-medical-claims rule here.** An alert says "sewage was reported
   twice this week and 30 mm of rain is forecast", never "this water is unsafe".
3. **Restoration measures table.** Map observed problems to measures from the
   OneAquaHealth catalogue, in `data/measures.json` with the same per-entry
   provenance discipline as `questions.json`. Each row: the problem, the measure,
   the expected ecological effect, and the claimed health benefit *with its
   source*. Where the catalogue is not publicly available, mark entries `manual`
   and say so.

### Phase 3 — Return

4. **Quests from real data gaps.** Compute them: sites with no visit in N days,
   sites never seen after rain (join the visit dates against Open-Meteo history),
   seasons missing for a site. A quest that points at a genuine gap is worth ten
   that gamify busywork.
5. **Points and leaderboard.** Award for photo quality (the blur and brightness
   scores already exist) and for agreement with other visitors to the same site
   within a window. Resist rewarding volume alone — it pays people to submit
   rubbish. Team-level board only; an individual board on a scientific dataset
   creates an incentive to fabricate.
6. **Wellbeing mirror.** Aggregate the emotion sliders by site and season. Report
   only in groups, never per person, and only above a minimum count so a single
   visitor cannot be identified. Present it as *what people felt*, never as a
   health measure.
7. **FHIR R4 export.** `Observation` + `Location` per the hl7-eu/oah IG. The
   citizen answers do not have official FHIR codes yet, so define local
   CodeSystems, mark them `experimental`, and carry the same provenance fields
   already in `questions.json`. Validate the output with the HL7 validator and
   commit the validation report — judges can check it.

### Worth doing before any of the above

8. **Run the Gemini provider against real photos** using `docs/photo-sources.md`,
   and iterate on the prompt. Everything else in Phase 1 is verified; this is the
   one part that is not.
9. **Get a native speaker** to review the Portuguese, and translate the question
   set into the remaining four languages.
