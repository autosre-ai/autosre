"""Tests for OpenSRE core modules."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from opensre.core.config import ConfigManager
from opensre.core.exceptions import (
    ConfigError,
    SecretNotFoundError,
    SkillExecutionError,
    SkillNotFoundError,
)
from opensre.core.models import (
    AgentDefinition,
    SkillMetadata,
    StepDefinition,
    StepStatus,
)
from opensre.core.runtime import Agent, AgentRunner, ExecutionContext
from opensre.core.skills import Skill, SkillRegistry, skill
from opensre.core.utils import (
    deep_merge,
    resolve_env_vars,
    resolve_template,
)


# ============== Utils Tests ==============

class TestUtils:
    """Tests for utility functions."""
    
    def test_resolve_env_vars_simple(self):
        """Test resolving simple environment variables."""
        os.environ["TEST_VAR"] = "hello"
        result = resolve_env_vars("${TEST_VAR}")
        assert result == "hello"
        del os.environ["TEST_VAR"]
    
    def test_resolve_env_vars_with_default(self):
        """Test resolving env vars with default values."""
        result = resolve_env_vars("${NONEXISTENT:-default_value}")
        assert result == "default_value"
    
    def test_resolve_env_vars_missing(self):
        """Test that missing env vars without default are kept."""
        result = resolve_env_vars("${NONEXISTENT}")
        assert result == "${NONEXISTENT}"
    
    def test_deep_merge(self):
        """Test deep merging of dictionaries."""
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 4, "e": 5}, "f": 6}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 4, "d": 3, "e": 5}, "f": 6}
    
    def test_resolve_template(self):
        """Test resolving template strings."""
        context = {"name": "World", "nested": {"value": 42}}
        result = resolve_template("Hello, {{ name }}!", context)
        assert result == "Hello, World!"
        
        result = resolve_template("Value: {{ nested.value }}", context)
        assert result == "Value: 42"


# ============== Config Tests ==============

class TestConfig:
    """Tests for configuration management."""
    
    def test_config_load(self, tmp_path):
        """Test loading configuration."""
        config_data = {
            "project_name": "test-project",
            "version": "1.0.0",
            "default_environment": "dev",
            "environments": {
                "dev": {"variables": {"debug": True}},
                "prod": {"variables": {"debug": False}}
            },
            "config": {"timeout": 30}
        }
        
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(tmp_path, "dev")
        config = manager.load()
        
        assert config.project_name == "test-project"
        assert manager.get("timeout") == 30
        assert manager.get("debug") is True
    
    def test_config_environment_switch(self, tmp_path):
        """Test switching environments."""
        config_data = {
            "project_name": "test",
            "environments": {
                "dev": {"variables": {"mode": "development"}},
                "prod": {"variables": {"mode": "production"}}
            }
        }
        
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(tmp_path, "dev")
        manager.load()
        assert manager.get("mode") == "development"
        
        manager.environment = "prod"
        assert manager.get("mode") == "production"
    
    def test_config_get_secret_from_env(self, tmp_path):
        """Test getting secrets from environment variables."""
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"project_name": "test"}, f)
        
        manager = ConfigManager(tmp_path)
        manager.load()
        
        os.environ["OPENSRE_SECRET_API_KEY"] = "secret123"
        assert manager.get_secret("api_key") == "secret123"
        del os.environ["OPENSRE_SECRET_API_KEY"]
    
    def test_config_secret_not_found(self, tmp_path):
        """Test that missing required secrets raise an error."""
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"project_name": "test"}, f)
        
        manager = ConfigManager(tmp_path)
        manager.load()
        
        with pytest.raises(SecretNotFoundError):
            manager.get_secret("nonexistent")
        
        # Optional secrets return None
        assert manager.get_secret("nonexistent", required=False) is None


# ============== Skills Tests ==============

class TestSkills:
    """Tests for the skill system."""
    
    def test_skill_base_class(self):
        """Test the base Skill class."""
        class TestSkill(Skill):
            name = "test_skill"
            version = "1.0.0"
            
            def do_work(self, context: dict, param: str) -> dict:
                return {"result": param.upper()}
        
        skill = TestSkill()
        skill.setup({"key": "value"})
        
        assert skill.name == "test_skill"
        assert skill.config == {"key": "value"}
        assert "do_work" in skill.get_methods()
    
    def test_skill_call_method(self):
        """Test calling a skill method."""
        class TestSkill(Skill):
            name = "test"
            
            def greet(self, context: dict, name: str) -> str:
                return f"Hello, {name}!"
        
        s = TestSkill()
        s.setup({})
        result = s.call("greet", {}, name="World")
        assert result == "Hello, World!"
    
    def test_skill_call_invalid_method(self):
        """Test that calling invalid method raises error."""
        class TestSkill(Skill):
            name = "test"
        
        s = TestSkill()
        s.setup({})
        
        with pytest.raises(SkillExecutionError):
            s.call("nonexistent", {})
    
    def test_skill_decorator(self):
        """Test the @skill decorator."""
        @skill(name="decorated", version="2.0.0")
        class MySkill:
            def do_something(self) -> str:
                return "done"
        
        instance = MySkill()
        assert instance.name == "decorated"
        assert instance.version == "2.0.0"
    
    def test_skill_registry_discover(self, tmp_path):
        """Test skill discovery."""
        # Create a skill directory
        skill_dir = tmp_path / "skills" / "my_skill"
        skill_dir.mkdir(parents=True)
        
        # Create skill.yaml
        metadata = {
            "name": "my_skill",
            "version": "1.0.0",
            "description": "Test skill",
            "methods": ["do_something"]
        }
        with open(skill_dir / "skill.yaml", "w") as f:
            yaml.dump(metadata, f)
        
        # Create skill.py
        skill_code = '''
from opensre.core.skills import Skill

class MySkill(Skill):
    name = "my_skill"
    version = "1.0.0"
    
    def do_something(self, context: dict) -> str:
        return "done"
'''
        (skill_dir / "skill.py").write_text(skill_code)
        
        # Discover
        registry = SkillRegistry(tmp_path / "skills")
        discovered = registry.discover()
        
        assert len(discovered) == 1
        assert discovered[0].name == "my_skill"
        assert discovered[0].version == "1.0.0"
    
    def test_skill_registry_load(self, tmp_path):
        """Test loading a skill from registry."""
        # Create skill
        skill_dir = tmp_path / "skills" / "loader_test"
        skill_dir.mkdir(parents=True)
        
        with open(skill_dir / "skill.yaml", "w") as f:
            yaml.dump({"name": "loader_test", "version": "1.0.0"}, f)
        
        skill_code = '''
from opensre.core.skills import Skill

class LoaderTestSkill(Skill):
    name = "loader_test"
    
    def test_method(self, context: dict) -> str:
        return "loaded"
'''
        (skill_dir / "skill.py").write_text(skill_code)
        
        # Load
        registry = SkillRegistry(tmp_path / "skills")
        skill_instance = registry.load("loader_test")
        
        assert skill_instance.name == "loader_test"
        assert skill_instance.call("test_method", {}) == "loaded"
    
    def test_skill_not_found(self, tmp_path):
        """Test that loading nonexistent skill raises error."""
        registry = SkillRegistry(tmp_path / "skills")
        
        with pytest.raises(SkillNotFoundError):
            registry.load("nonexistent")


# ============== Runtime Tests ==============

class TestRuntime:
    """Tests for the agent runtime."""
    
    def test_execution_context(self):
        """Test the execution context."""
        ctx = ExecutionContext({"initial": "value"})
        
        assert ctx.get("initial") == "value"
        assert ctx.get("missing") is None
        assert ctx.get("missing", "default") == "default"
        
        ctx.set("new_key", "new_value")
        assert ctx.get("new_key") == "new_value"
        
        ctx.set_output("output1", {"result": True})
        assert ctx.outputs()["output1"] == {"result": True}
    
    def test_agent_from_yaml(self, tmp_path):
        """Test loading an agent from YAML."""
        # Create config
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"project_name": "test"}, f)
        
        # Create agent definition
        agent_data = {
            "name": "test-agent",
            "version": "1.0.0",
            "description": "Test agent",
            "skills": ["test"],
            "steps": [
                {
                    "id": "step1",
                    "skill": "test",
                    "method": "do_work",
                    "args": {"param": "value"}
                }
            ]
        }
        
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "test-agent.yaml"
        with open(agent_file, "w") as f:
            yaml.dump(agent_data, f)
        
        # Create skill
        skill_dir = tmp_path / "skills" / "test"
        skill_dir.mkdir(parents=True)
        with open(skill_dir / "skill.yaml", "w") as f:
            yaml.dump({"name": "test", "version": "1.0.0"}, f)
        
        skill_code = '''
from opensre.core.skills import Skill

class TestSkill(Skill):
    name = "test"
    
    def do_work(self, context: dict, param: str) -> dict:
        return {"result": param}
'''
        (skill_dir / "skill.py").write_text(skill_code)
        
        # Load and verify
        config = ConfigManager(tmp_path)
        config.load()
        registry = SkillRegistry(tmp_path / "skills")
        
        agent = Agent.from_yaml(agent_file, registry, config)
        
        assert agent.definition.name == "test-agent"
        assert len(agent.definition.steps) == 1
        assert agent.definition.steps[0].skill == "test"
    
    def test_agent_run_dry(self, tmp_path):
        """Test dry run of an agent."""
        # Setup
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"project_name": "test"}, f)
        
        agent_data = {
            "name": "dry-test",
            "skills": ["dummy"],
            "steps": [{"id": "s1", "skill": "dummy", "method": "run", "args": {}}]
        }
        
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "dry-test.yaml"
        with open(agent_file, "w") as f:
            yaml.dump(agent_data, f)
        
        # Create dummy skill
        skill_dir = tmp_path / "skills" / "dummy"
        skill_dir.mkdir(parents=True)
        with open(skill_dir / "skill.yaml", "w") as f:
            yaml.dump({"name": "dummy", "version": "1.0.0"}, f)
        (skill_dir / "skill.py").write_text('''
from opensre.core.skills import Skill

class DummySkill(Skill):
    name = "dummy"
    def run(self, context: dict) -> dict:
        return {"executed": True}
''')
        
        # Run
        config = ConfigManager(tmp_path)
        config.load()
        runner = AgentRunner(config)
        result = runner.run(agent_file, dry_run=True)
        
        assert result.status == StepStatus.SUCCESS
        assert len(result.steps) == 1
        assert result.steps[0].output["dry_run"] is True
    
    def test_agent_run_with_context(self, tmp_path):
        """Test agent run with initial context."""
        # Setup
        config_file = tmp_path / "opensre.yaml"
        with open(config_file, "w") as f:
            yaml.dump({"project_name": "test"}, f)
        
        agent_data = {
            "name": "context-test",
            "skills": ["echo"],
            "steps": [{
                "id": "echo",
                "skill": "echo",
                "method": "echo",
                "args": {"message": "{{ input }}"},
                "output": "result"
            }]
        }
        
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "context-test.yaml"
        with open(agent_file, "w") as f:
            yaml.dump(agent_data, f)
        
        skill_dir = tmp_path / "skills" / "echo"
        skill_dir.mkdir(parents=True)
        with open(skill_dir / "skill.yaml", "w") as f:
            yaml.dump({"name": "echo", "version": "1.0.0"}, f)
        (skill_dir / "skill.py").write_text('''
from opensre.core.skills import Skill

class EchoSkill(Skill):
    name = "echo"
    def echo(self, context: dict, message: str) -> dict:
        return {"echoed": message}
''')
        
        # Run with context
        config = ConfigManager(tmp_path)
        config.load()
        runner = AgentRunner(config)
        result = runner.run(agent_file, context={"input": "Hello!"})
        
        assert result.status == StepStatus.SUCCESS
        assert result.context.get("result") == {"echoed": "Hello!"}


# ============== Models Tests ==============

class TestModels:
    """Tests for Pydantic models."""
    
    def test_skill_metadata(self):
        """Test SkillMetadata model."""
        metadata = SkillMetadata(
            name="test",
            version="1.0.0",
            description="A test skill",
            methods=["method1", "method2"]
        )
        
        assert metadata.name == "test"
        assert metadata.version == "1.0.0"
        assert len(metadata.methods) == 2
    
    def test_step_definition(self):
        """Test StepDefinition model."""
        step = StepDefinition(
            id="my-step",
            skill="my_skill",
            method="do_work",
            args={"key": "value"},
            retry=3,
            timeout=30.0
        )
        
        assert step.id == "my-step"
        assert step.retry == 3
        assert step.timeout == 30.0
        assert step.on_error == "fail"  # default
    
    def test_agent_definition(self):
        """Test AgentDefinition model."""
        agent = AgentDefinition(
            name="my-agent",
            skills=["skill1", "skill2"],
            steps=[
                StepDefinition(id="s1", skill="skill1", method="m1"),
                StepDefinition(id="s2", skill="skill2", method="m2")
            ]
        )
        
        assert agent.name == "my-agent"
        assert len(agent.skills) == 2
        assert len(agent.steps) == 2


# ============== Integration Tests ==============

class TestIntegration:
    """Integration tests for the full workflow."""
    
    def test_full_workflow(self, tmp_path):
        """Test a complete workflow from project setup to agent execution."""
        # 1. Create project structure
        (tmp_path / "skills").mkdir()
        (tmp_path / "agents").mkdir()
        
        # 2. Create config
        config_data = {
            "project_name": "integration-test",
            "version": "1.0.0",
            "default_environment": "dev",
            "environments": {
                "dev": {"variables": {"greeting": "Hello"}}
            }
        }
        with open(tmp_path / "opensre.yaml", "w") as f:
            yaml.dump(config_data, f)
        
        # 3. Create a skill
        skill_dir = tmp_path / "skills" / "greeter"
        skill_dir.mkdir()
        
        with open(skill_dir / "skill.yaml", "w") as f:
            yaml.dump({
                "name": "greeter",
                "version": "1.0.0",
                "description": "Greeting skill",
                "methods": ["greet", "farewell"]
            }, f)
        
        (skill_dir / "skill.py").write_text('''
from opensre.core.skills import Skill

class GreeterSkill(Skill):
    name = "greeter"
    version = "1.0.0"
    
    def greet(self, context: dict, name: str) -> dict:
        prefix = self.config.get("prefix", "Hello")
        return {"message": f"{prefix}, {name}!"}
    
    def farewell(self, context: dict, name: str) -> dict:
        return {"message": f"Goodbye, {name}!"}
''')
        
        # 4. Create an agent
        agent_data = {
            "name": "greeting-agent",
            "version": "1.0.0",
            "description": "Agent that greets and says goodbye",
            "skills": ["greeter"],
            "config": {
                "greeter": {"prefix": "Hi"}
            },
            "steps": [
                {
                    "id": "greet",
                    "skill": "greeter",
                    "method": "greet",
                    "args": {"name": "{{ target_name }}"},
                    "output": "greeting"
                },
                {
                    "id": "farewell",
                    "skill": "greeter",
                    "method": "farewell",
                    "args": {"name": "{{ target_name }}"},
                    "output": "farewell"
                }
            ]
        }
        with open(tmp_path / "agents" / "greeting-agent.yaml", "w") as f:
            yaml.dump(agent_data, f)
        
        # 5. Run the agent
        config = ConfigManager(tmp_path)
        config.load()
        
        runner = AgentRunner(config)
        result = runner.run(
            tmp_path / "agents" / "greeting-agent.yaml",
            context={"target_name": "World"}
        )
        
        # 6. Verify results
        assert result.status == StepStatus.SUCCESS
        assert len(result.steps) == 2
        assert result.context["greeting"] == {"message": "Hi, World!"}
        assert result.context["farewell"] == {"message": "Goodbye, World!"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
