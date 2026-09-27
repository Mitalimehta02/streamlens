# StreamLens

**A second pair of eyes for citizen stream assessments — the citizen always decides.**

IEEE OneAquaHealth Global Hackathon 2026.

## Try it

| | |
| --- | --- |
| **Live demo** | **<https://streamlens-ten.vercel.app>** |
| **API** | <https://streamlens-api.onrender.com> — [interactive docs](https://streamlens-api.onrender.com/docs) |
| **Runs locally** | `npm run setup && npm run dev` — no key needed |

The API is on a free Render instance. If it has been idle for a quarter of an
hour the first request wakes it, which took 42.7 s when measured; a cron-job.org
schedule pings it every ten minutes to prevent that. See
[Known limits](#known-limits).

The demo needs no account and no sign-in. It carries labelled synthetic data so
the maps and alerts have something to show; every synthetic record says
`synthetic: true`, and the toggle at the top of Explore and Community switches
between all data, real only and demo only.

### Judge quick tour (about four minutes)

The same five steps appear in the app itself, on the first screen.

1. **Pick a site.** The list is the OneAquaHealth / ENORA research sites in
   Benevento, Coimbra, Oslo and Toulouse. No location permission is needed to
   choose from the list.
2. **Choose whether the AI helps.** With AI, a shrunk and EXIF-stripped copy of
   the photographs goes to Google Gemini under its free-tier terms. Without, no
   request is made at all. Both paths ask the same questions and record the same
   data — see [docs/privacy.md](docs/privacy.md).
3. **Photograph upstream and downstream**, or open **"Try with sample photos"**
   for six Creative Commons photographs. One of them has no water in it: the
   assessment should refuse that one rather than guess.
4. **Confirm every answer.** The AI drafts; you accept, change or reject each
   chip. Where you disagree, both answers are kept. The Good / Moderate / Poor
   rating is never suggested.
5. **Read what came back.** *Explore* holds the health card, the 48-hour alerts
   with their thresholds and sources, and the restoration measures. *Community*
   holds coverage, team standings, the wellbeing mirror and the **FHIR R4
   export** — the download button on any site or city.

Worth a look while you are there: the **DEMO FORECAST** badge on a planted
weather row, the **demo AI (mock)** badge when the AI is unavailable or its free
quota is spent, and the per-threshold **source** line under every alert.

### Measured

Lighthouse 12, mobile preset (emulated Moto G Power, throttled 4G), against the
live site above, two consecutive runs:

| | Performance | Accessibility | Best practices | SEO |
| --- | --- | --- | --- | --- |
| Run 1 | 84 | 100 | 100 | 100 |
| Run 2 | 90 | 100 | 100 | 92 |

Both runs are reported rather than the better one. Performance varies because
the first screen waits for the site catalogue and the question set from a free
Render instance in Frankfurt: those two requests took 1.7 s and 1.5 s in the
slower run, and the map tiles come from OpenStreetMap at about 1.2 s each. The
SEO dip in run 2 was a failed fetch of `robots.txt` during the audit; the file
serves 200 with valid content. The same build scores 91 with the API on
localhost, which is the honest way to read the gap: it is the network, not the
bundle.

A cold start is worse than any of this. Measured on 27 September after
seventeen minutes of silence: **42.7 s** for the first request, then 0.56 s.

Hosting is Render (API), Neon (Postgres) and Vercel (web app), all on free
tiers, with a cron-job.org ping every ten minutes so the free instance does not
sleep. [docs/deploy.md](docs/deploy.md) has the steps and the limits.

StreamLens is a photo-first, offline-capable field companion for the
[OneAquaHealth](https://www.oneaquahealth.eu/) Citizen Science App. A vision model
looks at the citizen's upstream and downstream photos and pre-fills the app's own
assessment questions as **suggestion chips**, each with a confidence level and a
short reason in plain language. The citizen confirms or rejects every single one.

> **The AI never sets the overall rating.** It suggests answers to factual
> questions; the Good / Moderate / Poor verdict is always the citizen's.

## The loop

| Part | What it does | Tracks |
|---|---|---|
| **1. Observe** | Photo-first guided assessment, AI suggestion chips with reasons, plain-language glossary, live photo/GPS quality checks, 6 languages, offline-first PWA | 1, 3 |
| **2. Understand & Act** | Stream health card, rule-based 48-hour alert (Open-Meteo + recent reports) that shows its reasons, problems → restoration measures with health benefits | 6, 2 |
| **3. Return** | Quests computed from real data gaps, points for evidence quality and never for volume, team-only leaderboard, coverage map, wellbeing mirror with a minimum group size | 5, 4 |

Plus **FHIR R4 export** (Observation + Location) following the hl7-eu/oah
Implementation Guide.

**Status: all three parts built, plus FHIR R4 export.** See
[docs/STATUS.md](docs/STATUS.md) for exactly what works and what is stubbed —
including the things that are deliberately unfinished.

The FHIR export validates with **0 errors and 0 warnings** against the
OneAquaHealth IG profiles using the official HL7 validator; the report, the
modelling decisions and a negative control proving the profiles were really
applied are in [docs/fhir/](docs/fhir/).

## Quick start

Requires Node 20+, Python 3.11, and Git.

```powershell
git clone <this repo>
cd "IEEE Hackathon"

# 1. one-time setup (creates the venv, installs api + web dependencies)
npm install
npm run setup

# 2. start both apps
npm run dev
```

Other commands:

```powershell
npm test              # pytest + vitest
npm run test:api      # pytest only
npm run test:web      # vitest only
npm run build         # production build of the web app
npm run data:sites    # re-fetch data/sites.json from the ENORA API
npm run data:questions # rebuild data/questions.json
```

- Web app: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>

No API key is needed to run the demo. With no `GEMINI_API_KEY` set, StreamLens uses
a deterministic **mock** vision provider and the UI shows a **"demo AI (mock)"**
badge so nobody mistakes it for a real model. To use Gemini, copy `api/.env.example`
to `api/.env` and set `AI_PROVIDER=gemini` plus your `GEMINI_API_KEY`.

## Privacy in one paragraph

**AI help is optional and you choose before you take a photograph.** If you use
it, a copy of your photos — shrunk to 1024 px and stripped of all hidden data
including GPS — is sent to Google Gemini on its **free tier**, where Google's own
terms say human reviewers may read them and Google may use them to improve its
products. If you answer yourself, your photos are never sent to Google; the same
questions are asked and the same data recorded. StreamLens asks for no name, no
email and no password, and on the public demo photographs are not stored at all
once they have been measured. Google's terms tell users not to send personal
information through the free tier, so **photograph the water and the banks, not
people**. Full detail, with the terms quoted: **[docs/privacy.md](docs/privacy.md)**.

## Ethics and data handling

- **AI suggests, humans decide.** Every record stores the citizen's answer *and*
  what the AI suggested, so disagreement is measurable, not hidden.
- **No medical claims.** StreamLens discusses ecosystem health and general One
  Health relevance. It never diagnoses.
- **Synthetic data is labelled.** Every demo record carries `"synthetic": true`.
- **Photos are stripped of EXIF** (including embedded GPS) and downscaled to
  1600 px before storage. Location is stored only in its own field, from an
  explicit user action, after an explicit consent notice.
- **Provenance is visible.** Answer codes are not presented as official unless they
  came from a public source; machine-translated strings are flagged.

## Responsible AI

### What the AI does

It looks at the citizen's photographs and proposes draft answers to factual
questions about the stream — what the bed is made of, whether the banks are
hardened, what is growing on the margins — each with a confidence and a
one-sentence reason pointing at something in the picture.

### What it does not do

- **It never sets the overall rating.** Good / Moderate / Poor is the citizen's
  alone. The question is not offered to the model, and a suggestion for it is
  refused by the API even at confidence 1.0.
- **It never makes a health claim.** StreamLens describes the condition of a
  stream. It does not diagnose, does not advise, and does not say whether water
  is safe to touch or drink.
- **It never identifies people.** The prompt forbids describing people, vehicles
  or anything else that could identify someone, and photo metadata is destroyed
  before storage.
- **It never decides anything.** A suggestion the citizen has not acted on is
  not submitted. Silence is not consent.

### The three guards

1. **The prompt** tells the model to answer `NS` ("I'm not sure") rather than
   guess, and that the overall rating does not exist for it.
2. **The validation gate** checks every returned code against the published
   question set before a citizen can see it. Invented codes, unknown questions
   and answers to never-suggest questions are discarded into a `dropped` list
   that the interface surfaces rather than hides.
3. **The interface** starts every suggestion unanswered, records the citizen's
   answer alongside what the AI proposed so disagreement is measurable, and
   labels itself: a "demo AI (mock)" badge when no model is running, and an
   "AI unavailable — answer manually" notice when a real provider fails and the
   offline heuristic stands in. The fallback is never silent.

### How it is evaluated

`eval/run_eval.py` runs a folder of photographs through the real provider using
the same preparation and validation code as the live API, and scores the result
against a human labeller's own answers. It reports, per question and overall:
agreement, unknown (`NS`) rate, the rate of suggestions dropped by validation,
calibration (mean confidence when right versus when wrong), latency and
approximate cost. Reports are committed to `eval/reports/`, so a prompt change
can be argued for with numbers. See [eval/README.md](eval/README.md) for how to
read them.

### Latest numbers

Measured 24 September 2026 on **29 freely-licensed photographs** from Wikimedia
Commons, against **129 labels**, using **`gemini-3.5-flash-lite`**. Full reports
in [`eval/reports/`](eval/reports/); the comparison that chose the current
prompt is [`v1-vs-v2.md`](eval/reports/v1-vs-v2.md).

| | `assess_v1` | `assess_v2` (current) |
|---|---:|---:|
| Agreement with an independent AI labeller | 89% | **91%** |
| Suggestions dropped by validation | 0% | **0%** |
| Said "not sure" | 0% | 2% |
| Confidence when agreeing / disagreeing | 0.87 / 0.84 | 0.89 / 0.82 |
| Calibration gap | 0.03 | **0.07** |
| Stayed silent on images with no watercourse | 9 of 13 | 10 of 13 |
| Mean latency | 3.8 s | 4.0 s |
| Approximate cost | — | **$0.002 per photograph** (~$2 per 1,000) |

**Read "agreement", not "accuracy".** There were **no human expert labels**.
The labeller is Claude (the coding agent) viewing each photograph and answering
only what was clearly visible; the model under test is Gemini. Two AI systems
agreeing is not the same as either being right, and where they agree they may
be agreeing on the same mistake. On inspection, of six scored disagreements in
the baseline, one was a labeller error, two were ambiguous questions and one was
a scoring artefact - so the headline figure understates compatibility and the
sample is far too small to make a confident claim in either direction.

The result worth more than the percentages: **nothing was dropped by validation
in either run.** Across 173 suggestions the model never invented an answer code
or answered a question it was not offered. The guard held.

### Limits on those numbers

- **No human expert was involved.** Both the labeller and the model are AI.
- **Small sample.** 29 photographs, 129 labels, 45-57 scored comparisons. A
  two-point difference is well inside the noise, and per-question rows with two
  or three observations are anecdote.
- **Web photographs, not app submissions.** Images chosen from Commons
  categories and framed by photographers with other purposes - not phone snaps
  taken by a volunteer standing on a bank. Thirteen of the 29 turned out not to
  show a watercourse at all, and were kept deliberately as negative controls.
- **One photograph per assessment**, where the real flow sends two.
- **One model, one afternoon.** `gemini-3.6-flash` was unusable throughout
  (HTTP 503 under sustained load), so these are `gemini-3.5-flash-lite` numbers.
- **Costs are approximate** and depend on [`eval/pricing.json`](eval/pricing.json)
  being current.

## Known limits

Written here rather than left to be discovered. The full list, including what is
stubbed and what differs in production, is in [docs/STATUS.md](docs/STATUS.md).

- **Cold start.** The API is on a free Render instance that sleeps after about
  fifteen minutes idle; waking it took **42.7 s** when measured. A cron-job.org
  schedule requests `/health` every ten minutes to prevent that. If the demo is
  ever slow to load, that is what happened, and the second request is fast.
  (The GitHub Actions workflow in this repository would do the same job, but
  GitHub does not run scheduled workflows in a fork, and this repository is one.)
- **A free AI quota.** 10 AI calls per device per hour and 300 a day across the
  whole demo. Past either cap an assessment still works: it falls back to the
  labelled mock provider with a visible notice, and never returns an error.
- **Photographs are not kept.** On the hosted demo they are measured and
  discarded, so nothing can be shown publicly. The quality measurements are
  stored; the images are not.
- **Most of the demo data is synthetic**, and every synthetic record says so.
  Two sites carry a planted weather forecast so the rain-driven alert rules can
  be demonstrated on a dry day; those are labelled **DEMO FORECAST** wherever
  the number appears.
- **The question set is translated into English and Portuguese only.** The other
  four languages fall back to English for question text, and every non-English
  string is machine translated and flagged as such. A native speaker should
  review before field use.
- **No accounts, and no authentication.** Anyone who can reach the API can post
  an assessment. Acceptable for a demo; not for production.
- **The AI evaluation is small.** 29 photographs, one independent labeller, one
  model, one afternoon. The metric is *agreement with an independent AI
  labeller*, not accuracy against ground truth - see
  [Responsible AI](#responsible-ai).
- **Not tested on a physical phone.** The PWA manifest and service worker build
  and serve correctly, and the layout is designed for one hand outdoors, but
  the install has only been exercised in a desktop browser.

## Data sources

- **Research sites** — `https://api.enora-oah.eu/api/sites/all` (public, no auth).
  106 sites across Toulouse, Ghent, Coimbra, Benevento and Oslo, fetched once into
  [`data/sites.json`](data/sites.json) and served from that local file so the app
  works offline. *Site data: OneAquaHealth / ENORA API.*
- **Question set** — the app's `api/citizens/*` endpoints require authentication,
  so [`data/questions.json`](data/questions.json) is reconstructed from the published
  OneAquaHealth assessment categories and marked `"source": "manual"`.
- **Weather** — [Open-Meteo](https://open-meteo.com/) (no key).

## Testing the vision prompt

`docs/photo-sources.md` lists 45 checked, legally usable sources of stream
photographs — the real watercourses of all five research cities, plus one
category per thing the questions ask about (weirs, outfalls, gabions, dry beds,
invasive species), plus licence-filtered search platforms.

## Repository layout

```
api/    FastAPI + Pydantic v2 + SQLModel (SQLite locally, Postgres hosted)
web/    React + Vite + TypeScript + Tailwind + PWA + Leaflet + Dexie + i18next
data/   sites.json, questions.json, alert/quest/points rules
docs/   status, privacy, deploy, photo test sources, FHIR notes
eval/   the vision-prompt evaluation harness and its reports
web/public/samples/  six Creative Commons demo photographs, with licences
render.yaml, web/vercel.json, .github/workflows/  the hosted demo
```

See [CLAUDE.md](CLAUDE.md) for the full brief, architecture and working rules.

## Licence

Code: MIT. Site data belongs to the OneAquaHealth / ENORA consortium and is
redistributed here for hackathon evaluation with attribution. The six sample
photographs in `web/public/samples/` keep their own Creative Commons or public
domain licences, listed with their authors in
[web/public/samples/LICENCES.md](web/public/samples/LICENCES.md).
