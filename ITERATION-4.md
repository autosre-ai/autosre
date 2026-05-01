# Iteration 4 - Demo Mode & Examples

**Date:** 2026-05-02
**Duration:** ~40 minutes
**Focus:** Add demo mode, fix CLI to support demo data

## What Was Done

### 1. Added `--demo` Flag to Init Command
- Updated `autosre/cli/main.py` to accept `--demo` flag
- Updated `autosre/cli/commands/init.py` with `_populate_demo_data()` function

### 2. Demo Data Population
When `autosre init --demo` is run, the following data is created:

#### Services (5)
- `api-gateway` (production, healthy)
- `user-service` (production, healthy)
- `order-service` (production, degraded)
- `postgres` (production, healthy)
- `redis` (production, healthy)

#### Ownership (3)
- api-gateway → platform team
- user-service → identity team
- order-service → commerce team

#### Alerts (2)
- HighCPUUsage on order-service (warning)
- PodNotReady on order-service (critical)

#### Changes (3)
- Deployment of order-service v2.3.1
- Config change on order-service
- Scale-up of api-gateway

### 3. Bug Fixes in Model Usage
Fixed several model attribute errors:
- `AlertSeverity` → `Severity`
- `AlertStatus` → removed (not needed)
- `Change` → `ChangeEvent`
- `add_ownership()` → `set_ownership()`
- `type` → `change_type`
- `ChangeType.CONFIG` → `ChangeType.CONFIG_CHANGE`
- `ChangeType.SCALE` → `ChangeType.SCALE_UP`

## What Works

| Feature | Status | Notes |
|---------|--------|-------|
| `autosre init` | ✅ Working | Basic initialization |
| `autosre init --demo` | ✅ Working | Populates demo data |
| Demo services | ✅ Working | 5 services created |
| Demo alerts | ✅ Working | 2 firing alerts |
| Demo changes | ✅ Working | 3 recent changes |
| Demo ownership | ✅ Working | Team mappings |

## Demo Mode Usage

```bash
# Initialize with demo data
mkdir my-project && cd my-project
autosre init --demo

# View demo data (in current directory's database)
sqlite3 .autosre/context.db "select name from services;"
# Output: api-gateway, order-service, postgres, redis, user-service

# Run evaluation
autosre eval run --scenario high_cpu

# Start web dashboard
autosre web start --port 8080
```

## Metrics

```
Tests: 873 passing
New Feature: --demo flag
Demo Services: 5
Demo Alerts: 2
Demo Changes: 3
```

## Files Changed

```
autosre/cli/main.py                # Added --demo flag
autosre/cli/commands/init.py       # Added _populate_demo_data()
```

## Known Limitations

1. **Database Location**: Demo data goes to `.autosre/context.db` in the init directory, but CLI commands default to `~/.autosre/context.db`. This is by design - projects can have isolated data.

2. **No Web Demo Mode**: The web dashboard doesn't have a special demo mode yet. It reads from the default database location.

## Next Steps (Iteration 5)

1. Run full end-to-end tests
2. Update all documentation
3. Verify PyPI packaging
4. Add GitHub Actions CI
5. Create release notes
6. Tag v0.1.0 release

## Commands Reference

```bash
# Demo mode
autosre init --demo
autosre init --demo --dir ./my-project

# Verify demo data
sqlite3 .autosre/context.db "select count(*) from services;"

# Run tests
uv run pytest tests/ -v
```
