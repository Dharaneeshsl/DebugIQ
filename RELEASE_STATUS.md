# Release verification — November 16, 2026

Prepared and tested a self-hosted Windows release without Docker.

- 22 backend tests passed, including production configuration, private AI defaults,
  restricted registration, account isolation, token revocation, and backup/restore.
- Frontend built successfully with the patched Vite 8 and React Router 7 toolchain.
- npm dependency audit reported zero known vulnerabilities after fixes.
- pip-audit of the 64-package pinned backend snapshot reported no known vulnerabilities.
- Live production-mode acceptance passed on loopback port 8001: built UI,
  readiness, disabled public signup/docs, authentication, upload, dashboard,
  CSV report, cleanup, and logout revocation.
- The built production sign-in page rendered in the browser.

Production defaults keep external AI disabled and use a separate company database
with generated bootstrap credentials. Secrets and company databases are excluded
from the distributable archive. See PRODUCTION.md for installation and operations.

This is a tested release candidate for company evaluation, not evidence of an
approved company deployment. Remaining target-environment gates: HTTPS/DNS and
service supervision, engineer acceptance on proprietary simulator logs, agreed
load/capacity tests, off-host disaster recovery, and company security/privacy review.
No external AI, native MongoDB/RabbitMQ failover, SSO, or enterprise project-sharing
acceptance is claimed. The company and expected workload have not been specified.
