# OpenSRE Landing Page Content
# Website: opensre.dev

## Hero Section

### Headline
**Stop Debugging at 3 AM**

### Subheadline
OpenSRE is an AI-powered incident response platform that investigates alerts, finds root causes, and remediates issues — while you sleep.

### Hero CTA
[Get Started Free] [View Demo →]

---

## Value Proposition (Above the Fold)

### The 3 AM Problem
Your phone buzzes. PagerDuty alert. You stumble to your laptop. Query Prometheus. Tail logs. Check deploys. 45 minutes later, you find it: a memory leak.

### The OpenSRE Solution
```
🚨 Alert: checkout-service error rate spike (8.3%)

🔍 OpenSRE analyzed:
• Deployment v2.4.1 rolled out 12 min ago
• Memory usage trending up before crashes
• 3 pods OOMKilled

🎯 Root Cause (94% confidence):
Memory leak in v2.4.1

[✅ Approve Rollback] [❌ Dismiss]
```

You tap approve. Go back to sleep.

---

## Key Benefits Section

### 🤖 AI That Understands Infrastructure
Multi-agent system that correlates metrics, logs, events, and deployment history to find root causes — not just symptoms.

### ⚡ From Alert to Resolution in Minutes
What used to take 45+ minutes of manual investigation now happens in under 60 seconds. Automatically.

### 👤 Human-in-the-Loop Control
AI suggests. Humans approve. AI executes. You're always in control of what actions get taken.

---

## How It Works Section

### Step 1: Connect Your Stack
```bash
pip install opensre
opensre skill install prometheus kubernetes slack
```

### Step 2: Configure Alerts
Point your Alertmanager webhooks to OpenSRE. That's it.

### Step 3: Sleep Better
When alerts fire, OpenSRE investigates automatically and posts analysis to Slack with one-click approval buttons.

---

## Feature Grid

| Feature | Description |
|---------|-------------|
| **Multi-Signal Analysis** | Correlates Prometheus metrics, K8s events, logs, and deployments |
| **Root Cause Detection** | AI identifies why issues happen, not just what's happening |
| **Slack-Native Workflow** | Interactive buttons, threaded updates, approval flows |
| **Pluggable Skills** | Prometheus, K8s, AWS, GCP, Datadog, and more |
| **Runbook Integration** | Your runbooks inform the AI's decisions |
| **Safe by Default** | Dangerous actions always require human approval |
| **Local LLM Support** | Works with Ollama — your data never leaves your network |
| **Open Source** | Apache 2.0 licensed, community-driven |

---

## Social Proof Section

### Testimonial Placeholders

> "OpenSRE cut our MTTR by 70%. The AI analysis is genuinely helpful, not just noise."
> — **[Name], SRE Lead at [Company]**

> "Finally, an AI tool that actually understands our infrastructure. It caught a deployment-related issue before I even finished waking up."
> — **[Name], Platform Engineer at [Company]**

> "We were skeptical about AI for ops, but the human-in-the-loop approach makes it feel safe. Game changer."
> — **[Name], VP Engineering at [Company]**

---

## Integration Logos

**Works with your existing stack:**

[Prometheus] [Kubernetes] [Slack] [Datadog] [AWS] [GCP] [Azure] [PagerDuty] [Grafana] [ArgoCD]

---

## Comparison Section

### OpenSRE vs Manual Investigation

| | Manual | OpenSRE |
|---|--------|---------|
| Time to Root Cause | 30-60 min | < 60 sec |
| Correlation Effort | High | Automatic |
| Context Gathering | Manual | Automatic |
| 3 AM Friendliness | 😴 | 😎 |

### OpenSRE vs Other AIOps

| | OpenSRE | Proprietary AIOps |
|---|---------|-------------------|
| Open Source | ✅ | ❌ |
| Local LLM | ✅ | ❌ |
| Your Data Stays Yours | ✅ | ❌ |
| Extensible Skills | ✅ | Limited |
| Vendor Lock-in | None | High |

---

## Pricing Section

### Open Source
**Free Forever**

- Full platform
- All built-in skills
- Community support
- Self-hosted

[Get Started →]

### Enterprise
**Contact Us**

- Priority support
- Custom integrations
- SLA guarantees
- Training & onboarding

[Talk to Sales →]

---

## CTA Section

### Ready to Sleep Better?

Stop debugging at 3 AM. Let OpenSRE handle incident investigation so you can focus on building.

```bash
pip install opensre
```

[Get Started Free] [Read the Docs] [Star on GitHub ⭐]

---

## Footer

### Links
- Documentation
- GitHub
- Discord
- Twitter
- Blog

### Resources
- Getting Started
- API Reference
- Examples
- Contributing

### Company
- About
- Contact
- Privacy Policy
- Terms of Service

---

## SEO Metadata

**Title:** OpenSRE — AI-Powered Incident Response for SRE Teams

**Description:** OpenSRE is an open-source platform that automatically investigates alerts, finds root causes, and remediates issues. Stop debugging at 3 AM.

**Keywords:** SRE, DevOps, incident response, AIOps, Prometheus, Kubernetes, monitoring, observability, on-call, automation, open source

---

## Open Graph / Social

**OG Title:** OpenSRE — AI That Debugs at 3 AM So You Don't Have To

**OG Description:** Open-source incident response powered by AI. Correlates metrics, logs, and events to find root causes in seconds.

**OG Image:** [Hero image showing Slack notification with analysis]

---

## Analytics Events to Track

- Page view
- CTA clicks (Get Started, View Demo, Star GitHub)
- Documentation navigation
- GitHub repo visits
- pip install (if trackable via docs)
