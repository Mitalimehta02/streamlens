# Deploying StreamLens

Written for whoever puts this online: the maintainer, or a judge who wants to
run their own copy.

Everything here is free. No card is entered anywhere, no service is upgraded,
and nothing in this repository asks for one. Where a free tier has a limit that
matters, the limit is written down rather than discovered later.

| Piece | Host | Free tier, and what it costs us |
| --- | --- | --- |
| API (FastAPI) | Render | 750 instance-hours a month. One always-awake service uses about 720 of them, so run exactly one. |
| Database (Postgres) | Neon | 0.5 GB and about 190 compute-hours a month. Suspends after five minutes idle and wakes on the next query. |
| Web app (React) | Vercel | Hobby plan. Static build, generous bandwidth. |
| Keep-awake ping | cron-job.org | Free, no card, nothing to deploy. A GitHub Actions workflow does the same job, but not in a fork - see below. |

Render was chosen over Fly.io for the API because it needs no card at sign-up,
and Neon over Render's own Postgres because Render's free database is deleted
after 30 days, which is shorter than the life of this demo.

## Before you start

You need accounts on Neon, Render and Vercel, and push access to the
repository. Sign in to all three with GitHub and none of them will ask for a
card.

## 1. The database, on Neon

1. Create a project. Any name; region **eu-central-1 (Frankfurt)** keeps it next
   to the API.
2. On the project dashboard, copy the **pooled** connection string. It looks
   like `postgresql://user:password@ep-something-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
3. Keep it somewhere for step 2. Nothing else on Neon needs changing.

The pooled string matters: Render's free instance opens and drops connections
as it sleeps and wakes, and the pooler absorbs that. The API rewrites the URL
to the driver it installs, so paste it exactly as Neon prints it.

## 2. The API, on Render

1. **New > Blueprint**, point it at this repository. Render reads
   [`render.yaml`](../render.yaml) and proposes one free web service.
2. It will ask for the three values that are deliberately not in the file:

   | Key | Value |
   | --- | --- |
   | `DATABASE_URL` | the Neon string from step 1 |
   | `GEMINI_API_KEY` | your key from [aistudio.google.com](https://aistudio.google.com/apikey) |
   | `CORS_ORIGINS` | the Vercel URL from step 3, with no trailing slash |

   You will not have the Vercel URL yet. Put `http://localhost:5173` in for now
   and correct it after step 3.
3. Deploy. The first build takes a few minutes. When it finishes, open
   `https://<your-service>.onrender.com/health` - it should return JSON naming
   the provider and model.
4. The service seeds labelled synthetic demo data on its first start, because
   `SEED_DEMO=true`. It only does this when the database has none, so redeploys
   neither duplicate it nor touch real submissions.

Leave `STORE_PHOTOS=false` as the blueprint sets it. On the hosted demo the
photograph is measured and then dropped: nothing is written to disk, nothing can
be served, and there is nothing left to delete. Render's free disk is wiped on
every deploy anyway, so storing them would have been a promise the platform
could not keep.

## 3. The web app, on Vercel

1. **Add New > Project**, import this repository.
2. Set **Root Directory** to `web`. Vercel then reads
   [`web/vercel.json`](../web/vercel.json) and needs no other build settings.
3. Add one environment variable, for all environments:

   | Key | Value |
   | --- | --- |
   | `VITE_API_URL` | `https://<your-service>.onrender.com` |

4. Deploy, then copy the resulting URL back into Render's `CORS_ORIGINS` and
   redeploy the API. The API answers that one origin and no other; a wildcard
   would make every site on the internet able to spend your Gemini quota.
5. Check it took. `/health` lists the origins the running process will answer:

   ```bash
   curl -s https://<your-service>.onrender.com/health
   ```

   If the Vercel URL is not in `cors_origins`, the variable has not reached the
   process - the value is saved against another service, the key is misspelled,
   or the service has not restarted since. The symptom in a browser is the app
   loading its shell and then showing "The site list could not be loaded",
   because every request it makes is blocked; the API itself looks perfectly
   healthy from the outside, which is why it is worth checking directly.

## 4. The keep-awake ping

A free Render service sleeps after about fifteen minutes of silence, and the
first visitor afterwards waits for it to wake. On this service that wait was
measured at **42.7 seconds**, which is not a thing to hand a judge.

**This demo uses [cron-job.org](https://cron-job.org) to request
`/health` every ten minutes.** It is free, needs no card, and needs nothing in
this repository: create a cronjob, give it the URL
`https://<your-service>.onrender.com/health`, set the interval to ten minutes,
and save.

Whatever does the pinging, it should ping `/health` specifically. That endpoint
reads local JSON files and opens no database connection, so it keeps Render
awake without waking Neon, whose free compute-hours would otherwise be spent on
nothing but the pings themselves. Keeping one service awake continuously uses
about 720 of Render's 750 free instance-hours a month, which is the whole
allowance - it is another reason to run exactly one service.

### The GitHub Actions alternative, and why it is not what runs here

[`.github/workflows/keep-awake.yml`](../.github/workflows/keep-awake.yml) does
the same job from GitHub, for free, on a public repository. To use it, set one
repository variable - **Settings > Secrets and variables > Actions > Variables >
New repository variable**, named `API_URL`, with the Render URL - and the
schedule does the rest. Without the variable the workflow exits quietly rather
than failing.

**It cannot work in a fork.** GitHub disables workflows in a forked repository
until someone enables them on the Actions tab, and does not run `schedule`
events in forks at all: the workflow sits at zero runs no matter what the
variable says. This repository is a fork, which is exactly why the ping is
external. To use the workflow instead, take the repository out of the fork
network (**Settings > General**, or ask GitHub Support), or push the same
history to a repository created empty. The workflow is kept in the tree because
it costs nothing there and is correct the moment the repository is not a fork;
`workflow_dispatch` also still works by hand.

## What the hosted demo is, and is not

- Demo data is on by default and every synthetic record is labelled
  `synthetic: true`. The toggle in the app switches between all data, real only
  and demo only; the API filters on the same flag.
- Photographs are not stored. Photograph *measurements* are.
- AI help is opt-in, per assessment. Choosing "answer myself" means no request
  is made at all - see [privacy.md](privacy.md).
- The Gemini key is on a free tier, so the API caps itself at 10 AI calls per
  device per hour and 300 a day in total. Past either, assessments still work:
  they fall back to the labelled mock provider with a visible notice, and never
  return an error.
- One Render service, one Neon project. Adding a second of either is where a
  free tier turns into a bill.

## Running it yourself instead

```bash
npm run setup     # Python venv, Node packages
npm run dev       # API on :8000, web on :5173
```

Copy `api/.env.example` to `api/.env` first if you want Gemini rather than the
mock provider. Locally `STORE_PHOTOS` defaults to true, and stored photographs
are deleted after `PHOTO_RETENTION_DAYS` (14).
