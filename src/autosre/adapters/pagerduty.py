"""
OpenSRE PagerDuty Adapter — Incident management integration
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass
class PagerDutyIncident:
    """Represents a PagerDuty incident."""
    id: str
    title: str
    status: str  # triggered, acknowledged, resolved
    urgency: str  # high, low
    service_name: str
    created_at: datetime
    html_url: str


class PagerDutyAdapter:
    """
    PagerDuty integration for OpenSRE.

    Capabilities:
    - Fetch open incidents
    - Create new incidents
    - Add investigation notes
    - Resolve incidents with resolution details
    - Format investigation results as notes
    """

    BASE_URL = "https://api.pagerduty.com"

    def __init__(
        self,
        api_key: str | None = None,
        service_id: str | None = None,
        from_email: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENSRE_PAGERDUTY_API_KEY")
        self.service_id = service_id or os.environ.get("OPENSRE_PAGERDUTY_SERVICE_ID")
        self.from_email = from_email or os.environ.get(
            "OPENSRE_PAGERDUTY_FROM_EMAIL", "opensre@example.com"
        )

    @property
    def headers(self) -> dict:
        """Build authorization headers for PagerDuty API."""
        return {
            "Authorization": f"Token token={self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

    async def health_check(self) -> dict[str, Any]:
        """
        Check PagerDuty connection health.

        Returns:
            Status dict with connection info
        """
        if not self.api_key:
            return {
                "status": "not_configured",
                "details": "No PagerDuty API key configured",
                "configured": False,
            }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/users/me",
                    headers=self.headers,
                    timeout=10,
                )

                if response.status_code == 200:
                    user_data = response.json().get("user", {})
                    return {
                        "status": "connected",
                        "configured": True,
                        "details": "PagerDuty API connected",
                        "user": user_data.get("email"),
                        "service_id": self.service_id,
                    }

                return {
                    "status": "error",
                    "configured": True,
                    "details": f"HTTP {response.status_code}",
                }
        except httpx.TimeoutException:
            return {
                "status": "error",
                "configured": True,
                "details": "Connection timeout",
            }
        except Exception as e:
            return {
                "status": "error",
                "configured": True,
                "details": str(e),
            }

    async def get_incidents(
        self,
        statuses: list[str] | None = None,
        urgencies: list[str] | None = None,
        limit: int = 25,
    ) -> list[PagerDutyIncident]:
        """
        Get incidents from PagerDuty.

        Args:
            statuses: Filter by status (default: triggered, acknowledged)
            urgencies: Filter by urgency (high, low)
            limit: Maximum number of incidents to return

        Returns:
            List of PagerDutyIncident objects
        """
        statuses = statuses or ["triggered", "acknowledged"]

        params = {
            "statuses[]": statuses,
            "limit": limit,
            "sort_by": "created_at:desc",
        }
        if urgencies:
            params["urgencies[]"] = urgencies
        if self.service_id:
            params["service_ids[]"] = [self.service_id]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/incidents",
                headers=self.headers,
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

        incidents = []
        for item in data.get("incidents", []):
            incidents.append(PagerDutyIncident(
                id=item["id"],
                title=item["title"],
                status=item["status"],
                urgency=item["urgency"],
                service_name=item.get("service", {}).get("summary", "unknown"),
                created_at=datetime.fromisoformat(
                    item["created_at"].replace("Z", "+00:00")
                ),
                html_url=item["html_url"],
            ))

        return incidents

    async def get_incident(self, incident_id: str) -> PagerDutyIncident | None:
        """
        Get a single incident by ID.

        Args:
            incident_id: The PagerDuty incident ID

        Returns:
            PagerDutyIncident or None if not found
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/incidents/{incident_id}",
                headers=self.headers,
                timeout=10,
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            item = response.json()["incident"]

        return PagerDutyIncident(
            id=item["id"],
            title=item["title"],
            status=item["status"],
            urgency=item["urgency"],
            service_name=item.get("service", {}).get("summary", "unknown"),
            created_at=datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            ),
            html_url=item["html_url"],
        )

    async def create_incident(
        self,
        title: str,
        body: str,
        urgency: str = "high",
    ) -> PagerDutyIncident:
        """
        Create a new incident in PagerDuty.

        Args:
            title: Incident title
            body: Incident description/body
            urgency: "high" or "low"

        Returns:
            Created PagerDutyIncident
        """
        if not self.service_id:
            raise ValueError("service_id required to create incidents")

        payload = {
            "incident": {
                "type": "incident",
                "title": title,
                "service": {
                    "id": self.service_id,
                    "type": "service_reference",
                },
                "urgency": urgency,
                "body": {
                    "type": "incident_body",
                    "details": body,
                },
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/incidents",
                headers={**self.headers, "From": self.from_email},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            item = response.json()["incident"]

        return PagerDutyIncident(
            id=item["id"],
            title=item["title"],
            status=item["status"],
            urgency=item["urgency"],
            service_name=item.get("service", {}).get("summary", "unknown"),
            created_at=datetime.now(),
            html_url=item["html_url"],
        )

    async def add_note(self, incident_id: str, note: str) -> None:
        """
        Add a note to an incident.

        Useful for posting investigation results, progress updates,
        or additional context to the incident timeline.

        Args:
            incident_id: The PagerDuty incident ID
            note: The note content (supports markdown-like formatting)
        """
        payload = {
            "note": {
                "content": note,
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/incidents/{incident_id}/notes",
                headers={**self.headers, "From": self.from_email},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

    async def acknowledge_incident(self, incident_id: str) -> None:
        """
        Acknowledge an incident.

        Args:
            incident_id: The PagerDuty incident ID
        """
        payload = {
            "incident": {
                "type": "incident",
                "status": "acknowledged",
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/incidents/{incident_id}",
                headers={**self.headers, "From": self.from_email},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

    async def resolve_incident(
        self,
        incident_id: str,
        resolution: str = "",
    ) -> None:
        """
        Resolve an incident.

        Args:
            incident_id: The PagerDuty incident ID
            resolution: Optional resolution note to add before resolving
        """
        # Add final note before resolving
        if resolution:
            await self.add_note(incident_id, f"✅ Resolution: {resolution}")

        payload = {
            "incident": {
                "type": "incident",
                "status": "resolved",
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/incidents/{incident_id}",
                headers={**self.headers, "From": self.from_email},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

    async def reassign_incident(
        self,
        incident_id: str,
        user_ids: list[str],
    ) -> None:
        """
        Reassign an incident to different users.

        Args:
            incident_id: The PagerDuty incident ID
            user_ids: List of PagerDuty user IDs to assign
        """
        assignments = [
            {"assignee": {"id": uid, "type": "user_reference"}}
            for uid in user_ids
        ]

        payload = {
            "incident": {
                "type": "incident",
                "assignments": assignments,
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/incidents/{incident_id}",
                headers={**self.headers, "From": self.from_email},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

    def format_investigation_note(self, result) -> str:
        """
        Format an investigation result as a PagerDuty note.

        Args:
            result: InvestigationResult from the orchestrator

        Returns:
            Formatted note string suitable for PagerDuty
        """
        lines = [
            "🔍 **OpenSRE Investigation**",
            "",
            f"**Root Cause:** {result.root_cause}",
            f"**Confidence:** {result.confidence:.0%}",
            "",
            "**Key Observations:**",
        ]

        # Add top observations
        for obs in result.observations[:5]:
            source = getattr(obs, 'source', 'unknown')
            summary = getattr(obs, 'summary', str(obs))
            lines.append(f"• [{source}] {summary}")

        # Add contributing factors if present
        if hasattr(result, 'contributing_factors') and result.contributing_factors:
            lines.append("")
            lines.append("**Contributing Factors:**")
            for factor in result.contributing_factors[:3]:
                lines.append(f"• {factor}")

        # Add recommended actions
        if result.actions:
            lines.append("")
            lines.append("**Recommended Actions:**")
            for action in result.actions[:3]:
                risk = getattr(action, 'risk', None)
                risk_str = f" (Risk: {risk.value})" if risk else ""
                lines.append(f"• {action.description}{risk_str}")

        # Add investigation ID
        if hasattr(result, 'id'):
            lines.append("")
            lines.append(f"Investigation ID: {result.id[:8]}")

        return "\n".join(lines)

    async def post_investigation(self, incident_id: str, result) -> None:
        """
        Post an investigation result to a PagerDuty incident.

        Args:
            incident_id: The PagerDuty incident ID
            result: InvestigationResult from the orchestrator
        """
        note = self.format_investigation_note(result)
        await self.add_note(incident_id, note)

    async def auto_investigate_incident(
        self,
        incident: PagerDutyIncident,
        investigation_manager,
    ) -> dict[str, Any]:
        """
        Auto-investigate a PagerDuty incident.

        Starts an investigation, posts results as a note, and returns status.

        Args:
            incident: The PagerDutyIncident to investigate
            investigation_manager: The InvestigationManager instance

        Returns:
            Dict with investigation_id and status
        """
        import asyncio

        # Start investigation
        investigation_id = await investigation_manager.start_investigation(
            issue=incident.title,
            namespace="default",
        )

        # Wait for investigation to complete (with timeout)
        max_wait = 60  # seconds
        waited = 0
        investigation = None

        while waited < max_wait:
            investigation = await investigation_manager.get_investigation(
                investigation_id
            )
            if investigation and investigation.status in [
                "completed", "failed", "timeout"
            ]:
                break
            await asyncio.sleep(2)
            waited += 2

        # Post results to PagerDuty
        if investigation and investigation.status == "completed":
            await self.post_investigation(incident.id, investigation)

        return {
            "investigation_id": investigation_id,
            "status": investigation.status if investigation else "timeout",
            "incident_id": incident.id,
        }
