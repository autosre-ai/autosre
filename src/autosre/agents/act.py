"""
Actor Agent - Suggests and executes remediation actions
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from opensre_core.adapters.kubernetes import KubernetesAdapter
from opensre_core.adapters.llm import LLMAdapter
from opensre_core.agents.reason import AnalysisResult
from opensre_core.config import settings
from opensre_core.security.audit import EventType, get_audit_logger
from opensre_core.security.rbac import can_execute_command
from opensre_core.security.sanitize import sanitize_command
from opensre_core.utils.prompts import ACTOR_ACTION_PROMPT, ACTOR_SYSTEM_PROMPT


class ActionRisk(str, Enum):
    """Risk level of an action."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionStatus(str, Enum):
    """Status of an action."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Action:
    """A suggested remediation action."""
    id: str
    description: str
    command: str
    risk: ActionRisk
    requires_approval: bool = True
    rationale: str = ""
    status: ActionStatus = ActionStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)

    @property
    def is_safe(self) -> bool:
        """Check if action is safe to execute without approval."""
        return self.risk == ActionRisk.LOW and not self.requires_approval


@dataclass
class ActionPlan:
    """Plan of actions to remediate an issue."""
    actions: list[Action] = field(default_factory=list)
    summary: str = ""
    estimated_impact: str = ""

    def get_pending(self) -> list[Action]:
        """Get actions pending approval."""
        return [a for a in self.actions if a.status == ActionStatus.PENDING]

    def get_safe_actions(self) -> list[Action]:
        """Get actions safe to execute immediately."""
        return [a for a in self.actions if a.is_safe]


class ActorAgent:
    """
    Agent that suggests and executes remediation actions.

    Key principles:
    - Human-in-the-loop: Destructive actions require approval
    - Safe actions can be executed automatically
    - All actions are logged for audit
    - Commands are sanitized to prevent injection
    """

    # Actions that are safe to execute without approval
    SAFE_ACTIONS = {
        "kubectl get",
        "kubectl describe",
        "kubectl logs",
        "kubectl top",
    }

    # Actions that require approval
    DANGEROUS_ACTIONS = {
        "kubectl delete",
        "kubectl scale",
        "kubectl rollout",
        "kubectl apply",
        "kubectl patch",
        "kubectl exec",
    }

    def __init__(self, user: str = "system"):
        self.llm = LLMAdapter()
        self.kubernetes = KubernetesAdapter()
        self.audit = get_audit_logger()
        self.current_user = user

    async def plan_actions(
        self,
        analysis: AnalysisResult,
        namespace: str = "default",
        runbook_context: str | None = None,
    ) -> ActionPlan:
        """
        Generate action plan based on analysis.

        Args:
            analysis: Root cause analysis result
            namespace: Kubernetes namespace
            runbook_context: Optional runbook guidance

        Returns:
            ActionPlan with suggested actions
        """
        # Build prompt
        prompt = ACTOR_ACTION_PROMPT.format(
            root_cause=analysis.root_cause,
            confidence=f"{analysis.confidence:.0%}",
            analysis=analysis.to_context(),
            namespace=namespace,
            runbook_context=runbook_context or "No runbooks available.",
        )

        # Get LLM suggestions
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=ACTOR_SYSTEM_PROMPT,
            temperature=0.3,
        )

        # Parse actions
        plan = self._parse_actions(response.content, namespace)

        return plan

    def _parse_actions(self, response: str, namespace: str) -> ActionPlan:
        """Parse LLM response into action plan."""
        plan = ActionPlan()

        lines = response.strip().split("\n")
        action_id = 0

        for i, line in enumerate(lines):
            line = line.strip()

            # Look for command patterns
            if line.startswith("`") and line.endswith("`"):
                command = line.strip("`")
                action_id += 1

                # Determine risk and approval requirement
                risk, requires_approval = self._assess_risk(command)

                # Get description from previous line if available
                description = lines[i - 1].strip().lstrip("-•*0123456789. ") if i > 0 else command

                plan.actions.append(Action(
                    id=f"action_{action_id}",
                    description=description,
                    command=command,
                    risk=risk,
                    requires_approval=requires_approval,
                ))

            # Also look for kubectl commands inline
            elif "kubectl" in line:
                # Extract command
                import re
                match = re.search(r'`([^`]*kubectl[^`]*)`', line)
                if match:
                    command = match.group(1)
                    action_id += 1

                    risk, requires_approval = self._assess_risk(command)
                    description = line.split("`")[0].strip().lstrip("-•*0123456789. ") or command

                    plan.actions.append(Action(
                        id=f"action_{action_id}",
                        description=description,
                        command=command,
                        risk=risk,
                        requires_approval=requires_approval,
                    ))

            # Parse summary
            if "summary:" in line.lower():
                plan.summary = line.split(":", 1)[-1].strip()

            if "impact:" in line.lower():
                plan.estimated_impact = line.split(":", 1)[-1].strip()

        return plan

    def _determine_risk_level(self, command: str) -> ActionRisk:
        """
        Determine risk level for a kubectl command using pattern matching.

        This is deterministic and overrides any LLM-generated risk levels.
        """
        import re

        # Normalize command
        command_lower = command.lower().strip()

        # Extract the kubectl subcommand (e.g., "kubectl get" -> "get")
        # Handle both "kubectl <verb>" and "kubectl <verb> <subverb>" patterns
        kubectl_match = re.search(r'kubectl\s+(\S+)(?:\s+(\S+))?', command_lower)
        if not kubectl_match:
            # Not a kubectl command, default to MEDIUM
            return ActionRisk.MEDIUM

        verb = kubectl_match.group(1)
        subverb = kubectl_match.group(2) or ""

        # LOW risk (read-only commands)
        low_risk_verbs = {
            "get", "describe", "logs", "top", "events",
            "explain", "api-resources", "version", "cluster-info",
            "config", "auth", "diff",
        }
        if verb in low_risk_verbs:
            return ActionRisk.LOW

        # HIGH risk (destructive commands)
        high_risk_verbs = {"delete", "replace", "drain"}
        if verb in high_risk_verbs:
            return ActionRisk.HIGH

        # HIGH risk: apply, patch, edit (modification commands)
        high_risk_modify = {"apply", "patch", "edit", "create"}
        if verb in high_risk_modify:
            return ActionRisk.HIGH

        # MEDIUM risk: rollout (depends on subcommand)
        if verb == "rollout":
            if subverb == "undo":
                return ActionRisk.HIGH
            # rollout restart, status, history, pause, resume
            return ActionRisk.MEDIUM

        # MEDIUM risk (reversible commands)
        medium_risk_verbs = {
            "scale", "cordon", "uncordon", "taint", "untaint",
            "label", "annotate", "set", "expose", "autoscale",
        }
        if verb in medium_risk_verbs:
            return ActionRisk.MEDIUM

        # exec is HIGH (can do anything inside container)
        if verb == "exec":
            return ActionRisk.HIGH

        # Default: MEDIUM for unknown commands
        return ActionRisk.MEDIUM

    def _assess_risk(self, command: str) -> tuple[ActionRisk, bool]:
        """Assess risk level and approval requirement for a command."""
        risk = self._determine_risk_level(command)

        # Determine approval requirement based on risk
        requires_approval = risk != ActionRisk.LOW

        return risk, requires_approval

    async def execute_action(
        self,
        action: Action,
        dry_run: bool = True,
        user_roles: list[str] = None,
        approved_by: str = None,
    ) -> dict[str, Any]:
        """
        Execute a single action.

        Args:
            action: Action to execute
            dry_run: If True, don't actually execute (for preview)
            user_roles: Roles of the user executing the action
            approved_by: Who approved this action (for audit)

        Returns:
            Execution result
        """
        # Default roles if not provided
        if user_roles is None:
            user_roles = ["viewer"]

        if dry_run:
            action.status = ActionStatus.PENDING
            return {
                "dry_run": True,
                "command": action.command,
                "would_execute": True,
                "risk": action.risk.value,
            }

        # Check RBAC permissions
        if not can_execute_command(user_roles, action.risk.value):
            self.audit.log_permission_denied(
                user=self.current_user,
                action=f"execute {action.id}",
                required_permission=f"execute:{action.risk.value}",
            )
            return {
                "error": f"Permission denied: requires execute:{action.risk.value}",
                "command": action.command,
                "risk": action.risk.value,
            }

        # Sanitize command before execution
        is_safe, reason = sanitize_command(action.command)
        if not is_safe:
            self.audit.log_sanitize_failure(
                user=self.current_user,
                command=action.command,
                reason=reason,
            )
            action.status = ActionStatus.REJECTED
            action.result = {"error": f"Command blocked: {reason}"}
            return action.result

        if action.requires_approval and settings.require_approval:
            action.status = ActionStatus.PENDING
            self.audit.log_action_proposed(
                user=self.current_user,
                action_id=action.id,
                command=action.command,
                risk=action.risk.value,
            )
            return {
                "requires_approval": True,
                "command": action.command,
                "risk": action.risk.value,
            }

        # Execute the action
        action.status = ActionStatus.EXECUTING

        try:
            result = await self._execute_command(action.command)
            action.status = ActionStatus.COMPLETED
            action.result = result

            # Log successful execution
            self.audit.log_action_executed(
                user=self.current_user,
                action_id=action.id,
                command=action.command,
                exit_code=result.get("exit_code", 0),
                approved_by=approved_by or self.current_user,
            )

            return result
        except Exception as e:
            action.status = ActionStatus.FAILED
            action.result = {"error": str(e)}

            # Log failed execution
            self.audit.log(
                EventType.ACTION_FAILED,
                user=self.current_user,
                action=f"Failed to execute {action.id}",
                details={"action_id": action.id, "error": str(e)},
                result="failure",
            )

            return {"error": str(e)}

    async def _execute_command(self, command: str) -> dict[str, Any]:
        """Execute a kubectl command."""
        import asyncio

        # Security check - only kubectl commands allowed
        if not command.startswith("kubectl"):
            raise ValueError("Only kubectl commands are supported")

        # Final sanitization check
        is_safe, reason = sanitize_command(command)
        if not is_safe:
            raise ValueError(f"Command blocked by security: {reason}")

        # Execute
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout.decode() if stdout else "",
            "stderr": stderr.decode() if stderr else "",
            "success": proc.returncode == 0,
        }

    async def approve_action(
        self,
        action: Action,
        approved_by: str,
        user_roles: list[str] = None,
    ) -> dict[str, Any]:
        """Approve and execute an action."""
        if user_roles is None:
            user_roles = ["sre"]  # Default to sre for approvals

        action.status = ActionStatus.APPROVED

        # Log approval
        self.audit.log_action_approved(
            user=self.current_user,
            action_id=action.id,
            command=action.command,
            approved_by=approved_by,
        )

        return await self.execute_action(
            action,
            dry_run=False,
            user_roles=user_roles,
            approved_by=approved_by,
        )

    def reject_action(self, action: Action, reason: str = "") -> None:
        """Reject an action."""
        action.status = ActionStatus.REJECTED
        action.result = {"rejected": True, "reason": reason}

        # Log rejection
        self.audit.log_action_rejected(
            user=self.current_user,
            action_id=action.id,
            reason=reason,
        )
