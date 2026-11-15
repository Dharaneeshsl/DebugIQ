# Company installation and release operations

This release targets one self-hosted internal installation for a chip verification
team. It does not claim enterprise certification or a validated capacity for an
unknown company workload. No Docker is needed.

## Install and start

1. Use the tested Windows runtime: Python 3.14 and Node.js 24. Revalidate other platforms.
2. Create `.venv` and install `backend/requirements-release.txt` into it.
3. In `frontend`, run `npm ci` and `npm run build`. Do not set a frontend API URL;
   the release uses `/api` on the same origin.
4. Run `.venv/Scripts/python.exe backend/provision_production.py` once.
5. Restrict `backend/.env.production` to the service account and operators. Read
   the generated initial username/password privately. Never commit this file.
6. Run `powershell -ExecutionPolicy Bypass -File scripts/start_production.ps1`.

The launcher binds only to loopback on port 8000. The same server serves the built
dashboard and the API. Use the company's managed HTTPS reverse proxy for employee
access. TLS termination, host DNS, certificate renewal, network restrictions, and
service supervision are deployment requirements; they are not provisioned by this
repository. Keep one API worker with the default in-memory rate limiter.

Production mode rejects weak bootstrap credentials and a short signing secret,
disables public signup and API schema pages, adds security headers and request
identifiers, and logs request status and timing without bodies or credentials.
It rejects the existing default demo admin. The generated company configuration
uses a separate database so local demo records and accounts are not migrated.

Create employee accounts from a restricted operator terminal:

```powershell
.venv/Scripts/python.exe backend/manage_users.py --env backend/.env.production --username engineer-name
```

The password is entered twice without echo. This initial release does not include
SSO, a password-reset email service, project sharing, or enterprise account lifecycle
management. Companies requiring these must treat them as additional scope.

## Privacy

External AI calls are disabled by default even if provider keys are present.
Only an operator setting `DEBUGIQ_ALLOW_EXTERNAL_AI=true` enables the provider
code. Keep it false unless the company explicitly approves disclosure of log
excerpts to that provider. Rule-based guidance continues to work privately.
Set file permissions and volume encryption for databases and backups. Logs can
contain proprietary chip designs and testbench details.

## Monitoring and queues

Monitor `/health` for process liveness and `/ready` for database availability.
Production request logs contain request IDs, HTTP methods, status, and duration;
collect them with the company's log agent. Metrics are not exposed publicly in
production. Configure alerts for readiness failures, repeated server errors, full
disks, backup failure, and stalled processing.

SQLite supports the single-machine profile. The document adapter scans records,
so this is not a validated high-volume configuration. For shared deployments,
configure native MongoDB and test it against the target workload. For durable
background ingestion, configure native RabbitMQ and run `backend/worker.py` with
the same production environment. Synchronous ingestion works without a broker.
Local in-process jobs are marked failed after interruption and require re-upload.
RabbitMQ delivery confirmation is enabled for API publication; worker crash and
broker-failover behavior still require environment-specific acceptance testing.

## Backup and restore

Create an online SQLite backup, using a new destination name each time:

```powershell
.venv/Scripts/python.exe backend/backup_store.py backend/data/company.sqlite3 backups/company-YYYYMMDD.sqlite3
```

The utility uses SQLite's online backup API and checks database integrity. Keep
encrypted copies off the host and store the production environment file separately
under equivalent access controls. A database backup does not contain the signing
secret or server configuration.

To restore, stop the API and worker, copy the backup to a NEW database path using
the same utility, change `DEBUGIQ_SQLITE_PATH` in the environment file to that path,
and restart. This avoids overwriting the current database. Run the acceptance
check below and verify record counts before releasing access. Set backup frequency,
retention, and recovery targets with the company. Use native MongoDB backup tools
when MongoDB is selected; this utility is only for SQLite.

## Release gate

Run the backend test suite, frontend production build, and dependency audits.
Then run this against a dedicated test installation configured for production:

```powershell
.venv/Scripts/python.exe backend/release_check.py --env backend/.env.production --url http://127.0.0.1:8000
```

The check creates and deletes its own test run. Before a company go-live, require:

- HTTPS and restricted access verified from an employee device.
- Representative simulator logs checked by verification engineers, including
  duplicate matching, severity extraction, rankings, and assertion context.
- Agreed concurrency, throughput, log size, latency and storage targets exercised.
- Backup restored on a separate host, with company recovery targets met.
- Company security/privacy review and an assigned operations/support owner.

The repository checks establish behavior in the tested environment. They do not
replace company acceptance, a penetration test, or a capacity commitment.
