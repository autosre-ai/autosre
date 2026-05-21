"""Automation Maturity Model - Assess and improve automation levels.

Maturity Levels:
1. Manual Operations - No automation, all human intervention
2. Personal Scripts - Individual automation, not shared
3. Generic Shared Scripts - Team-wide automation tools
4. System Ships with Automation - Built-in automation from day 1
5. Self-Healing Systems - Autonomous operation, minimal human touch

Goal: Level 5 - "If a human needs to touch during normal ops, you have a bug"
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional
from datetime import datetime


class MaturityLevel(IntEnum):
    """Automation maturity levels (1-5)."""
    MANUAL_OPS = 1
    PERSONAL_SCRIPTS = 2
    GENERIC_SHARED = 3
    SHIPS_WITH_AUTOMATION = 4
    SELF_HEALING = 5


MATURITY_DESCRIPTIONS = {
    MaturityLevel.MANUAL_OPS: {
        "name": "Manual Operations",
        "description": "Operations are performed manually by humans following runbooks or tribal knowledge.",
        "characteristics": [
            "Runbooks are the primary operational tool",
            "Human operators perform all remediation",
            "High toil, high error rate",
            "Knowledge siloed in individuals",
            "Incident response is reactive",
        ],
        "risks": [
            "Single points of failure (people)",
            "Inconsistent execution",
            "Doesn't scale with growth",
            "Operator burnout",
        ],
    },
    MaturityLevel.PERSONAL_SCRIPTS: {
        "name": "Personal Scripts",
        "description": "Individual engineers create scripts to automate their own work.",
        "characteristics": [
            "Ad-hoc scripts on engineer laptops",
            "Automation is person-specific",
            "Limited sharing or documentation",
            "Scripts may break without maintenance",
            "Duplication of effort across team",
        ],
        "risks": [
            "Scripts lost when engineers leave",
            "No standardization",
            "Security concerns (credentials in scripts)",
            "Inconsistent error handling",
        ],
    },
    MaturityLevel.GENERIC_SHARED: {
        "name": "Generic Shared Scripts",
        "description": "Team maintains shared automation tools and libraries.",
        "characteristics": [
            "Centralized script repository",
            "Documented automation tools",
            "Code review for automation",
            "Some integration with monitoring",
            "Standardized patterns",
        ],
        "risks": [
            "Automation may lag behind system changes",
            "Still requires human trigger",
            "May not cover edge cases",
            "Maintenance burden",
        ],
    },
    MaturityLevel.SHIPS_WITH_AUTOMATION: {
        "name": "System Ships with Automation",
        "description": "New systems include automation as part of initial design and delivery.",
        "characteristics": [
            "Automation is part of Definition of Done",
            "Operators involved in system design",
            "Comprehensive runbook automation",
            "Integration with incident management",
            "Metrics-driven automation triggers",
        ],
        "risks": [
            "Automation complexity",
            "May over-automate edge cases",
            "Testing automation is challenging",
            "Requires cultural shift",
        ],
    },
    MaturityLevel.SELF_HEALING: {
        "name": "Self-Healing Systems",
        "description": "Systems detect and remediate issues autonomously with minimal human intervention.",
        "characteristics": [
            "Automatic detection and remediation",
            "Human intervention only for novel issues",
            "Continuous improvement from incidents",
            "Chaos engineering validated resilience",
            "Operator role shifts to system improvement",
        ],
        "risks": [
            "Over-confidence in automation",
            "Cascading automated failures",
            "Skill atrophy in operators",
            "Complex debugging when automation fails",
        ],
    },
}


@dataclass
class MaturityIndicators:
    """Indicators used to assess maturity level."""
    # Level 1 indicators
    has_runbooks: bool = False
    runbooks_are_primary_tool: bool = True
    
    # Level 2 indicators
    has_personal_scripts: bool = False
    scripts_are_shared: bool = False
    
    # Level 3 indicators
    has_shared_repo: bool = False
    has_documentation: bool = False
    has_code_review: bool = False
    has_monitoring_integration: bool = False
    
    # Level 4 indicators
    automation_in_design: bool = False
    operators_in_design: bool = False
    automation_in_dod: bool = False  # Definition of Done
    
    # Level 5 indicators
    auto_detection: bool = False
    auto_remediation: bool = False
    chaos_engineering: bool = False
    human_for_novel_only: bool = False
    
    # Metrics
    manual_intervention_rate: float = 1.0  # 0-1, lower is better
    mttr_minutes: float = 60.0
    automation_coverage: float = 0.0  # 0-1, higher is better
    incident_recurrence_rate: float = 0.5  # 0-1, lower is better


@dataclass
class MaturityAssessment:
    """Assessment of automation maturity for a service/team."""
    subject: str  # Service or team name
    subject_type: str  # "service" or "team"
    current_level: MaturityLevel
    target_level: MaturityLevel
    score: float  # 1.0-5.0, continuous score
    indicators: MaturityIndicators
    gaps: list[str]
    recommendations: list[str]
    assessed_at: datetime = field(default_factory=datetime.now)
    
    @property
    def level_name(self) -> str:
        return MATURITY_DESCRIPTIONS[self.current_level]["name"]
    
    @property
    def target_level_name(self) -> str:
        return MATURITY_DESCRIPTIONS[self.target_level]["name"]
    
    @property
    def levels_to_target(self) -> int:
        return self.target_level - self.current_level
    
    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "subject_type": self.subject_type,
            "current_level": self.current_level.value,
            "current_level_name": self.level_name,
            "target_level": self.target_level.value,
            "target_level_name": self.target_level_name,
            "score": round(self.score, 2),
            "gaps": self.gaps,
            "recommendations": self.recommendations,
            "assessed_at": self.assessed_at.isoformat(),
        }


class AutomationMaturityModel:
    """Assess and improve automation maturity for services and teams."""
    
    def __init__(self, default_target: MaturityLevel = MaturityLevel.SHIPS_WITH_AUTOMATION):
        self.default_target = default_target
        self.assessments: dict[str, MaturityAssessment] = {}
    
    def assess(
        self,
        subject: str,
        subject_type: str = "service",
        indicators: Optional[MaturityIndicators] = None,
        target_level: Optional[MaturityLevel] = None,
    ) -> MaturityAssessment:
        """Assess automation maturity for a service or team."""
        indicators = indicators or MaturityIndicators()
        target = target_level or self.default_target
        
        # Calculate level based on indicators
        level, score = self._calculate_level(indicators)
        
        # Identify gaps
        gaps = self._identify_gaps(level, target, indicators)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(level, target, indicators)
        
        assessment = MaturityAssessment(
            subject=subject,
            subject_type=subject_type,
            current_level=level,
            target_level=target,
            score=score,
            indicators=indicators,
            gaps=gaps,
            recommendations=recommendations,
        )
        
        self.assessments[subject] = assessment
        return assessment
    
    def _calculate_level(self, ind: MaturityIndicators) -> tuple[MaturityLevel, float]:
        """Calculate maturity level from indicators."""
        score = 1.0  # Start at level 1
        
        # Level 2 criteria
        if ind.has_personal_scripts:
            score += 0.5
        if not ind.runbooks_are_primary_tool:
            score += 0.3
        if ind.automation_coverage > 0.1:
            score += 0.2
        
        # Level 3 criteria
        if ind.scripts_are_shared:
            score += 0.3
        if ind.has_shared_repo:
            score += 0.3
        if ind.has_documentation:
            score += 0.2
        if ind.has_code_review:
            score += 0.2
        if ind.has_monitoring_integration:
            score += 0.3
        if ind.automation_coverage > 0.3:
            score += 0.2
        
        # Level 4 criteria
        if ind.automation_in_design:
            score += 0.4
        if ind.operators_in_design:
            score += 0.3
        if ind.automation_in_dod:
            score += 0.3
        if ind.automation_coverage > 0.6:
            score += 0.2
        if ind.manual_intervention_rate < 0.5:
            score += 0.2
        
        # Level 5 criteria
        if ind.auto_detection:
            score += 0.3
        if ind.auto_remediation:
            score += 0.4
        if ind.chaos_engineering:
            score += 0.2
        if ind.human_for_novel_only:
            score += 0.3
        if ind.manual_intervention_rate < 0.1:
            score += 0.2
        if ind.incident_recurrence_rate < 0.1:
            score += 0.2
        
        # Clamp score
        score = min(5.0, max(1.0, score))
        
        # Determine level from score
        if score >= 4.5:
            level = MaturityLevel.SELF_HEALING
        elif score >= 3.5:
            level = MaturityLevel.SHIPS_WITH_AUTOMATION
        elif score >= 2.5:
            level = MaturityLevel.GENERIC_SHARED
        elif score >= 1.5:
            level = MaturityLevel.PERSONAL_SCRIPTS
        else:
            level = MaturityLevel.MANUAL_OPS
        
        return level, score
    
    def _identify_gaps(
        self,
        current: MaturityLevel,
        target: MaturityLevel,
        ind: MaturityIndicators,
    ) -> list[str]:
        """Identify gaps between current and target level."""
        gaps = []
        
        if current >= target:
            return ["None - at or above target level"]
        
        # Gaps to reach each level
        if current < MaturityLevel.PERSONAL_SCRIPTS and target >= MaturityLevel.PERSONAL_SCRIPTS:
            if not ind.has_personal_scripts:
                gaps.append("No automation scripts exist")
        
        if current < MaturityLevel.GENERIC_SHARED and target >= MaturityLevel.GENERIC_SHARED:
            if not ind.scripts_are_shared:
                gaps.append("Scripts are not shared across team")
            if not ind.has_shared_repo:
                gaps.append("No centralized automation repository")
            if not ind.has_documentation:
                gaps.append("Automation lacks documentation")
            if not ind.has_code_review:
                gaps.append("No code review for automation")
        
        if current < MaturityLevel.SHIPS_WITH_AUTOMATION and target >= MaturityLevel.SHIPS_WITH_AUTOMATION:
            if not ind.automation_in_design:
                gaps.append("Automation not considered in system design")
            if not ind.operators_in_design:
                gaps.append("Operations not involved in design phase")
            if not ind.automation_in_dod:
                gaps.append("Automation not part of Definition of Done")
            if ind.automation_coverage < 0.6:
                gaps.append(f"Low automation coverage ({ind.automation_coverage:.0%})")
        
        if current < MaturityLevel.SELF_HEALING and target >= MaturityLevel.SELF_HEALING:
            if not ind.auto_detection:
                gaps.append("No automatic issue detection")
            if not ind.auto_remediation:
                gaps.append("No automatic remediation")
            if not ind.chaos_engineering:
                gaps.append("No chaos engineering practices")
            if ind.manual_intervention_rate > 0.1:
                gaps.append(f"High manual intervention rate ({ind.manual_intervention_rate:.0%})")
        
        return gaps
    
    def _generate_recommendations(
        self,
        current: MaturityLevel,
        target: MaturityLevel,
        ind: MaturityIndicators,
    ) -> list[str]:
        """Generate recommendations to improve maturity."""
        recommendations = []
        
        if current >= target:
            recommendations.append("Maintain current practices and monitor for regression")
            return recommendations
        
        # Recommendations for next level
        next_level = MaturityLevel(current.value + 1)
        
        if next_level == MaturityLevel.PERSONAL_SCRIPTS:
            recommendations.extend([
                "Start automating repetitive tasks with simple scripts",
                "Document common operational procedures",
                "Identify highest-toil tasks for initial automation",
            ])
        
        elif next_level == MaturityLevel.GENERIC_SHARED:
            recommendations.extend([
                "Create a shared repository for automation tools",
                "Establish code review process for automation",
                "Document all automation with usage examples",
                "Integrate scripts with monitoring/alerting",
                "Standardize on common tools and patterns",
            ])
        
        elif next_level == MaturityLevel.SHIPS_WITH_AUTOMATION:
            recommendations.extend([
                "Include automation requirements in system design",
                "Add 'operability' to Definition of Done",
                "Involve SRE/Ops in architecture reviews",
                "Build automation hooks into new systems",
                "Create automation templates for common patterns",
            ])
        
        elif next_level == MaturityLevel.SELF_HEALING:
            recommendations.extend([
                "Implement automatic detection for known issues",
                "Build auto-remediation for common failures",
                "Practice chaos engineering to validate resilience",
                "Design for autonomous operation",
                "Shift operator focus to system improvement",
                "Remember: If a human needs to touch during normal ops, you have a bug",
            ])
        
        # Add metric-based recommendations
        if ind.manual_intervention_rate > 0.5:
            recommendations.append(
                f"Reduce manual intervention rate from {ind.manual_intervention_rate:.0%} "
                "by automating common remediation paths"
            )
        
        if ind.automation_coverage < 0.5:
            recommendations.append(
                f"Increase automation coverage from {ind.automation_coverage:.0%} "
                "to at least 50%"
            )
        
        if ind.incident_recurrence_rate > 0.3:
            recommendations.append(
                f"Address recurring incidents (rate: {ind.incident_recurrence_rate:.0%}) "
                "with permanent fixes, not automation"
            )
        
        return recommendations
    
    def get_level_description(self, level: MaturityLevel) -> dict:
        """Get description for a maturity level."""
        return MATURITY_DESCRIPTIONS[level]
    
    def compare_subjects(self, subjects: list[str]) -> list[dict]:
        """Compare maturity across multiple subjects."""
        comparisons = []
        for subject in subjects:
            if subject in self.assessments:
                assessment = self.assessments[subject]
                comparisons.append({
                    "subject": subject,
                    "level": assessment.current_level.value,
                    "level_name": assessment.level_name,
                    "score": assessment.score,
                    "target_gap": assessment.levels_to_target,
                })
        
        # Sort by score descending
        return sorted(comparisons, key=lambda x: x["score"], reverse=True)
    
    def get_upgrade_plan(
        self,
        subject: str,
        target: Optional[MaturityLevel] = None,
    ) -> dict:
        """Generate an upgrade plan to reach target maturity."""
        if subject not in self.assessments:
            return {"error": f"No assessment found for {subject}"}
        
        assessment = self.assessments[subject]
        target = target or assessment.target_level
        
        if assessment.current_level >= target:
            return {
                "subject": subject,
                "current_level": assessment.current_level.value,
                "target_level": target.value,
                "status": "Already at or above target",
                "phases": [],
            }
        
        phases = []
        for level in range(assessment.current_level.value + 1, target.value + 1):
            level_enum = MaturityLevel(level)
            desc = MATURITY_DESCRIPTIONS[level_enum]
            
            phases.append({
                "phase": level - assessment.current_level.value,
                "target_level": level,
                "target_name": desc["name"],
                "description": desc["description"],
                "characteristics": desc["characteristics"],
                "risks": desc["risks"],
            })
        
        return {
            "subject": subject,
            "current_level": assessment.current_level.value,
            "current_name": assessment.level_name,
            "target_level": target.value,
            "target_name": MATURITY_DESCRIPTIONS[target]["name"],
            "phases": phases,
            "recommendations": assessment.recommendations,
        }
