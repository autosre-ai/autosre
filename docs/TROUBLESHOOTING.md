# Troubleshooting

Common issues and solutions for OpenSRE.

## Quick Diagnostics

Run the built-in diagnostic tool:

```bash
autosre diagnose
```

This checks:
- Configuration validity
- Service connectivity
- Permissions
- Resource availability

---

## Installation Issues

### Python Version Mismatch

**Symptom:**
```
ERROR: opensre requires Python >=3.11
```

**Solution:**
```bash
# Check Python version
python --version

# Use specific version
python3.11 -m pip install opensre

# Or use pyenv
pyenv install 3.12.0
pyenv global 3.12.0
pip install opensre
```

### Missing System Dependencies

**Symptom:**
```
error: command 'gcc' failed with exit status 1
```

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-dev build-essential

# macOS
xcode-select --install

# Then reinstall
pip install opensre
```

### Permission Denied

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/usr/local/lib/python3.11/...'
```

**Solution:**
```bash
# Use virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install opensre

# Or install to user directory
pip install --user opensre
```

---

## Connection Issues

### Prometheus Not Connecting

**Symptom:**
```
PrometheusError: Connection refused to http://localhost:9090
```

**Diagnosis:**
```bash
# Test connectivity
curl http://localhost:9090/-/healthy

# Check from inside container
kubectl exec -it opensre-pod -- curl http://prometheus:9090/-/healthy
```

**Solutions:**

1. **Wrong URL:**
   ```bash
   export OPENSRE_PROMETHEUS_URL=http://prometheus.monitoring:9090
   ```

2. **Network policy blocking:**
   ```yaml
   # Add network policy allowing egress to Prometheus
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   # ... (see security.md)
   ```

3. **Authentication required:**
   ```yaml
   prometheus:
     url: http://prometheus:9090
     auth:
       type: basic
       username: admin
       password: ${PROMETHEUS_PASSWORD}
   ```

### Kubernetes Not Connecting

**Symptom:**
```
KubernetesError: Unable to connect to the server
```

**Diagnosis:**
```bash
# Check kubeconfig
kubectl config current-context

# Test connectivity
kubectl cluster-info
```

**Solutions:**

1. **Wrong kubeconfig path:**
   ```bash
   export OPENSRE_KUBECONFIG=~/.kube/config
   ```

2. **In-cluster without service account:**
   ```yaml
   apiVersion: v1
   kind: ServiceAccount
   metadata:
     name: opensre
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: opensre
   subjects:
     - kind: ServiceAccount
       name: opensre
       namespace: opensre
   roleRef:
     kind: ClusterRole
     name: view
     apiGroup: rbac.authorization.k8s.io
   ```

3. **Certificate issues:**
   ```bash
   # Skip TLS verification (dev only!)
   export OPENSRE_KUBE_INSECURE=true
   ```

### LLM Not Responding

**Symptom:**
```
LLMError: Connection to ollama timed out
```

**Diagnosis:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check model is available
ollama list
```

**Solutions:**

1. **Ollama not running:**
   ```bash
   ollama serve
   ```

2. **Model not pulled:**
   ```bash
   ollama pull llama3.1:8b
   ```

3. **Wrong host (Docker):**
   ```bash
   # Inside Docker, use host.docker.internal
   export OPENSRE_OLLAMA_HOST=http://host.docker.internal:11434
   ```

4. **GPU memory issues:**
   ```bash
   # Use smaller model
   ollama pull llama3.1:7b-q4_0
   export OPENSRE_OLLAMA_MODEL=llama3.1:7b-q4_0
   ```

### Slack Not Connecting

**Symptom:**
```
SlackError: invalid_auth
```

**Diagnosis:**
```bash
# Test token
curl -X POST https://slack.com/api/auth.test \
  -H "Authorization: Bearer $OPENSRE_SLACK_BOT_TOKEN"
```

**Solutions:**

1. **Wrong token:**
   - Verify token starts with `xoxb-` (bot token)
   - Regenerate token in Slack App settings

2. **Missing scopes:**
   Required OAuth scopes:
   - `chat:write`
   - `channels:read`
   - `groups:read`
   - `users:read`

3. **Bot not in channel:**
   ```
   /invite @opensre
   ```

---

## Investigation Issues

### Investigation Times Out

**Symptom:**
```
InvestigationError: Investigation timed out after 300s
```

**Solutions:**

1. **Increase timeout:**
   ```yaml
   agents:
     timeout: 600  # 10 minutes
   ```

2. **LLM too slow:**
   - Use faster model
   - Reduce context size
   ```yaml
   llm:
     max_context_tokens: 4096
   ```

3. **Too many metrics:**
   - Narrow the query scope
   - Add namespace/service filters

### Investigation Returns No Results

**Symptom:**
```
Investigation complete. No issues found.
```

**Possible causes:**

1. **No relevant metrics:**
   ```bash
   # Check metrics exist
   autosre skill test prometheus
   ```

2. **Time range mismatch:**
   - Alert happened before investigation started
   - Check `--since` parameter

3. **Wrong namespace/context:**
   ```bash
   autosre investigate "error rate" --namespace production
   ```

### Actions Not Executing

**Symptom:**
```
Action queued for approval... (timeout)
```

**Solutions:**

1. **No approvers available:**
   - Check Slack channel
   - Configure additional approvers

2. **Auto-approve safe actions:**
   ```yaml
   safety:
     auto_approve:
       - "kubernetes.get_*"
       - "prometheus.*"
   ```

3. **Approval timeout too short:**
   ```yaml
   safety:
     approval_timeout: 600
   ```

---

## Performance Issues

### High Memory Usage

**Diagnosis:**
```bash
# Check memory
ps aux | grep opensre

# Inside container
kubectl top pod -n opensre
```

**Solutions:**

1. **Limit concurrent investigations:**
   ```yaml
   agents:
     max_concurrent: 2
   ```

2. **Reduce context size:**
   ```yaml
   llm:
     max_context_tokens: 4096
   ```

3. **Increase container memory:**
   ```yaml
   resources:
     requests:
       memory: 1Gi
     limits:
       memory: 2Gi
   ```

### Slow Investigations

**Diagnosis:**
```bash
# Enable timing logs
export OPENSRE_LOG_LEVEL=DEBUG
autosre investigate "test"
```

**Solutions:**

1. **Use faster LLM:**
   ```yaml
   llm:
     provider: ollama
     ollama:
       model: llama3.1:8b  # Faster than 70b
   ```

2. **Enable caching:**
   ```yaml
   cache:
     enabled: true
     ttl: 300
   ```

3. **Reduce metric queries:**
   ```yaml
   prometheus:
     max_query_range: 1h
     max_samples: 10000
   ```

---

## Agent Issues

### Agent Won't Start

**Symptom:**
```
AgentError: Failed to load agent 'incident-responder'
```

**Diagnosis:**
```bash
# Validate agent config
autosre agent validate incident-responder/agent.yaml
```

**Solutions:**

1. **Invalid YAML:**
   ```bash
   # Check YAML syntax
   python -c "import yaml; yaml.safe_load(open('agent.yaml'))"
   ```

2. **Missing skill:**
   ```bash
   autosre skill list --installed
   autosre skill install prometheus kubernetes
   ```

3. **Invalid action reference:**
   - Check action exists in skill
   ```bash
   autosre skill info prometheus
   ```

### Agent Crashes During Execution

**Symptom:**
```
AgentError: Step 'analyze-metrics' failed unexpectedly
```

**Diagnosis:**
```bash
# Get detailed logs
autosre agent logs incident-responder --tail 100

# Enable debug mode
export OPENSRE_DEBUG=true
autosre agent run incident-responder
```

**Solutions:**

1. **Missing context variable:**
   ```yaml
   steps:
     - name: analyze
       action: prometheus.query
       params:
         query: "{{ alert.query }}"  # Ensure 'alert' exists
   ```

2. **Add error handling:**
   ```yaml
   steps:
     - name: risky-step
       action: kubernetes.get_pods
       on_error: continue  # Don't fail entire agent
   ```

### Webhook Not Triggering Agent

**Symptom:**
- Alertmanager/PagerDuty sends webhook
- Agent doesn't run

**Diagnosis:**
```bash
# Check incoming webhooks
tail -f /var/log/opensre/access.log | grep webhook

# Test webhook manually
curl -X POST http://localhost:8000/webhook/alertmanager \
  -H "Content-Type: application/json" \
  -d '{"alerts": [{"status": "firing"}]}'
```

**Solutions:**

1. **Wrong webhook URL:**
   - Alertmanager: `/webhook/alertmanager`
   - PagerDuty: `/webhook/pagerduty`
   - Generic: `/webhook/generic`

2. **Authentication failing:**
   ```bash
   # Check auth header
   curl -v http://localhost:8000/webhook/alertmanager 2>&1 | grep -i auth
   ```

3. **Trigger filter not matching:**
   ```yaml
   triggers:
     - type: webhook
       source: alertmanager
       filter:
         severity: critical  # Must match alert labels
   ```

---

## Docker Issues

### Container Won't Start

**Symptom:**
```
Error: failed to start container: OCI runtime create failed
```

**Solutions:**

1. **Check logs:**
   ```bash
   docker logs opensre
   ```

2. **Missing environment variables:**
   ```bash
   docker run \
     -e OPENSRE_PROMETHEUS_URL=... \
     -e OPENSRE_LLM_PROVIDER=... \
     ghcr.io/srisainath/opensre:latest
   ```

3. **Port already in use:**
   ```bash
   docker run -p 8001:8000 ...
   ```

### Can't Access Host Services

**Symptom:**
```
Connection refused to http://localhost:9090
```

**Solution:**
```bash
# Use special Docker hostname
docker run \
  -e OPENSRE_PROMETHEUS_URL=http://host.docker.internal:9090 \
  -e OPENSRE_OLLAMA_HOST=http://host.docker.internal:11434 \
  ghcr.io/srisainath/opensre:latest
```

---

## Kubernetes Deployment Issues

### Pod CrashLoopBackOff

**Diagnosis:**
```bash
kubectl describe pod -n opensre opensre-xxx
kubectl logs -n opensre opensre-xxx --previous
```

**Common causes:**

1. **Missing secrets:**
   ```bash
   kubectl get secret -n opensre
   # Create if missing
   ```

2. **ConfigMap issues:**
   ```bash
   kubectl get configmap -n opensre opensre-config -o yaml
   ```

3. **Resource limits too low:**
   ```yaml
   resources:
     requests:
       memory: 512Mi
       cpu: 250m
     limits:
       memory: 1Gi
       cpu: 500m
   ```

### Service Account Permissions

**Symptom:**
```
Forbidden: User "system:serviceaccount:opensre:opensre" cannot list pods
```

**Solution:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: opensre
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events", "services"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: opensre
subjects:
  - kind: ServiceAccount
    name: opensre
    namespace: opensre
roleRef:
  kind: ClusterRole
  name: opensre
  apiGroup: rbac.authorization.k8s.io
```

---

## Getting Help

### Debug Mode

Enable verbose logging:

```bash
export OPENSRE_LOG_LEVEL=DEBUG
autosre start --foreground
```

### Collecting Diagnostics

```bash
autosre diagnose --output diagnostics.tar.gz
```

This collects:
- Configuration (secrets redacted)
- Recent logs
- System information
- Connectivity test results

### Community Support

- **GitHub Issues:** [srisainath/opensre/issues](https://github.com/srisainath/opensre/issues)
- **Discussions:** [srisainath/opensre/discussions](https://github.com/srisainath/opensre/discussions)
- **Discord:** [discord.gg/opensre](https://discord.gg/opensre)

### Reporting Bugs

Include:
1. OpenSRE version (`autosre --version`)
2. Python version (`python --version`)
3. OS/container info
4. Configuration (secrets redacted)
5. Full error message and stack trace
6. Steps to reproduce

---

## Next Steps

- **[Getting Started](getting-started.md)** — Basic setup
- **[Configuration](CONFIGURATION.md)** — Configuration reference
- **[Security](security.md)** — Security settings
