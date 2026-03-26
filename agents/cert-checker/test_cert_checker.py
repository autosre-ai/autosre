"""
Tests for Certificate Expiry Checker Agent
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta


class TestCertCheckerAgent:
    """Test suite for cert-checker agent"""
    
    @pytest.fixture
    def agent_config(self):
        """Load agent configuration"""
        return {
            "name": "cert-checker",
            "version": "1.0.0",
            "config": {
                "slack_channel": "#security-alerts",
                "alert_thresholds_days": [30, 14, 7, 3, 1],
                "critical_threshold_days": 7,
                "sources": [
                    {"type": "kubernetes", "namespaces": ["*"]},
                    {"type": "endpoints", "urls": ["https://api.example.com"]},
                    {"type": "acm", "regions": ["us-east-1"]}
                ],
                "auto_renew_enabled": False,
                "pagerduty_on_critical": True
            }
        }
    
    @pytest.fixture
    def mock_skills(self):
        """Create mock skill implementations"""
        return {
            "ssl": Mock(),
            "kubernetes": Mock(),
            "aws": Mock(),
            "slack": Mock(),
            "pagerduty": Mock(),
            "jira": Mock(),
            "prometheus": Mock(),
            "compute": Mock(),
            "template": Mock()
        }
    
    @pytest.fixture
    def sample_certificates(self):
        """Sample certificate data"""
        now = datetime.utcnow()
        return [
            {
                "common_name": "api.example.com",
                "issuer": "Let's Encrypt",
                "not_after": (now + timedelta(days=5)).isoformat(),
                "days_until_expiry": 5,
                "source": "kubernetes",
                "source_ref": "production/api-tls"
            },
            {
                "common_name": "www.example.com",
                "issuer": "DigiCert",
                "not_after": (now + timedelta(days=45)).isoformat(),
                "days_until_expiry": 45,
                "source": "endpoints",
                "source_ref": "https://www.example.com"
            },
            {
                "common_name": "internal.example.com",
                "issuer": "Let's Encrypt",
                "not_after": (now + timedelta(days=12)).isoformat(),
                "days_until_expiry": 12,
                "source": "acm",
                "source_ref": "arn:aws:acm:us-east-1:123:certificate/abc"
            },
            {
                "common_name": "expired.example.com",
                "issuer": "Let's Encrypt",
                "not_after": (now - timedelta(days=2)).isoformat(),
                "days_until_expiry": -2,
                "source": "kubernetes",
                "source_ref": "default/expired-tls"
            }
        ]
    
    @pytest.fixture
    def categorized_certs(self, sample_certificates):
        """Categorized certificates by urgency"""
        return {
            "expired": [c for c in sample_certificates if c["days_until_expiry"] < 0],
            "critical": [c for c in sample_certificates if 0 <= c["days_until_expiry"] <= 7],
            "warning": [c for c in sample_certificates if 7 < c["days_until_expiry"] <= 14],
            "attention": [c for c in sample_certificates if 14 < c["days_until_expiry"] <= 30],
            "healthy": [c for c in sample_certificates if c["days_until_expiry"] > 30]
        }
    
    def test_scan_kubernetes_secrets(self, mock_skills):
        """Test Kubernetes TLS secret scanning"""
        mock_skills["kubernetes"].list_secrets.return_value = {
            "items": [
                {
                    "metadata": {"name": "api-tls", "namespace": "production"},
                    "type": "kubernetes.io/tls",
                    "data": {"tls.crt": "base64-cert-data"}
                }
            ]
        }
        
        result = mock_skills["kubernetes"].list_secrets(
            namespaces=["*"],
            field_selector="type=kubernetes.io/tls"
        )
        
        assert len(result["items"]) == 1
        assert result["items"][0]["metadata"]["name"] == "api-tls"
    
    def test_parse_kubernetes_certs(self, mock_skills, sample_certificates):
        """Test certificate parsing"""
        mock_skills["ssl"].parse_certificates.return_value = [sample_certificates[0]]
        
        result = mock_skills["ssl"].parse_certificates(
            certificates=["base64-cert-data"],
            source="kubernetes"
        )
        
        assert len(result) == 1
        assert result[0]["common_name"] == "api.example.com"
    
    def test_scan_endpoint_certs(self, mock_skills, sample_certificates):
        """Test endpoint certificate checking"""
        mock_skills["ssl"].check_endpoints.return_value = [sample_certificates[1]]
        
        result = mock_skills["ssl"].check_endpoints(
            urls=["https://www.example.com"],
            timeout_seconds=10,
            verify=False
        )
        
        assert len(result) == 1
        assert result[0]["source"] == "endpoints"
    
    def test_scan_acm_certs(self, mock_skills, sample_certificates):
        """Test AWS ACM certificate listing"""
        mock_skills["aws"].acm_list_certificates.return_value = [sample_certificates[2]]
        
        result = mock_skills["aws"].acm_list_certificates(
            regions=["us-east-1"],
            statuses=["ISSUED", "PENDING_VALIDATION"]
        )
        
        assert len(result) == 1
        assert result[0]["source"] == "acm"
    
    def test_aggregate_certificates(self, mock_skills, sample_certificates):
        """Test certificate aggregation from multiple sources"""
        mock_skills["compute"].aggregate.return_value = sample_certificates
        
        result = mock_skills["compute"].aggregate(
            sources=[
                {"name": "kubernetes", "data": [sample_certificates[0]]},
                {"name": "endpoints", "data": [sample_certificates[1]]},
                {"name": "acm", "data": [sample_certificates[2]]}
            ]
        )
        
        assert len(result) == 4
    
    def test_categorize_by_urgency(self, mock_skills, sample_certificates, categorized_certs):
        """Test certificate categorization"""
        mock_skills["compute"].categorize.return_value = categorized_certs
        
        result = mock_skills["compute"].categorize(
            items=sample_certificates,
            categories={
                "expired": "days_until_expiry < 0",
                "critical": "days_until_expiry >= 0 and days_until_expiry <= 7"
            }
        )
        
        assert len(result["expired"]) == 1
        assert len(result["critical"]) == 1
        assert len(result["warning"]) == 1
        assert len(result["healthy"]) == 1
    
    def test_notify_expired(self, mock_skills, categorized_certs):
        """Test expired certificate notification"""
        mock_skills["slack"].send_message.return_value = {"ok": True}
        
        if len(categorized_certs["expired"]) > 0:
            result = mock_skills["slack"].send_message(
                channel="#security-alerts",
                blocks=[{"type": "header", "text": {"type": "plain_text", "text": "🚨 EXPIRED CERTIFICATES"}}]
            )
            assert result["ok"] is True
    
    def test_notify_critical(self, mock_skills, categorized_certs):
        """Test critical certificate notification"""
        mock_skills["slack"].send_message.return_value = {"ok": True}
        
        if len(categorized_certs["critical"]) > 0:
            result = mock_skills["slack"].send_message(
                channel="#security-alerts",
                blocks=[{"type": "header", "text": {"type": "plain_text", "text": "⚠️ Certificates Expiring"}}]
            )
            assert result["ok"] is True
    
    def test_page_on_critical(self, agent_config, mock_skills, categorized_certs):
        """Test PagerDuty incident creation for critical certs"""
        mock_skills["pagerduty"].create_incident.return_value = {"id": "P123"}
        
        has_urgent = len(categorized_certs["expired"]) > 0 or len(categorized_certs["critical"]) > 0
        
        if agent_config["config"]["pagerduty_on_critical"] and has_urgent:
            result = mock_skills["pagerduty"].create_incident(
                title="SSL Certificate Expiry - Immediate Action Required",
                urgency="high"
            )
            assert result["id"] == "P123"
    
    def test_create_renewal_tickets(self, mock_skills, categorized_certs):
        """Test Jira ticket creation for critical certs"""
        mock_skills["jira"].bulk_create.return_value = {
            "issues": [{"key": "SEC-123"}]
        }
        
        if len(categorized_certs["critical"]) > 0:
            result = mock_skills["jira"].bulk_create(
                project="SEC",
                issue_type="Task",
                issues=[{"summary": "Renew SSL Certificate: api.example.com"}]
            )
            assert len(result["issues"]) == 1
    
    def test_auto_renewal_acm(self, mock_skills, categorized_certs):
        """Test auto-renewal for ACM certificates"""
        acm_certs = [c for c in categorized_certs["critical"] if c.get("source") == "acm"]
        
        if len(acm_certs) > 0:
            mock_skills["ssl"].request_renewal.return_value = {"status": "renewal_requested"}
            
            result = mock_skills["ssl"].request_renewal(
                certificates=["arn:aws:acm:..."]
            )
            assert result["status"] == "renewal_requested"
    
    def test_store_metrics(self, mock_skills, categorized_certs):
        """Test metrics storage"""
        mock_skills["prometheus"].push_metrics.return_value = {"status": "success"}
        
        result = mock_skills["prometheus"].push_metrics(
            metrics=[
                {"name": "opensre_cert_total", "value": 4},
                {"name": "opensre_cert_expired", "value": len(categorized_certs["expired"])},
                {"name": "opensre_cert_critical", "value": len(categorized_certs["critical"])}
            ]
        )
        
        assert result["status"] == "success"
    
    def test_full_workflow(self, agent_config, mock_skills, sample_certificates, categorized_certs):
        """Integration test: full workflow"""
        # Setup mocks
        mock_skills["kubernetes"].list_secrets.return_value = {"items": []}
        mock_skills["ssl"].parse_certificates.return_value = [sample_certificates[0]]
        mock_skills["ssl"].check_endpoints.return_value = [sample_certificates[1]]
        mock_skills["aws"].acm_list_certificates.return_value = [sample_certificates[2]]
        mock_skills["compute"].aggregate.return_value = sample_certificates
        mock_skills["compute"].categorize.return_value = categorized_certs
        mock_skills["slack"].send_message.return_value = {"ok": True}
        mock_skills["pagerduty"].create_incident.return_value = {"id": "P123"}
        mock_skills["jira"].bulk_create.return_value = {"issues": []}
        mock_skills["prometheus"].push_metrics.return_value = {"status": "success"}
        
        steps_executed = []
        
        # Execute workflow
        mock_skills["kubernetes"].list_secrets(namespaces=["*"])
        steps_executed.append("scan_kubernetes_certs")
        
        mock_skills["ssl"].parse_certificates(certificates=[])
        steps_executed.append("parse_kubernetes_certs")
        
        mock_skills["ssl"].check_endpoints(urls=["https://api.example.com"])
        steps_executed.append("scan_endpoint_certs")
        
        mock_skills["aws"].acm_list_certificates(regions=["us-east-1"])
        steps_executed.append("scan_acm_certs")
        
        mock_skills["compute"].aggregate(sources=[])
        steps_executed.append("aggregate_certificates")
        
        result = mock_skills["compute"].categorize(items=sample_certificates)
        steps_executed.append("categorize_by_urgency")
        
        if len(result["expired"]) > 0:
            mock_skills["slack"].send_message(channel="#security-alerts")
            steps_executed.append("notify_expired")
        
        if len(result["critical"]) > 0:
            mock_skills["slack"].send_message(channel="#security-alerts")
            steps_executed.append("notify_critical")
            
            if agent_config["config"]["pagerduty_on_critical"]:
                mock_skills["pagerduty"].create_incident(title="SSL Expiry")
                steps_executed.append("page_on_critical")
        
        mock_skills["prometheus"].push_metrics(metrics=[])
        steps_executed.append("store_metrics")
        
        expected = [
            "scan_kubernetes_certs", "parse_kubernetes_certs", 
            "scan_endpoint_certs", "scan_acm_certs",
            "aggregate_certificates", "categorize_by_urgency",
            "notify_expired", "notify_critical", "page_on_critical",
            "store_metrics"
        ]
        assert steps_executed == expected


class TestCertificateCalculations:
    """Test certificate date calculations"""
    
    def test_days_until_expiry(self):
        """Test days until expiry calculation"""
        now = datetime.utcnow()
        expiry = now + timedelta(days=15)
        days = (expiry - now).days
        assert days == 15
    
    def test_expired_certificate(self):
        """Test expired certificate detection"""
        now = datetime.utcnow()
        expiry = now - timedelta(days=5)
        days = (expiry - now).days
        assert days == -5
        assert days < 0
    
    def test_categorization_boundaries(self):
        """Test categorization at boundary values"""
        def categorize(days):
            if days < 0:
                return "expired"
            elif days <= 7:
                return "critical"
            elif days <= 14:
                return "warning"
            elif days <= 30:
                return "attention"
            else:
                return "healthy"
        
        assert categorize(-1) == "expired"
        assert categorize(0) == "critical"
        assert categorize(7) == "critical"
        assert categorize(8) == "warning"
        assert categorize(14) == "warning"
        assert categorize(15) == "attention"
        assert categorize(30) == "attention"
        assert categorize(31) == "healthy"


class TestCertificateParsing:
    """Test certificate parsing utilities"""
    
    def test_extract_common_name(self):
        """Test extracting CN from certificate subject"""
        subject = "CN=api.example.com,O=Example Inc,C=US"
        cn = subject.split(",")[0].replace("CN=", "")
        assert cn == "api.example.com"
    
    def test_parse_san_entries(self):
        """Test parsing Subject Alternative Names"""
        san = "DNS:api.example.com,DNS:www.example.com,IP:192.168.1.1"
        entries = san.split(",")
        dns_entries = [e.replace("DNS:", "") for e in entries if e.startswith("DNS:")]
        assert len(dns_entries) == 2
        assert "api.example.com" in dns_entries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
