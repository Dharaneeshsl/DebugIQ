# Release verification — November 18, 2026

Prepared a self-hosted Windows release without Docker. This revision adds direct
dashboard links, employee offboarding and password resets, and archive verification.

- The previous revision passed 22 backend tests, including production configuration, private AI defaults,
  restricted registration, account isolation, token revocation, and backup/restore.
- Frontend built successfully with the patched Vite 8 and React Router 7 toolchain.
- The audit of shipped frontend dependencies reported zero known vulnerabilities.
  The November 18 full audit flagged a build-only `picomatch` advisory
  ([GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)).
  npm reported no patched published version. Install from the prebuilt ZIP to
  deploy without running frontend build tools.
- pip-audit of the 64-package pinned backend snapshot reported no known vulnerabilities.
- The previous revision passed live production acceptance on loopback port 8001, including
  readiness, disabled public signup/docs, authentication, upload, dashboard,
  CSV report, cleanup, and logout revocation.
- For this revision, the pinned Python dependencies installed in a clean environment.
  Windows application control on the development machine blocked native scikit-learn
  modules during the full test run. The Windows GitHub Actions workflow runs the
  test suite and verifies the extracted archive before and after a database restore.

Production defaults keep external AI disabled and use a separate company database
with generated bootstrap credentials. Secrets and company databases are excluded
from the distributable archive. The release keeps only parsed failure excerpts
after processing new uploads. See PRODUCTION.md for installation and operations.

This is a tested release candidate for company evaluation, not evidence of an
approved company deployment. Remaining target-environment gates: HTTPS/DNS and
service supervision, engineer acceptance on proprietary simulator logs, agreed
load/capacity tests, off-host disaster recovery, and company security/privacy review.
No external AI, native MongoDB/RabbitMQ failover, SSO, or enterprise project-sharing
acceptance is claimed. The company and expected workload have not been specified.
