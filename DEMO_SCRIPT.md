# OpenSRE Demo Script

A step-by-step guide for recording a compelling OpenSRE demo video.

---

## 📋 Pre-Recording Checklist

### Environment Setup
- [ ] Terminal with dark theme (recommended: Dracula, One Dark, or similar)
- [ ] Font size: 16-18pt for readability
- [ ] Terminal dimensions: 120x30 minimum
- [ ] Screen recording software ready (OBS, QuickTime, Loom)
- [ ] Microphone tested and working
- [ ] Notifications disabled (Do Not Disturb)

### Technical Setup
- [ ] Ollama running: `ollama serve`
- [ ] Model pulled: `ollama pull llama3:8b`
- [ ] OpenSRE venv activated: `cd ~/clawd/projects/opensre && source .venv/bin/activate`
- [ ] Demo script executable: `python demo.py --help`

### Optional (for full K8s demo)
- [ ] Kind cluster running: `kind get clusters` shows `opensre-demo`
- [ ] Prometheus installed with metrics flowing
- [ ] Bookstore app deployed

---

## 🎬 Demo Script

### Opening (30 seconds)

**Action:** Terminal open, clear screen

**Say:**
> "Your phone buzzes at 3 AM. PagerDuty alert. Checkout service error rate is spiking. 
> You stumble to your laptop... query Prometheus... tail logs... check deploys...
> 45 minutes later, you find it: a memory leak from the latest deployment.
>
> What if AI could do all of that automatically?
>
> Let me show you OpenSRE."

---

### Scenario 1: Memory Leak (2-3 minutes)

**Action:** Run the demo
```bash
python demo.py
```

**Talking Points:**

1. **When the menu appears:**
   > "OpenSRE includes five real-world incident scenarios. Let's start with the most common one: a memory leak after deployment."

2. **Select scenario 1, press Enter**

3. **When the alert appears:**
   > "Here's our alert. Error rate at 8.3%, memory trending up, three pods OOMKilled.
   > Notice it also shows a recent deployment — v2.4.1 rolled out 12 minutes ago."

4. **Press Enter to start investigation**

5. **During signal collection:**
   > "The Observer agent is now querying our observability stack.
   > It's pulling data from Prometheus, Kubernetes events, and deployment history.
   > This is what would take YOU 15-20 minutes of clicking around."

6. **When LLM analysis appears:**
   > "Now the Reasoner agent correlates all these signals using an LLM.
   > Look at this — 94% confidence it's a memory leak from the new deployment.
   > It's suggesting an immediate rollback, and follow-up steps to investigate the root cause."

7. **Point out the stats:**
   > "This analysis took [X] seconds and used local Ollama — your data never leaves your machine.
   > You could also use GPT-4 or Claude for even better analysis."

8. **At the action prompt:**
   > "Now the Actor agent is waiting for approval. OpenSRE never acts without human confirmation.
   > One tap to approve the rollback, and you can go back to sleep."

---

### Scenario 2: Database Connection Pool (2 minutes)

**Say:**
> "Let's try another one. This time, no recent deployment — something's gone wrong with the database."

**Action:** Select scenario 2

**Talking Points:**

1. **When alert appears:**
   > "P99 latency at 2.3 seconds, database pool at 95%, and 847 active queries when normal is 50.
   > But crucially — no recent deployments. This rules out code changes."

2. **After analysis:**
   > "The AI correctly identifies this as a slow query problem, probably a missing index or a query plan change.
   > It's recommending we identify and kill the blocking queries, then investigate pg_stat_statements."

---

### Scenario 3: Certificate Expiry (1-2 minutes)

**Say:**
> "One more quick one — a classic ops failure mode."

**Action:** Select scenario 3

**Talking Points:**

1. **After analysis:**
   > "Instant diagnosis: certificate expiry. The cert-manager renewal job failed silently three days ago.
   > The AI's telling us to manually renew, then fix the alerting gap."

---

### All Scenarios Summary (30 seconds)

**Action:** Press 'a' to run all scenarios

**Say:**
> "Let me quickly show you all five scenarios. Each one demonstrates a different failure mode:
> memory leaks, database issues, SSL problems, crash loops, and CPU spikes."

**After summary table:**
> "Five incident investigations, all under a minute each.
> Compare that to 45 minutes of manual debugging at 3 AM."

---

### Closing (30 seconds)

**Say:**
> "That's OpenSRE: AI-powered incident response that investigates while you sleep.
>
> It's open source, works with local LLMs for privacy, and integrates with Prometheus, Kubernetes, Slack, and more.
>
> Check it out at github.com/srisainath/opensre. Star the repo if you find it useful.
>
> Thanks for watching!"

---

## ⚠️ Recovery Steps

### If Ollama Fails
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, restart it
ollama serve

# If model missing
ollama pull llama3:8b
```

### If Demo Crashes
```bash
# Kill any hanging Python processes
pkill -f demo.py

# Clear terminal and restart
clear
python demo.py
```

### If Analysis Takes Too Long
- The first request to Ollama may be slow (model loading)
- Subsequent requests should be faster
- If consistently slow, try a smaller model: `ollama pull phi3:mini`

### If Rich Rendering Looks Wrong
- Ensure terminal supports Unicode and 256 colors
- Try: `export TERM=xterm-256color`
- Fallback: iTerm2 or modern terminal emulator

---

## 📝 Post-Recording

### Edit Points
- Trim any awkward pauses during LLM generation
- Speed up the signal collection phase slightly (not too much)
- Add lower-third text for key points:
  - "Observer: Collects signals from infrastructure"
  - "Reasoner: AI analysis with LLM"
  - "Actor: Executes with human approval"

### Thumbnail Ideas
- Terminal showing the alert with "3 AM" overlaid
- Before/After: stressed SRE vs sleeping SRE
- The OpenSRE logo with "AI-Powered Incident Response"

### Video Description Template
```
🛡️ OpenSRE - AI-Powered Incident Response for SRE Teams

Stop debugging at 3 AM. Let AI investigate incidents while you sleep.

In this demo:
00:00 - Introduction
00:30 - Memory Leak Scenario
02:30 - Database Connection Issue
04:30 - Certificate Expiry
05:30 - All Scenarios Summary
06:00 - Closing

Features:
✅ Multi-agent architecture (Observer → Reasoner → Actor)
✅ Local LLM support (Ollama) - your data stays private
✅ Integrates with Prometheus, Kubernetes, Slack, PagerDuty
✅ Human-in-the-loop for safe automation
✅ Open source (Apache 2.0)

🔗 GitHub: https://github.com/srisainath/opensre
📚 Docs: https://opensre.dev/docs
💬 Discord: https://discord.gg/opensre

#SRE #DevOps #AI #Kubernetes #Prometheus #OpenSource #IncidentResponse
```

---

## 🎤 Alternative Narration Styles

### For Technical Audience (SREs/DevOps)
Focus more on the technical details:
> "Notice how it's correlating Prometheus memory metrics with Kubernetes events and deployment timestamps. This is pattern matching that would take multiple PromQL queries and kubectl commands."

### For Executive/Non-Technical Audience
Focus on business value:
> "This could reduce mean-time-to-resolution by 80%. Your on-call engineers get better sleep, and your customers experience less downtime."

### For Conference Talk
Add more context:
> "We built OpenSRE because we were tired of the 3 AM page that required 45 minutes of investigation. The insight was that 90% of that time is just data gathering — something an AI can do faster and more consistently than a sleep-deprived human."
