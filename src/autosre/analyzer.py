"""
SRE Agent - LLM Analyzer

Uses local Ollama LLM to analyze incident context and generate insights.
"""
import json
from datetime import datetime

import ollama

from .models import (
    HealthStatus,
    IncidentContext,
    RecommendedAction,
    RootCauseSignal,
    SituationReport,
)

ANALYSIS_PROMPT = """You are an expert Site Reliability Engineer analyzing an incident.
Based on the following context, provide a structured analysis.

## Alert
- Service: {service}
- Title: {title}
- Severity: {severity}
- Started: {started_at}

## Metrics (Prometheus)
- Error Rate: {error_rate_current}% (baseline: {error_rate_baseline}%)
- Request Rate: {request_rate_current} req/s (baseline: {request_rate_baseline} req/s)
- P99 Latency: {latency_p99_current}ms (baseline: {latency_p99_baseline}ms)
- Error Breakdown: {error_breakdown}

## Recent Deployments
{deployments}

## Error Logs
{error_patterns}

Top error messages:
{error_samples}

## Infrastructure (Kubernetes/OpenShift)
- Pods: {pod_count} running, {pod_restarts} total restarts
- Resource Pressure: {resource_pressure}
- Pod Status: {pod_status}

## Dependencies
{dependencies}

## Traffic Analysis
- Malicious Traffic: {is_malicious}
- DDoS Detected: {is_ddos}
- Akamai Status: {akamai_status}

---

Analyze this incident and provide:

1. LIKELY ROOT CAUSE: What is most likely causing this incident? Consider:
   - Recent deployments and their changes
   - Dependency health (especially degraded services)
   - Infrastructure issues
   - Traffic anomalies

2. ROOT CAUSE SIGNALS: List each signal that points to a potential cause, with confidence level (0-100).

3. RECOMMENDED ACTIONS: List specific actions in priority order, including:
   - Immediate mitigation steps
   - Investigation commands
   - Rollback procedures if relevant

4. IMPACT ASSESSMENT: Estimate customer impact.

Respond in this exact JSON format:
{{
    "likely_root_cause": "Brief description of most likely cause",
    "confidence": "HIGH|MEDIUM|LOW",
    "reasoning": "Explanation of your analysis",
    "signals": [
        {{
            "source": "deployment|infrastructure|dependency|traffic|logs",
            "description": "What this signal indicates",
            "confidence": 85,
            "evidence": ["evidence point 1", "evidence point 2"],
            "is_likely_cause": true
        }}
    ],
    "actions": [
        {{
            "priority": 1,
            "action": "Specific action to take",
            "command": "optional shell command"
        }}
    ],
    "impact": {{
        "summary": "Impact summary",
        "affected_customers_estimate": 500
    }}
}}
"""


class LLMAnalyzer:
    """Analyzes incident context using local LLM"""

    def __init__(self, config: dict):
        self.config = config
        self.llm_config = config.get("llm", {})
        self.model = self.llm_config.get("model", "llama3.3:latest")

    def analyze(self, context: IncidentContext) -> SituationReport:
        """Analyze context and generate situation report"""

        # Build prompt with context
        prompt = self._build_prompt(context)

        # Call LLM
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": self.llm_config.get("temperature", 0.1),
                    "num_predict": 2000,
                }
            )

            # Parse response
            analysis = self._parse_response(response["response"])

        except Exception as e:
            # Fallback to rule-based analysis
            analysis = self._rule_based_analysis(context)
            analysis["reasoning"] = f"LLM analysis failed ({str(e)}), using rule-based fallback"

        # Build situation report
        return self._build_report(context, analysis)

    def _build_prompt(self, context: IncidentContext) -> str:
        """Build analysis prompt from context"""

        # Format deployments
        deployments = "None in last 24h"
        if context.github and context.github.recent_deployments:
            deps = []
            for dep in context.github.recent_deployments:
                deps.append(f"- {dep.hours_ago:.1f}h ago: {dep.message} by @{dep.author} (commit {dep.short_sha})")
                if dep.files_changed:
                    deps.append(f"  Files: {', '.join(dep.files_changed[:5])}")
            deployments = "\n".join(deps)

        # Format error patterns
        error_patterns = "No patterns detected"
        if context.logs and context.logs.error_patterns:
            patterns = []
            for p in context.logs.error_patterns:
                patterns.append(f"- {p.pattern}: {p.count} occurrences ({p.percentage:.1f}%)")
            error_patterns = "\n".join(patterns)

        # Format error samples
        error_samples = "No recent errors"
        if context.logs and context.logs.error_samples:
            samples = []
            for e in context.logs.error_samples[:3]:
                samples.append(f"- [{e.level}] {e.message} (count: {e.count})")
            error_samples = "\n".join(samples)

        # Format dependencies
        dependencies = "No dependency data"
        if context.dependencies:
            deps = []
            for dep in context.dependencies:
                status_emoji = "✅" if dep.status == HealthStatus.HEALTHY else "⚠️" if dep.status == HealthStatus.DEGRADED else "❌"
                deps.append(f"- {status_emoji} {dep.name}: {dep.status.value} (p99: {dep.latency_p99}ms, errors: {dep.error_rate}%)")
            dependencies = "\n".join(deps)

        # Format pod status
        pod_status = "Unknown"
        pod_count = 0
        pod_restarts = 0
        if context.kubernetes:
            pod_count = len(context.kubernetes.pods)
            pod_restarts = sum(p.restarts for p in context.kubernetes.pods)
            statuses = [f"{p.name}: {p.status}" for p in context.kubernetes.pods[:3]]
            pod_status = ", ".join(statuses) if statuses else "Unknown"

        return ANALYSIS_PROMPT.format(
            service=context.alert.service,
            title=context.alert.title,
            severity=context.alert.severity.value,
            started_at=context.alert.started_at.isoformat(),
            error_rate_current=context.prometheus.error_rate.current if context.prometheus else "N/A",
            error_rate_baseline=context.prometheus.error_rate.baseline if context.prometheus else "N/A",
            request_rate_current=context.prometheus.request_rate.current if context.prometheus else "N/A",
            request_rate_baseline=context.prometheus.request_rate.baseline if context.prometheus else "N/A",
            latency_p99_current=context.prometheus.latency_p99.current if context.prometheus else "N/A",
            latency_p99_baseline=context.prometheus.latency_p99.baseline if context.prometheus else "N/A",
            error_breakdown=json.dumps(context.prometheus.error_breakdown) if context.prometheus else "{}",
            deployments=deployments,
            error_patterns=error_patterns,
            error_samples=error_samples,
            pod_count=pod_count,
            pod_restarts=pod_restarts,
            resource_pressure=context.kubernetes.resource_pressure if context.kubernetes else "Unknown",
            pod_status=pod_status,
            dependencies=dependencies,
            is_malicious=context.traffic.is_malicious if context.traffic else "Unknown",
            is_ddos=context.traffic.is_ddos if context.traffic else "Unknown",
            akamai_status=context.traffic.akamai_status if context.traffic else "Unknown"
        )

    def _parse_response(self, response_text: str) -> dict:
        """Parse LLM JSON response"""
        # Find JSON in response
        try:
            # Try to extract JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback
        return {
            "likely_root_cause": "Unable to parse LLM response",
            "confidence": "LOW",
            "reasoning": response_text[:500],
            "signals": [],
            "actions": [],
            "impact": {"summary": "Unknown", "affected_customers_estimate": None}
        }

    def _rule_based_analysis(self, context: IncidentContext) -> dict:
        """Fallback rule-based analysis when LLM fails"""
        signals = []
        actions = []
        likely_cause = None
        confidence = "LOW"

        # Check for recent deployment correlation
        if context.github and context.github.recent_deployments:
            recent = context.github.recent_deployments[0]
            if recent.hours_ago < 4:  # Deployment in last 4 hours
                signals.append({
                    "source": "deployment",
                    "description": f"Recent deployment {recent.hours_ago:.1f}h ago: {recent.message}",
                    "confidence": 75,
                    "evidence": [f"Commit {recent.short_sha} by {recent.author}", f"Files: {', '.join(recent.files_changed[:3])}"],
                    "is_likely_cause": True
                })
                likely_cause = f"Recent deployment ({recent.short_sha}): {recent.message}"
                confidence = "MEDIUM"
                actions.append({
                    "priority": 1,
                    "action": f"Consider rollback of commit {recent.short_sha}",
                    "command": f"git revert {recent.sha}"
                })

        # Check for dependency issues
        if context.dependencies:
            degraded = [d for d in context.dependencies if d.status != HealthStatus.HEALTHY]
            for dep in degraded:
                is_likely = dep.error_rate > 10  # High error rate
                signals.append({
                    "source": "dependency",
                    "description": f"Dependency {dep.name} is {dep.status.value}",
                    "confidence": 90 if is_likely else 60,
                    "evidence": [f"Error rate: {dep.error_rate}%", f"P99 latency: {dep.latency_p99}ms"],
                    "is_likely_cause": is_likely
                })
                if is_likely and not likely_cause:
                    likely_cause = f"Dependency failure: {dep.name} ({dep.status.value})"
                    confidence = "HIGH"

        # Check for traffic anomalies
        if context.traffic:
            if context.traffic.is_malicious or context.traffic.is_ddos:
                signals.append({
                    "source": "traffic",
                    "description": "Malicious or DDoS traffic detected",
                    "confidence": 85,
                    "evidence": [f"Akamai status: {context.traffic.akamai_status}"],
                    "is_likely_cause": True
                })
                if not likely_cause:
                    likely_cause = "Malicious traffic / DDoS attack"
                    confidence = "HIGH"

        # Default action
        if not actions:
            actions.append({
                "priority": 1,
                "action": "Check application logs for more details",
                "command": None
            })

        return {
            "likely_root_cause": likely_cause or "Unable to determine - more investigation needed",
            "confidence": confidence,
            "reasoning": "Rule-based analysis based on available signals",
            "signals": signals,
            "actions": actions,
            "impact": {
                "summary": f"Service {context.alert.service} experiencing elevated error rates",
                "affected_customers_estimate": None
            }
        }

    def _build_report(self, context: IncidentContext, analysis: dict) -> SituationReport:
        """Build final situation report"""

        # Calculate duration
        now = datetime.utcnow()
        started = context.alert.started_at
        # Handle timezone-aware datetimes
        if started.tzinfo is not None:
            started = started.replace(tzinfo=None)
        duration = (now - started).total_seconds() / 60

        # Build signals
        signals = []
        for s in analysis.get("signals", []):
            signals.append(RootCauseSignal(
                source=s.get("source", "unknown"),
                description=s.get("description", ""),
                confidence=s.get("confidence", 0) / 100,
                evidence=s.get("evidence", []),
                is_likely_cause=s.get("is_likely_cause", False)
            ))

        # Build actions
        actions = []
        for a in analysis.get("actions", []):
            actions.append(RecommendedAction(
                priority=a.get("priority", 99),
                action=a.get("action", ""),
                command=a.get("command")
            ))

        # Build impact summary
        impact_data = analysis.get("impact", {})
        impact_summary = impact_data.get("summary", f"Service {context.alert.service} degraded")
        affected = impact_data.get("affected_customers_estimate")

        return SituationReport(
            alert=context.alert,
            summary=analysis.get("likely_root_cause", "Unknown"),
            impact=impact_summary,
            duration_minutes=duration,
            affected_customers_estimate=affected,
            root_cause_signals=signals,
            likely_root_cause=analysis.get("likely_root_cause"),
            confidence=analysis.get("confidence", "LOW"),
            recommended_actions=sorted(actions, key=lambda x: x.priority),
            runbooks=[],  # TODO: Add runbook matching
            raw_context=context,
            analysis_reasoning=analysis.get("reasoning"),
            generated_at=datetime.utcnow()
        )
