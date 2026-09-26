# WorkTrack RFID — Backend (MVP)

Deployable implementation of the MVP scope (PRD section 22) from
[`n8n-workflow/WorkTrack_RFID_PRD.md`](../n8n-workflow/WorkTrack_RFID_PRD.md):
employee/RFID/device management, RFID event ingestion (MQTT + HTTP fallback),
attendance, project time tracking, exceptions/corrections, and dashboard APIs.

## Stack

- **FastAPI** — REST API and RBAC (JWT bearer tokens)
- **PostgreSQL** — system of record
- **Mosquitto (MQTT)** — RFID gateway transport
- **SQLAlchemy** — ORM, tables created automatically on startup
- Plain **Docker Compose** — one command to run the whole stack

## Run it

```bash
cd worktrack-backend
cp .env.example .env        # edit SECRET_KEY before any real deployment
docker compose up --build -d
docker compose exec api python -m scripts.seed
```

This starts Postgres, Mosquitto, and the API on `http://localhost:8000`
(interactive docs at `/docs`). The seed script creates:

- an admin user — `admin` / `ChangeMe123!` (**change this immediately**)
- default activities (PRD FR-010)
- a demo department, employee (`EMP001`), RFID card (`CARD-DEMO-001`)
- a demo gateway (`GW-01`), a gate reader and a project reader
- a demo project (`PRJ-001`)

## Try the RFID pipeline without hardware

```bash
pip install paho-mqtt
python scripts/simulate_rfid_event.py --reader READER-GATE-01 --card CARD-DEMO-001   # clock in
python scripts/simulate_rfid_event.py --reader READER-PRJ-001 --card CARD-DEMO-001   # start project work
python scripts/simulate_rfid_event.py --reader READER-GATE-01 --card CARD-DEMO-001   # clock out
```

Then check:

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=ChangeMe123!" | python -m json.tool

curl -s http://localhost:8000/dashboard/live -H "Authorization: Bearer <token>"
curl -s http://localhost:8000/attendance -H "Authorization: Bearer <token>"
curl -s http://localhost:8000/timelogs -H "Authorization: Bearer <token>"
```

Or ingest an event over plain HTTP instead of MQTT (useful for gateways that
can't reach the broker, or for testing):

```bash
curl -s -X POST http://localhost:8000/events/rfid -H "Content-Type: application/json" -d '{
  "event_id": "evt-001",
  "rfid_uid": "CARD-DEMO-001",
  "reader_id": "READER-GATE-01",
  "gateway_id": "GW-01",
  "timestamp": "2026-09-15T08:30:00Z"
}'
```

## How an RFID scan becomes attendance/time data

`app/services/event_processor.py` implements PRD FR-005 to FR-014:

1. Deduplicate on `event_uid` (idempotent — safe against MQTT at-least-once
   delivery and gateway retries) and on a configurable debounce window per
   employee+reader (`DEBOUNCE_SECONDS`).
2. Resolve the RFID UID to an employee via `RFIDCard`; unknown cards raise an
   `UNKNOWN_CARD` exception instead of silently dropping the scan.
3. Classify the event by the reader's type (`GATE`, `PROJECT`/`WORKSTATION`,
   `BREAK`) and current state:
   - **GATE** — first scan of the day = entry, subsequent scans keep updating
     `last_exit` and recompute gross/net/overtime minutes.
   - **PROJECT/WORKSTATION** — closes any current active session into a
     `TimeLog` row and opens a new one for the reader's mapped project/activity.
   - **BREAK** — toggles a break session; break time is excluded from net
     working hours.
4. Raw `rfid_events` rows are immutable; corrections only ever touch derived
   `TimeLog`/`Attendance` rows, and only through the `/corrections` approval
   workflow (FR-015).

## API surface

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/users` (admin) |
| Employees | `/departments`, `/employees` |
| Devices | `/locations`, `/gateways`, `/gateways/{id}/heartbeat`, `/readers`, `/rfid-cards`, `/rfid-cards/{id}/assign`, `/rfid-cards/{id}/deactivate` |
| Projects | `/projects`, `/projects/{id}/assignments`, `/activities` |
| Events | `POST /events/rfid` (HTTP fallback ingestion), `GET /events/rfid` |
| Tracking | `/attendance`, `/timelogs`, `/sessions/active`, `/exceptions`, `/exceptions/{id}/resolve`, `/corrections`, `/corrections/{id}/decide` |
| Dashboards | `/dashboard/live`, `/dashboard/employee/{id}`, `/dashboard/supervisor/{manager_id}`, `/dashboard/project/{id}`, `/dashboard/management` |

All endpoints except `/auth/login`, `/events/rfid` and `/health` require a
bearer token. Roles: `ADMIN`, `HR`, `SUPERVISOR`, `PROJECT_MANAGER`,
`FINANCE`, `MANAGEMENT`, `EMPLOYEE` — `ADMIN` can do everything.

## Power BI

Apply the curated reporting views (PRD section 17) once against the running
database, then point Power BI's PostgreSQL connector at those views only —
never at `rfid_events` or other operational tables:

```bash
docker compose exec -T postgres psql -U worktrack -d worktrack < sql/reporting_views.sql
```

## What's deliberately out of scope for this MVP

Matches PRD section 5 (Non-Goals) and section 23 (Post-MVP): payroll,
biometric verification, GPS tracking, ERP/HRMS integration, the real-time
workforce monitor UI, the mobile app, and AI-based analytics. Also not yet
included, called out here so they aren't mistaken for oversights:

- **Database migrations** — tables are created with `Base.metadata.create_all`
  on startup. Introduce Alembic before this schema needs to evolve under real
  data.
- **MQTT/TLS security** — `mosquitto.conf` allows anonymous plaintext
  connections for local development only; see the comment in that file for
  what production requires (PRD section 12).
- **Gateway-side offline buffering** (PRD section 13) — this repo is the
  central platform; the edge-gateway agent that buffers events during network
  outages and replays them is a separate, device-side project.
- **Scheduled exception detection** (missing exit, excessive hours, etc.) —
  currently only the exceptions raised inline during event processing
  (unknown card, unmapped reader) exist. A daily batch job for the rest of
  FR-014 is a natural next addition.
