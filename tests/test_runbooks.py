"""
Tests for runbook indexing and matching.
"""

import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from autosre.foundation.runbooks import RunbookIndexer
from autosre.foundation.models import Runbook, Alert, Severity


class TestRunbookIndexer:
    """Tests for RunbookIndexer."""
    
    def test_init(self, context_store):
        """Test initialization with context store."""
        indexer = RunbookIndexer(context_store)
        assert indexer.context_store is context_store
    
    def test_add_runbook(self, context_store):
        """Test adding a runbook."""
        indexer = RunbookIndexer(context_store)
        
        runbook = Runbook(
            id="high-cpu",
            title="High CPU Troubleshooting",
            alert_names=["HighCPUUsage"],
            services=["api-service"],
            keywords=["cpu", "performance"],
            description="Steps for CPU issues",
            steps=["Check CPU usage", "Identify process", "Scale if needed"],
        )
        
        indexer.add_runbook(runbook)
        
        result = indexer.get_by_id("high-cpu")
        assert result is not None
        assert result.title == "High CPU Troubleshooting"
    
    def test_list_all(self, context_store):
        """Test listing all runbooks."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(id="rb-1", title="Runbook 1", description="First", alert_names=["Alert1"]))
        indexer.add_runbook(Runbook(id="rb-2", title="Runbook 2", description="Second", alert_names=["Alert2"]))
        
        all_runbooks = indexer.list_all()
        assert len(all_runbooks) == 2
    
    def test_get_by_id_found(self, context_store):
        """Test getting runbook by ID."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(id="test-rb", title="Test", description="Test runbook", alert_names=["Test"]))
        
        result = indexer.get_by_id("test-rb")
        assert result is not None
        assert result.id == "test-rb"
    
    def test_get_by_id_not_found(self, context_store):
        """Test getting nonexistent runbook."""
        indexer = RunbookIndexer(context_store)
        
        result = indexer.get_by_id("nonexistent")
        assert result is None


class TestRunbookLoading:
    """Tests for loading runbooks from files."""
    
    def test_load_yaml_runbook(self, context_store):
        """Test loading runbook from YAML file."""
        indexer = RunbookIndexer(context_store)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_content = """
id: disk-full
title: Disk Full Troubleshooting
alert_names:
  - DiskSpaceLow
  - NodeFilesystemAlmostOutOfSpace
services:
  - storage-service
keywords:
  - disk
  - storage
  - filesystem
description: Steps to resolve disk space issues
steps:
  - Check disk usage with df -h
  - Identify large files
  - Clean up logs or temp files
automated: false
requires_approval: true
author: sre-team
"""
            yaml_path = Path(tmpdir) / "disk-full.yaml"
            yaml_path.write_text(yaml_content)
            
            count = indexer.load_from_directory(tmpdir)
            
            assert count == 1
            
            rb = indexer.get_by_id("disk-full")
            assert rb is not None
            assert rb.title == "Disk Full Troubleshooting"
            assert "DiskSpaceLow" in rb.alert_names
            assert len(rb.steps) == 3
            assert rb.automated is False
    
    def test_load_markdown_runbook(self, context_store):
        """Test loading runbook from Markdown with frontmatter."""
        indexer = RunbookIndexer(context_store)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            md_content = """---
id: memory-leak
alert_names:
  - MemoryLeak
  - OOMKilled
services:
  - api
keywords:
  - memory
  - oom
description: Memory troubleshooting guide
---

# Memory Leak Troubleshooting

This guide helps resolve memory issues.

## Steps

1. Check pod memory usage
2. Review recent deployments
3. Analyze heap dumps
4. Restart if necessary
"""
            md_path = Path(tmpdir) / "memory-leak.md"
            md_path.write_text(md_content)
            
            count = indexer.load_from_directory(tmpdir)
            
            assert count == 1
            
            rb = indexer.get_by_id("memory-leak")
            assert rb is not None
            assert rb.title == "Memory Leak Troubleshooting"
            assert "MemoryLeak" in rb.alert_names
            assert len(rb.steps) == 4
    
    def test_load_multiple_runbooks(self, context_store):
        """Test loading multiple runbooks from directory."""
        indexer = RunbookIndexer(context_store)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # YAML runbook
            (Path(tmpdir) / "cpu.yaml").write_text("""
id: cpu-high
title: High CPU
description: CPU troubleshooting
alert_names:
  - HighCPU
""")
            # YML runbook
            (Path(tmpdir) / "memory.yml").write_text("""
id: memory-high
title: High Memory
description: Memory troubleshooting
alert_names:
  - HighMemory
""")
            # Markdown runbook
            (Path(tmpdir) / "network.md").write_text("""---
id: network-issue
description: Network troubleshooting
alert_names:
  - NetworkError
---
# Network Issues

1. Check connectivity
2. Review firewall rules
""")
            
            count = indexer.load_from_directory(tmpdir)
            
            assert count == 3
            assert indexer.get_by_id("cpu-high") is not None
            assert indexer.get_by_id("memory-high") is not None
            assert indexer.get_by_id("network-issue") is not None
    
    def test_load_from_subdirectories(self, context_store):
        """Test loading runbooks from nested directories."""
        indexer = RunbookIndexer(context_store)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "infrastructure"
            subdir.mkdir()
            
            (subdir / "dns.yaml").write_text("""
id: dns-issue
title: DNS Troubleshooting
description: DNS issue resolution
alert_names:
  - DNSFailure
""")
            
            count = indexer.load_from_directory(tmpdir)
            
            assert count == 1
            assert indexer.get_by_id("dns-issue") is not None
    
    def test_load_invalid_yaml(self, context_store):
        """Test handling invalid YAML files."""
        indexer = RunbookIndexer(context_store)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "invalid.yaml").write_text("invalid: yaml: content::")
            
            count = indexer.load_from_directory(tmpdir)
            
            assert count == 0  # Should skip invalid files
    
    def test_load_empty_yaml(self, context_store):
        """Test handling empty YAML files."""
        indexer = RunbookIndexer(context_store)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "empty.yaml").write_text("")
            
            count = indexer.load_from_directory(tmpdir)
            
            assert count == 0


class TestRunbookMatching:
    """Tests for runbook-to-alert matching."""
    
    def test_find_for_alert_exact_match(self, context_store):
        """Test exact alert name match."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="cpu-rb",
            title="CPU Runbook",
            description="CPU troubleshooting",
            alert_names=["HighCPUUsage"],
            services=[],
            keywords=[],
        ))
        
        alert = Alert(
            id="alert-1",
            name="HighCPUUsage",
            summary="CPU is high",
            severity=Severity.HIGH,
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 1
        assert matches[0].id == "cpu-rb"
    
    def test_find_for_alert_service_match(self, context_store):
        """Test service-based matching."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="api-rb",
            title="API Runbook",
            description="API troubleshooting",
            alert_names=[],
            services=["api-service"],
            keywords=[],
        ))
        
        alert = Alert(
            id="alert-1",
            name="SomeError",
            summary="Error occurred",
            severity=Severity.MEDIUM,
            service_name="api-service",
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 1
        assert matches[0].id == "api-rb"
    
    def test_find_for_alert_keyword_match(self, context_store):
        """Test keyword-based matching."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="latency-rb",
            title="Latency Runbook",
            description="Latency troubleshooting",
            alert_names=[],
            services=[],
            keywords=["latency", "slow", "timeout"],
        ))
        
        alert = Alert(
            id="alert-1",
            name="ServiceAlert",
            summary="High latency detected on checkout service",
            severity=Severity.HIGH,
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 1
        assert matches[0].id == "latency-rb"
    
    def test_find_for_alert_partial_name_match(self, context_store):
        """Test partial alert name matching."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="memory-rb",
            title="Memory Runbook",
            description="Memory troubleshooting",
            alert_names=["memory"],
            services=[],
            keywords=[],
        ))
        
        alert = Alert(
            id="alert-1",
            name="HighMemoryUsage",
            summary="Memory alert",
            severity=Severity.HIGH,
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 1
        assert matches[0].id == "memory-rb"
    
    def test_find_for_alert_ranking(self, context_store):
        """Test that better matches rank higher."""
        indexer = RunbookIndexer(context_store)
        
        # Exact match runbook
        indexer.add_runbook(Runbook(
            id="exact-rb",
            title="Exact Match",
            description="Exact match runbook",
            alert_names=["SpecificAlert"],
            services=[],
            keywords=[],
        ))
        
        # Keyword match runbook
        indexer.add_runbook(Runbook(
            id="keyword-rb",
            title="Keyword Match",
            description="Keyword match runbook",
            alert_names=[],
            services=[],
            keywords=["specific"],
        ))
        
        alert = Alert(
            id="alert-1",
            name="SpecificAlert",
            summary="A specific error",
            severity=Severity.HIGH,
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 2
        # Exact match should be first
        assert matches[0].id == "exact-rb"
        assert matches[1].id == "keyword-rb"
    
    def test_find_for_alert_no_match(self, context_store):
        """Test when no runbooks match."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="unrelated",
            title="Unrelated Runbook",
            description="Unrelated",
            alert_names=["DifferentAlert"],
            services=["other-service"],
            keywords=["unrelated"],
        ))
        
        alert = Alert(
            id="alert-1",
            name="NewAlert",
            summary="Something happened",
            severity=Severity.LOW,
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 0
    
    def test_find_for_alert_label_matching(self, context_store):
        """Test matching against alert labels."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="db-rb",
            title="Database Runbook",
            description="Database troubleshooting",
            alert_names=[],
            services=[],
            keywords=["postgres", "database"],
        ))
        
        alert = Alert(
            id="alert-1",
            name="GenericError",
            summary="Error",
            severity=Severity.HIGH,
            labels={"db_type": "postgres"},
        )
        
        matches = indexer.find_for_alert(alert)
        
        assert len(matches) == 1
        assert matches[0].id == "db-rb"


class TestRunbookSearch:
    """Tests for runbook search functionality."""
    
    def test_search_by_title(self, context_store):
        """Test searching by title."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="kubernetes-rb",
            title="Kubernetes Pod Troubleshooting",
            description="K8s troubleshooting",
            alert_names=[],
        ))
        indexer.add_runbook(Runbook(
            id="network-rb",
            title="Network Issues",
            description="Network troubleshooting",
            alert_names=[],
        ))
        
        results = indexer.search("kubernetes")
        
        assert len(results) == 1
        assert results[0].id == "kubernetes-rb"
    
    def test_search_by_keyword(self, context_store):
        """Test searching by keywords."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="scaling-rb",
            title="Scaling Guide",
            description="Scaling runbook",
            alert_names=[],
            keywords=["autoscaling", "hpa", "replicas"],
        ))
        
        results = indexer.search("autoscaling")
        
        assert len(results) == 1
        assert results[0].id == "scaling-rb"
    
    def test_search_case_insensitive(self, context_store):
        """Test case-insensitive search."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="ssl-rb",
            title="SSL Certificate Renewal",
            description="SSL cert renewal",
            alert_names=[],
        ))
        
        results = indexer.search("SSL")
        assert len(results) == 1
        
        results = indexer.search("ssl")
        assert len(results) == 1
    
    def test_search_no_results(self, context_store):
        """Test search with no matches."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(id="test", title="Test", description="Test runbook", alert_names=[]))
        
        results = indexer.search("nonexistent")
        
        assert len(results) == 0


class TestRunbookUsageTracking:
    """Tests for tracking runbook usage."""
    
    def test_record_successful_usage(self, context_store):
        """Test recording successful runbook usage."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="test-rb",
            title="Test",
            description="Test runbook",
            alert_names=[],
            success_rate=0.5,
        ))
        
        indexer.record_usage("test-rb", successful=True)
        
        rb = indexer.get_by_id("test-rb")
        # Success rate should increase
        assert rb.success_rate > 0.5
    
    def test_record_failed_usage(self, context_store):
        """Test recording failed runbook usage."""
        indexer = RunbookIndexer(context_store)
        
        indexer.add_runbook(Runbook(
            id="test-rb",
            title="Test",
            description="Test runbook",
            alert_names=[],
            success_rate=0.8,
        ))
        
        indexer.record_usage("test-rb", successful=False)
        
        rb = indexer.get_by_id("test-rb")
        # Success rate should decrease
        assert rb.success_rate < 0.8
    
    def test_record_usage_nonexistent_runbook(self, context_store):
        """Test recording usage for nonexistent runbook."""
        indexer = RunbookIndexer(context_store)
        
        # Should not raise
        indexer.record_usage("nonexistent", successful=True)
    
    def test_record_usage_updates_timestamp(self, context_store):
        """Test that recording usage updates last_updated."""
        indexer = RunbookIndexer(context_store)
        
        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        indexer.add_runbook(Runbook(
            id="test-rb",
            title="Test",
            description="Test runbook",
            alert_names=[],
            last_updated=old_time,
        ))
        
        indexer.record_usage("test-rb", successful=True)
        
        rb = indexer.get_by_id("test-rb")
        assert rb.last_updated > old_time
