# LinkedIn Announcement Post

---

🚀 Just open-sourced AutoSRE — an AI-powered SRE agent built foundation-first.

After years in SRE, I've seen too many AI incident tools fail because they start with the AI and bolt on context later. That's backwards.

AutoSRE flips it:
→ Context store FIRST (services, ownership, changes, runbooks)
→ AI reasoning SECOND (with rich context)
→ Safe remediation with guardrails

What it does:
• Correlates alerts with recent deployments
• Root cause analysis with confidence scores
• Runbook matching and guided execution
• Learns from feedback to improve over time

Built with:
• 33 synthetic incident scenarios for testing
• Full CLI (init, context, eval, sandbox, agent)
• Multi-LLM support (Ollama, OpenAI, Anthropic)
• 700+ tests

Try it:
```
pip install autosre
autosre init
autosre eval list
```

GitHub: https://github.com/autosre-ai/autosre

This is v0.1.0 — early but functional. Looking for feedback from fellow SREs and DevOps engineers.

What incident scenarios would you want to test first?

#opensource #sre #devops #kubernetes #ai #incidentmanagement #observability

---
