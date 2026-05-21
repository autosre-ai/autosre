# AutoSRE Enhancement Plan Based on SRE Learnings

**Generated:** 2025-06-07
**Source:** 51 SRE learnings from Google SRE Book, Marcel Koert's AI reliability insights, and industry best practices

---

## Executive Summary

This plan incorporates 51 production-validated SRE learnings into AutoSRE to create a truly production-grade AI SRE platform. The enhancements fall into 7 major categories:

1. **AI Safety & Reliability** - Prevent AI from causing incidents
2. **Investigation Quality** - Evidence-first, not hypothesis-first
3. **On-Call Integration** - Respectful of human cognitive limits
4. **SLO-Driven Operations** - Error budgets guide actions
5. **Cascading Failure Prevention** - Safe degradation patterns
6. **Post-Incident Learning** - Systematic improvement loop
7. **Toil Elimination** - Measurable automation ROI

---

## Category 1: AI Safety & Reliability (Marcel Koert Learnings)

### 1.1 Hypothesis-First Output Format

**Learning:** AI recommendations during incidents should be treated as HYPOTHESIS, not instructions.

**Current State:** AutoSRE outputs findings as statements of fact.

**Enhancement:**
```python
# src/autosre/agents/output.py
@dataclass
class AIHypothesis:
    """Every AI finding is a hypothesis until verified."""
    summary: str
    evidence: list[Evidence]
    confidence: float  # 0.0 to 1.0
    counter_checks: list[str]  # Required verifications before action
    blast_radius: str  # "low" | "medium" | "high" | "critical"
    requires_human_approval: bool  # True for high-risk actions

class Evidence:
    source: str  # "prometheus" | "logs" | "kubernetes" | etc.
    query: str
    raw_data: str
    interpretation: str
    timestamp: datetime
```

**Implementation Tasks:**
- [ ] Add `AIHypothesis` dataclass to all agent outputs
- [ ] Require `counter_checks` field for every hypothesis
- [ ] Add confidence scoring based on evidence quality
- [ ] Auto-flag high blast radius actions for human approval

### 1.2 AI Telemetry & Observability

**Learning:** Build telemetry for AI itself - what context it used, confidence level, whether recommendations were accepted/correct.

**Enhancement:**
```python
# src/autosre/telemetry/ai_metrics.py
class AIMetrics:
    """Track AI operational behavior."""
    
    def record_investigation(
        self,
        investigation_id: str,
        context_documents: list[str],  # Which runbooks/docs were used
        confidence_reported: float,
        recommendation: str,
        accepted_by_human: bool | None,
        outcome_correct: bool | None,  # Filled in post-incident
        time_to_resolution: timedelta | None,
    ):
        """Record every AI recommendation for learning."""
        ...
    
    def get_accuracy_rate(self, window_days: int = 30) -> float:
        """What % of recommendations were correct?"""
        ...
    
    def get_false_positive_rate(self, severity: str) -> float:
        """How often do we cry wolf?"""
        ...
```

**Implementation Tasks:**
- [ ] Create AI telemetry module
- [ ] Add Prometheus metrics: `autosre_ai_accuracy_rate`, `autosre_ai_recommendation_total`
- [ ] Track per-skill accuracy rates
- [ ] Dashboard for AI operational health

### 1.3 AI Error Budgets

**Learning:** AI systems need reliability targets - accuracy rates, safe-action rates, human-override rates.

**Enhancement:**
```yaml
# config/ai_error_budgets.yaml
ai_reliability:
  targets:
    # AI must be right at least 80% of the time on high-severity
    high_severity_accuracy: 0.80
    # AI should recommend safe actions 99% of the time
    safe_action_rate: 0.99
    # Humans should override AI less than 20% of the time
    # (high override rate = AI not trustworthy)
    human_override_threshold: 0.20
    # Bad recommendations should be < 5% of total
    bad_recommendation_rate: 0.05
  
  actions:
    # If accuracy drops below target, switch to "conservative mode"
    on_accuracy_breach: "conservative_mode"
    # If bad_recommendation_rate breached, disable auto-actions
    on_safety_breach: "disable_auto_remediation"
```

**Implementation Tasks:**
- [ ] Implement AI error budget tracking
- [ ] Add circuit breaker for AI actions when budget exhausted
- [ ] Conservative mode: require human approval for all actions
- [ ] Dashboard widget showing AI error budget burn rate

### 1.4 AI Game Days

**Learning:** Test AI operational behavior BEFORE outages. Feed messy incidents, stale docs.

**Enhancement:**
```python
# src/autosre/evals/game_day.py
class AIGameDay:
    """Inject chaos to test AI behavior."""
    
    scenarios = [
        "stale_runbook",      # Outdated documentation
        "ambiguous_symptoms", # Multiple possible causes
        "contradictory_logs", # Logs say one thing, metrics another
        "cascading_failure",  # Multiple systems failing
        "false_positive",     # Alert but no real problem
        "novel_failure",      # Never-seen-before issue
    ]
    
    def run_scenario(self, scenario: str) -> GameDayResult:
        """
        Run AI against adversarial scenario.
        
        Checks:
        - Does AI ask for evidence or sprint to wrong fix?
        - Does AI cite confidence levels?
        - Does AI recommend safe actions?
        - Does AI escalate when uncertain?
        """
        ...
```

**Implementation Tasks:**
- [ ] Create game day scenario framework
- [ ] Build 10+ adversarial test cases
- [ ] Add to CI/CD as optional "AI reliability" gate
- [ ] Generate game day reports with improvement suggestions

---

## Category 2: Investigation Quality (Google SRE Learnings)

### 2.1 Stop Bleeding First

**Learning:** STOP THE BLEEDING FIRST. Divert traffic, drop load, disable subsystems. Triage first, then investigate.

**Enhancement:**
```python
# src/autosre/agents/planner.py
class InvestigationPhases(Enum):
    """Mandatory investigation phases."""
    TRIAGE = "triage"        # Is service impaired? How bad?
    MITIGATE = "mitigate"    # Stop the bleeding
    INVESTIGATE = "investigate"  # Find root cause
    REMEDIATE = "remediate"  # Fix the issue
    VERIFY = "verify"        # Confirm fix worked
    DOCUMENT = "document"    # Postmortem

TRIAGE_FIRST_PROMPT = """
STOP. Before investigating root cause, answer these questions:
1. Is the service currently impaired? (Y/N)
2. What is the impact? (users affected, revenue impact)
3. Can we mitigate RIGHT NOW? (rollback, scale up, rate limit)

Only after mitigation should you investigate root cause.
"""
```

**Implementation Tasks:**
- [ ] Add mandatory triage phase to investigation flow
- [ ] Prompt agents to suggest mitigation before investigation
- [ ] Track time-to-mitigation vs time-to-root-cause separately
- [ ] Block "investigate" phase until "mitigate" considered

### 2.2 Four Golden Signals

**Learning:** Always measure: Latency, Traffic, Errors, Saturation. These 4 cover most monitoring needs.

**Enhancement:**
```python
# src/autosre/skills/metrics/golden_signals.py
GOLDEN_SIGNALS_QUERIES = {
    "latency": {
        "prometheus": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))",
        "datadog": "avg:trace.http.request.duration{*} by {service}.as_count()",
        "description": "Request latency p99",
    },
    "traffic": {
        "prometheus": "sum(rate(http_requests_total[5m])) by (service)",
        "datadog": "sum:trace.http.request.hits{*} by {service}.as_rate()",
        "description": "Requests per second",
    },
    "errors": {
        "prometheus": "sum(rate(http_requests_total{status=~'5..'}[5m])) / sum(rate(http_requests_total[5m]))",
        "datadog": "sum:trace.http.request.errors{*} by {service} / sum:trace.http.request.hits{*} by {service}",
        "description": "Error rate",
    },
    "saturation": {
        "prometheus": "avg(container_memory_usage_bytes / container_spec_memory_limit_bytes) by (pod)",
        "datadog": "avg:kubernetes.memory.usage{*} by {pod_name}",
        "description": "Resource saturation",
    },
}

class GoldenSignalsChecker:
    """Always check golden signals first."""
    
    async def check_all(self, service: str) -> dict[str, SignalStatus]:
        """Check all four golden signals for a service."""
        ...
```

**Implementation Tasks:**
- [ ] Create golden signals skill
- [ ] Add to investigation kickoff (always check these first)
- [ ] Generate "signal dashboard" in investigation report
- [ ] Alert if any golden signal missing for a service

### 2.3 Percentiles Over Averages

**Learning:** Use percentiles (p50, p95, p99, p999) not averages. Averages hide long-tail latency.

**Enhancement:**
```python
# src/autosre/skills/metrics/analysis.py
class LatencyAnalyzer:
    """Analyze latency with proper percentiles."""
    
    REQUIRED_PERCENTILES = ["p50", "p90", "p95", "p99", "p999"]
    
    def analyze(self, service: str, window: str = "5m") -> LatencyReport:
        """
        Get full latency distribution, not just average.
        
        Returns:
            LatencyReport with all percentiles and histogram
        """
        # NEVER use avg(latency) - always use histogram_quantile
        queries = {
            f"p{p}": f"histogram_quantile(0.{p}, rate(http_request_duration_seconds_bucket{{service='{service}'}}[{window}]))"
            for p in [50, 90, 95, 99]
        }
        queries["p999"] = f"histogram_quantile(0.999, ...)"
        ...
```

**Implementation Tasks:**
- [ ] Remove all `avg()` from latency queries
- [ ] Always report p50, p95, p99, p999
- [ ] Flag services missing histogram metrics
- [ ] Add histogram visualization to reports

### 2.4 Correlate with Recent Changes

**Learning:** Systems have inertia - working systems stay working until external force. Start by correlating with recent changes.

**Enhancement:**
```python
# src/autosre/agents/subagents/changes.py
class ChangesSubagent(BaseSubagent):
    """Correlate issues with recent changes."""
    
    agent_id = "changes"
    
    CHANGE_SOURCES = [
        "kubernetes_deployments",  # Recent deploys
        "config_changes",          # ConfigMaps, secrets
        "infrastructure_changes",  # Terraform, Pulumi
        "feature_flags",           # LaunchDarkly, Split
        "dependency_updates",      # Renovate, Dependabot
        "traffic_patterns",        # Traffic shifts
    ]
    
    async def investigate(self, alert, hypotheses, service_context, llm_client):
        """
        First question: What changed recently?
        
        Check all change sources within blast radius of affected service.
        """
        ...
```

**Implementation Tasks:**
- [ ] Create changes subagent
- [ ] Integrate with GitHub deployments API
- [ ] Integrate with ArgoCD/Flux deployment events
- [ ] Add change correlation to investigation prompt

---

## Category 3: On-Call Integration (Google SRE Ch. 11)

### 3.1 Alert Quality Gates

**Learning:** Never trigger alert just because something seems weird. Pages must be: clear failure, actionable, user-visible impact.

**Enhancement:**
```python
# src/autosre/alerts/quality.py
class AlertQualityChecker:
    """Validate alerts before paging."""
    
    REQUIRED_FIELDS = [
        "failure_mode",      # What is broken
        "user_impact",       # How users are affected
        "action_required",   # What on-call should do
        "severity",          # P1-P5
        "runbook_url",       # Link to response procedures
    ]
    
    def validate(self, alert: Alert) -> AlertQualityResult:
        """
        Check if alert is worth paging for.
        
        Reject alerts that are:
        - "Something seems weird" (not actionable)
        - Missing runbook (no guidance)
        - No user impact (why wake someone?)
        """
        score = 0
        issues = []
        
        for field in self.REQUIRED_FIELDS:
            if not getattr(alert, field, None):
                issues.append(f"Missing: {field}")
            else:
                score += 1
        
        return AlertQualityResult(
            quality_score=score / len(self.REQUIRED_FIELDS),
            issues=issues,
            should_page=score >= 4,  # At least 4/5 required
        )
```

**Implementation Tasks:**
- [ ] Add alert quality validation
- [ ] Reject alerts missing required fields
- [ ] Track alert quality metrics
- [ ] Generate alert quality reports

### 3.2 On-Call Load Limits

**Learning:** Target max 2 incidents per 12-hour shift. Each incident needs ~6 hours (triage, RCA, remediation, postmortem).

**Enhancement:**
```python
# src/autosre/oncall/load.py
class OnCallLoadTracker:
    """Track on-call load to prevent burnout."""
    
    MAX_INCIDENTS_PER_SHIFT = 2
    SHIFT_HOURS = 12
    
    def check_load(self, oncall_user: str) -> LoadStatus:
        """Check if on-call is overloaded."""
        incidents_this_shift = self._count_incidents(oncall_user, hours=self.SHIFT_HOURS)
        
        if incidents_this_shift >= self.MAX_INCIDENTS_PER_SHIFT:
            return LoadStatus(
                overloaded=True,
                message=f"On-call has handled {incidents_this_shift} incidents this shift. Consider escalating or getting backup.",
                recommendation="route_to_backup_or_escalate",
            )
        
        return LoadStatus(overloaded=False)
```

**Implementation Tasks:**
- [ ] Track incidents per on-call shift
- [ ] Alert when on-call approaching overload
- [ ] Suggest escalation when overloaded
- [ ] Include in weekly on-call reports

### 3.3 Deliberate Reasoning Under Stress

**Learning:** Avoid intuitive rapid action under stress. Stress hormones impair cognition. Use deliberate, data-driven thinking.

**Enhancement:**
```python
# Add to investigation prompts
DELIBERATE_REASONING_PROMPT = """
PAUSE. Take a breath. Before acting, complete this checklist:

1. [ ] What EVIDENCE supports this hypothesis? (not intuition)
2. [ ] What would DISPROVE this hypothesis?
3. [ ] What are we ASSUMING that might be wrong?
4. [ ] Is there a SAFER action we could try first?
5. [ ] Who else should we CONSULT before acting?

Only after completing this checklist should you proceed with changes.
"""
```

**Implementation Tasks:**
- [ ] Add deliberate reasoning prompts
- [ ] Require evidence citation for all recommendations
- [ ] Add "pause and verify" step before destructive actions
- [ ] Track time spent on deliberation vs action

---

## Category 4: SLO-Driven Operations (Google SRE Ch. 3, 4)

### 4.1 Error Budget Tracking

**Learning:** Allow an error budget - a rate at which SLOs can be missed. 100% targets reduce innovation.

**Enhancement:**
```python
# src/autosre/slo/error_budget.py
class ErrorBudgetTracker:
    """Track error budget consumption."""
    
    def get_budget_status(self, service: str) -> BudgetStatus:
        """
        Calculate remaining error budget.
        
        Example: 99.9% SLO = 0.1% error budget = ~43 min/month downtime
        """
        slo = self._get_slo(service)  # e.g., 0.999
        error_budget = 1 - slo        # e.g., 0.001 (0.1%)
        
        # Calculate actual error rate this period
        actual_errors = self._get_error_rate(service)
        
        budget_remaining = error_budget - actual_errors
        budget_percentage = budget_remaining / error_budget * 100
        
        return BudgetStatus(
            slo=slo,
            error_budget=error_budget,
            consumed=actual_errors,
            remaining=budget_remaining,
            percentage_remaining=budget_percentage,
            can_deploy=budget_percentage > 20,  # Safe to deploy if >20% budget
        )
```

**Implementation Tasks:**
- [ ] Implement error budget calculator
- [ ] Add to investigation context (show budget impact)
- [ ] Block risky deploys when budget exhausted
- [ ] Dashboard showing budget burn rate

### 4.2 Request Success Rate Metric

**Learning:** Use request success rate instead of time-based uptime. For global services, you are always partially up.

**Enhancement:**
```python
# src/autosre/slo/availability.py
class AvailabilityCalculator:
    """Calculate availability as request success rate."""
    
    def calculate(self, service: str, window: str = "30d") -> float:
        """
        Availability = successful_requests / total_requests
        
        NOT uptime (which is meaningless for distributed systems).
        """
        query = f"""
        sum(rate(http_requests_total{{service="{service}", status=~"2.."}}[{window}]))
        /
        sum(rate(http_requests_total{{service="{service}"}}[{window}]))
        """
        return self._query_prometheus(query)
```

**Implementation Tasks:**
- [ ] Use request success rate for SLIs
- [ ] Remove uptime-based availability metrics
- [ ] Add per-endpoint availability tracking
- [ ] Include in investigation context

---

## Category 5: Cascading Failure Prevention (Google SRE Ch. 21, 22)

### 5.1 Client-Side Throttling

**Learning:** Implement client-side adaptive throttling. When requests > 2x accepts, client self-rejects locally.

**Enhancement:**
```python
# Add to skill documentation
THROTTLING_SKILL = """
## Client-Side Adaptive Throttling

When investigating cascading failures, check for client-side throttling:

**Healthy Pattern:**
- Client tracks request/accept ratio
- When ratio > 2.0, client rejects locally
- Prevents backend from wasting resources on rejects

**Queries:**
```promql
# Client rejection rate
sum(rate(client_requests_rejected_total[5m])) by (service)

# Server-side rejection rate (should be low if client throttling works)
sum(rate(server_requests_rejected_total[5m])) by (service)
```

**Red Flags:**
- High server-side rejection + low client rejection = missing client throttling
- Server CPU spent just rejecting requests = wasted capacity
"""
```

### 5.2 LIFO Queue During Overload

**Learning:** Switch to LIFO or CoDel algorithm during overload. Old queued requests are likely abandoned.

**Enhancement:**
```python
# Add to cascading failure investigation
QUEUE_INVESTIGATION = """
## Queue Behavior Under Load

**Check queue configuration:**
- Is FIFO or LIFO used?
- Is CoDel (Controlled Delay) enabled?
- What's the queue depth?

**Why LIFO matters:**
- During overload, old requests are likely abandoned (user refreshed)
- Processing 10-second-old request wastes capacity
- LIFO processes newest requests first

**Queries:**
```promql
# Queue wait time
histogram_quantile(0.99, rate(request_queue_wait_seconds_bucket[5m]))

# If p99 queue wait > 5s, old requests probably abandoned
```
"""
```

### 5.3 Recovery Requires Dropping to Low Load

**Learning:** During cascading failure, dropping to normal load won't recover. If 10% of servers healthy, drop to 10% of normal load.

**Enhancement:**
```python
# src/autosre/skills/cascading_failure.py
class CascadingFailureAnalyzer:
    """Analyze and recover from cascading failures."""
    
    def calculate_recovery_load(self, service: str) -> RecoveryPlan:
        """
        Calculate load level needed for recovery.
        
        Key insight: Can't recover at normal load when capacity is degraded.
        """
        current_capacity = self._get_healthy_capacity(service)
        normal_load = self._get_normal_load(service)
        
        # Recovery load = current_capacity * safety_factor
        recovery_load = current_capacity * 0.8
        
        return RecoveryPlan(
            current_capacity_percent=current_capacity * 100,
            normal_load=normal_load,
            recovery_load=recovery_load,
            actions=[
                f"Reduce load to {recovery_load:.0%} of normal",
                "Wait for healthy instances to stabilize",
                "Gradually increase load (10% increments)",
                "Monitor for GC pressure and CPU saturation",
            ],
        )
```

**Implementation Tasks:**
- [ ] Add cascading failure analyzer
- [ ] Calculate recovery load requirements
- [ ] Generate recovery runbook
- [ ] Track recovery time metrics

---

## Category 6: Post-Incident Learning (Google SRE Ch. 15)

### 6.1 Blameless Postmortem Structure

**Learning:** Blameless postmortems focus on SYSTEMS not people. Assume everyone had good intentions.

**Enhancement:**
```python
# src/autosre/postmortem/template.py
POSTMORTEM_TEMPLATE = """
# Incident Postmortem: {title}

## Summary
- **Date:** {date}
- **Duration:** {duration}
- **Impact:** {impact}
- **Severity:** {severity}

## Timeline
{timeline}

## Root Cause
{root_cause}

## What SYSTEMS Failed (Not People)
- [ ] Monitoring gaps
- [ ] Runbook gaps
- [ ] Automation gaps
- [ ] Communication gaps
- [ ] Process gaps

## AI Performance Review
- Did AI accelerate or delay resolution?
- Did AI retrieve outdated documentation?
- Did humans over-trust AI recommendations?
- Did AI create anchoring bias?

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
{action_items}

## Lessons Learned
{lessons}
"""
```

**Implementation Tasks:**
- [ ] Create postmortem template
- [ ] Auto-generate postmortem draft from investigation
- [ ] Include AI performance review section
- [ ] Track action item completion

### 6.2 Postmortem Triggers

**Learning:** Define postmortem triggers BEFORE incidents. Any stakeholder can request one.

**Enhancement:**
```yaml
# config/postmortem_policy.yaml
postmortem:
  triggers:
    - condition: "user_visible_degradation"
      threshold: "> 1% of users affected"
    - condition: "data_loss"
      threshold: "any"
    - condition: "on_call_intervention"
      threshold: "required manual intervention"
    - condition: "resolution_time"
      threshold: "> 30 minutes"
    - condition: "monitoring_failure"
      threshold: "alert did not fire or was wrong"
    - condition: "stakeholder_request"
      threshold: "any stakeholder can request"
```

**Implementation Tasks:**
- [ ] Implement postmortem trigger detection
- [ ] Auto-create postmortem ticket when triggered
- [ ] Track postmortem completion rate
- [ ] Generate weekly postmortem summary

---

## Category 7: Toil Elimination (Google SRE Ch. 5, 7)

### 7.1 Toil Classification

**Learning:** Toil is specifically: manual, repetitive, automatable, tactical, no enduring value, scales O(n).

**Enhancement:**
```python
# src/autosre/toil/classifier.py
class ToilClassifier:
    """Classify operational work as toil or not."""
    
    TOIL_CRITERIA = [
        "manual",         # Requires human touch
        "repetitive",     # Done regularly
        "automatable",    # Could be scripted
        "tactical",       # Reactive, not strategic
        "no_enduring_value",  # No lasting improvement
        "scales_with_growth",  # More service = more work
    ]
    
    def is_toil(self, task: str) -> ToilAssessment:
        """
        Assess if a task is toil.
        
        Not toil:
        - First-time problem solving
        - Grungy work with long-term value
        - Strategic planning
        """
        ...
```

### 7.2 Toil Budget

**Learning:** Cap toil at 50% of SRE time. At least 50% must be engineering work.

**Enhancement:**
```python
# src/autosre/toil/budget.py
class ToilBudget:
    """Track toil vs engineering time."""
    
    TOIL_CAP = 0.50  # Max 50% toil
    
    def get_team_toil_ratio(self, team: str, period: str = "30d") -> float:
        """
        Calculate toil ratio for a team.
        
        If > 50%, need to step back and fix systemic issues.
        """
        ...
    
    def get_toil_reduction_opportunities(self, team: str) -> list[ToilOpportunity]:
        """
        Identify high-ROI automation opportunities.
        """
        ...
```

**Implementation Tasks:**
- [ ] Track time spent on toil vs engineering
- [ ] Generate toil reduction recommendations
- [ ] Alert when toil exceeds 50%
- [ ] Dashboard showing toil trends

---

## Implementation Roadmap

### Phase 1: AI Safety (Week 1-2)
- [ ] Implement AIHypothesis output format
- [ ] Add AI telemetry
- [ ] Create AI error budget tracking
- [ ] Build 5 game day scenarios

### Phase 2: Investigation Quality (Week 3-4)
- [ ] Add triage-first phase
- [ ] Implement golden signals checker
- [ ] Create changes subagent
- [ ] Add percentile-based metrics

### Phase 3: SLO & Cascading Failure (Week 5-6)
- [ ] Error budget calculator
- [ ] Request success rate availability
- [ ] Cascading failure analyzer
- [ ] Recovery load calculator

### Phase 4: On-Call & Postmortem (Week 7-8)
- [ ] Alert quality validation
- [ ] On-call load tracking
- [ ] Postmortem automation
- [ ] Toil tracking

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| AI recommendation accuracy | Unknown | >80% |
| Time to mitigation | Unknown | <15 min |
| Postmortem completion rate | Unknown | >90% |
| Toil ratio | Unknown | <50% |
| On-call incidents per shift | Unknown | <2 |
| Alert quality score | Unknown | >80% |

---

## Dependencies

- PostgreSQL for metrics storage
- Prometheus for metrics queries
- PagerDuty/OpsGenie for on-call integration
- GitHub/GitLab for change tracking
- Slack for notifications

---

*This plan incorporates 51 production-validated SRE learnings to make AutoSRE truly production-grade.*
