"""Tests for the SRE skills system."""

import json
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add the project root to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.skills.base import ToolResult, SREToolError
from src.agent.skills.kubernetes import KubernetesTools
from src.agent.skills.metrics import MetricsTools
from src.agent.skills.logs import LogsTools
from src.agent.skills.aws import AWSTools
from src.agent.skills.traces import TracesTools
from src.agent.skills import (
    get_all_tools,
    resolve_tools,
    make_load_skill,
    make_run_script,
    get_skill_catalog,
)


class TestToolResult:
    """Tests for ToolResult dataclass."""
    
    def test_success_result(self):
        result = ToolResult(success=True, data={"key": "value"})
        assert result.success
        assert result.data == {"key": "value"}
        assert result.error is None
    
    def test_error_result(self):
        result = ToolResult(success=False, error="Something went wrong")
        assert not result.success
        assert result.error == "Something went wrong"
    
    def test_str_representation(self):
        result = ToolResult(success=True, data={"count": 5})
        output = str(result)
        assert "count" in output
        assert "5" in output
    
    def test_error_str_representation(self):
        result = ToolResult(success=False, error="Connection failed")
        output = str(result)
        assert "Error: Connection failed" in output


class TestKubernetesTools:
    """Tests for Kubernetes tools."""
    
    def test_mock_mode_list_pods(self):
        k8s = KubernetesTools(mock_mode=True)
        tools = k8s.get_tools()
        list_pods = next(t for t in tools if t.name == "list_pods")
        
        result = list_pods.invoke({"namespace": "default"})
        data = json.loads(result)
        
        assert "pods" in data
        assert isinstance(data["pods"], list)
    
    def test_mock_mode_get_pod_logs(self):
        k8s = KubernetesTools(mock_mode=True)
        tools = k8s.get_tools()
        get_logs = next(t for t in tools if t.name == "get_pod_logs")
        
        result = get_logs.invoke({"pod_name": "test-pod"})
        assert isinstance(result, str)
        assert "Mock log" in result
    
    def test_custom_mock_response(self):
        k8s = KubernetesTools(mock_mode=True)
        k8s.set_mock_response("list_pods", {
            "pods": [{"name": "custom-pod", "phase": "Running"}]
        })
        
        tools = k8s.get_tools()
        list_pods = next(t for t in tools if t.name == "list_pods")
        
        result = list_pods.invoke({})
        data = json.loads(result)
        
        assert data["pods"][0]["name"] == "custom-pod"
    
    def test_tool_count(self):
        k8s = KubernetesTools(mock_mode=True)
        tools = k8s.get_tools()
        
        expected_tools = [
            "list_pods", "get_pod_logs", "describe_pod",
            "get_deployments", "get_services", "get_events", "get_node_status"
        ]
        tool_names = [t.name for t in tools]
        
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestMetricsTools:
    """Tests for metrics tools."""
    
    def test_mock_mode_query_prometheus(self):
        metrics = MetricsTools(mock_mode=True)
        tools = metrics.get_tools()
        query_prom = next(t for t in tools if t.name == "query_prometheus")
        
        result = query_prom.invoke({"query": "up"})
        data = json.loads(result)
        
        assert data["status"] == "success"
        assert "data" in data
    
    def test_mock_mode_query_datadog(self):
        metrics = MetricsTools(mock_mode=True)
        tools = metrics.get_tools()
        query_dd = next(t for t in tools if t.name == "query_datadog")
        
        result = query_dd.invoke({"query": "avg:system.cpu.user{*}"})
        data = json.loads(result)
        
        assert "series" in data
    
    def test_tool_count(self):
        metrics = MetricsTools(mock_mode=True)
        tools = metrics.get_tools()
        
        expected_tools = ["query_prometheus", "query_datadog", "query_grafana"]
        tool_names = [t.name for t in tools]
        
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestLogsTools:
    """Tests for log tools."""
    
    def test_mock_mode_search_elasticsearch(self):
        logs = LogsTools(mock_mode=True)
        tools = logs.get_tools()
        search_es = next(t for t in tools if t.name == "search_elasticsearch")
        
        result = search_es.invoke({"query": "error"})
        data = json.loads(result)
        
        assert "hits" in data
        assert isinstance(data["hits"], list)
    
    def test_mock_mode_search_loki(self):
        logs = LogsTools(mock_mode=True)
        tools = logs.get_tools()
        search_loki = next(t for t in tools if t.name == "search_loki")
        
        result = search_loki.invoke({"query": '{app="nginx"}'})
        data = json.loads(result)
        
        assert "result" in data
    
    def test_tool_count(self):
        logs = LogsTools(mock_mode=True)
        tools = logs.get_tools()
        
        expected_tools = ["search_elasticsearch", "search_loki", "tail_logs"]
        tool_names = [t.name for t in tools]
        
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestAWSTools:
    """Tests for AWS tools."""
    
    def test_mock_mode_describe_ec2(self):
        aws = AWSTools(mock_mode=True)
        tools = aws.get_tools()
        describe_ec2 = next(t for t in tools if t.name == "describe_ec2")
        
        result = describe_ec2.invoke({})
        data = json.loads(result)
        
        assert "instances" in data
        assert isinstance(data["instances"], list)
    
    def test_mock_mode_describe_rds(self):
        aws = AWSTools(mock_mode=True)
        tools = aws.get_tools()
        describe_rds = next(t for t in tools if t.name == "describe_rds")
        
        result = describe_rds.invoke({})
        data = json.loads(result)
        
        assert "instances" in data
    
    def test_tool_count(self):
        aws = AWSTools(mock_mode=True)
        tools = aws.get_tools()
        
        expected_tools = [
            "describe_ec2", "describe_rds", 
            "get_cloudwatch_metrics", "describe_ecs_services"
        ]
        tool_names = [t.name for t in tools]
        
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestTracesTools:
    """Tests for tracing tools."""
    
    def test_mock_mode_search_jaeger(self):
        traces = TracesTools(mock_mode=True)
        tools = traces.get_tools()
        search_jaeger = next(t for t in tools if t.name == "search_jaeger")
        
        result = search_jaeger.invoke({"service": "api"})
        data = json.loads(result)
        
        assert "traces" in data
    
    def test_mock_mode_get_trace(self):
        traces = TracesTools(mock_mode=True)
        tools = traces.get_tools()
        get_trace = next(t for t in tools if t.name == "get_trace")
        
        result = get_trace.invoke({"trace_id": "abc123"})
        data = json.loads(result)
        
        assert "traceID" in data
        assert "spans" in data
    
    def test_tool_count(self):
        traces = TracesTools(mock_mode=True)
        tools = traces.get_tools()
        
        expected_tools = ["search_jaeger", "get_trace"]
        tool_names = [t.name for t in tools]
        
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"


class TestGetAllTools:
    """Tests for get_all_tools function."""
    
    def test_returns_all_tools_by_default(self):
        tools = get_all_tools(mock_mode=True)
        
        # Should have tools from all 5 skill areas
        tool_names = [t.name for t in tools]
        
        # Kubernetes tools
        assert "list_pods" in tool_names
        # Metrics tools
        assert "query_prometheus" in tool_names
        # Logs tools
        assert "search_elasticsearch" in tool_names
        # AWS tools
        assert "describe_ec2" in tool_names
        # Traces tools
        assert "search_jaeger" in tool_names
    
    def test_filter_by_enabled_skills(self):
        tools = get_all_tools(
            mock_mode=True,
            enabled_skills={"kubernetes", "metrics"}
        )
        
        tool_names = [t.name for t in tools]
        
        # Should have kubernetes and metrics tools
        assert "list_pods" in tool_names
        assert "query_prometheus" in tool_names
        
        # Should NOT have logs, aws, traces tools
        assert "search_elasticsearch" not in tool_names
        assert "describe_ec2" not in tool_names
        assert "search_jaeger" not in tool_names


class TestSkillCatalog:
    """Tests for skill catalog generation."""
    
    def test_includes_all_skills_by_default(self):
        catalog = get_skill_catalog()
        
        assert "kubernetes" in catalog
        assert "metrics" in catalog
        assert "logs" in catalog
        assert "aws" in catalog
        assert "traces" in catalog
    
    def test_filter_by_enabled_skills(self):
        catalog = get_skill_catalog(enabled_skills={"kubernetes"})
        
        assert "kubernetes" in catalog
        assert "metrics" not in catalog


class TestResolveTools:
    """Tests for resolve_tools function."""
    
    def test_resolves_native_tools(self):
        tools = resolve_tools(
            agent_name="test-agent",
            mock_mode=True,
            include_native_tools=True,
        )
        
        # Should have native tools
        tool_names = [t.name for t in tools]
        assert "list_pods" in tool_names
    
    def test_respects_enabled_skills(self):
        tools = resolve_tools(
            agent_name="test-agent",
            enabled_skills={"kubernetes"},
            mock_mode=True,
        )
        
        tool_names = [t.name for t in tools]
        
        # Should have kubernetes tools
        assert "list_pods" in tool_names
        
        # Should NOT have other tools
        assert "describe_ec2" not in tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
