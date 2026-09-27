# FHIR R4 validation report

Written for: the HL7 reviewer. Facts, dates and commands, so every claim here
can be re-run.

Validated **24 September 2026** and re-validated **27 September 2026** with the
official HL7 validator, `validator_cli.jar` (`org.hl7.fhir.core`, downloaded from
the project's latest release on each of those days), on OpenJDK 17.0.10.

The re-run was needed because the repository moved and the canonical base of our
two local CodeSystems moved with it, from
`hackathons-4thyear.github.io/streamlens/fhir` to
`mitalimehta02.github.io/streamlens/fhir`. A canonical URL is an identifier
rather than an address, so it did not have to change; it was changed so that
nothing in a standards-facing artefact names a repository that no longer exists.
The committed `OperationOutcome` files are the output of that second run, on a
freshly downloaded validator, and the counts below are identical to the first.
The example bundle was regenerated from the same stored assessment, so the only
differences from the first run are the base URL and the bundle timestamp.

## Result

| Run | Profiles used | Errors | Warnings | Information |
|---|---|---:|---:|---:|
| Base FHIR R4 only | `hl7.fhir.r4.core#4.0.1` | **0** | 15 | 15 |
| **Against the OneAquaHealth IG** | `hl7.eu.fhir.oah` compiled from source | **0** | **0** | 14 |

The 15 warnings in the base-R4 run were all one issue — the IG profiles named in
`meta.profile` could not be resolved, because the IG is not published (see
below). Once the IG was compiled locally and supplied to the validator, those
warnings disappeared and the bundle validated against the real profiles with
nothing outstanding.

### The 14 information messages

All 14 are the same message:

> None of the codings provided are in the value set 'OAH Indicators (Non-Health)'
> (`http://hl7.eu/fhir/ig/oah/ValueSet/oah-indicators-no-health-oah-vs`)

This is expected and correct. `ObservationIndicatorsOah` binds `code` to that
value set with strength **`preferred`**, not `required`. The IG does not define
codes for the citizen question set — it covers physico-chemical and health
indicators — so StreamLens defines its own in a local CodeSystem, marked
`experimental: true`, and the validator reports the preferred-binding miss as
information rather than as a problem. A `required` binding would have made this
an error, and the bundle would have needed different codes.

### Proof the profiles are actually enforced

A clean result is only meaningful if the profile was really applied. As a
negative control, one Observation in the bundle was deliberately broken —
`performer` removed and `status` changed from `final` to `preliminary` — and
re-validated with the same command:

```
ERROR  Observation.performer: minimum required = 1, but only found 0
       (from .../StructureDefinition/observation-indicators-oah)
ERROR  Value is 'preliminary' but is fixed to 'final' in the profile
       .../StructureDefinition/observation-indicators-oah
ERROR  The contained resource 'programme' is not referenced from elsewhere...
```

The validator produced exactly the constraints the profile defines, so the
zero-error result on the real bundle is a real pass and not a silently skipped
profile.

## Reproducing it

```bash
# 1. the validator
curl -L -o tools/validator_cli.jar \
  https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar

# 2. the IG, compiled from its FSH source (it is not published - see below)
curl -L -o ig.tar.gz https://github.com/hl7-eu/oah/archive/refs/heads/master.tar.gz
tar xzf ig.tar.gz && cd oah-master
npx fsh-sushi@3 . -o ../out          # 7 profiles, 11 value sets, 0 errors

# 3. a bundle from a running StreamLens
curl -s http://localhost:8000/observations/<id>/fhir > example-bundle.json

# 4. validate against the IG profiles  -> validation-oah-ig.json
java -jar tools/validator_cli.jar docs/fhir/example-bundle.json -version 4.0.1 \
  -ig tools/oah-ig/out/fsh-generated/resources \
  -ig docs/fhir                     # our local CodeSystems

# 5. and against base R4 alone, for comparison -> validation-base-r4.json
java -jar tools/validator_cli.jar docs/fhir/example-bundle.json -version 4.0.1 \
  -ig docs/fhir                     # still needed, or every local code
```                                  # is reported as an unresolvable system

Neither the validator jar nor the IG source is committed: they are 200 MB and
570 KB of somebody else's work respectively, and both are one command away.

## The state of the IG, and when

`hl7-eu/oah` defines the profiles this export targets. Its **published form was
not available** while this was built:

| Checked | What | Result |
|---|---|---|
| 24 Sep 2026, 10:43 UTC | `build.fhir.org/ig/hl7-eu/oah/` | HTTP 404 |
| 24 Sep 2026, 10:43 UTC | `.../oah/package.tgz` | HTTP 404 |
| 24 Sep 2026, 10:43 UTC | `.../oah/index.html` | HTTP 404 |
| 24 Sep 2026, 10:43 UTC | An example page previously indexed by search | HTTP 404 |
| 24 Sep 2026 | `packages.fhir.org/hl7.fhir.eu.oah` | HTTP 404 |
| 24 Sep 2026 | `packages2.fhir.org/packages/hl7.fhir.eu.oah` | HTTP 404 |
| 24 Sep 2026 | `build.fhir.org/ig/qas.json` | 200, no `oah` entry |

The CI build was reportedly reachable on 23 September, and search engines had
indexed pages from it, so this looks like a transient CI-build outage rather
than a withdrawal. It was re-checked once before falling back, as agreed.

The fallback was to compile the IG from its own FSH source with SUSHI, which
succeeded with 0 errors and 0 warnings and produced profiles whose canonical
URLs match those the export targets exactly:

- `http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah`
- `http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-indicators-oah`

Source: `hl7-eu/oah@master`, `sushi-config.yaml` canonical `http://hl7.eu/fhir/ig/oah`,
version `0.1.0-ci-build`.

## Modelling decisions

These are choices, not facts, and a reviewer may reasonably disagree with any of
them.

### `Observation.performer` is a contained `Organization`

The profile requires `performer 1..`. StreamLens deliberately holds no identity
for its citizens — no name, no email, no account — so there is no person to
name. The performer is therefore the monitoring programme, or the team where the
citizen typed a team code: *"StreamLens citizen monitoring – team ESC-COIMBRA-7B"*.

A contained `RelatedPerson` was considered and rejected. In R4
`RelatedPerson.patient` is 1..1, so it would require a `Patient` that does not
exist and should not be invented; a citizen assessing a stream is not a patient
of anything.

The Organization is *contained* rather than a separate bundle entry so that each
Observation remains interpretable if it is extracted on its own. The cost is
that the same Organization repeats in every Observation of a bundle.

### The citizen is a logical reference in `Provenance.agent`

```json
{ "type": { "coding": [{ "code": "author" }] },
  "who": { "identifier": { "system": ".../pseudonymous-client",
                           "value": "<random id generated on the phone>" },
           "display": "Citizen observer (pseudonymous)" } }
```

R4 permits a `Reference` carrying only an `identifier`, which is exactly the
case where a participant is known by an id in another system but has no resource.
This keeps the pseudonymous id — which is all StreamLens ever receives — in the
record without fabricating a `Patient` or `RelatedPerson`.

`author` was chosen over `verifier`: the citizen is the origin of the answers,
not a reviewer of somebody else's.

### The AI is a contained `Device` with type `assembler`

```json
{ "type": { "coding": [{ "code": "assembler" }] },
  "who": { "reference": "#ai" } }
```

The contained `Device` carries the model name (`deviceName`) and the prompt
version (`version`). `assembler` from
`http://terminology.hl7.org/CodeSystem/provenance-participant-type` is the
closest honest fit: the model assembled a draft that a person then confirmed or
overrode. It is deliberately **not** `author` and never `verifier` — the whole
product rule is that the AI suggests and the citizen decides, and the Provenance
should not say otherwise.

When no AI was involved the Device and its agent are simply absent.

### Whether the citizen agreed with the AI

Recorded per Observation in `note`, in plain text, e.g.

> Citizen-confirmed answer. The AI suggested 'ART' with confidence 0.62. The
> citizen chose differently. Model: gemini-3.5-flash-lite. Prompt: assess_v3.

A structured extension would be more machine-readable, but the IG defines no
element for it and inventing an extension for a hackathon export seemed worse
than plain text that a human reviewer can read. This is the weakest part of the
mapping and the first thing worth improving.

### Multi-select answers become `component`, not multiple codings

Several `coding` entries inside one `CodeableConcept` means "the same concept
expressed in different systems". A choose-ALL answer is several *different*
concepts, so each selected code becomes its own `component` with
`valueCodeableConcept`. The profile explicitly allows `component.value[x]` as
`CodeableConcept`.

### The citizen's overall rating

Exported as an Observation like any other, with a note stating that StreamLens
never lets the AI suggest this value.

## Local terminology

Two CodeSystems, both `status: draft`, `experimental: true`, published in this
folder:

| File | Codes | URL |
|---|---:|---|
| `CodeSystem-citizen-question.json` | 24 | `.../CodeSystem/citizen-question` |
| `CodeSystem-citizen-answer.json` | 85 | `.../CodeSystem/citizen-answer` |

Their description states plainly that they are **not** official OneAquaHealth
codes. The answer codes themselves largely reuse the OAH app's own codes (see
`data/questions.json` provenance); the `litter` question and its options are
entirely ours and are marked `source: manual` throughout.

## Known limits

- **One bundle per assessment.** `GET /cities/{city}/fhir` returns a Bundle of
  Bundles, which is legal but not elegant; a transaction bundle or a paged
  search result would suit a real integration better.
- **`Bundle.type` is `collection`.** Nothing here is intended to be POSTed to a
  server as-is.
- **No `Patient`, no health data.** StreamLens exports environmental
  observations and the provenance of who recorded them. It holds no personal
  health information and makes no health claims, so the IG's health-measure
  profiles are not used.
- **Validated against one bundle.** The structure is identical across
  assessments, but only one has been through the validator.
