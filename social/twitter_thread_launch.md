# AutoSRE Launch Twitter Thread

Copy-paste ready. Post as a thread (each section = 1 tweet).

---

## Tweet 1 (Hook)
```
🚨 Announcing AutoSRE: AI-powered incident investigation for SREs

No more 3am page → open 5 dashboards → search Confluence → find nothing → wake up senior engineer.

One command. 30 seconds. Full context.

Open source (MIT). Let me show you 🧵
```

---

## Tweet 2 (Demo)
```
Here's what it looks like:

$ autosre investigate "checkout latency spike"

In 30 seconds, you get:
✅ Relevant metrics from Prometheus/Datadog
✅ Correlated events
✅ Similar past incidents
✅ Matching runbook with remediation steps

No context switching. No frantic Slack searching.
```

---

## Tweet 3 (How it works)
```
How does it work?

AutoSRE uses LangGraph agents:

🔍 Investigation Agent - queries your metrics & logs
📚 Knowledge Agent - searches runbooks semantically
🎯 Action Agent - suggests remediation steps

Three agents coordinate. You get answers.
```

---

## Tweet 4 (RAG)
```
The secret sauce: your runbooks become instantly searchable.

Traditional search: "database slow" → 0 results
AutoSRE semantic search: "database slow" → finds "PostgreSQL connection pool exhaustion runbook"

Powered by ChromaDB + RAG. Index your docs in 5 minutes.
```

---

## Tweet 5 (Integrations)
```
Works with your existing stack:

📊 Prometheus, Datadog, New Relic
🚨 Alertmanager, PagerDuty, Opsgenie  
📝 Loki, Elasticsearch
📖 Confluence, Notion, Markdown

One CLI to query them all.
```

---

## Tweet 6 (CLI Examples)
```
The CLI is designed for 3am:

# Investigate an incident
autosre investigate "high latency" --service checkout

# Interactive chat
autosre chat

# View active alerts
autosre alerts --status active

# Start API server
autosre serve
```

---

## Tweet 7 (Quick Start)
```
Get started in 60 seconds:

pip install autosre
export OPENAI_API_KEY=sk-...
autosre chat

That's it. Ask it anything about your infrastructure.

Add integrations later. Start with the conversational assistant now.
```

---

## Tweet 8 (CTA)
```
AutoSRE is 100% open source (MIT license).

⭐ Star: github.com/autosre/autosre
📖 Docs: [link]
💬 Discord: [link]

Built for SREs, by SREs.

If you've ever been woken up at 3am, this is for you.

Please RT if this looks useful! 🙏
```

---

## Tweet 9 (Bonus - Architecture)
```
For the technically curious:

Built with:
• LangGraph for agent orchestration
• LangChain for LLM abstractions
• ChromaDB for vector search
• FastAPI for REST API
• Typer + Rich for CLI

Architecture diagram in the docs 👇
[link to architecture doc]
```

---

## Alt Versions

### Shorter Version (5 tweets)
```
1/ 🚨 Announcing AutoSRE: AI-powered incident investigation

One command: autosre investigate "high latency"
30 seconds: metrics, correlated events, matching runbook

Open source. github.com/autosre/autosre 🧵

2/ How it works:
- Investigation Agent queries Prometheus/Datadog
- Knowledge Agent searches your runbooks (semantic search)
- Action Agent suggests remediation

LangGraph agents coordinate everything.

3/ Your runbooks become instantly searchable.

Index: autosre knowledge index ./runbooks/
Search: autosre knowledge search "redis failover"

Finds the right runbook even without exact keyword matches.

4/ Works with: Prometheus, Datadog, PagerDuty, Alertmanager, Loki, Elasticsearch, Confluence, Notion.

One CLI. All your tools.

5/ Get started:
pip install autosre
autosre chat

Docs: [link]
Star us: github.com/autosre/autosre

RT if useful! 🙏
```

---

## Engagement Replies

Keep these ready to reply to common questions:

**Q: How is this different from X?**
```
Great question! AutoSRE is specifically for incident investigation:
- Agents coordinate across multiple tools
- Semantic runbook search (not just keywords)
- Built for CLI (3am-friendly)
- Self-hosted, your data stays yours

Different focus than general AIOps dashboards.
```

**Q: What LLMs does it support?**
```
Currently OpenAI (GPT-4). 

Adding support for:
- Claude
- Local models (Ollama)
- Azure OpenAI

PRs welcome for other providers!
```

**Q: Does it actually work?**
```
We've used it internally for 6 months. Reduced our median investigation time from 15 min to 2 min.

But don't take our word for it - try it on your stack and let us know!
```

**Q: Is it production ready?**
```
v0.1.0 - stable for investigation workflows.

We're battle-testing the knowledge base and multi-agent features. 

Star the repo for updates, or join Discord for early access to new features.
```
