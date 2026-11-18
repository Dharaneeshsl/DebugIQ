# Release verification — November 18, 2026

DebugIQ's supported Windows installation is ready for self-hosted delivery
without Docker. The ZIP includes the built dashboard, backend, pinned dependencies,
operator tools, installation guide, and a file checksum manifest.

- GitHub Actions installed the pinned Python 3.14 dependencies on a clean
  Windows runner. All 24 backend tests passed, including account lifecycle
  and session revocation, private AI defaults, and background log cleanup.
- The frontend built from its lockfile. The shipped npm dependency audit and
  the pinned Python dependency audit found no known vulnerabilities.
- The Windows runner verified the archive, started the extracted production
  app, and passed live acceptance before and after a database restore. The
  checks included dashboard assets, saved run links, login, upload, CSV,
  disabled public registration, and logout.
- The handoff archive excludes credentials, local databases, and installed dependencies.

See the [Windows acceptance run](https://github.com/Dharaneeshsl/DebugIQ/actions/runs/44329536373)
and [PRODUCTION.md](PRODUCTION.md) for the installation and operations guide.

The full frontend audit flagged a build-tool dependency advisory in `picomatch`.
No patched version was published when checked. Deploy from the prebuilt ZIP to
avoid using the frontend build tools on the production host.
[Build-tool advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)

The target company still needs to verify HTTPS and network access, acceptance on
its simulator logs, performance at its workload, and recovery against its own
retention and recovery targets. The tested profile is a single Windows host with
SQLite and external AI disabled. The live acceptance run did not exercise native
MongoDB, RabbitMQ failover, or external AI services.
