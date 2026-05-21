"""Toil Classifier - Identify and assess toil in operations work.

Toil is work that:
1. Is manual
2. Is repetitive
3. Is automatable
4. Is tactical (interrupt-driven, not strategic)
5. Has no enduring value
6. Scales with service growth (O(n) with load/size)

NOT toil:
- First-time problem solving (one-off debugging)
- Grungy work with long-term value (capacity planning)
- Overhead (meetings, HR, training)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal
import re


class ToilCriterion(Enum):
    """The six characteristics of toil."""
    MANUAL = "manual"
    REPETITIVE = "repetitive"
    AUTOMATABLE = "automatable"
    TACTICAL = "tactical"
    NO_ENDURING_VALUE = "no_enduring_value"
    SCALES_WITH_GROWTH = "scales_with_growth"


# Canonical list of toil criteria
TOIL_CRITERIA = [c.value for c in ToilCriterion]


@dataclass
class ToilAssessment:
    """Assessment of whether a task is toil and its automation potential."""
    task: str
    is_toil: bool
    score: float  # 0-1, higher = more toil-like
    criteria_matched: list[str]
    automation_potential: Literal["high", "medium", "low"]
    estimated_hours_per_month: float
    automation_roi: float  # hours saved / hours to automate
    reasoning: str = ""
    
    @property
    def priority_score(self) -> float:
        """Combined score for prioritizing automation efforts."""
        # Weight: ROI matters most, then hours, then toil score
        return (
            self.automation_roi * 0.5 +
            min(self.estimated_hours_per_month / 40, 1.0) * 0.3 +  # Cap at 40h
            self.score * 0.2
        )
    
    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "is_toil": self.is_toil,
            "score": self.score,
            "criteria_matched": self.criteria_matched,
            "automation_potential": self.automation_potential,
            "estimated_hours_per_month": self.estimated_hours_per_month,
            "automation_roi": self.automation_roi,
            "reasoning": self.reasoning,
            "priority_score": self.priority_score,
        }


@dataclass
class TaskInput:
    """Input for toil classification."""
    name: str
    description: str = ""
    frequency: str = "weekly"  # daily, weekly, monthly, ad-hoc
    duration_minutes: int = 30
    requires_human_judgment: bool = False
    requires_context_switching: bool = True
    has_runbook: bool = False
    involves_waiting: bool = False
    affects_multiple_services: bool = False
    triggered_by: str = "alert"  # alert, request, schedule, manual
    automation_hours_estimate: float = 8.0  # Hours to automate


class ToilClassifier:
    """Classifies operational tasks as toil or engineering work."""
    
    # Patterns that suggest toil
    TOIL_PATTERNS = [
        r"restart|reboot|bounce",
        r"clear|purge|clean(up)?",
        r"rotate|roll|cycle",
        r"acknowledge|ack|dismiss",
        r"manual(ly)?",
        r"copy|paste|transfer",
        r"check|verify|confirm",
        r"update config|change setting",
        r"add user|remove user|grant access",
        r"scale (up|down|out|in)",
        r"flip (flag|switch|toggle)",
    ]
    
    # Patterns that suggest NOT toil (engineering/strategic work)
    ENGINEERING_PATTERNS = [
        r"design|architect",
        r"investigate|analyze|debug",
        r"capacity plan",
        r"performance tun(e|ing)",
        r"security (audit|review)",
        r"post-?mortem|incident review",
        r"document(ation)?",
        r"training|onboard",
        r"code review",
        r"reliability (review|improvement)",
    ]
    
    # Frequency multipliers for monthly hour calculation
    FREQUENCY_MULTIPLIERS = {
        "hourly": 720,  # 24 * 30
        "daily": 30,
        "weekly": 4.3,
        "bi-weekly": 2.15,
        "monthly": 1,
        "quarterly": 0.33,
        "ad-hoc": 2,  # Assume ~2x per month for ad-hoc
    }
    
    def __init__(self):
        self.toil_patterns = [re.compile(p, re.IGNORECASE) for p in self.TOIL_PATTERNS]
        self.engineering_patterns = [re.compile(p, re.IGNORECASE) for p in self.ENGINEERING_PATTERNS]
    
    def is_toil(self, task: TaskInput) -> ToilAssessment:
        """Assess whether a task qualifies as toil."""
        criteria_matched = []
        reasoning_parts = []
        
        text = f"{task.name} {task.description}".lower()
        
        # Check each criterion
        scores = {}
        
        # 1. Manual
        manual_score = self._assess_manual(task, text)
        scores["manual"] = manual_score
        if manual_score > 0.5:
            criteria_matched.append("manual")
            reasoning_parts.append(f"Manual: requires direct human action (score: {manual_score:.2f})")
        
        # 2. Repetitive
        repetitive_score = self._assess_repetitive(task)
        scores["repetitive"] = repetitive_score
        if repetitive_score > 0.5:
            criteria_matched.append("repetitive")
            reasoning_parts.append(f"Repetitive: occurs {task.frequency} (score: {repetitive_score:.2f})")
        
        # 3. Automatable
        automatable_score = self._assess_automatable(task, text)
        scores["automatable"] = automatable_score
        if automatable_score > 0.5:
            criteria_matched.append("automatable")
            reasoning_parts.append(f"Automatable: can be scripted (score: {automatable_score:.2f})")
        
        # 4. Tactical
        tactical_score = self._assess_tactical(task)
        scores["tactical"] = tactical_score
        if tactical_score > 0.5:
            criteria_matched.append("tactical")
            reasoning_parts.append(f"Tactical: interrupt-driven work (score: {tactical_score:.2f})")
        
        # 5. No Enduring Value
        no_value_score = self._assess_no_enduring_value(task, text)
        scores["no_enduring_value"] = no_value_score
        if no_value_score > 0.5:
            criteria_matched.append("no_enduring_value")
            reasoning_parts.append(f"No enduring value: doesn't improve system (score: {no_value_score:.2f})")
        
        # 6. Scales with Growth
        scales_score = self._assess_scales_with_growth(task, text)
        scores["scales_with_growth"] = scales_score
        if scales_score > 0.5:
            criteria_matched.append("scales_with_growth")
            reasoning_parts.append(f"Scales with growth: O(n) with load/services (score: {scales_score:.2f})")
        
        # Calculate overall toil score
        # Weighted average - manual and repetitive are strongest indicators
        weights = {
            "manual": 0.25,
            "repetitive": 0.20,
            "automatable": 0.15,
            "tactical": 0.15,
            "no_enduring_value": 0.15,
            "scales_with_growth": 0.10,
        }
        
        toil_score = sum(scores[k] * weights[k] for k in scores)
        
        # Check for engineering patterns that override toil classification
        engineering_match = any(p.search(text) for p in self.engineering_patterns)
        if engineering_match and toil_score < 0.7:
            toil_score *= 0.5  # Reduce score for engineering-like work
            reasoning_parts.append("Engineering pattern detected - reduced toil score")
        
        # Is it toil? Need score > 0.5 AND at least 3 criteria
        is_toil = toil_score > 0.5 and len(criteria_matched) >= 3
        
        # Calculate hours per month
        frequency_mult = self.FREQUENCY_MULTIPLIERS.get(task.frequency, 1)
        hours_per_month = (task.duration_minutes / 60) * frequency_mult
        
        # Determine automation potential
        automation_potential = self._assess_automation_potential(task, automatable_score)
        
        # Calculate ROI
        if task.automation_hours_estimate > 0:
            # How many months until automation pays off?
            # ROI = hours saved per month / hours to automate
            automation_roi = hours_per_month / task.automation_hours_estimate
        else:
            automation_roi = 0.0
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No strong toil indicators found"
        
        return ToilAssessment(
            task=task.name,
            is_toil=is_toil,
            score=round(toil_score, 3),
            criteria_matched=criteria_matched,
            automation_potential=automation_potential,
            estimated_hours_per_month=round(hours_per_month, 2),
            automation_roi=round(automation_roi, 3),
            reasoning=reasoning,
        )
    
    def _assess_manual(self, task: TaskInput, text: str) -> float:
        """Assess how manual the task is."""
        score = 0.5  # Base score - assume some manual component
        
        # Direct manual indicators
        if "manual" in text:
            score += 0.3
        
        # Has runbook suggests documented manual process
        if task.has_runbook:
            score += 0.2
        
        # Human judgment reduces automation, but still manual
        if task.requires_human_judgment:
            score += 0.1
        
        # Pattern matching
        if any(p.search(text) for p in self.toil_patterns):
            score += 0.2
        
        return min(score, 1.0)
    
    def _assess_repetitive(self, task: TaskInput) -> float:
        """Assess how repetitive the task is."""
        # More frequent = more repetitive
        frequency_scores = {
            "hourly": 1.0,
            "daily": 0.9,
            "weekly": 0.7,
            "bi-weekly": 0.5,
            "monthly": 0.3,
            "quarterly": 0.1,
            "ad-hoc": 0.4,  # Ad-hoc can still be repetitive
        }
        return frequency_scores.get(task.frequency, 0.5)
    
    def _assess_automatable(self, task: TaskInput, text: str) -> float:
        """Assess if the task can be automated."""
        score = 0.6  # Most ops tasks are automatable
        
        # Human judgment is hard to automate
        if task.requires_human_judgment:
            score -= 0.4
        
        # Has runbook = well-defined steps = automatable
        if task.has_runbook:
            score += 0.2
        
        # Waiting can be automated away
        if task.involves_waiting:
            score += 0.1
        
        # Pattern-based tasks are automatable
        if any(p.search(text) for p in self.toil_patterns):
            score += 0.2
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_tactical(self, task: TaskInput) -> float:
        """Assess if the task is tactical/interrupt-driven."""
        score = 0.3  # Base
        
        # Alert-triggered = interrupt-driven
        if task.triggered_by == "alert":
            score += 0.4
        elif task.triggered_by == "request":
            score += 0.3
        elif task.triggered_by == "manual":
            score += 0.2
        # Scheduled work is less tactical
        elif task.triggered_by == "schedule":
            score -= 0.1
        
        # Context switching = tactical
        if task.requires_context_switching:
            score += 0.2
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_no_enduring_value(self, task: TaskInput, text: str) -> float:
        """Assess if the task provides no enduring value."""
        score = 0.5  # Base assumption
        
        # Engineering patterns add enduring value
        if any(p.search(text) for p in self.engineering_patterns):
            score -= 0.4
        
        # Toil patterns suggest no enduring value
        if any(p.search(text) for p in self.toil_patterns):
            score += 0.3
        
        # Affects multiple services might have broader impact
        if task.affects_multiple_services:
            score -= 0.1
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_scales_with_growth(self, task: TaskInput, text: str) -> float:
        """Assess if the task scales with service/load growth."""
        score = 0.4  # Base
        
        # Keywords suggesting scaling issues
        scaling_keywords = ["per service", "per user", "each", "every", "all"]
        if any(kw in text for kw in scaling_keywords):
            score += 0.3
        
        # Multi-service suggests O(n)
        if task.affects_multiple_services:
            score += 0.2
        
        # Scaling operations
        if re.search(r"scale|add|provision|deploy", text):
            score += 0.2
        
        return min(score, 1.0)
    
    def _assess_automation_potential(
        self, 
        task: TaskInput, 
        automatable_score: float
    ) -> Literal["high", "medium", "low"]:
        """Determine automation potential category."""
        # Adjust for human judgment requirement
        effective_score = automatable_score
        if task.requires_human_judgment:
            effective_score *= 0.6
        
        if effective_score >= 0.7:
            return "high"
        elif effective_score >= 0.4:
            return "medium"
        else:
            return "low"
    
    def classify_batch(self, tasks: list[TaskInput]) -> list[ToilAssessment]:
        """Classify multiple tasks and return sorted by priority."""
        assessments = [self.is_toil(task) for task in tasks]
        # Sort by priority score (highest first)
        return sorted(assessments, key=lambda a: a.priority_score, reverse=True)


# Convenience function
def is_toil(task: TaskInput) -> ToilAssessment:
    """Quick function to assess if a task is toil."""
    classifier = ToilClassifier()
    return classifier.is_toil(task)
