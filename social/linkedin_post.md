# AutoSRE LinkedIn Launch Post

Copy-paste ready. Choose Version A (technical) or Version B (story-driven).

---

## Version A: Technical Focus

```
🚨 Announcing AutoSRE: AI-Powered Site Reliability Engineering Assistant

After too many 3am incidents where I spent 20 minutes searching for the right runbook, I built something better.

AutoSRE is an open-source AI assistant that helps on-call engineers investigate incidents faster:

🔍 One command to investigate:
$ autosre investigate "checkout latency spike"

In 30 seconds, you get:
• Relevant metrics from Prometheus/Datadog
• Correlated events and anomalies
• Similar past incidents
• Matching runbook with remediation steps

📚 Semantic runbook search:
Traditional search: "database slow" → 0 results
AutoSRE: "database slow" → finds "PostgreSQL connection pool exhaustion runbook"

Your runbooks become instantly searchable with ChromaDB and RAG.

🔧 Integrates with your stack:
• Monitoring: Prometheus, Datadog, New Relic
• Alerting: Alertmanager, PagerDuty, Opsgenie
• Logging: Loki, Elasticsearch
• Docs: Confluence, Notion, Markdown

🤖 Built with modern AI:
• LangGraph for multi-agent orchestration
• LangChain for LLM abstractions
• Typer + Rich for a CLI designed for 3am

100% open source (MIT license).

If you've ever been woken up by a page and spent the first 20 minutes just gathering context, this is for you.

GitHub: github.com/autosre/autosre
Docs: [link]

I'd love feedback from SREs and platform engineers. What features would make this useful for your on-call rotation?

#SRE #DevOps #AIOps #OpenSource #IncidentManagement #Observability #LangGraph
```

---

## Version B: Story-Driven

```
3:47am. PagerDuty wakes me up.

"CRITICAL: Checkout latency > 5s"

What happens next usually takes 20-30 minutes:
• Open Grafana, find the right dashboard
• Open Datadog, check for correlated errors
• Search Confluence for the runbook (find nothing)
• Check Slack for similar past incidents
• Message the senior engineer who knows this service

I built AutoSRE to fix this.

Now it's one command:
$ autosre investigate "checkout latency spike"

30 seconds later:
✅ Prometheus metrics showing latency jumped at 3:42am
✅ Correlation: Database connection pool exhausted
✅ Similar incident from 3 months ago with resolution
✅ Relevant runbook: "PostgreSQL Connection Pool Exhaustion"

The AI agents do the context-gathering. I do the fixing.

What makes AutoSRE different:

1. Multi-agent architecture (LangGraph)
Not just "ask GPT" – specialized agents for investigation, knowledge search, and action planning coordinate together.

2. Semantic runbook search (ChromaDB)
Your runbooks become searchable by meaning, not just keywords. Index them once, search instantly during incidents.

3. Your data stays yours
Self-hosted, open source, MIT license. No vendor lock-in.

We've been using this internally for 6 months. Median investigation time went from 15 minutes to 2 minutes.

Now it's open source: github.com/autosre/autosre

If you're on-call and tired of context-switching during incidents, give it a try. Would love your feedback.

#SRE #DevOps #AIOps #OnCall #OpenSource #IncidentManagement
```

---

## Version C: Short & Punchy

```
I built an AI assistant for 3am incidents.

One command:
$ autosre investigate "high latency on checkout"

30 seconds later:
• Relevant metrics
• Correlated events
• Similar past incidents
• Matching runbook

No more opening 5 dashboards. No more frantic Confluence searches.

AutoSRE uses LangGraph agents + RAG over your runbooks.

Open source: github.com/autosre/autosre

#SRE #DevOps #AIOps #OpenSource
```

---

## Follow-Up Posts (Week 2+)

### Architecture Post
```
How AutoSRE investigates incidents with AI agents 🧵

When you run `autosre investigate "high latency"`, three LangGraph agents coordinate:

1. Investigation Agent
- Queries Prometheus/Datadog for recent metrics
- Searches logs for errors
- Identifies anomalies and correlations

2. Knowledge Agent
- Searches your runbooks semantically (ChromaDB)
- Finds similar past incidents
- Retrieves relevant documentation

3. Action Agent
- Synthesizes findings
- Suggests remediation steps
- Links to relevant runbooks

Why multi-agent vs. single prompt?

Complex incidents need multi-step reasoning. Each agent is specialized. They share state through LangGraph's graph structure.

The result: what took 20 minutes of context-switching now takes 30 seconds.

Full architecture docs: [link]

#SRE #LangGraph #AIArchitecture #DevOps
```

### Community Update Post
```
1 week since AutoSRE launched! 🎉

The response has been incredible:
⭐ [X] GitHub stars
🍴 [X] forks
🐛 [X] issues
🔀 [X] merged PRs

Thank you to everyone who tried it, gave feedback, and contributed!

Top feature requests so far:
1. Slack integration
2. Claude/local LLM support
3. Automated runbook generation
4. Kubernetes-native deployment

We're working on all of these.

Join the community:
💬 Discord: [link]
📖 Docs: [link]
⭐ GitHub: github.com/autosre/autosre

#OpenSource #SRE #DevOps
```

---

## Hashtag Reference

Always include: #SRE #DevOps #OpenSource

Add as relevant:
- #AIOps (AI/automation focus)
- #IncidentManagement (incident content)
- #Observability (monitoring content)
- #OnCall (on-call focused)
- #LangGraph #LangChain (technical content)
- #PlatformEngineering (platform team focus)
