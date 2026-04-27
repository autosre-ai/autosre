"""
Tests for skills base class and registry.
"""

import pytest
from autosre.skills import (
    Skill,
    ActionResult,
    ActionDefinition,
    SkillRegistry,
    action,
    registry,
)


class TestActionResult:
    """Tests for ActionResult."""
    
    def test_ok_result(self):
        """Test creating a successful result."""
        result = ActionResult.ok({"value": 42}, source="test")
        
        assert result.success is True
        assert result.data == {"value": 42}
        assert result.error is None
        assert result.metadata == {"source": "test"}
    
    def test_fail_result(self):
        """Test creating a failed result."""
        result = ActionResult.fail("Connection timeout", retries=3)
        
        assert result.success is False
        assert result.data is None
        assert result.error == "Connection timeout"
        assert result.metadata == {"retries": 3}
    
    def test_direct_creation(self):
        """Test direct construction."""
        result = ActionResult(success=True, data="test", error=None)
        assert result.success is True
        assert result.data == "test"


class TestActionDefinition:
    """Tests for ActionDefinition."""
    
    def test_basic_definition(self):
        """Test creating an action definition."""
        async def handler(**kwargs):
            return ActionResult.ok("done")
        
        definition = ActionDefinition(
            name="test_action",
            description="A test action",
            handler=handler,
            params=[{"name": "arg1", "type": "str"}],
            returns="str",
            requires_approval=True,
        )
        
        assert definition.name == "test_action"
        assert definition.description == "A test action"
        assert definition.requires_approval is True
        assert len(definition.params) == 1
    
    def test_default_values(self):
        """Test default values."""
        definition = ActionDefinition(
            name="simple",
            description="Simple action",
            handler=lambda: None,
        )
        
        assert definition.params == []
        assert definition.returns == "Any"
        assert definition.requires_approval is False


class MockSkill(Skill):
    """Mock skill for testing."""
    name = "mock"
    version = "1.0.0"
    description = "A mock skill for testing"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.health_called = False
        
        # Register actions
        self.register_action(
            name="query",
            handler=self._query,
            description="Run a query",
            params=[{"name": "promql", "type": "str"}],
        )
        self.register_action(
            name="dangerous",
            handler=self._dangerous,
            description="A dangerous action",
            requires_approval=True,
        )
    
    async def health_check(self):
        self.health_called = True
        return ActionResult.ok({"status": "healthy"})
    
    async def _query(self, promql: str):
        return ActionResult.ok([{"value": 100}], query=promql)
    
    async def _dangerous(self):
        return ActionResult.ok("executed")


class TestSkill:
    """Tests for Skill base class."""
    
    @pytest.fixture
    def skill(self):
        """Create a mock skill."""
        return MockSkill({"url": "http://localhost:9090"})
    
    def test_init(self, skill):
        """Test skill initialization."""
        assert skill.name == "mock"
        assert skill.version == "1.0.0"
        assert skill.config == {"url": "http://localhost:9090"}
        assert skill._initialized is False
    
    @pytest.mark.asyncio
    async def test_initialize(self, skill):
        """Test skill initialize method."""
        await skill.initialize()
        assert skill._initialized is True
    
    @pytest.mark.asyncio
    async def test_shutdown(self, skill):
        """Test skill shutdown."""
        await skill.initialize()
        assert skill._initialized is True
        
        await skill.shutdown()
        assert skill._initialized is False
    
    @pytest.mark.asyncio
    async def test_health_check(self, skill):
        """Test health check."""
        result = await skill.health_check()
        
        assert skill.health_called is True
        assert result.success is True
        assert result.data["status"] == "healthy"
    
    def test_get_actions(self, skill):
        """Test getting all actions."""
        actions = skill.get_actions()
        
        assert len(actions) == 2
        names = [a.name for a in actions]
        assert "query" in names
        assert "dangerous" in names
    
    def test_get_action(self, skill):
        """Test getting a specific action."""
        action_def = skill.get_action("query")
        
        assert action_def is not None
        assert action_def.name == "query"
        assert action_def.requires_approval is False
    
    def test_get_action_not_found(self, skill):
        """Test getting nonexistent action."""
        action_def = skill.get_action("nonexistent")
        assert action_def is None
    
    @pytest.mark.asyncio
    async def test_invoke_action(self, skill):
        """Test invoking an action."""
        result = await skill.invoke("query", promql="up")
        
        assert result.success is True
        assert result.data == [{"value": 100}]
        assert result.metadata["query"] == "up"
    
    @pytest.mark.asyncio
    async def test_invoke_unknown_action(self, skill):
        """Test invoking unknown action."""
        result = await skill.invoke("unknown")
        
        assert result.success is False
        assert "Unknown action" in result.error
    
    @pytest.mark.asyncio
    async def test_invoke_with_error(self, skill):
        """Test invoking action that raises error."""
        # Create a skill with an action that raises
        async def failing_handler():
            raise ValueError("Something went wrong")
        
        skill.register_action("failing", failing_handler, "Fails")
        
        result = await skill.invoke("failing")
        
        assert result.success is False
        assert "Something went wrong" in result.error
    
    def test_repr(self, skill):
        """Test string representation."""
        repr_str = repr(skill)
        assert "MockSkill" in repr_str
        assert "mock" in repr_str
        assert "1.0.0" in repr_str
    
    def test_action_requires_approval(self, skill):
        """Test action requiring approval flag."""
        action_def = skill.get_action("dangerous")
        assert action_def.requires_approval is True


class TestSkillDecorator:
    """Tests for the @action decorator."""
    
    def test_action_decorator(self):
        """Test action decorator applies metadata."""
        class DecoratedSkill(Skill):
            name = "decorated"
            
            @action(name="custom_name", description="Custom desc", requires_approval=True)
            async def my_action(self):
                return ActionResult.ok("done")
            
            async def health_check(self):
                return ActionResult.ok({})
        
        skill = DecoratedSkill()
        
        # Check that metadata is stored on the function
        assert hasattr(skill.my_action, "_action_metadata")
        metadata = skill.my_action._action_metadata
        assert metadata["name"] == "custom_name"
        assert metadata["description"] == "Custom desc"
        assert metadata["requires_approval"] is True
    
    def test_action_decorator_defaults(self):
        """Test action decorator with defaults."""
        @action()
        async def my_action():
            """My docstring."""
            pass
        
        assert my_action._action_metadata["name"] == "my_action"
        assert "docstring" in my_action._action_metadata["description"]


class TestSkillRegistry:
    """Tests for SkillRegistry."""
    
    @pytest.fixture
    def test_registry(self):
        """Create a fresh registry."""
        return SkillRegistry()
    
    def test_register(self, test_registry):
        """Test registering a skill."""
        test_registry.register(MockSkill)
        
        assert "mock" in test_registry.list_skills()
    
    def test_get(self, test_registry):
        """Test getting a skill class."""
        test_registry.register(MockSkill)
        
        skill_class = test_registry.get("mock")
        assert skill_class is MockSkill
    
    def test_get_not_found(self, test_registry):
        """Test getting nonexistent skill."""
        result = test_registry.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_instance(self, test_registry):
        """Test getting/creating skill instance."""
        test_registry.register(MockSkill)
        
        instance = await test_registry.get_instance("mock", {"url": "http://test"})
        
        assert instance is not None
        assert instance.name == "mock"
        assert instance._initialized is True
    
    @pytest.mark.asyncio
    async def test_get_instance_cached(self, test_registry):
        """Test that instances are cached."""
        test_registry.register(MockSkill)
        
        instance1 = await test_registry.get_instance("mock")
        instance2 = await test_registry.get_instance("mock")
        
        assert instance1 is instance2
    
    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, test_registry):
        """Test getting instance for unregistered skill."""
        instance = await test_registry.get_instance("nonexistent")
        assert instance is None
    
    def test_list_skills(self, test_registry):
        """Test listing registered skills."""
        test_registry.register(MockSkill)
        
        skills = test_registry.list_skills()
        assert "mock" in skills
    
    @pytest.mark.asyncio
    async def test_shutdown_all(self, test_registry):
        """Test shutting down all instances."""
        test_registry.register(MockSkill)
        
        instance = await test_registry.get_instance("mock")
        assert instance._initialized is True
        
        await test_registry.shutdown_all()
        
        # Instance cache should be cleared
        assert test_registry._instances == {}


class TestGlobalRegistry:
    """Tests for global registry."""
    
    def test_global_registry_exists(self):
        """Test that global registry is available."""
        assert registry is not None
        assert isinstance(registry, SkillRegistry)
