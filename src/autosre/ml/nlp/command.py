"""Natural language command parsing for operations."""

from datetime import datetime
from typing import Any, Optional, List, Dict
from enum import Enum
import re

from pydantic import BaseModel, Field, ConfigDict

from autosre.models.common import utc_now, generate_id


class CommandType(str, Enum):
    """Type of operational command."""
    SCALE = "scale"
    RESTART = "restart"
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    INVESTIGATE = "investigate"
    DIAGNOSE = "diagnose"
    STATUS = "status"
    LOGS = "logs"
    METRICS = "metrics"
    ALERT = "alert"
    CONFIG = "config"
    UNKNOWN = "unknown"


class ParsedCommand(BaseModel):
    """Parsed command from natural language."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
    )
    
    command_id: str = Field(default_factory=generate_id)
    
    # Command type
    command_type: CommandType = Field(default=CommandType.UNKNOWN)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Parsed elements
    action: str = Field(default="")
    target: str = Field(default="")
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    # Original input
    original_text: str = Field(default="")
    
    # Extracted entities
    service_name: str = Field(default="")
    environment: str = Field(default="")
    version: str = Field(default="")
    time_range: str = Field(default="")
    count: Optional[int] = None
    
    # Execution info
    executable: bool = Field(default=False)
    requires_confirmation: bool = Field(default=False)
    risk_level: str = Field(default="low")  # low, medium, high
    
    # Generated command
    cli_command: str = Field(default="")
    api_endpoint: str = Field(default="")
    
    # Metadata
    parsed_at: datetime = Field(default_factory=utc_now)


class CommandParser:
    """Parse natural language into operational commands.
    
    Converts phrases like:
    - "restart the auth service"
    - "scale api to 5 replicas"
    - "show logs for payment-service"
    
    Into structured commands that can be executed.
    
    Features:
    - Intent detection
    - Entity extraction
    - Parameter parsing
    - Command generation
    """
    
    def __init__(
        self,
        allow_dangerous: bool = False,
        require_confirmation: List[CommandType] = None,
    ):
        """Initialize the parser.
        
        Args:
            allow_dangerous: Allow dangerous commands
            require_confirmation: Commands requiring confirmation
        """
        self.allow_dangerous = allow_dangerous
        self.require_confirmation = require_confirmation or [
            CommandType.RESTART,
            CommandType.DEPLOY,
            CommandType.ROLLBACK,
            CommandType.SCALE,
        ]
        
        # Command patterns
        self._patterns = {
            CommandType.SCALE: [
                r"scale\s+(\S+)\s+to\s+(\d+)",
                r"set\s+replicas?\s+for\s+(\S+)\s+to\s+(\d+)",
                r"increase\s+(\S+)\s+to\s+(\d+)",
                r"scale\s+up\s+(\S+)",
                r"scale\s+down\s+(\S+)",
            ],
            CommandType.RESTART: [
                r"restart\s+(?:the\s+)?(\S+)",
                r"bounce\s+(?:the\s+)?(\S+)",
                r"reboot\s+(?:the\s+)?(\S+)",
                r"cycle\s+(?:the\s+)?(\S+)",
            ],
            CommandType.DEPLOY: [
                r"deploy\s+(\S+)\s+(?:version\s+)?(\S+)?",
                r"release\s+(\S+)",
                r"push\s+(\S+)\s+to\s+(\S+)",
            ],
            CommandType.ROLLBACK: [
                r"rollback\s+(\S+)",
                r"revert\s+(\S+)",
                r"undo\s+deploy(?:ment)?\s+(?:of\s+)?(\S+)",
            ],
            CommandType.INVESTIGATE: [
                r"investigate\s+(\S+)",
                r"look\s+into\s+(\S+)",
                r"check\s+(\S+)",
                r"analyze\s+(\S+)",
            ],
            CommandType.DIAGNOSE: [
                r"diagnose\s+(\S+)",
                r"troubleshoot\s+(\S+)",
                r"debug\s+(\S+)",
            ],
            CommandType.STATUS: [
                r"(?:get\s+)?status\s+(?:of\s+)?(\S+)?",
                r"how\s+is\s+(\S+)",
                r"is\s+(\S+)\s+(?:running|up|down)",
            ],
            CommandType.LOGS: [
                r"(?:show\s+)?logs?\s+(?:for\s+)?(\S+)",
                r"tail\s+(\S+)",
                r"get\s+logs?\s+from\s+(\S+)",
            ],
            CommandType.METRICS: [
                r"(?:show\s+)?metrics?\s+(?:for\s+)?(\S+)",
                r"(?:get\s+)?(\S+)\s+metrics",
                r"dashboard\s+(?:for\s+)?(\S+)",
            ],
            CommandType.ALERT: [
                r"(?:show\s+)?alerts?\s+(?:for\s+)?(\S+)?",
                r"silence\s+alert\s+(\S+)",
                r"acknowledge\s+(\S+)",
            ],
            CommandType.CONFIG: [
                r"(?:show\s+)?config(?:uration)?\s+(?:for\s+)?(\S+)",
                r"set\s+(\S+)\s+(?:to\s+)?(\S+)",
                r"update\s+config\s+(\S+)",
            ],
        }
        
        # Environment patterns
        self._env_patterns = [
            r"\b(prod(?:uction)?)\b",
            r"\b(stag(?:ing)?)\b",
            r"\b(dev(?:elopment)?)\b",
            r"\b(test(?:ing)?)\b",
        ]
        
        # Time patterns
        self._time_patterns = [
            r"(?:last|past)\s+(\d+)\s+(minute|hour|day|week)s?",
            r"since\s+(\S+)",
            r"from\s+(\S+)\s+to\s+(\S+)",
        ]
    
    def parse(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ParsedCommand:
        """Parse natural language command.
        
        Args:
            text: Input text
            context: Additional context
            
        Returns:
            Parsed command
        """
        text_lower = text.lower().strip()
        context = context or {}
        
        # Detect command type and extract entities
        command_type = CommandType.UNKNOWN
        confidence = 0.0
        target = ""
        parameters = {}
        
        for cmd_type, patterns in self._patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    command_type = cmd_type
                    confidence = 0.8
                    
                    groups = match.groups()
                    if groups:
                        target = groups[0] if groups[0] else ""
                        if len(groups) > 1:
                            parameters["value"] = groups[1]
                    break
            
            if command_type != CommandType.UNKNOWN:
                break
        
        # Extract service name
        service_name = self._extract_service_name(text_lower, target)
        
        # Extract environment
        environment = self._extract_environment(text_lower)
        
        # Extract version
        version = self._extract_version(text_lower)
        
        # Extract time range
        time_range = self._extract_time_range(text_lower)
        
        # Extract count/number
        count = self._extract_count(text_lower)
        
        # Determine risk level
        risk_level = self._determine_risk(command_type, parameters)
        
        # Check if executable
        executable = command_type != CommandType.UNKNOWN and service_name != ""
        
        # Check if confirmation required
        requires_confirmation = command_type in self.require_confirmation
        
        # Generate CLI command
        cli_command = self._generate_cli_command(
            command_type, service_name, environment, parameters, count
        )
        
        # Generate API endpoint
        api_endpoint = self._generate_api_endpoint(
            command_type, service_name, environment
        )
        
        return ParsedCommand(
            command_type=command_type,
            confidence=confidence,
            action=command_type.value,
            target=target,
            parameters=parameters,
            original_text=text,
            service_name=service_name,
            environment=environment,
            version=version,
            time_range=time_range,
            count=count,
            executable=executable,
            requires_confirmation=requires_confirmation,
            risk_level=risk_level,
            cli_command=cli_command,
            api_endpoint=api_endpoint,
        )
    
    def _extract_service_name(self, text: str, target: str) -> str:
        """Extract service name from text.
        
        Args:
            text: Input text
            target: Initially detected target
            
        Returns:
            Service name
        """
        if target and target not in ["the", "a", "an", "to", "from"]:
            return target.replace("the", "").replace("-", "_").strip()
        
        # Look for common service name patterns
        patterns = [
            r"service[:\s]+([a-z0-9\-_]+)",
            r"([a-z0-9\-_]+)-service",
            r"([a-z0-9\-_]+)-api",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_environment(self, text: str) -> str:
        """Extract environment from text.
        
        Args:
            text: Input text
            
        Returns:
            Environment name
        """
        for pattern in self._env_patterns:
            match = re.search(pattern, text)
            if match:
                env = match.group(1)
                if env.startswith("prod"):
                    return "production"
                elif env.startswith("stag"):
                    return "staging"
                elif env.startswith("dev"):
                    return "development"
                elif env.startswith("test"):
                    return "testing"
        
        return ""
    
    def _extract_version(self, text: str) -> str:
        """Extract version from text.
        
        Args:
            text: Input text
            
        Returns:
            Version string
        """
        patterns = [
            r"version\s+([v]?\d+\.\d+\.\d+)",
            r"([v]?\d+\.\d+\.\d+)",
            r"release\s+([v]?\S+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_time_range(self, text: str) -> str:
        """Extract time range from text.
        
        Args:
            text: Input text
            
        Returns:
            Time range string
        """
        for pattern in self._time_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return ""
    
    def _extract_count(self, text: str) -> Optional[int]:
        """Extract count/number from text.
        
        Args:
            text: Input text
            
        Returns:
            Count value or None
        """
        patterns = [
            r"(\d+)\s*replicas?",
            r"to\s+(\d+)",
            r"(\d+)\s*instances?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        
        return None
    
    def _determine_risk(
        self,
        command_type: CommandType,
        parameters: Dict[str, Any],
    ) -> str:
        """Determine risk level of command.
        
        Args:
            command_type: Type of command
            parameters: Command parameters
            
        Returns:
            Risk level
        """
        high_risk = [CommandType.DEPLOY, CommandType.ROLLBACK]
        medium_risk = [CommandType.RESTART, CommandType.SCALE, CommandType.CONFIG]
        
        if command_type in high_risk:
            return "high"
        elif command_type in medium_risk:
            return "medium"
        return "low"
    
    def _generate_cli_command(
        self,
        command_type: CommandType,
        service: str,
        environment: str,
        parameters: Dict[str, Any],
        count: Optional[int],
    ) -> str:
        """Generate CLI command.
        
        Args:
            command_type: Type of command
            service: Service name
            environment: Environment
            parameters: Parameters
            count: Count value
            
        Returns:
            CLI command string
        """
        env_flag = f" --env {environment}" if environment else ""
        
        if command_type == CommandType.SCALE:
            replicas = count or parameters.get("value", 1)
            return f"kubectl scale deployment/{service} --replicas={replicas}{env_flag}"
        
        elif command_type == CommandType.RESTART:
            return f"kubectl rollout restart deployment/{service}{env_flag}"
        
        elif command_type == CommandType.LOGS:
            return f"kubectl logs -f deployment/{service}{env_flag}"
        
        elif command_type == CommandType.STATUS:
            return f"kubectl get pods -l app={service}{env_flag}"
        
        elif command_type == CommandType.ROLLBACK:
            return f"kubectl rollout undo deployment/{service}{env_flag}"
        
        return f"# {command_type.value} {service}"
    
    def _generate_api_endpoint(
        self,
        command_type: CommandType,
        service: str,
        environment: str,
    ) -> str:
        """Generate API endpoint.
        
        Args:
            command_type: Type of command
            service: Service name
            environment: Environment
            
        Returns:
            API endpoint
        """
        base = "/api/v1"
        env_path = f"/{environment}" if environment else ""
        
        endpoints = {
            CommandType.SCALE: f"{base}/services/{service}/scale",
            CommandType.RESTART: f"{base}/services/{service}/restart",
            CommandType.STATUS: f"{base}/services/{service}/status",
            CommandType.LOGS: f"{base}/services/{service}/logs",
            CommandType.METRICS: f"{base}/services/{service}/metrics",
            CommandType.DEPLOY: f"{base}/services/{service}/deploy",
            CommandType.ROLLBACK: f"{base}/services/{service}/rollback",
        }
        
        return endpoints.get(command_type, f"{base}/services/{service}")
    
    def validate_command(self, command: ParsedCommand) -> Dict[str, Any]:
        """Validate a parsed command.
        
        Args:
            command: Parsed command
            
        Returns:
            Validation result
        """
        errors = []
        warnings = []
        
        if command.command_type == CommandType.UNKNOWN:
            errors.append("Could not determine command type")
        
        if not command.service_name and command.command_type not in [CommandType.STATUS, CommandType.ALERT]:
            errors.append("Service name required")
        
        if command.risk_level == "high" and not command.environment:
            warnings.append("No environment specified for high-risk command")
        
        if command.command_type == CommandType.SCALE and command.count is None:
            errors.append("Replica count required for scale command")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "command": command,
        }
