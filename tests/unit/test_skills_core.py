"""Tests for opensre_core.skills module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from opensre_core.skills import (
    ActionResult,
    ActionDefinition,
    Skill,
    SkillRegistry,
    action,
    registry,
)


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_ok_creates_successful_result(self):
        """Test ActionResult.ok() creates a success result."""
        result = ActionResult.ok({"value": 42})
        assert result.success is True
        assert result.data == {"value": 42}
        assert result.error is None

    def test_ok_with_metadata(self):
        """Test ActionResult.ok() accepts metadata."""
        result = ActionResult.ok("data", source="test", count=5)
        assert result.success is True
        assert result.metadata == {"source": "test", "count": 5}

    def test_fail_creates_failed_result(self):
        """Test ActionResult.fail() creates a failure result."""
        result = ActionResult.fail("Connection timeout")
        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.data is None

    def test_fail_with_metadata(self):
        """Test ActionResult.fail() accepts metadata."""
        result = ActionResult.fail("Error", retry_count=3)
        assert result.metadata == {"retry_count": 3}


class TestActionDefinition:
    """Tests for ActionDefinition dataclass."""

    def test_basic_creation(self):
        """Test creating an ActionDefinition."""
        handler = AsyncMock()
        defn = ActionDefinition(
            name="test_action",
            description="A test action",
            handler=handler,
        )
        assert defn.name == "test_action"
        assert defn.description == "A test action"
        assert defn.handler is handler
        assert defn.params == []
        assert defn.returns == "Any"
        assert defn.requires_approval is False

    def test_with_params(self):
        """Test ActionDefinition with parameters."""
        defn = ActionDefinition(
            name="query",
            description="Run a query",
            handler=AsyncMock(),
            params=[{"name": "promql", "type": "str", "required": True}],
            returns="list[dict]",
            requires_approval=True,
        )
        assert len(defn.params) == 1
        assert defn.params[0]["name"] == "promql"
        assert defn.requires_approval is True


class MockSkill(Skill):
    """Mock skill for testing."""

    name = "mock"
    version = "1.0.0"
    description = "A mock skill for testing"

    async def health_check(self):
        return ActionResult.ok({"status": "healthy"})


class TestSkill:
    """Tests for Skill base class."""

    def test_skill_initialization(self):
        """Test skill initializes with config."""
        config = {"url": "http://localhost:9090"}
        skill = MockSkill(config)
        assert skill.config == config
        assert skill._initialized is False

    @pytest.mark.asyncio
    async def test_skill_initialize(self):
        """Test skill.initialize() sets initialized flag."""
        skill = MockSkill()
        await skill.initialize()
        assert skill._initialized is True

    @pytest.mark.asyncio
    async def test_skill_shutdown(self):
        """Test skill.shutdown() clears initialized flag."""
        skill = MockSkill()
        await skill.initialize()
        await skill.shutdown()
        assert skill._initialized is False

    def test_register_action(self):
        """Test registering an action."""
        skill = MockSkill()
        handler = AsyncMock()

        skill.register_action(
            name="custom_action",
            handler=handler,
            description="A custom action",
            requires_approval=True,
        )

        actions = skill.get_actions()
        assert len(actions) == 1
        assert actions[0].name == "custom_action"
        assert actions[0].requires_approval is True

    def test_get_action(self):
        """Test getting a specific action."""
        skill = MockSkill()
        skill.register_action("action1", AsyncMock())
        skill.register_action("action2", AsyncMock())

        action = skill.get_action("action1")
        assert action is not None
        assert action.name == "action1"

    def test_get_action_not_found(self):
        """Test getting non-existent action returns None."""
        skill = MockSkill()
        assert skill.get_action("nonexistent") is None

    @pytest.mark.asyncio
    async def test_invoke_action(self):
        """Test invoking a registered action."""
        skill = MockSkill()
        handler = AsyncMock(return_value={"result": "success"})
        skill.register_action("my_action", handler)

        result = await skill.invoke("my_action", param1="value1")

        handler.assert_called_once_with(param1="value1")
        assert result.success is True
        assert result.data == {"result": "success"}

    @pytest.mark.asyncio
    async def test_invoke_action_with_action_result(self):
        """Test invoking action that returns ActionResult."""
        skill = MockSkill()
        handler = AsyncMock(return_value=ActionResult.ok("data"))
        skill.register_action("my_action", handler)

        result = await skill.invoke("my_action")

        assert result.success is True
        assert result.data == "data"

    @pytest.mark.asyncio
    async def test_invoke_unknown_action(self):
        """Test invoking unknown action returns failure."""
        skill = MockSkill()

        result = await skill.invoke("unknown_action")

        assert result.success is False
        assert "Unknown action" in result.error

    @pytest.mark.asyncio
    async def test_invoke_action_exception(self):
        """Test invoking action that raises exception."""
        skill = MockSkill()
        handler = AsyncMock(side_effect=ValueError("Test error"))
        skill.register_action("failing_action", handler)

        result = await skill.invoke("failing_action")

        assert result.success is False
        assert "Test error" in result.error

    def test_skill_repr(self):
        """Test skill string representation."""
        skill = MockSkill()
        repr_str = repr(skill)
        assert "MockSkill" in repr_str
        assert "mock" in repr_str
        assert "1.0.0" in repr_str


class TestActionDecorator:
    """Tests for @action decorator."""

    def test_action_decorator_basic(self):
        """Test @action decorator adds metadata."""

        class TestSkill(Skill):
            name = "test"

            @action(description="Query something")
            async def query(self, promql: str):
                pass

            async def health_check(self):
                return ActionResult.ok({})

        # Check metadata was added
        assert hasattr(TestSkill.query, "_action_metadata")
        metadata = TestSkill.query._action_metadata
        assert metadata["name"] == "query"
        assert metadata["description"] == "Query something"
        assert metadata["requires_approval"] is False

    def test_action_decorator_with_custom_name(self):
        """Test @action decorator with custom name."""

        class TestSkill(Skill):
            name = "test"

            @action(name="custom_query", requires_approval=True)
            async def query(self, promql: str):
                pass

            async def health_check(self):
                return ActionResult.ok({})

        metadata = TestSkill.query._action_metadata
        assert metadata["name"] == "custom_query"
        assert metadata["requires_approval"] is True


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_register_skill(self):
        """Test registering a skill class."""
        reg = SkillRegistry()
        reg.register(MockSkill)

        assert "mock" in reg.list_skills()
        assert reg.get("mock") is MockSkill

    def test_get_unknown_skill(self):
        """Test getting unknown skill returns None."""
        reg = SkillRegistry()
        assert reg.get("unknown") is None

    @pytest.mark.asyncio
    async def test_get_instance(self):
        """Test getting a skill instance."""
        reg = SkillRegistry()
        reg.register(MockSkill)

        config = {"url": "http://test"}
        instance = await reg.get_instance("mock", config)

        assert instance is not None
        assert isinstance(instance, MockSkill)
        assert instance.config == config
        assert instance._initialized is True

    @pytest.mark.asyncio
    async def test_get_instance_cached(self):
        """Test skill instances are cached."""
        reg = SkillRegistry()
        reg.register(MockSkill)

        instance1 = await reg.get_instance("mock")
        instance2 = await reg.get_instance("mock")

        assert instance1 is instance2

    @pytest.mark.asyncio
    async def test_get_instance_unknown(self):
        """Test getting instance of unknown skill returns None."""
        reg = SkillRegistry()
        instance = await reg.get_instance("unknown")
        assert instance is None

    def test_list_skills(self):
        """Test listing registered skills."""
        reg = SkillRegistry()
        reg.register(MockSkill)

        class AnotherSkill(Skill):
            name = "another"
            async def health_check(self):
                return ActionResult.ok({})

        reg.register(AnotherSkill)

        skills = reg.list_skills()
        assert "mock" in skills
        assert "another" in skills
        assert len(skills) == 2

    @pytest.mark.asyncio
    async def test_shutdown_all(self):
        """Test shutting down all skill instances."""
        reg = SkillRegistry()
        reg.register(MockSkill)

        instance = await reg.get_instance("mock")
        assert instance._initialized is True

        await reg.shutdown_all()

        # Instance should be shut down and cleared from cache
        assert instance._initialized is False
        assert len(reg._instances) == 0


class TestGlobalRegistry:
    """Tests for global skill registry."""

    def test_global_registry_exists(self):
        """Test global registry is available."""
        assert registry is not None
        assert isinstance(registry, SkillRegistry)
