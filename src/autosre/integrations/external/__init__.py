"""External Integrations for AutoSRE V2.

Provides clients for external services and platforms:
- Jira: Issue tracking
- ServiceNow: ITSM
- GitHub: PR/deploy tracking
- Terraform: Infrastructure management
- Vault: Secrets management
- Datadog: Observability
- New Relic: Monitoring
"""

from autosre.integrations.external.jira import (
    JiraIntegration,
    JiraConfig,
    JiraIssue,
    JiraTransition,
    JiraComment,
    JiraPriority,
    JiraIssueType,
)
from autosre.integrations.external.servicenow import (
    ServiceNowIntegration,
    ServiceNowConfig,
    ServiceNowIncident,
    ServiceNowChangeRequest,
    ServiceNowState,
)
from autosre.integrations.external.github import (
    GitHubIntegration,
    GitHubConfig,
    GitHubPullRequest,
    GitHubDeployment,
    GitHubCommit,
    DeploymentState,
)
from autosre.integrations.external.terraform import (
    TerraformIntegration,
    TerraformConfig,
    TerraformPlan,
    TerraformState,
    TerraformResource,
    PlanAction,
)
from autosre.integrations.external.vault import (
    VaultIntegration,
    VaultConfig,
    VaultSecret,
    VaultToken,
    VaultAuthMethod,
)
from autosre.integrations.external.datadog import (
    DatadogIntegration,
    DatadogConfig,
    DatadogMetric,
    DatadogEvent,
    DatadogMonitor,
    DatadogLog,
)
from autosre.integrations.external.newrelic import (
    NewRelicIntegration,
    NewRelicConfig,
    NewRelicMetric,
    NewRelicEvent,
    NewRelicAlert,
    NewRelicDeployment,
)

__all__ = [
    # Jira
    "JiraIntegration",
    "JiraConfig",
    "JiraIssue",
    "JiraTransition",
    "JiraComment",
    "JiraPriority",
    "JiraIssueType",
    # ServiceNow
    "ServiceNowIntegration",
    "ServiceNowConfig",
    "ServiceNowIncident",
    "ServiceNowChangeRequest",
    "ServiceNowState",
    # GitHub
    "GitHubIntegration",
    "GitHubConfig",
    "GitHubPullRequest",
    "GitHubDeployment",
    "GitHubCommit",
    "DeploymentState",
    # Terraform
    "TerraformIntegration",
    "TerraformConfig",
    "TerraformPlan",
    "TerraformState",
    "TerraformResource",
    "PlanAction",
    # Vault
    "VaultIntegration",
    "VaultConfig",
    "VaultSecret",
    "VaultToken",
    "VaultAuthMethod",
    # Datadog
    "DatadogIntegration",
    "DatadogConfig",
    "DatadogMetric",
    "DatadogEvent",
    "DatadogMonitor",
    "DatadogLog",
    # New Relic
    "NewRelicIntegration",
    "NewRelicConfig",
    "NewRelicMetric",
    "NewRelicEvent",
    "NewRelicAlert",
    "NewRelicDeployment",
]
