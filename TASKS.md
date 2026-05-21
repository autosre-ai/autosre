# AutoSRE Build Plan

## Pre-Build Checklist
- [x] SPEC.md created
- [ ] Clone OpenSRE as starting point
- [ ] Project structure setup
- [ ] Core implementation

---

## Phase 1: Foundation (Task 1-5)

### Task 1: Clone and Setup OpenSRE Base [S]
**Verify:** `uv sync` works, `opensre --help` runs
- Clone Tracer-Cloud/opensre
- Set up uv/pyproject.toml
- Verify base installation works

### Task 2: Rename and Restructure [M]
**Verify:** `autosre --help` shows our branding
- Rename package from `opensre` to `autosre`
- Update all imports
- Update CLI entry point
- Update pyproject.toml metadata

### Task 3: Memory System - Episodic [M]
**Verify:** Investigation saved and retrievable
- Create `autosre/memory/episodic.py`
- SQLite schema for past investigations
- save_investigation(), search_investigations()
- Context loading before new investigations

### Task 4: Skill System Framework [M]
**Verify:** Custom skill loads and executes
- Create `autosre/skills/` structure
- YAML + script skill format (like Hermes)
- Skill loader and registry
- Built-in skills for K8s, AWS, DB

### Task 5: Self-Improvement Hook [M]
**Verify:** After investigation, skill extraction suggested
- Create `autosre/agents/learner.py`
- After successful RCA, analyze for patterns
- Suggest new skills to user
- Store learnings in memory

---

## Phase 2: Integrations (Task 6-8)

### Task 6: Verify Core Integrations [M]
**Verify:** Datadog, Grafana, K8s tools work
- Test Datadog integration
- Test Grafana/Loki integration
- Test Kubernetes integration
- Fix any issues from OpenSRE base

### Task 7: LLM Provider Setup [S]
**Verify:** Works with Copilot, Claude, OpenAI
- Configure multi-provider support
- Default to Copilot (free for you)
- Fallback chain
- Model selection per task

### Task 8: Delivery Channels [M]
**Verify:** Investigation sent to Telegram
- Verify Slack integration
- Add Telegram delivery
- Format output nicely
- Add webhook receiver for PagerDuty

---

## Phase 3: Polish (Task 9-12)

### Task 9: CLI UX [S]
**Verify:** Great onboarding experience
- `autosre onboard` wizard
- `autosre investigate` with progress
- `autosre skills list/add`
- `autosre memory search`

### Task 10: Docker Compose [S]
**Verify:** `docker compose up` works
- Dockerfile optimized
- docker-compose.yml
- Environment variable handling
- Volume mounts for data

### Task 11: Documentation [M]
**Verify:** New user can set up in 5 min
- README.md with quickstart
- CONTRIBUTING.md
- docs/architecture.md
- docs/skills.md

### Task 12: GitHub Repo Setup [S]
**Verify:** Repo looks professional
- GitHub Actions CI
- Issue templates
- PR template
- LICENSE
- SECURITY.md
- Social preview image

---

## Estimates
- S = < 30 min
- M = 30 min - 2 hours
- L = 2+ hours

Total: ~8-10 hours

---

## Dependencies Graph

```
Task 1 ─────┬───► Task 2 ───► Task 3 ───► Task 5
            │
            ├───► Task 6 ───► Task 8
            │
            └───► Task 7
            
Task 2 ───► Task 4

Task 3,4,5,6,7,8 ───► Task 9

Task 9 ───► Task 10 ───► Task 11 ───► Task 12
```

---

## Parallel Work Opportunities

**Batch 1 (Foundation):**
- Task 1: Clone and setup

**Batch 2 (Core):**
- Task 2: Rename (depends on 1)
- Task 6: Test integrations (depends on 1)
- Task 7: LLM providers (depends on 1)

**Batch 3 (Features):**
- Task 3: Memory system (depends on 2)
- Task 4: Skills system (depends on 2)
- Task 8: Delivery (depends on 6)

**Batch 4 (Enhancement):**
- Task 5: Self-improvement (depends on 3,4)

**Batch 5 (Polish):**
- Task 9: CLI UX (depends on 3,4,5,6,7,8)
- Task 10: Docker (depends on 9)
- Task 11: Docs (depends on 10)
- Task 12: GitHub (depends on 11)
