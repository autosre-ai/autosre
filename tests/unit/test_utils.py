"""Unit tests for utility functions."""

from datetime import timedelta

import pytest

from autosre.utils.helpers import (
    camel_to_snake,
    deep_merge,
    extract_json_from_text,
    flatten_dict,
    format_bytes,
    format_duration,
    parse_duration,
    safe_json_loads,
    snake_to_camel,
    truncate_string,
)
from autosre.utils.config import (
    Config,
    InvestigationConfig,
    LLMConfig,
    LoggingConfig,
    RunbookConfig,
    ServerConfig,
    load_config,
)


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestFormatDuration:
    """Tests for format_duration."""

    def test_seconds_only(self):
        """Test formatting seconds."""
        assert format_duration(30) == "30s"
        assert format_duration(1) == "1s"
        assert format_duration(0) == "0s"

    def test_minutes_and_seconds(self):
        """Test formatting minutes and seconds."""
        assert format_duration(90) == "1m 30s"
        assert format_duration(60) == "1m"
        assert format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        """Test formatting hours, minutes, and seconds."""
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(3600) == "1h"
        assert format_duration(9015) == "2h 30m 15s"

    def test_negative_returns_zero(self):
        """Test negative values return 0s."""
        assert format_duration(-10) == "0s"

    def test_float_truncates(self):
        """Test float values are truncated."""
        assert format_duration(30.7) == "30s"


class TestFormatBytes:
    """Tests for format_bytes."""

    def test_bytes(self):
        """Test formatting bytes."""
        assert format_bytes(500) == "500 B"
        assert format_bytes(0) == "0 B"

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1536) == "1.50 KB"

    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 2.5) == "2.50 MB"

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1536000000) == "1.43 GB"

    def test_negative_returns_zero(self):
        """Test negative values return 0 B."""
        assert format_bytes(-100) == "0 B"


class TestTruncateString:
    """Tests for truncate_string."""

    def test_no_truncation_needed(self):
        """Test string shorter than max_length."""
        result = truncate_string("Hello", max_length=10)
        assert result == "Hello"

    def test_truncation(self):
        """Test string truncation."""
        result = truncate_string("Hello World!", max_length=8)
        assert result == "Hello..."
        assert len(result) == 8

    def test_custom_suffix(self):
        """Test custom truncation suffix."""
        result = truncate_string("Hello World!", max_length=10, suffix="…")
        assert result.endswith("…")

    def test_exact_length(self):
        """Test string exactly at max_length."""
        result = truncate_string("Hello", max_length=5)
        assert result == "Hello"


class TestParseDuration:
    """Tests for parse_duration."""

    def test_seconds(self):
        """Test parsing seconds."""
        assert parse_duration("30s") == timedelta(seconds=30)
        assert parse_duration("1s") == timedelta(seconds=1)

    def test_minutes(self):
        """Test parsing minutes."""
        assert parse_duration("5m") == timedelta(minutes=5)
        assert parse_duration("1m") == timedelta(minutes=1)

    def test_hours(self):
        """Test parsing hours."""
        assert parse_duration("2h") == timedelta(hours=2)

    def test_days(self):
        """Test parsing days."""
        assert parse_duration("1d") == timedelta(days=1)

    def test_weeks(self):
        """Test parsing weeks."""
        assert parse_duration("1w") == timedelta(weeks=1)

    def test_combined(self):
        """Test parsing combined durations."""
        assert parse_duration("2h30m") == timedelta(hours=2, minutes=30)
        assert parse_duration("1d12h") == timedelta(days=1, hours=12)
        assert parse_duration("1h30m45s") == timedelta(hours=1, minutes=30, seconds=45)

    def test_integer_assumes_seconds(self):
        """Test plain integer assumes seconds."""
        assert parse_duration("60") == timedelta(seconds=60)

    def test_invalid_format_raises(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError):
            parse_duration("")
        
        with pytest.raises(ValueError):
            parse_duration("abc")


class TestSafeJsonLoads:
    """Tests for safe_json_loads."""

    def test_valid_json(self):
        """Test parsing valid JSON."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_returns_default(self):
        """Test invalid JSON returns default."""
        result = safe_json_loads("not json", default={})
        assert result == {}

    def test_none_input(self):
        """Test None input returns default."""
        result = safe_json_loads(None, default=[])
        assert result == []


class TestExtractJsonFromText:
    """Tests for extract_json_from_text."""

    def test_direct_json(self):
        """Test extracting direct JSON."""
        result = extract_json_from_text('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_block(self):
        """Test extracting JSON from markdown block."""
        text = """Here is the result:
```json
{"key": "value"}
```
"""
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_json_in_generic_code_block(self):
        """Test extracting JSON from generic code block."""
        text = """Result:
```
{"status": "ok"}
```
"""
        result = extract_json_from_text(text)
        assert result == {"status": "ok"}

    def test_json_embedded_in_text(self):
        """Test extracting JSON embedded in text."""
        text = 'The response is {"found": true} and that is all.'
        result = extract_json_from_text(text)
        assert result == {"found": True}

    def test_no_json_returns_none(self):
        """Test no JSON returns None."""
        result = extract_json_from_text("No JSON here!")
        assert result is None


class TestSnakeToCamel:
    """Tests for snake_to_camel."""

    def test_single_word(self):
        """Test single word."""
        assert snake_to_camel("hello") == "hello"

    def test_two_words(self):
        """Test two words."""
        assert snake_to_camel("hello_world") == "helloWorld"

    def test_multiple_words(self):
        """Test multiple words."""
        assert snake_to_camel("get_user_by_id") == "getUserById"


class TestCamelToSnake:
    """Tests for camel_to_snake."""

    def test_single_word(self):
        """Test single word."""
        assert camel_to_snake("hello") == "hello"

    def test_two_words(self):
        """Test two words."""
        assert camel_to_snake("helloWorld") == "hello_world"

    def test_multiple_words(self):
        """Test multiple words."""
        assert camel_to_snake("getUserById") == "get_user_by_id"

    def test_all_caps_acronym(self):
        """Test handling of acronyms."""
        assert camel_to_snake("HTTPServer") == "h_t_t_p_server"


class TestDeepMerge:
    """Tests for deep_merge."""

    def test_simple_merge(self):
        """Test simple dictionary merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        
        result = deep_merge(base, override)
        
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """Test nested dictionary merge."""
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3, "d": 4}}
        
        result = deep_merge(base, override)
        
        assert result == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_override_replaces_non_dict(self):
        """Test override replaces non-dict values."""
        base = {"a": [1, 2, 3]}
        override = {"a": [4, 5]}
        
        result = deep_merge(base, override)
        
        assert result == {"a": [4, 5]}

    def test_does_not_modify_original(self):
        """Test original dicts are not modified."""
        base = {"a": 1}
        override = {"b": 2}
        
        result = deep_merge(base, override)
        
        assert "b" not in base


class TestFlattenDict:
    """Tests for flatten_dict."""

    def test_simple_dict(self):
        """Test flattening simple dict."""
        d = {"a": 1, "b": 2}
        result = flatten_dict(d)
        
        assert result == {"a": 1, "b": 2}

    def test_nested_dict(self):
        """Test flattening nested dict."""
        d = {"a": {"b": {"c": 1}}}
        result = flatten_dict(d)
        
        assert result == {"a.b.c": 1}

    def test_mixed_nesting(self):
        """Test mixed nesting levels."""
        d = {"a": {"b": 1}, "c": 2}
        result = flatten_dict(d)
        
        assert result == {"a.b": 1, "c": 2}

    def test_custom_separator(self):
        """Test custom separator."""
        d = {"a": {"b": 1}}
        result = flatten_dict(d, sep="/")
        
        assert result == {"a/b": 1}


# ============================================================================
# Config Tests
# ============================================================================


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_defaults(self):
        """Test default values."""
        config = LLMConfig()
        
        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.1
        assert config.max_tokens == 4096

    def test_custom_values(self):
        """Test custom values."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3-opus",
            temperature=0.5,
        )
        
        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.temperature == 0.5


class TestInvestigationConfig:
    """Tests for InvestigationConfig."""

    def test_defaults(self):
        """Test default values."""
        config = InvestigationConfig()
        
        assert config.auto_start is False
        assert config.max_parallel == 3
        assert config.timeout_minutes == 30
        assert config.max_iterations == 3

    def test_validation(self):
        """Test validation constraints."""
        # Valid config
        config = InvestigationConfig(max_parallel=5)
        assert config.max_parallel == 5
        
        # Invalid max_parallel
        with pytest.raises(ValueError):
            InvestigationConfig(max_parallel=0)
        
        with pytest.raises(ValueError):
            InvestigationConfig(max_parallel=15)


class TestServerConfig:
    """Tests for ServerConfig."""

    def test_defaults(self):
        """Test default values."""
        config = ServerConfig()
        
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.workers == 4


class TestRunbookConfig:
    """Tests for RunbookConfig."""

    def test_defaults(self):
        """Test default values."""
        config = RunbookConfig()
        
        assert config.path == "./runbooks"
        assert config.auto_execute is False


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_defaults(self):
        """Test default values."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.format == "json"


class TestConfig:
    """Tests for main Config."""

    def test_defaults(self):
        """Test default configuration."""
        config = Config()
        
        assert config.version == "2.0"
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.investigation, InvestigationConfig)

    def test_from_yaml(self, tmp_path):
        """Test loading from YAML file."""
        import yaml
        
        config_data = {
            "version": "2.0",
            "llm": {
                "provider": "anthropic",
                "model": "claude-3",
            },
            "investigation": {
                "auto_start": True,
            },
        }
        
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        
        config = Config.from_yaml(config_path)
        
        assert config.llm.provider == "anthropic"
        assert config.investigation.auto_start is True

    def test_env_var_expansion(self, tmp_path, monkeypatch):
        """Test environment variable expansion."""
        import yaml
        
        monkeypatch.setenv("TEST_API_KEY", "secret-key-123")
        
        config_data = {
            "version": "2.0",
            "llm": {
                "api_key": "${TEST_API_KEY}",
            },
        }
        
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        
        config = Config.from_yaml(config_path)
        
        assert config.llm.api_key == "secret-key-123"

    def test_load_config_default(self, tmp_path):
        """Test load_config with default search paths."""
        # When no config file exists, returns default config
        config = load_config(search_paths=[tmp_path / "nonexistent"])
        
        assert isinstance(config, Config)
        assert config.version == "2.0"

    def test_load_config_explicit_path(self, tmp_path):
        """Test load_config with explicit path."""
        import yaml
        
        config_data = {"version": "2.0", "llm": {"model": "custom-model"}}
        config_path = tmp_path / "my-config.yaml"
        
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        
        config = load_config(path=config_path)
        
        assert config.llm.model == "custom-model"
