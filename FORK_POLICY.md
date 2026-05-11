# Fork Policy & Maintenance Guidelines

## Overview

**ThermoFlow Print** is a **community fork** of [Dejniel's TiMini-Print](https://github.com/Dejniel/TiMini-Print) with production-ready enhancements. The fork maintains 100% compatibility with the original while adding targeted improvements for containerized deployments.

---

## Core Philosophy

### What This Fork Is
✅ **Production enhancement** of the original  
✅ **Docker-first** architecture with clear release/dev channels  
✅ **Backward compatible** — all original functionality preserved  
✅ **Additive only** — new features don't break existing code  

### What This Fork Is NOT
❌ **Not a reimplementation** — we leverage the excellent original code  
❌ **Not a replacement** — Dejniel's repo remains the authoritative source  
❌ **Not abandoning upstream** — we track improvements and integrate them  

---

## Integration Strategy

### Monitoring Upstream Changes

We periodically check [Dejniel's repository](https://github.com/Dejniel/TiMini-Print) for:
- Bug fixes in core printer protocol handling
- New printer models added to the device catalog
- Security updates in dependencies
- Architecture improvements

### When to Integrate Upstream

**Process:**
1. Review Dejniel's commits for breaking changes or improvements
2. Test compatibility in our development environment (port 8901)
3. If compatible and useful: merge and test thoroughly
4. If conflicts exist: analyze, adapt, and create fork-specific tests

**Example scenarios:**
- ✅ New printer model added → Easy to merge (data-only change)
- ✅ Bug fix in protocol.py → Review and merge if compatible
- ❌ Major API refactor → Evaluate impact, may skip if incompatible with our architecture

### When NOT to Integrate

- Changes that conflict with our release/dev channel architecture
- Changes that interfere with consolidated debug system
- Breaking changes to CLI/API that would affect our deployments
- Changes unmaintained or untested by upstream

---

## Fork-Specific Modifications

### Files We Own (Never Sync Blindly)

These are customized for the fork and should be reviewed carefully before any upstream integration:

| File | Reason | Action |
|------|--------|--------|
| `docker-compose.yml` | Dev channel config (port 8901, dev-latest) | Manual merge only |
| `docker-compose.release.yml` | Release config (port 8001, v1.0.0) | Manual merge only |
| `Dockerfile` | Production multi-stage build | Manual merge only |
| `.github/workflows/docker-publish.yml` | Channel-aware tagging system | Manual merge only |
| `timiniprint/app/web.py` | Debug consolidation (setupDebugMode) | Selective merge |
| `timiniprint/app/web_static/app.js` | Debug system hooks | Selective merge |
| `README.md` | Fork documentation | Keep as-is |
| `RELEASE_CHECKLIST.md` | Our release procedure | Keep as-is |
| `FORK_POLICY.md` | This file | Keep as-is |

### Files We Don't Own (Safe to Sync)

These are directly from the original and can be updated more freely:

- `timiniprint/` (core logic) — except files listed above
- `tests/` — all test files
- `docs/` — all documentation (except fork-specific notes)
- `requirements.txt` — dependency list
- `data/` — printer profiles, detection rules

---

## Release Policy

### Development Releases

**Trigger:** Push to master branch  
**Image:** `ghcr.io/cfridgen/timiniwebprint:dev-latest`, `dev-{commit-sha}`  
**Port:** 8901  
**Deployment:** Direct to Portainer  
**Stability:** Latest code, experimental, frequent updates  

### Production Releases

**Trigger:** Annotated git tag (e.g., `v1.0.0`)  
**Image:** `ghcr.io/cfridgen/timiniwebprint:v1.0.0`, `release-latest`  
**Port:** 8001  
**Deployment:** Manual via docker-compose.release.yml  
**Stability:** Pinned, immutable, carefully tested  
**Cadence:** Deliberate, infrequent  

### Release Procedure

See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for step-by-step instructions.

**Key Rules:**
- Releases ONLY via GitHub (git tag workflow)
- Dev goes directly to Portainer (fast iteration)
- Release image is pinned in docker-compose.release.yml (no drift)
- Each release is immutable (no tag reuse)

---

## Communication

### Issues & Bug Reports

**For original TiMini-Print bugs:**
→ Report to [Dejniel's issues](https://github.com/Dejniel/TiMini-Print/issues)

**For fork-specific issues (Docker, channels, debug):**
→ Report here with `[Fork]` prefix

**Example:**
```
[Fork] Debug mode not disabling on production builds
[Fork] Port 8901 conflicting with Portainer
```

### Pull Requests

**For original TiMini-Print enhancements:**
→ Submit to [Dejniel's repository](https://github.com/Dejniel/TiMini-Print)

**For fork-specific improvements:**
→ Submit here

---

## Maintenance Checklist

**Monthly:**
- ☐ Check Dejniel's repo for new releases
- ☐ Review new printer models added upstream
- ☐ Scan dependencies for security updates

**Quarterly:**
- ☐ Test dev channel (port 8901) with latest changes
- ☐ Review any upstream breaking changes
- ☐ Update documentation if needed

**On Release:**
- ☐ Follow RELEASE_CHECKLIST.md
- ☐ Verify both channels working (8001 & 8901)
- ☐ Test printer detection on Linux
- ☐ Validate debug mode is off by default

---

## Attribution

**Original Project Creator:** [Dejniel](https://github.com/Dejniel)  
**Original Repository:** [Dejniel/TiMini-Print](https://github.com/Dejniel/TiMini-Print)  
**This Fork:** Production-enhanced version with Docker/K8s support  
**Support Original:** [Buy Me a Coffee](https://buymeacoffee.com/dejniel)

---

## License

This fork maintains the original project's license. See [LICENSE](LICENSE) for details.
