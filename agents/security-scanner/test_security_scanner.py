"""Tests for security-scanner agent."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timedelta


@pytest.fixture
def agent_yaml():
    """Load the agent YAML configuration."""
    agent_path = Path(__file__).parent / "agent.yaml"
    with open(agent_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_trivy():
    """Mock Trivy skill."""
    mock = MagicMock()
    mock.scan_images.return_value = {
        "vulnerabilities": [
            {
                "cve_id": "CVE-2024-1234",
                "severity": "CRITICAL",
                "title": "Remote code execution",
                "cvss_score": 9.8,
                "fixed_version": "2.0.1",
                "published_date": "2024-01-01",
                "image": "nginx:1.24"
            },
            {
                "cve_id": "CVE-2024-5678",
                "severity": "HIGH",
                "title": "Information disclosure",
                "cvss_score": 7.5,
                "fixed_version": "1.2.3",
                "published_date": "2024-01-10",
                "image": "python:3.11"
            }
        ]
    }
    mock.scan_config.return_value = {
        "misconfigurations": [
            {
                "check_id": "KSV001",
                "title": "Privileged container",
                "severity": "HIGH"
            }
        ]
    }
    mock.compliance_check.return_value = {
        "CIS": {"passed": 45, "failed": 5, "score": 90},
        "PCI-DSS": {"passed": 38, "failed": 2, "score": 95},
        "overall_score": 92.5
    }
    return mock


@pytest.fixture
def mock_kubernetes():
    """Mock Kubernetes skill."""
    mock = MagicMock()
    mock.get_pods.return_value = {
        "items": [
            {
                "metadata": {"name": "api-pod", "namespace": "production"},
                "spec": {
                    "containers": [
                        {"name": "api", "image": "nginx:1.24"},
                        {"name": "sidecar", "image": "envoy:1.28"}
                    ]
                }
            },
            {
                "metadata": {"name": "worker-pod", "namespace": "production"},
                "spec": {
                    "containers": [
                        {"name": "worker", "image": "python:3.11"}
                    ]
                }
            }
        ]
    }
    mock.get_deployments.return_value = {
        "items": [
            {"metadata": {"name": "api", "namespace": "production"}},
            {"metadata": {"name": "worker", "namespace": "production"}}
        ]
    }
    return mock


class TestAgentConfiguration:
    """Test agent YAML configuration."""

    def test_agent_has_required_fields(self, agent_yaml):
        """Test that agent has all required top-level fields."""
        assert agent_yaml["name"] == "security-scanner"
        assert "description" in agent_yaml
        assert "version" in agent_yaml
        assert "triggers" in agent_yaml
        assert "skills" in agent_yaml
        assert "config" in agent_yaml
        assert "steps" in agent_yaml

    def test_triggers_configured(self, agent_yaml):
        """Test triggers are properly configured."""
        triggers = agent_yaml["triggers"]
        
        # Check schedule trigger (daily at 2 AM)
        schedule = next((t for t in triggers if t["type"] == "schedule"), None)
        assert schedule is not None
        assert schedule["cron"] == "0 2 * * *"

    def test_required_skills(self, agent_yaml):
        """Test required skills are listed."""
        skills = agent_yaml["skills"]
        assert "trivy" in skills
        assert "kubernetes" in skills
        assert "slack" in skills

    def test_severity_thresholds(self, agent_yaml):
        """Test severity thresholds are configured."""
        config = agent_yaml["config"]
        assert "severity_thresholds" in config
        thresholds = config["severity_thresholds"]
        assert "page" in thresholds
        assert "alert" in thresholds
        assert "CRITICAL" in thresholds["page"]

    def test_scan_targets(self, agent_yaml):
        """Test scan targets are configured."""
        config = agent_yaml["config"]
        assert "scan_targets" in config
        assert "namespaces" in config["scan_targets"]
        assert len(config["scan_targets"]["namespaces"]) > 0

    def test_compliance_standards(self, agent_yaml):
        """Test compliance standards are configured."""
        config = agent_yaml["config"]
        assert "compliance_standards" in config
        assert "CIS" in config["compliance_standards"]

    def test_sla_configuration(self, agent_yaml):
        """Test SLA configuration."""
        config = agent_yaml["config"]
        assert config["max_age_days_critical"] == 7
        assert config["max_age_days_high"] == 30


class TestStepDefinitions:
    """Test step definitions in the agent."""

    def test_all_steps_have_required_fields(self, agent_yaml):
        """Test all steps have name and action."""
        for step in agent_yaml["steps"]:
            assert "name" in step
            assert "action" in step

    def test_image_extraction_step(self, agent_yaml):
        """Test image extraction step exists."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "extract_unique_images"), None)
        assert step is not None
        assert step["action"] == "compute.extract"

    def test_cve_scan_step(self, agent_yaml):
        """Test CVE scanning step."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "scan_images_for_cves"), None)
        assert step is not None
        assert step["action"] == "trivy.scan_images"

    def test_config_scan_step(self, agent_yaml):
        """Test configuration scanning step."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "scan_kubernetes_config"), None)
        assert step is not None
        assert step["action"] == "trivy.scan_config"

    def test_compliance_check_step(self, agent_yaml):
        """Test compliance checking step."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "check_compliance"), None)
        assert step is not None
        assert step["action"] == "trivy.compliance_check"


class TestVulnerabilityProcessing:
    """Test vulnerability processing logic."""

    def test_severity_categorization(self):
        """Test vulnerability severity categorization."""
        vulns = [
            {"severity": "CRITICAL", "cve_id": "CVE-1"},
            {"severity": "HIGH", "cve_id": "CVE-2"},
            {"severity": "MEDIUM", "cve_id": "CVE-3"},
            {"severity": "HIGH", "cve_id": "CVE-4"},
        ]
        
        by_severity = {}
        for v in vulns:
            sev = v["severity"]
            by_severity.setdefault(sev, []).append(v)
        
        assert len(by_severity["CRITICAL"]) == 1
        assert len(by_severity["HIGH"]) == 2
        assert len(by_severity["MEDIUM"]) == 1

    def test_sla_calculation(self):
        """Test SLA violation calculation."""
        critical_sla_days = 7
        high_sla_days = 30
        
        def is_overdue(severity, published_date, today):
            days_since = (today - published_date).days
            if severity == "CRITICAL":
                return days_since > critical_sla_days
            elif severity == "HIGH":
                return days_since > high_sla_days
            return False
        
        today = datetime.now()
        
        # Critical CVE from 10 days ago - overdue
        assert is_overdue("CRITICAL", today - timedelta(days=10), today) == True
        
        # Critical CVE from 5 days ago - not overdue
        assert is_overdue("CRITICAL", today - timedelta(days=5), today) == False
        
        # High CVE from 35 days ago - overdue
        assert is_overdue("HIGH", today - timedelta(days=35), today) == True

    def test_unique_image_extraction(self):
        """Test unique image extraction from pods."""
        pods = [
            {"spec": {"containers": [
                {"image": "nginx:1.24"},
                {"image": "redis:7"}
            ]}},
            {"spec": {"containers": [
                {"image": "nginx:1.24"},  # Duplicate
                {"image": "python:3.11"}
            ]}}
        ]
        
        images = set()
        for pod in pods:
            for container in pod["spec"]["containers"]:
                images.add(container["image"])
        
        assert len(images) == 3
        assert "nginx:1.24" in images


class TestAlertConditions:
    """Test alert conditions."""

    def test_critical_alert_condition(self, agent_yaml):
        """Test critical vulnerability alert has condition."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "notify_critical_vulns"), None)
        assert step is not None
        assert "condition" in step
        assert "CRITICAL" in step["condition"]

    def test_page_condition(self, agent_yaml):
        """Test PagerDuty page condition."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "page_critical_overdue"), None)
        assert step is not None
        assert "condition" in step

    def test_compliance_alert_condition(self, agent_yaml):
        """Test compliance alert condition."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "notify_compliance_issues"), None)
        assert step is not None
        assert "condition" in step


class TestJiraIntegration:
    """Test Jira ticket creation."""

    def test_auto_ticket_step(self, agent_yaml):
        """Test auto-ticket creation step exists."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "create_vulnerability_tickets"), None)
        assert step is not None
        assert step["action"] == "jira.bulk_create"

    def test_ticket_has_condition(self, agent_yaml):
        """Test ticket creation has proper condition."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "create_vulnerability_tickets"), None)
        assert "condition" in step
        assert "enable_auto_ticket" in step["condition"]

    def test_ticket_params(self, agent_yaml):
        """Test ticket has required parameters."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "create_vulnerability_tickets"), None)
        params = step["params"]
        assert "project" in params
        assert "issue_type" in params
        assert "issues" in params


class TestComplianceScanning:
    """Test compliance scanning functionality."""

    def test_compliance_standards_scanned(self, agent_yaml):
        """Test all configured standards are scanned."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "check_compliance"), None)
        assert step is not None
        assert "standards" in step["params"]

    def test_compliance_score_calculation(self):
        """Test compliance score calculation."""
        results = {
            "CIS": {"passed": 90, "failed": 10},
            "PCI-DSS": {"passed": 95, "failed": 5}
        }
        
        for standard, data in results.items():
            total = data["passed"] + data["failed"]
            score = (data["passed"] / total) * 100
            results[standard]["score"] = score
        
        assert results["CIS"]["score"] == 90.0
        assert results["PCI-DSS"]["score"] == 95.0


class TestMetrics:
    """Test metrics pushing."""

    def test_metrics_step_exists(self, agent_yaml):
        """Test metrics pushing step exists."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        assert step is not None
        assert step["action"] == "prometheus.push_metrics"

    def test_metrics_include_vuln_counts(self, agent_yaml):
        """Test metrics include vulnerability counts."""
        step = next((s for s in agent_yaml["steps"] 
                    if s["name"] == "push_metrics"), None)
        params_str = str(step["params"])
        assert "opensre_security_vulns" in params_str


class TestIntegration:
    """Integration tests."""

    def test_full_scan_workflow(self, mock_trivy, mock_kubernetes):
        """Test full scanning workflow."""
        # Get pods
        pods = mock_kubernetes.get_pods()
        assert len(pods["items"]) == 2
        
        # Extract images
        images = set()
        for pod in pods["items"]:
            for container in pod["spec"]["containers"]:
                images.add(container["image"])
        assert len(images) == 3
        
        # Scan images
        scan_result = mock_trivy.scan_images(list(images))
        assert len(scan_result["vulnerabilities"]) == 2
        
        # Check compliance
        compliance = mock_trivy.compliance_check()
        assert compliance["CIS"]["score"] == 90

    def test_critical_vuln_triggers_alert(self, mock_trivy):
        """Test critical vulnerability triggers alert."""
        scan_result = mock_trivy.scan_images([])
        critical_vulns = [v for v in scan_result["vulnerabilities"] 
                         if v["severity"] == "CRITICAL"]
        
        # Should trigger alert when critical vulns found
        assert len(critical_vulns) > 0

    def test_overdue_vulns_trigger_page(self):
        """Test overdue vulnerabilities trigger PagerDuty."""
        today = datetime.now()
        vulns = [
            {
                "cve_id": "CVE-2024-1234",
                "severity": "CRITICAL",
                "published_date": today - timedelta(days=10)  # Overdue
            },
            {
                "cve_id": "CVE-2024-5678",
                "severity": "CRITICAL",
                "published_date": today - timedelta(days=3)  # Not overdue
            }
        ]
        
        overdue = [v for v in vulns 
                   if (today - v["published_date"]).days > 7]
        
        assert len(overdue) == 1
        assert overdue[0]["cve_id"] == "CVE-2024-1234"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
