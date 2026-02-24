"""
Actor Agent - Suggests and executes remediation actions
"""

from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from opensre_core.adapters.llm import LLMAdapter
from opensre_core.adapters.kubernetes import KubernetesAdapter
from opensre_core.agents.reason import AnalysisResult
from opensre_core.utils.prompts import ACTOR_SYSTEM_PROMPT, ACTOR_ACTION_PROMPT
from opensre_core.config import settings


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
    
    def __init__(self):
        self.llm = LLMAdapter()
        self.kubernetes = KubernetesAdapter()
    
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
    
    def _assess_risk(self, command: str) -> tuple[ActionRisk, bool]:
        """Assess risk level and approval requirement for a command."""
        command_lower = command.lower()
        
        # Check for dangerous patterns
        if any(pattern in command_lower for pattern in ["delete", "rm ", "drop"]):
            return ActionRisk.HIGH, True
        
        # Check for modification patterns
        if any(pattern in command_lower for pattern in ["scale", "rollout", "apply", "patch", "edit"]):
            return ActionRisk.MEDIUM, True
        
        # Check for safe patterns
        if any(pattern in command_lower for pattern in ["get", "describe", "logs", "top", "status"]):
            return ActionRisk.LOW, False
        
        # Default: medium risk, requires approval
        return ActionRisk.MEDIUM, True
    
    async def execute_action(
        self,
        action: Action,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        Execute a single action.
        
        Args:
            action: Action to execute
            dry_run: If True, don't actually execute (for preview)
        
        Returns:
            Execution result
        """
        if dry_run:
            action.status = ActionStatus.PENDING
            return {
                "dry_run": True,
                "command": action.command,
                "would_execute": True,
                "risk": action.risk.value,
            }
        
        if action.requires_approval and settings.require_approval:
            action.status = ActionStatus.PENDING
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
            return result
        except Exception as e:
            action.status = ActionStatus.FAILED
            action.result = {"error": str(e)}
            return {"error": str(e)}
    
    async def _execute_command(self, command: str) -> dict[str, Any]:
        """Execute a kubectl command."""
        import asyncio
        
        # Security check
        if not command.startswith("kubectl"):
            raise ValueError("Only kubectl commands are supported")
        
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
    
    async def approve_action(self, action: Action) -> dict[str, Any]:
        """Approve and execute an action."""
        action.status = ActionStatus.APPROVED
        return await self.execute_action(action, dry_run=False)
    
    def reject_action(self, action: Action, reason: str = "") -> None:
        """Reject an action."""
        action.status = ActionStatus.REJECTED
        action.result = {"rejected": True, "reason": reason}
