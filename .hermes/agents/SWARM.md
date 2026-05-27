# AutoSRE Agent Factory - Build Swarm

## Active Mission
Build AutoSRE continuously for 36 hours. Fix all issues, improve quality, ship features.

## Agents

### 1. TestAgent (QA)
**Role:** Run tests, flag issues, track regressions
**Cadence:** Every hour
**Output:** Test report with failures, new issues

### 2. DevAgent (Builder)  
**Role:** Fix issues flagged by TestAgent, implement improvements
**Cadence:** Triggered by TestAgent issues
**Output:** Commits with fixes

### 3. UserAgent (End-User QA)
**Role:** Test from end-user perspective, try CLI commands, report UX issues
**Cadence:** Every 2 hours
**Output:** UX report, feature requests

## Coordination
- TestAgent runs first, produces issue list
- DevAgent picks up issues, fixes them
- UserAgent validates fixes from user perspective
- Hourly consolidated report to Sainath

## Current State
- 1090 tests passing
- 1 test failing: test_run_mock (--mock flag removed)
- 103 tests skipped

## Known Issues Queue
1. test_run_mock - needs fix (--mock removed but test not updated)
