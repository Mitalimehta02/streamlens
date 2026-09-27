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
| Keep-awake ping | GitHub Actions | Free and unlimited on a public repository. |

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
first visitor afterwards waits the better part of a minute for it to wake. The
workflow in [`.github/workflows/keep-awake.yml`](../.github/workflows/keep-awake.yml)
pings it every ten minutes.

Set one repository variable: **Settings > Secrets and variables > Actions >
Variables > New repository variable**, named `API_URL`, with the Render URL.
Without it the workflow exits quietly rather than failing. Run it once by hand
from the Actions tab to check.

**This does not work in a fork.** GitHub disables workflows in a forked
repository until someone enables them on the Actions tab, and it does not run
`schedule` events in forks at all - the workflow will sit at zero runs no matter
what the variable says. If the deployed repository is a fork, either take it out
of the fork network (**Settings > General**, or ask GitHub Support) or push the
same history to a repository created empty. `workflow_dispatch` still works in a
fork, so the ping can be triggered by hand, which is fine for a demo being
watched and useless otherwise.

It pings `/health`, which reads local JSON files and opens no database
connection. That is deliberate: a ping that touched the database would wake Neon
every ten minutes and spend the compute-hour allowance on nothing.

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
