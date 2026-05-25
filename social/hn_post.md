# AutoSRE Hacker News Launch Post

---

## Show HN Post

**Title:**
```
Show HN: AutoSRE – AI-powered incident investigation with LangGraph agents
```

**URL:**
```
https://github.com/autosre/autosre
```

**Text (Comment):**
```
Hi HN,

I'm releasing AutoSRE, an open-source AI assistant for SRE incident investigation.

The problem: At 3am when PagerDuty wakes you up, you spend 20 minutes gathering context - opening dashboards, searching for runbooks, checking Slack history for similar incidents. Only then can you start fixing.

AutoSRE does the context-gathering for you:

    $ autosre investigate "checkout latency spike" --service checkout

In ~30 seconds, you get:
- Relevant metrics from Prometheus/Datadog
- Correlated events and anomalies
- Similar past incidents
- Matching runbook with remediation steps

How it works:

1. LangGraph agents coordinate the investigation:
   - Investigation Agent queries metrics/logs
   - Knowledge Agent searches runbooks semantically
   - Action Agent suggests remediation

2. ChromaDB + RAG for runbook search:
   - Index your runbooks (Markdown, Confluence, Notion)
   - Semantic search finds relevant docs even without keyword matches
   - "database slow" → finds "PostgreSQL connection pool exhaustion" runbook

3. Integrates with existing tools:
   - Monitoring: Prometheus, Datadog, New Relic
   - Alerting: PagerDuty, Alertmanager, Opsgenie
   - Logging: Loki, Elasticsearch

Tech stack: LangGraph, LangChain, ChromaDB, FastAPI, Typer

Quick start:
    pip install autosre
    export OPENAI_API_KEY=sk-...
    autosre chat

We've used this internally for ~6 months. Median investigation time went from 15 minutes to 2 minutes.

MIT licensed. Would love feedback and contributions.

What features would make this useful for your on-call rotation?
```

---

## Alternative Titles (A/B test)

```
Show HN: AutoSRE – Open-source AI assistant for on-call engineers
Show HN: AutoSRE – LangGraph agents for incident investigation
Show HN: AutoSRE – Semantic runbook search for 3am incidents
Show HN: AutoSRE – AI that gathers incident context so you don't have to
```

---

## Reply Templates

Keep these ready for common questions/comments:

### "How is this different from ChatGPT/Claude?"
```
ChatGPT is general-purpose. AutoSRE is specialized for incident investigation:

1. Multi-agent architecture: Three agents coordinate (investigation, knowledge, action) vs. a single prompt

2. Tool integrations: Queries your actual Prometheus/Datadog/PagerDuty, not just general knowledge

3. Your runbooks: RAG over your docs means it knows YOUR infrastructure

4. CLI-first: Designed for 3am terminal usage

You could prompt-engineer ChatGPT to do some of this, but AutoSRE is turnkey for incident workflows.
```

### "Does it actually work in practice?"
```
We've used it internally for 6 months on ~200 incidents.

Measurable impact:
- Median investigation time: 15 min → 2 min
- Runbook find time: 5 min → instant
- Escalations (context not included): Down ~40%

The agents work well for "gathering context" tasks. For novel incidents, it still surfaces relevant history and runbooks even if it can't solve automatically.

That said, we'd love more real-world testing. Try it and let us know what breaks!
```

### "Why LangGraph vs. just calling OpenAI?"
```
Complex incidents need multi-step reasoning:

1. Query metrics → find anomaly
2. Correlate with logs → identify errors
3. Search runbooks → find procedures
4. Check history → similar incidents
5. Synthesize → suggest remediation

Single prompt can't coordinate this well. LangGraph lets us define a state graph where specialized agents handle each step and pass context to the next.

Also makes it easier to add new capabilities (just add a node to the graph) and debug (each step is observable).
```

### "What about data privacy/security?"
```
AutoSRE runs locally. Your data stays on your infrastructure.

- No data sent to AutoSRE servers (there aren't any)
- OpenAI API calls contain only what you investigate (you control this)
- ChromaDB stores embeddings locally
- MIT license, full source available

For air-gapped environments, we're adding support for local LLMs (Ollama). Coming soon.
```

### "What's the business model?"
```
None right now. This is a genuine open-source release (MIT license).

We built this to solve our own problem. Making it available because we think more SRE teams could benefit.

If there's demand, we might offer:
- Managed cloud version
- Enterprise support
- Premium integrations

But the core will always be open source.
```

### "What's on the roadmap?"
```
Near-term (Q1):
- Slack integration (get summaries where you work)
- Claude + Ollama support (more LLM options)
- Automated runbook generation from resolutions
- Kubernetes-native deployment (Helm chart)

Medium-term (Q2-Q3):
- Training mode (learn from your resolution patterns)
- Multi-cluster support
- Anomaly detection improvements
- Mobile app for on-call

What would you prioritize? Always looking for feedback.
```

### "This seems like a thin wrapper around LangChain"
```
Fair question. The value-add beyond LangChain/LangGraph:

1. Pre-built agents for SRE workflows (investigation, knowledge, action)
2. Integrations with monitoring/alerting tools (Prometheus, PagerDuty, etc.)
3. ChromaDB setup for runbook indexing
4. CLI designed for incident response
5. Battle-tested on real incidents for 6 months

You could build this yourself with LangChain. AutoSRE saves you ~2 months of integration work.

Think of it as "LangChain for SRE" – specialized tooling for a specific domain.
```

### On criticism/skepticism (general approach)
```
Appreciate the skepticism – it's warranted for AI tools.

A few things:
1. Try it on a test incident. 30 min setup, then judge for yourself.
2. Open source, so you can see exactly what it does
3. We're not claiming it solves all incidents – it's a context-gathering assistant

Happy to dig into specific concerns. What would make you more confident this is useful?
```

---

## Timing Tips

Best times to post on HN:
- Tuesday-Thursday
- 9-10am PT (12-1pm ET)
- Avoid weekends and holidays

Engagement:
- Reply to every comment in the first few hours
- Be genuine, acknowledge limitations
- Don't be defensive about criticism
- Thank people for feedback, even negative
