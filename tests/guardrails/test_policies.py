"""Tests for safety policies."""

import pytest
import asyncio
from autosre.guardrails import (
    SafetyPolicy,
    PolicyEngine,
    PolicyResult,
    PolicyAction,
    RiskLevel,
    ActionCategory,
    ActionPolicy,
    ActionRestriction,
    RateLimitConfig,
    RateLimiter,
)
from autosre.guardrails.policies import create_default_policy


class TestSafetyPolicy:
    """Tests for SafetyPolicy."""
    
    @pytest.fixture
    def basic_policy(self):
        """Create a basic safety policy."""
        return SafetyPolicy(
            id="test-policy",
            name="Test Policy",
            description="A test safety policy",
        )
    
    def test_policy_creation(self, basic_policy):
        """Test that a policy can be created."""
        assert basic_policy.id == "test-policy"
        assert basic_policy.name == "Test Policy"
        assert basic_policy.enabled is True
    
    def test_default_policy_creation(self):
        """Test creating default policies for different environments."""
        dev_policy = create_default_policy(environment="development")
        prod_policy = create_default_policy(environment="production")
        strict_policy = create_default_policy(environment="production", strict=True)
        
        assert dev_policy.id == "default-development"
        assert prod_policy.id == "default-production"
        assert prod_policy.production_restrictions is True
        assert strict_policy.require_approval_for_risk == RiskLevel.MEDIUM


class TestPolicyEngine:
    """Tests for PolicyEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create a policy engine with default policy."""
        policy = create_default_policy(environment="production")
        return PolicyEngine(policy=policy)
    
    @pytest.fixture
    def strict_engine(self):
        """Create a strict policy engine."""
        policy = create_default_policy(environment="production", strict=True)
        return PolicyEngine(policy=policy)
    
    @pytest.mark.asyncio
    async def test_allow_read_action(self, engine):
        """Test that read actions are evaluated with appropriate risk."""
        result = await engine.evaluate(
            action=ActionCategory.READ,
            target="metrics",
            context={"environment": "production", "user_id": "user123"},
        )
        
        # Read action in production should not be denied, but may require confirmation
        assert result.action != PolicyAction.DENY
        assert result.risk_assessment is not None
    
    @pytest.mark.asyncio
    async def test_high_risk_action_requires_approval(self, engine):
        """Test that high-risk actions require approval."""
        result = await engine.evaluate(
            action=ActionCategory.DELETE,
            target="production-service",
            context={"environment": "production", "user_id": "user123"},
        )
        
        # Delete in production should require approval or be denied
        assert result.action in (
            PolicyAction.REQUIRE_APPROVAL,
            PolicyAction.REQUIRE_MULTI_APPROVAL,
            PolicyAction.DENY,
        )
    
    @pytest.mark.asyncio
    async def test_environment_restriction(self, engine):
        """Test that invalid environments are blocked."""
        result = await engine.evaluate(
            action=ActionCategory.READ,
            target="metrics",
            context={"environment": "invalid-env", "user_id": "user123"},
        )
        
        assert result.action == PolicyAction.DENY
        assert "not allowed" in result.reason
    
    @pytest.mark.asyncio
    async def test_risk_assessment(self, engine):
        """Test that risk assessment is performed."""
        result = await engine.evaluate(
            action=ActionCategory.DEPLOY,
            target="critical-service",
            context={"environment": "production", "user_id": "user123"},
        )
        
        assert result.risk_assessment is not None
        assert result.risk_assessment.level in list(RiskLevel)
        assert 0.0 <= result.risk_assessment.score <= 1.0
    
    def test_update_policy(self, engine):
        """Test policy can be updated."""
        new_policy = SafetyPolicy(id="new-policy", name="New Policy")
        engine.set_policy(new_policy)
        
        assert engine.get_policy().id == "new-policy"


class TestRateLimiter:
    """Tests for RateLimiter."""
    
    @pytest.fixture
    def limiter(self):
        """Create a rate limiter."""
        config = RateLimitConfig(
            id="test-limiter",
            name="Test Limiter",
            requests_per_minute=10,
            requests_per_hour=100,
        )
        return RateLimiter(config)
    
    def test_allow_under_limit(self, limiter):
        """Test that requests under the limit are allowed."""
        allowed, reason = limiter.check("user123")
        assert allowed is True
        assert reason is None
    
    def test_block_over_limit(self, limiter):
        """Test that requests over the limit are blocked."""
        # Make requests up to the limit
        for _ in range(10):
            limiter.check("user123")
        
        # Next request should be blocked
        allowed, reason = limiter.check("user123")
        assert allowed is False
        assert "Rate limit exceeded" in reason
    
    def test_separate_users(self, limiter):
        """Test that rate limits are per-user."""
        # Exhaust limit for user1
        for _ in range(10):
            limiter.check("user1")
        
        # User2 should still be allowed
        allowed, reason = limiter.check("user2")
        assert allowed is True
    
    def test_get_usage(self, limiter):
        """Test getting usage statistics."""
        for _ in range(5):
            limiter.check("user123")
        
        usage = limiter.get_usage("user123")
        assert "requests_per_minute" in usage
        assert usage["requests_per_minute"]["current"] == 5
    
    def test_reset(self, limiter):
        """Test resetting rate limits."""
        for _ in range(10):
            limiter.check("user123")
        
        limiter.reset("user123")
        
        allowed, reason = limiter.check("user123")
        assert allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
