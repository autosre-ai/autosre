"""
Tests for Dynatrace Skill
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import httpx

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from skills.dynatrace import DynatraceSkill
from skills.dynatrace.actions import Problem, ProblemDetails, MetricData, Entity


@pytest.fixture
def skill():
    """Create Dynatrace skill instance."""
    return DynatraceSkill({
        "url": "https://abc12345.live.dynatrace.com",
        "api_token": "dt0c01.test-token",
        "timeout": 10,
    })


@pytest.fixture
def mock_response():
    """Factory for mock HTTP responses."""
    def _make(json_data, status_code=200):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            error = httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=response
            )
            response.raise_for_status.side_effect = error
        return response
    return _make


class TestDynatraceSkillInit:
    """Test skill initialization."""
    
    def test_default_config(self):
        """Test skill with default config."""
        skill = DynatraceSkill()
        assert skill.url == ""
        assert skill.api_token == ""
        assert skill.timeout == 30
    
    def test_custom_config(self):
        """Test skill with custom config."""
        skill = DynatraceSkill({
            "url": "https://test.live.dynatrace.com/",
            "api_token": "test-token",
            "timeout": 60,
        })
        assert skill.url == "https://test.live.dynatrace.com"
        assert skill.api_token == "test-token"
        assert skill.timeout == 60
    
    def test_headers(self, skill):
        """Test API headers."""
        headers = skill._get_headers()
        assert "Api-Token" in headers["Authorization"]
        assert headers["Accept"] == "application/json"


class TestHealthCheck:
    """Test health check action."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, skill, mock_response):
        """Test successful health check."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({})
            
            result = await skill.health_check()
            
            assert result.success
            assert result.data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_check_no_url(self):
        """Test health check without URL."""
        skill = DynatraceSkill({"api_token": "test"})
        result = await skill.health_check()
        
        assert not result.success
        assert "URL not configured" in result.error
    
    @pytest.mark.asyncio
    async def test_health_check_no_token(self):
        """Test health check without token."""
        skill = DynatraceSkill({"url": "https://test.dynatrace.com"})
        result = await skill.health_check()
        
        assert not result.success
        assert "token not configured" in result.error


class TestGetProblems:
    """Test get_problems action."""
    
    @pytest.mark.asyncio
    async def test_get_problems_success(self, skill, mock_response):
        """Test getting problems."""
        response_data = {
            "problems": [
                {
                    "problemId": "P-123",
                    "displayId": "P-123",
                    "title": "High CPU usage",
                    "status": "OPEN",
                    "severityLevel": "PERFORMANCE",
                    "impactLevel": "SERVICE",
                    "affectedEntities": [
                        {"entityId": {"id": "HOST-1"}, "name": "host-1"}
                    ],
                    "startTime": 1705312800000,
                }
            ]
        }
        
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            
            result = await skill.get_problems()
            
            assert result.success
            assert len(result.data) == 1
            assert result.data[0].problem_id == "P-123"
            assert result.data[0].title == "High CPU usage"
            assert result.data[0].status == "OPEN"
    
    @pytest.mark.asyncio
    async def test_get_problems_with_filters(self, skill, mock_response):
        """Test getting problems with filters."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({"problems": []})
            
            await skill.get_problems(
                status="OPEN",
                impact_level="APPLICATION",
                severity_level="ERROR",
            )
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert "OPEN" in params["problemSelector"]
            assert "APPLICATION" in params["problemSelector"]
            assert "ERROR" in params["problemSelector"]
    
    @pytest.mark.asyncio
    async def test_get_problems_auth_error(self, skill, mock_response):
        """Test problems with auth error."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({}, status_code=401)
            
            result = await skill.get_problems()
            
            assert not result.success
            assert "Authentication failed" in result.error


class TestGetProblemDetails:
    """Test get_problem_details action."""
    
    @pytest.mark.asyncio
    async def test_get_problem_details_success(self, skill, mock_response):
        """Test getting problem details."""
        response_data = {
            "problemId": "P-123",
            "displayId": "P-123",
            "title": "High CPU usage",
            "status": "OPEN",
            "severityLevel": "PERFORMANCE",
            "impactLevel": "SERVICE",
            "affectedEntities": [
                {"entityId": {"id": "HOST-1"}, "name": "host-1"}
            ],
            "rootCauseEntity": {
                "entityId": {"id": "PROCESS-1", "type": "PROCESS_GROUP"},
                "name": "java-process",
            },
            "impactedEntities": [
                {"entityId": {"id": "SERVICE-1"}, "name": "api-service"}
            ],
            "evidenceDetails": {
                "details": [
                    {
                        "evidenceType": "METRIC_EVIDENCE",
                        "entity": {"name": "host-1"},
                        "data": {"metric": "cpu.usage"},
                    }
                ]
            },
        }
        
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            
            result = await skill.get_problem_details("P-123")
            
            assert result.success
            assert result.data.problem.problem_id == "P-123"
            assert result.data.root_cause_entity["name"] == "java-process"
            assert len(result.data.evidence_details) == 1
    
    @pytest.mark.asyncio
    async def test_get_problem_not_found(self, skill, mock_response):
        """Test problem not found."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({}, status_code=404)
            
            result = await skill.get_problem_details("P-999")
            
            assert not result.success
            assert "not found" in result.error.lower()


class TestGetMetrics:
    """Test get_metrics action."""
    
    @pytest.mark.asyncio
    async def test_get_metrics_success(self, skill, mock_response):
        """Test getting metrics."""
        now_ms = int(datetime.now().timestamp() * 1000)
        response_data = {
            "result": [
                {
                    "metricId": "builtin:host.cpu.usage",
                    "unit": "Percent",
                    "dimensionMap": {"0": "host"},
                    "data": [
                        {
                            "dimensions": ["HOST-1"],
                            "timestamps": [now_ms - 60000, now_ms],
                            "values": [45.5, 50.2],
                        }
                    ],
                }
            ]
        }
        
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            
            result = await skill.get_metrics("builtin:host.cpu.usage")
            
            assert result.success
            assert result.data.metric_key == "builtin:host.cpu.usage"
            assert result.data.unit == "Percent"
            assert len(result.data.series) == 1
            assert len(result.data.series[0].data_points) == 2
    
    @pytest.mark.asyncio
    async def test_get_metrics_with_entity(self, skill, mock_response):
        """Test getting metrics with entity selector."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({"result": []})
            
            await skill.get_metrics(
                "builtin:host.cpu.usage",
                entity="entityId(\"HOST-1\")",
                time_range="now-24h",
                resolution="5m",
            )
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert params["entitySelector"] == "entityId(\"HOST-1\")"
            assert params["from"] == "now-24h"
            assert params["resolution"] == "5m"


class TestGetEntities:
    """Test get_entities action."""
    
    @pytest.mark.asyncio
    async def test_get_entities_success(self, skill, mock_response):
        """Test getting entities."""
        response_data = {
            "entities": [
                {
                    "entityId": "HOST-1",
                    "displayName": "production-host-1",
                    "type": "HOST",
                    "properties": {"osType": "LINUX"},
                    "tags": [{"key": "environment"}],
                    "managementZones": [{"name": "production"}],
                },
                {
                    "entityId": "HOST-2",
                    "displayName": "production-host-2",
                    "type": "HOST",
                }
            ]
        }
        
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response(response_data)
            
            result = await skill.get_entities(type="HOST")
            
            assert result.success
            assert len(result.data) == 2
            assert result.data[0].entity_id == "HOST-1"
            assert result.data[0].display_name == "production-host-1"
            assert "environment" in result.data[0].tags
            assert "production" in result.data[0].management_zones
    
    @pytest.mark.asyncio
    async def test_get_entities_with_filter(self, skill, mock_response):
        """Test getting entities with filter."""
        with patch.object(skill.client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response({"entities": []})
            
            await skill.get_entities(
                type="SERVICE",
                filter="tag(\"environment:production\")",
                limit=50,
            )
            
            call_args = mock_get.call_args
            params = call_args[1]["params"]
            assert "SERVICE" in params["entitySelector"]
            assert "tag" in params["entitySelector"]
            assert params["pageSize"] == 50


class TestActionRegistration:
    """Test action registration."""
    
    def test_actions_registered(self, skill):
        """Test that all actions are registered."""
        actions = skill.get_actions()
        action_names = [a.name for a in actions]
        
        assert "get_problems" in action_names
        assert "get_problem_details" in action_names
        assert "get_metrics" in action_names
        assert "get_entities" in action_names
    
    def test_no_approval_required(self, skill):
        """Test that read actions don't require approval."""
        for action_def in skill.get_actions():
            assert not action_def.requires_approval


class TestTimestampParsing:
    """Test timestamp parsing."""
    
    def test_parse_valid_timestamp(self, skill):
        """Test parsing valid timestamp."""
        # 2024-01-15 10:00:00 UTC
        ts_ms = 1705312800000
        result = skill._parse_timestamp(ts_ms)
        
        assert result is not None
        assert result.year == 2024
    
    def test_parse_none_timestamp(self, skill):
        """Test parsing None timestamp."""
        result = skill._parse_timestamp(None)
        assert result is None
    
    def test_parse_invalid_timestamp(self, skill):
        """Test parsing invalid timestamp."""
        result = skill._parse_timestamp("invalid")
        assert result is None
