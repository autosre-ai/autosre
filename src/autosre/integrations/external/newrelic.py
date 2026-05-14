"""New Relic Integration for AutoSRE V2.

Provides New Relic integration for:
- Metrics submission (via Metrics API)
- Event submission
- Alert management
- Deployment tracking
- NRQL queries
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from autosre.integrations.base import (
    AuthenticatedIntegration,
    ConnectionConfig,
    HealthCheckResult,
    HealthStatus,
    IntegrationError,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """New Relic metric types."""
    
    GAUGE = "gauge"
    COUNT = "count"
    SUMMARY = "summary"


class AlertPriority(str, Enum):
    """Alert priority levels."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentPreference(str, Enum):
    """Incident preferences."""
    
    PER_POLICY = "PER_POLICY"
    PER_CONDITION = "PER_CONDITION"
    PER_CONDITION_AND_TARGET = "PER_CONDITION_AND_TARGET"


class ConditionType(str, Enum):
    """Alert condition types."""
    
    NRQL = "nrql"
    APM_APP_METRIC = "apm_app_metric"
    BROWSER_METRIC = "browser_metric"
    INFRASTRUCTURE = "infrastructure"


@dataclass
class NewRelicConfig:
    """Configuration for New Relic integration."""
    
    # API Keys
    api_key: str  # User API Key or License Key
    account_id: str
    
    # Optional Insert Key for events/metrics
    insert_key: Optional[str] = None
    
    # Region (us or eu)
    region: str = "us"
    
    # URLs (auto-generated from region)
    api_url: Optional[str] = None
    metrics_url: Optional[str] = None
    events_url: Optional[str] = None
    
    # Timeouts
    timeout_seconds: float = 30.0
    
    # Default attributes
    default_attributes: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.region == "eu":
            self.api_url = self.api_url or "https://api.eu.newrelic.com"
            self.metrics_url = self.metrics_url or "https://metric-api.eu.newrelic.com"
            self.events_url = self.events_url or "https://insights-collector.eu01.nr-data.net"
        else:
            self.api_url = self.api_url or "https://api.newrelic.com"
            self.metrics_url = self.metrics_url or "https://metric-api.newrelic.com"
            self.events_url = self.events_url or "https://insights-collector.newrelic.com"


class NewRelicMetric(BaseModel):
    """New Relic metric model."""
    
    name: str
    type: MetricType = MetricType.GAUGE
    value: Union[float, Dict[str, float]]  # Dict for summary type
    
    # Timing
    timestamp: Optional[int] = None  # milliseconds
    
    # Attributes
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # For summary metrics
    interval_ms: Optional[int] = None


class NewRelicEvent(BaseModel):
    """New Relic event model."""
    
    eventType: str
    
    # Event attributes
    attributes: Dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    timestamp: Optional[int] = None  # milliseconds
    
    def to_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        payload = {"eventType": self.eventType}
        payload.update(self.attributes)
        
        if self.timestamp:
            payload["timestamp"] = self.timestamp
        
        return payload


class NewRelicAlert(BaseModel):
    """New Relic alert model."""
    
    # Identity
    id: Optional[int] = None
    
    # Definition
    name: str
    policy_id: Optional[int] = None
    
    # Type
    type: ConditionType = ConditionType.NRQL
    
    # NRQL query
    nrql: Optional[str] = None
    
    # Thresholds
    critical_threshold: Optional[float] = None
    warning_threshold: Optional[float] = None
    
    # Duration
    duration_minutes: int = 5
    
    # Enabled
    enabled: bool = True


class NewRelicPolicy(BaseModel):
    """New Relic alert policy."""
    
    id: Optional[int] = None
    name: str
    incident_preference: IncidentPreference = IncidentPreference.PER_POLICY
    
    # Channels
    channel_ids: List[int] = Field(default_factory=list)


class NewRelicDeployment(BaseModel):
    """New Relic deployment marker."""
    
    # Identity
    id: Optional[str] = None
    
    # Application
    entity_guid: str
    
    # Deployment info
    version: str
    description: Optional[str] = None
    user: Optional[str] = None
    changelog: Optional[str] = None
    commit: Optional[str] = None
    
    # Timing
    timestamp: Optional[int] = None  # milliseconds
    
    # Group
    deployment_type: Optional[str] = None  # BASIC, BLUE_GREEN, CANARY, ROLLING, SHADOW


class NewRelicApplication(BaseModel):
    """New Relic APM application."""
    
    id: int
    name: str
    
    # Language
    language: Optional[str] = None
    
    # Status
    health_status: Optional[str] = None
    reporting: bool = True
    
    # Settings
    settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Entity GUID
    entity_guid: Optional[str] = None


class NRQLResult(BaseModel):
    """NRQL query result."""
    
    results: List[Dict[str, Any]] = Field(default_factory=list)
    facets: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Timing
    begin_time_seconds: Optional[int] = None
    end_time_seconds: Optional[int] = None


class NewRelicIntegration(AuthenticatedIntegration):
    """
    New Relic integration for observability.
    
    Provides comprehensive New Relic functionality:
    - Metric submission
    - Event submission
    - Alert management
    - Deployment markers
    - NRQL queries
    
    Example:
        config = NewRelicConfig(
            api_key="NRAK-xxx",
            account_id="12345",
            insert_key="NRII-xxx",
        )
        
        async with NewRelicIntegration(config) as nr:
            # Submit metrics
            await nr.submit_metrics([
                NewRelicMetric(
                    name="autosre.investigation.duration",
                    value=45.2,
                    attributes={"environment": "production"},
                )
            ])
            
            # Create event
            await nr.submit_event(NewRelicEvent(
                eventType="AutoSREInvestigation",
                attributes={
                    "investigationId": "inv-123",
                    "alertName": "HighLatency",
                },
            ))
            
            # Query with NRQL
            result = await nr.query_nrql(
                "SELECT count(*) FROM Transaction WHERE appName = 'myapp'"
            )
    """
    
    def __init__(self, config: NewRelicConfig):
        """Initialize New Relic integration.
        
        Args:
            config: New Relic configuration
        """
        self.nr_config = config
        
        conn_config = ConnectionConfig(
            base_url=config.api_url,
            timeout=config.timeout_seconds,
            headers={
                "Content-Type": "application/json",
                "Api-Key": config.api_key,
            },
        )
        
        super().__init__(config=conn_config)
    
    @property
    def name(self) -> str:
        return "newrelic"
    
    async def health_check(self) -> HealthCheckResult:
        """Check New Relic connectivity."""
        try:
            start = asyncio.get_event_loop().time()
            
            # Query account info via NerdGraph
            query = """
            {
                actor {
                    account(id: %s) {
                        name
                    }
                }
            }
            """ % self.nr_config.account_id
            
            await self._graphql(query)
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Connected to New Relic",
                latency_ms=latency,
                details={"account_id": self.nr_config.account_id},
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
    
    async def _graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute NerdGraph GraphQL query.
        
        Args:
            query: GraphQL query
            variables: Query variables
            
        Returns:
            Query result
        """
        client = await self._get_client()
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        response = await client.post(
            "/graphql",
            json=payload,
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "errors" in data:
            raise IntegrationError(
                f"GraphQL error: {data['errors']}",
                integration=self.name,
            )
        
        return data.get("data", {})
    
    # Metrics
    
    async def submit_metrics(
        self,
        metrics: List[NewRelicMetric],
    ) -> None:
        """Submit metrics to New Relic.
        
        Args:
            metrics: List of metrics to submit
        """
        if not self.nr_config.insert_key:
            raise IntegrationError(
                "Insert key required for metrics submission",
                integration=self.name,
            )
        
        # Build metrics payload
        metric_data = []
        
        for metric in metrics:
            entry = {
                "name": metric.name,
                "type": metric.type.value,
                "value": metric.value,
                "timestamp": metric.timestamp or int(time.time() * 1000),
                "attributes": {
                    **self.nr_config.default_attributes,
                    **metric.attributes,
                },
            }
            
            if metric.interval_ms:
                entry["interval.ms"] = metric.interval_ms
            
            metric_data.append(entry)
        
        payload = [
            {
                "metrics": metric_data,
            }
        ]
        
        # Use metrics API endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.nr_config.metrics_url}/metric/v1",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Api-Key": self.nr_config.insert_key,
                },
            )
            response.raise_for_status()
        
        logger.debug(
            "Submitted metrics to New Relic",
            count=len(metrics),
        )
    
    async def submit_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Submit a single metric.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Metric type
            attributes: Metric attributes
        """
        metric = NewRelicMetric(
            name=name,
            value=value,
            type=metric_type,
            attributes=attributes or {},
        )
        
        await self.submit_metrics([metric])
    
    # Events
    
    async def submit_events(
        self,
        events: List[NewRelicEvent],
    ) -> None:
        """Submit events to New Relic.
        
        Args:
            events: List of events to submit
        """
        if not self.nr_config.insert_key:
            raise IntegrationError(
                "Insert key required for events submission",
                integration=self.name,
            )
        
        # Build events payload
        payload = []
        for event in events:
            event_data = event.to_payload()
            event_data.update(self.nr_config.default_attributes)
            payload.append(event_data)
        
        # Use events API endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.nr_config.events_url}/v1/accounts/{self.nr_config.account_id}/events",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Api-Key": self.nr_config.insert_key,
                },
            )
            response.raise_for_status()
        
        logger.debug(
            "Submitted events to New Relic",
            count=len(events),
        )
    
    async def submit_event(
        self,
        event: NewRelicEvent,
    ) -> None:
        """Submit a single event.
        
        Args:
            event: Event to submit
        """
        await self.submit_events([event])
    
    # NRQL Queries
    
    async def query_nrql(
        self,
        query: str,
        timeout: int = 120,
    ) -> NRQLResult:
        """Execute NRQL query.
        
        Args:
            query: NRQL query string
            timeout: Query timeout in seconds
            
        Returns:
            NRQLResult
        """
        graphql_query = """
        query($accountId: Int!, $nrql: Nrql!) {
            actor {
                account(id: $accountId) {
                    nrql(query: $nrql, timeout: %d) {
                        results
                        totalResult
                    }
                }
            }
        }
        """ % timeout
        
        data = await self._graphql(
            graphql_query,
            variables={
                "accountId": int(self.nr_config.account_id),
                "nrql": query,
            },
        )
        
        nrql_data = data.get("actor", {}).get("account", {}).get("nrql", {})
        
        return NRQLResult(
            results=nrql_data.get("results", []),
        )
    
    # Applications
    
    async def list_applications(self) -> List[NewRelicApplication]:
        """List APM applications.
        
        Returns:
            List of applications
        """
        query = """
        query($accountId: Int!) {
            actor {
                entitySearch(query: "domain = 'APM' AND type = 'APPLICATION' AND accountId = '%s'") {
                    results {
                        entities {
                            guid
                            name
                            ... on ApmApplicationEntityOutline {
                                language
                                reporting
                            }
                        }
                    }
                }
            }
        }
        """ % self.nr_config.account_id
        
        data = await self._graphql(query, {"accountId": int(self.nr_config.account_id)})
        
        entities = data.get("actor", {}).get("entitySearch", {}).get("results", {}).get("entities", [])
        
        apps = []
        for entity in entities:
            apps.append(NewRelicApplication(
                id=0,  # GUID is used instead
                name=entity.get("name", ""),
                language=entity.get("language"),
                reporting=entity.get("reporting", True),
                entity_guid=entity.get("guid"),
            ))
        
        return apps
    
    async def get_application(self, entity_guid: str) -> NewRelicApplication:
        """Get application by entity GUID.
        
        Args:
            entity_guid: Entity GUID
            
        Returns:
            NewRelicApplication
        """
        query = """
        query($guid: EntityGuid!) {
            actor {
                entity(guid: $guid) {
                    guid
                    name
                    ... on ApmApplicationEntity {
                        language
                        reporting
                        settings {
                            apdexTarget
                        }
                    }
                }
            }
        }
        """
        
        data = await self._graphql(query, {"guid": entity_guid})
        
        entity = data.get("actor", {}).get("entity", {})
        
        return NewRelicApplication(
            id=0,
            name=entity.get("name", ""),
            language=entity.get("language"),
            reporting=entity.get("reporting", True),
            settings=entity.get("settings", {}),
            entity_guid=entity.get("guid"),
        )
    
    # Deployments
    
    async def create_deployment(
        self,
        deployment: NewRelicDeployment,
    ) -> NewRelicDeployment:
        """Create a deployment marker.
        
        Args:
            deployment: Deployment to create
            
        Returns:
            Created deployment
        """
        mutation = """
        mutation($entityGuid: EntityGuid!, $deployment: ChangeTrackingDeploymentInput!) {
            changeTrackingCreateDeployment(
                entityGuid: $entityGuid,
                deployment: $deployment
            ) {
                deploymentId
                entityGuid
            }
        }
        """
        
        deployment_input = {
            "version": deployment.version,
        }
        
        if deployment.description:
            deployment_input["description"] = deployment.description
        if deployment.user:
            deployment_input["user"] = deployment.user
        if deployment.changelog:
            deployment_input["changelog"] = deployment.changelog
        if deployment.commit:
            deployment_input["commit"] = deployment.commit
        if deployment.timestamp:
            deployment_input["timestamp"] = deployment.timestamp
        if deployment.deployment_type:
            deployment_input["deploymentType"] = deployment.deployment_type
        
        data = await self._graphql(
            mutation,
            {
                "entityGuid": deployment.entity_guid,
                "deployment": deployment_input,
            },
        )
        
        result = data.get("changeTrackingCreateDeployment", {})
        deployment.id = result.get("deploymentId")
        
        logger.info(
            "Created New Relic deployment",
            deployment_id=deployment.id,
            version=deployment.version,
        )
        
        return deployment
    
    # Alert Policies
    
    async def list_policies(self) -> List[NewRelicPolicy]:
        """List alert policies.
        
        Returns:
            List of policies
        """
        query = """
        query($accountId: Int!) {
            actor {
                account(id: $accountId) {
                    alerts {
                        policiesSearch {
                            policies {
                                id
                                name
                                incidentPreference
                            }
                        }
                    }
                }
            }
        }
        """
        
        data = await self._graphql(
            query,
            {"accountId": int(self.nr_config.account_id)},
        )
        
        policies_data = (
            data.get("actor", {})
            .get("account", {})
            .get("alerts", {})
            .get("policiesSearch", {})
            .get("policies", [])
        )
        
        policies = []
        for p in policies_data:
            policies.append(NewRelicPolicy(
                id=int(p.get("id")),
                name=p.get("name", ""),
                incident_preference=IncidentPreference(p.get("incidentPreference", "PER_POLICY")),
            ))
        
        return policies
    
    async def create_policy(
        self,
        policy: NewRelicPolicy,
    ) -> NewRelicPolicy:
        """Create an alert policy.
        
        Args:
            policy: Policy to create
            
        Returns:
            Created policy
        """
        mutation = """
        mutation($accountId: Int!, $policy: AlertsPolicyInput!) {
            alertsPolicyCreate(accountId: $accountId, policy: $policy) {
                policy {
                    id
                    name
                    incidentPreference
                }
            }
        }
        """
        
        data = await self._graphql(
            mutation,
            {
                "accountId": int(self.nr_config.account_id),
                "policy": {
                    "name": policy.name,
                    "incidentPreference": policy.incident_preference.value,
                },
            },
        )
        
        result = data.get("alertsPolicyCreate", {}).get("policy", {})
        policy.id = int(result.get("id"))
        
        logger.info(
            "Created New Relic policy",
            policy_id=policy.id,
            name=policy.name,
        )
        
        return policy
    
    # NRQL Conditions
    
    async def create_nrql_condition(
        self,
        policy_id: int,
        name: str,
        nrql: str,
        critical_threshold: float,
        warning_threshold: Optional[float] = None,
        duration_minutes: int = 5,
    ) -> Dict[str, Any]:
        """Create an NRQL alert condition.
        
        Args:
            policy_id: Policy ID
            name: Condition name
            nrql: NRQL query
            critical_threshold: Critical threshold
            warning_threshold: Warning threshold
            duration_minutes: Evaluation duration
            
        Returns:
            Created condition
        """
        mutation = """
        mutation(
            $accountId: Int!,
            $policyId: ID!,
            $condition: AlertsNrqlConditionStaticInput!
        ) {
            alertsNrqlConditionStaticCreate(
                accountId: $accountId,
                policyId: $policyId,
                condition: $condition
            ) {
                id
                name
            }
        }
        """
        
        terms = [
            {
                "threshold": critical_threshold,
                "thresholdOccurrences": "ALL",
                "thresholdDuration": duration_minutes * 60,
                "priority": "CRITICAL",
                "operator": "ABOVE",
            }
        ]
        
        if warning_threshold is not None:
            terms.append({
                "threshold": warning_threshold,
                "thresholdOccurrences": "ALL",
                "thresholdDuration": duration_minutes * 60,
                "priority": "WARNING",
                "operator": "ABOVE",
            })
        
        condition = {
            "name": name,
            "enabled": True,
            "nrql": {"query": nrql},
            "terms": terms,
            "violationTimeLimitSeconds": 86400,
        }
        
        data = await self._graphql(
            mutation,
            {
                "accountId": int(self.nr_config.account_id),
                "policyId": str(policy_id),
                "condition": condition,
            },
        )
        
        result = data.get("alertsNrqlConditionStaticCreate", {})
        
        logger.info(
            "Created NRQL condition",
            condition_id=result.get("id"),
            name=name,
        )
        
        return result
    
    # Dashboards
    
    async def list_dashboards(self) -> List[Dict[str, Any]]:
        """List dashboards.
        
        Returns:
            List of dashboards
        """
        query = """
        query($accountId: Int!) {
            actor {
                entitySearch(
                    query: "type = 'DASHBOARD' AND accountId = %s"
                ) {
                    results {
                        entities {
                            guid
                            name
                            ... on DashboardEntityOutline {
                                createdAt
                                updatedAt
                            }
                        }
                    }
                }
            }
        }
        """ % self.nr_config.account_id
        
        data = await self._graphql(query, {"accountId": int(self.nr_config.account_id)})
        
        return data.get("actor", {}).get("entitySearch", {}).get("results", {}).get("entities", [])
