# Twitter/X Announcement Thread

---

**Tweet 1:**
🚀 Just shipped AutoSRE — an open-source AI SRE agent.

Most AI incident tools fail because they start with AI and bolt on context later.

AutoSRE flips it: context store FIRST, AI reasoning SECOND.

https://github.com/autosre-ai/autosre

🧵👇

---

**Tweet 2:**
The foundation-first approach:

1️⃣ Context Store — services, ownership, recent changes, runbooks
2️⃣ Observer — watch for alerts/anomalies
3️⃣ Reasoner — LLM analysis WITH context
4️⃣ Actor — safe remediation with guardrails

No AI hallucinating about services that don't exist.

---

**Tweet 3:**
What makes it different:

• 33 synthetic incident scenarios to test BEFORE production
• Multi-LLM (Ollama, OpenAI, Anthropic)
• Learns from feedback
• 700+ tests
• Full CLI

```
pip install autosre
autosre init
autosre eval run --scenario high_cpu
```

---

**Tweet 4:**
Built for real SRE workflows:

→ Correlate alerts with deployments
→ Match runbooks automatically
→ Require approval for risky actions
→ Auto-approve safe operations
→ Full audit logging

The agent you can actually trust on-call.

---

**Tweet 5:**
This is v0.1.0 — early but functional.

Looking for:
• Feedback from SREs
• Scenario suggestions
• Integration requests (Datadog? Loki?)
• Contributors!

⭐ Star it: https://github.com/autosre-ai/autosre

Let's build the SRE agent we actually want to use.

---
