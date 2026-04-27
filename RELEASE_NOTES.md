# AutoSRE v0.1.0 Release Notes

## 🚀 Initial Release

AutoSRE is an open-source AI SRE agent built foundation-first for reliable incident response.

### ✨ Features

**Context-Aware Analysis**
- Correlates alerts with recent deployments, config changes, and dependencies
- Maintains service topology and ownership mappings
- Tracks historical incidents for pattern recognition

**Intelligent Root Cause Analysis**
- Multi-LLM support (Ollama, OpenAI, Anthropic, Azure)
- Structured reasoning with confidence scores
- Learns from feedback to improve over time

**Runbook Integration**
- Matches alerts to relevant runbooks
- Step-by-step execution guidance
- Automated execution with guardrails

**Safe Remediation**
- Approval workflows for risky actions
- Auto-approve low-risk operations
- Audit logging for compliance

**Built-in Evaluation**
- 33 synthetic incident scenarios
- Measure accuracy before production
- Track improvements over time

### 📦 Installation

```bash
pip install autosre
```

### 🏁 Quick Start

```bash
autosre init
autosre status
autosre eval list
autosre eval run --scenario high_cpu
```

### 📊 Stats

- **704 passing tests**
- **33 evaluation scenarios**
- **7 CLI commands** (init, status, context, eval, sandbox, agent, feedback)
- **Python 3.11+** support

### 🔗 Links

- [Documentation](https://github.com/autosre-ai/autosre#-documentation)
- [Getting Started](https://github.com/autosre-ai/autosre/blob/main/docs/getting-started.md)
- [Contributing](https://github.com/autosre-ai/autosre/blob/main/CONTRIBUTING.md)

---

**Full Changelog**: https://github.com/autosre-ai/autosre/commits/v0.1.0
