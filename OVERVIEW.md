# RescueMate: Social Media Sensor + Digital Twin Map — Overview

A high-level introduction to what these two systems do and what you need to
gather before you can run them. For the actual step-by-step launch, see the
`quick_setup/` directory in the
[social-media-sensor](https://git.informatik.uni-hamburg.de/rescue-mate/social-media-sensor)
repo — that's the "plug and play" part; this document is the "know what
you're plugging in" part.

This file is kept in sync between the social-media-sensor and
[sems-digital-twin-map](https://github.com/semantic-systems/sems-digital-twin-map)
(this repo) repositories.

## What these systems are

RescueMate monitors social media for disaster-relevant reports and shows them
on a map. Two independent systems do this, connected by a shared knowledge
graph:

```
 Mastodon / Bluesky / RSS
           │
           ▼
 ┌───────────────────────┐        writes         ┌─────────────────────┐
 │   Social Media Sensor  │ ─────────────────────▶ │  RescueMate          │
 │   (social-media-sensor │                        │  Knowledge Graph     │
 │   repo)                │                        │  (SPARQL, Keycloak-  │
 └───────────────────────┘                        │  protected)          │
                                                     └─────────────────────┘
 ┌───────────────────────┐        reads                      │
 │   Digital Twin Map     │ ◀─────────────────────────────────┘
 │   (this repo)          │
 └───────────────────────┘
           │
           ▼
     Map UI (browser)
```

### Social Media Sensor

Continuously collects posts from Mastodon, Bluesky, and RSS feeds, then for
each post:

1. **Relevance classification** — is this actually about a disaster/incident?
2. **Event classification** — what kind of event (few-shot, LLM-based)?
3. **Geolocation extraction** — which places are mentioned, resolved to coordinates.
4. **Publishing** — every processed post is written to the RescueMate
   Knowledge Graph, tagged with its relevance, event type, and any geolocated
   place mentions found (locations are an enrichment, not a gate — a post
   with none found is still published). Dropping irrelevant posts before
   publishing is optional (`filter_by_relevance` in `config.yaml`, off by
   default) — by default everything goes in, with the relevance label left
   for consumers like the map to filter on.

It doesn't have a UI of its own — it's a background service. All of the above
except the final publish step relies on an LLM (an OpenAI-compatible
endpoint), not a locally-running model.

### Digital Twin Map

A web map (React frontend + FastAPI backend + PostGIS) that reads reports
back out of the same Knowledge Graph and displays them as pins, alongside
Hamburg open-data layers. It also handles report triage (mark seen/flagged),
user accounts, and a demo mode. See this repo's own `README.md` for the full
feature list.

### The connecting piece

Both systems talk to the **same RescueMate Knowledge Graph** — the sensor
writes to it, this repo's `server_reports` worker reads from it via SPARQL.
Both authenticate with **the same Keycloak account** (see below): the sensor
needs write access to publish posts, the map needs read access to query them.

## What you need before you start

Four things have to be gathered before either system does anything useful.
The quick-setup script (in the social-media-sensor repo) will prompt you for
all of these interactively and explains where each one goes — this section
is about *obtaining* them, not entering them.

### 1. RescueMate Keycloak account (shared by both systems)

A username + password for the Keycloak instance that protects the RescueMate
Knowledge Graph. This is **one account used by both systems** — the sensor's
`TARGET_SERVER_USERNAME`/`PASSWORD` and this repo's `USERNAME`/`PASSWORD` are
the same credential under different names (a historical naming difference
between the two codebases, not two separate accounts).

**How to get it:** ask the RescueMate project team. It's not self-service —
there's no signup flow.

### 2. Mastodon access token

An API token so the sensor can read posts from a Mastodon instance.

**How to get it**, on the instance you want to monitor (default:
`mastodon.social`, but any instance works):
1. Log in to that instance in a browser.
2. Go to **Settings → Development → New application**.
3. Give it any name, leave the default scopes (read access is enough — the
   sensor never posts).
4. Submit, then open the application you just created and copy **"Your
   access token"**.

This token is tied to that specific instance and to your account there — if
you switch instances later, generate a new one.

### 3. LLM access

An OpenAI-compatible LLM endpoint, used for relevance/event classification
and geo-disambiguation. You need:
- **An endpoint URL** (e.g. an internal vLLM deployment, or a hosted
  OpenAI-compatible proxy).
- **An API key** for it, if it requires auth.
- **A model name** actually served at that endpoint.

**How to get it:** ask the project team for the shared endpoint + key, or
point at your own OpenAI-compatible deployment. The quick-setup script
queries the endpoint's `/models` list once it has the URL and key, and lets
you pick from what's actually available — you don't need to know the exact
model name in advance.

### 4. Map-only: database & admin passwords

Unlike the above, these aren't obtained from anyone — they're passwords
*you* set for services this stack creates itself (the Postgres database
storing map reports, and the map's own bootstrap admin login). The
quick-setup script generates safe placeholders and lets you override them.

## External services and their parameters

Neither system is self-contained: both call out to services that must exist
and be reachable. This is the handover-relevant map of *what talks to what*,
and which parameter points at each. "Where" gives the file the parameter
lives in; every one can also be overridden by an environment variable of the
same name (upper-cased; geolinker's take a `GEO_LINKER__` prefix).

### Social Media Sensor

| Service | What it's for | Parameter(s) | Where | If missing |
|---|---|---|---|---|
| **LLM endpoint** (OpenAI-compatible) | Relevance + event classification, geo-disambiguation. Nothing runs locally. | `llm_address`, `model_name`, `OPENAI_API_KEY` | `config.yaml` / env (sensor repo) | Sensor can't classify at all — hard dependency |
| **RescueMate KG nodes** | Where posts are published (`/datasets`) and deduplicated (`/sparql`) | `target_server_nodes`, `target_server_dataset`, `target_server_username`/`_password` | `config.yaml` / env (sensor repo) | Posts are dropped ("no usable KG node") |
| **Keycloak** | Issues the token for the KG nodes. Only node-1's realm knows the `uhh` client. | `target_server_nodes[].keycloak_url` | `config.yaml` | 401 / no token → nothing published |
| **Photon** | Primary geocoding candidate search | `photon_url` | `geolinker/config.yaml` (sensor repo) | Geo-linking raises — effectively mandatory |
| **Nominatim** | OSM lookup for polygons/geometries | `nominatim_url` | `geolinker/config.yaml` (sensor repo) | Optional: guarded, returns no geometries |
| **Overpass** | Adds OSM containing-relations as extra candidates | `overpass_url`, `add_containing_relations` | `geolinker/config.yaml` (sensor repo) | Optional: off unless both are set |
| **Mastodon instance** | Post source (authenticated) | `MASTODON_SERVER`, `MASTODON_ACCESS_TOKEN`, `social_media_platforms.mastodon` | env / `config.yaml` | That source yields nothing |
| **Bluesky Jetstream** | Post source (public firehose, no auth) | `BLUESKY_SERVER`, `social_media_platforms.bluesky` | env / `config.yaml` | That source yields nothing |
| **RSS feeds** | Post source (Abendblatt, Tagesschau, NDR, SHZ) | `social_media_platforms.rss.feeds` | `config.yaml` | That source yields nothing |
| **DSPy LM** | Query rewriting / candidate ranking | `dspy_lm_model`, `dspy_lm_url` | `geolinker/config.yaml` (sensor repo) | Optional: falls back to the main LLM above |
| **Fine-tuned retrieval model** | Alternative query generation backend | `cr_model_path` / `cr_external_model_url` | `geolinker/config.yaml` (sensor repo) | Optional: unset → main LLM is used |

The DSPy *program* files (`cr_dspy_program_path`, `dspy_ranker_program_path`)
are not services — they default to files bundled in `geolinker/data/`, which
is why they're deliberately absent from `geolinker/config.yaml` (sensor repo).

### Digital Twin Map

| Service | What it's for | Parameter(s) | Where | If missing |
|---|---|---|---|---|
| **RescueMate KG SPARQL** | Reads the reports the sensor published. All nodes are queried and unioned (they're failover peers, not replicas). | `SPARQL_ENDPOINTS`, `USERNAME`/`PASSWORD` | `.env` (this repo) / `map.env` | No reports appear on the map |
| **Keycloak** | Token for those SPARQL reads | `SPARQL_KEYCLOAK_URLS` | `.env` (this repo) / `map.env` | Unset → each node is asked for a token from its *own* Keycloak; only node-1's knows the `uhh` client, so node-2 returns `invalid_client`. node-1 is tried first either way, so setting this only suppresses that doomed second request — it does not make auth succeed when node-1 is down |
| **PostgreSQL + PostGIS** | Stores reports, users, triage state | `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` | `.env` (this repo) / `map.env` | Backend won't start — started by compose itself |
| **Hamburg Urban Data Hub** | Open geodata layers (schools, care homes, …) | `api_config.json` | this repo | Those layers are empty; reports still work |

### Current endpoints

The addresses actually configured today, so a new maintainer knows what these
services *are* and not just that they exist. Hostnames like `hcds-rescuemate`
and `sems-coypu-2` are **internal** — reachable only from the university
network/VPN, which is the usual cause of a fresh deployment hanging on
geocoding or LLM calls.

| Parameter | Configured value | Set in |
|---|---|---|
| `llm_address` | `https://llm.api.hcds.uni-hamburg.de/v1` | `config.yaml` (sensor repo) |
| `model_name` | `google/gemma-4-26B-A4B-it` | `config.yaml` (sensor repo) |
| `target_server_nodes` | `https://node-1.net.uhh.rescue-mate.de`, `https://node-2.net.uhh.rescue-mate.de` (node-2 authenticates via node-1) | `config.yaml` (sensor repo) |
| `target_server_dataset` | `social_media_data_fixed` | `config.yaml` (sensor repo) |
| `photon_url` | `http://hcds-rescuemate:2322/api/` | `geolinker/config.yaml` (sensor repo) |
| `nominatim_url` | `http://hcds-rescuemate:8080` | `geolinker/config.yaml` (sensor repo) |
| `overpass_url` | `http://hcds-rescuemate:12346/api/interpreter` | `geolinker/config.yaml` (sensor repo) |
| `MASTODON_SERVER` | `https://mastodon.nliwod.org/` (Python default: `https://mastodon.social/`) | `sensor.env` |
| `BLUESKY_SERVER` | `wss://jetstream2.us-west.bsky.network/subscribe` | Python default (unset everywhere) |
| `SPARQL_ENDPOINTS` | the two nodes above, each with `/sparql` | `map.env` |
| `SPARQL_KEYCLOAK_URLS` | node-1 twice (the list must match `SPARQL_ENDPOINTS` in length; the duplicate is deduped at runtime) | `map.env` |

> **Note on precedence.** `quick_setup`'s `sensor.env` sets `LLM_ADDRESS`
> explicitly, and environment variables outrank both YAML files — so that
> value wins over `config.yaml` (sensor repo) no matter what the image was built with.
> Both now point at `llm.api.hcds.uni-hamburg.de`; if you repoint one,
> repoint the other too or the two ways of running the sensor will disagree.

### Shared credential

The Keycloak account is the **same** for both systems — the sensor calls it
`TARGET_SERVER_USERNAME`/`PASSWORD`, the map calls it `USERNAME`/`PASSWORD`.
Only node-1's Keycloak authenticates the `uhh` client today, which is why
both systems' node lists point their auth at node-1.

Configuration precedence, highest first (sensor repo `src/manager/settings.py`):
environment variables → `.env` → `config.local.yaml` (gitignored, personal
overrides) → `config.yaml` (sensor repo). `GeoLinkerSettings` is independent, reading
`geolinker/config.yaml` (sensor repo) and `GEO_LINKER__*` env vars.

## Where to actually run it

Everything above is what you need *before* running
`quick_setup/run-full-stack.sh` in the social-media-sensor repo, which
starts both systems together from pre-built images — no source checkout of
either project required (not even this one). See that repo's
`quick_setup/README.md` for the full walkthrough, including the one manual
step after startup: the sensor doesn't collect posts until you explicitly
start its feed.

If you only want to run **this map on its own** — no sensor, e.g. against
an existing set of reports already in the Knowledge Graph — this repo has
its own quick start too: see [Quick start (Docker)](README.md#quick-start-docker)
in this repo's `README.md` (`docker compose up -d --build`, after copying
`example.env` to `.env`). That path still needs the RescueMate Keycloak
account (§1) and a SPARQL endpoint, but not Mastodon or LLM access — those
are sensor-only.
