# Kubernetes Deployment

Deploy OpenSRE to Kubernetes using Helm or raw manifests.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.8+ (for Helm deployment)
- kubectl configured
- Prometheus accessible within cluster
- Ollama or external LLM API access

## Helm Deployment (Recommended)

### Add Repository

```bash
helm repo add opensre https://srisainath.github.io/opensre
helm repo update
```

### Basic Installation

```bash
helm install opensre opensre/opensre \
  --namespace opensre \
  --create-namespace
```

### Custom Values

Create `values.yaml`:

```yaml
# values.yaml
replicaCount: 2

image:
  repository: ghcr.io/srisainath/opensre
  tag: latest
  pullPolicy: IfNotPresent

# LLM Configuration
llm:
  provider: ollama
  ollama:
    host: http://ollama.ollama:11434
    model: llama3.1:8b
  # Or use OpenAI
  # provider: openai
  # openai:
  #   apiKey: "" # Set via secret

# Prometheus
prometheus:
  url: http://prometheus-server.monitoring:9090
  auth:
    type: none

# Slack
slack:
  enabled: true
  botToken: ""  # Set via secret
  channel: "#incidents"

# API
api:
  port: 8000
  # Generate with: openssl rand -hex 32
  apiKey: ""  # Set via secret

# Service
service:
  type: ClusterIP
  port: 8000

# Ingress
ingress:
  enabled: false
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: opensre.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: opensre-tls
      hosts:
        - opensre.example.com

# Resources
resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 2Gi

# Autoscaling
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70

# Persistence
persistence:
  enabled: true
  storageClass: ""
  size: 10Gi

# Service Account
serviceAccount:
  create: true
  name: opensre
  annotations: {}

# RBAC
rbac:
  create: true
  clusterRole: true  # Access all namespaces

# Pod Security
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000

securityContext:
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL

# Probes
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 5
  periodSeconds: 5

# Node selection
nodeSelector: {}
tolerations: []
affinity: {}
```

### Install with Values

```bash
helm install opensre opensre/opensre \
  --namespace opensre \
  --create-namespace \
  --values values.yaml \
  --set slack.botToken=$SLACK_BOT_TOKEN \
  --set api.apiKey=$API_KEY
```

### Using Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: opensre-secrets
  namespace: opensre
type: Opaque
stringData:
  slack-bot-token: xoxb-your-token
  api-key: your-api-key
  openai-api-key: sk-your-key  # If using OpenAI
```

```bash
kubectl apply -f secrets.yaml
```

Reference in values:

```yaml
# values.yaml
existingSecret: opensre-secrets
secretKeys:
  slackBotToken: slack-bot-token
  apiKey: api-key
```

## Raw Manifest Deployment

### Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: opensre
  labels:
    name: opensre
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: opensre-config
  namespace: opensre
data:
  opensre.yaml: |
    log_level: INFO
    
    llm:
      provider: ollama
      ollama:
        host: http://ollama.ollama:11434
        model: llama3.1:8b
    
    prometheus:
      url: http://prometheus-server.monitoring:9090
    
    slack:
      channel: "#incidents"
    
    safety:
      auto_approve:
        - "prometheus.*"
        - "kubernetes.get_*"
        - "kubernetes.describe_*"
      require_approval:
        - "kubernetes.rollback"
        - "kubernetes.delete_*"
        - "kubernetes.scale"
```

### Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: opensre-secrets
  namespace: opensre
type: Opaque
stringData:
  slack-bot-token: xoxb-your-token
  api-key: your-api-key
```

### ServiceAccount & RBAC

```yaml
# rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: opensre
  namespace: opensre
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: opensre
rules:
  # Read-only access to most resources
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events", "services", "endpoints", "configmaps", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch"]
  
  # Write access for remediation
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["delete"]  # For pod restart
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["patch", "update"]  # For scaling, rollback
  - apiGroups: ["apps"]
    resources: ["deployments/rollback"]
    verbs: ["create"]
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

### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opensre
  namespace: opensre
  labels:
    app: opensre
spec:
  replicas: 2
  selector:
    matchLabels:
      app: opensre
  template:
    metadata:
      labels:
        app: opensre
    spec:
      serviceAccountName: opensre
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: opensre
          image: ghcr.io/srisainath/opensre:latest
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          env:
            - name: OPENSRE_CONFIG_PATH
              value: /app/config/opensre.yaml
            - name: OPENSRE_SLACK_BOT_TOKEN
              valueFrom:
                secretKeyRef:
                  name: opensre-secrets
                  key: slack-bot-token
            - name: OPENSRE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: opensre-secrets
                  key: api-key
          volumeMounts:
            - name: config
              mountPath: /app/config
              readOnly: true
            - name: data
              mountPath: /app/data
            - name: tmp
              mountPath: /tmp
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: 1000m
              memory: 2Gi
          securityContext:
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: config
          configMap:
            name: opensre-config
        - name: data
          persistentVolumeClaim:
            claimName: opensre-data
        - name: tmp
          emptyDir: {}
```

### PVC

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: opensre-data
  namespace: opensre
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: opensre
  namespace: opensre
  labels:
    app: opensre
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: http
      protocol: TCP
      name: http
  selector:
    app: opensre
```

### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: opensre
  namespace: opensre
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - opensre.example.com
      secretName: opensre-tls
  rules:
    - host: opensre.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: opensre
                port:
                  number: 8000
```

### Apply All

```bash
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f rbac.yaml
kubectl apply -f pvc.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
```

## Network Policies

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: opensre
  namespace: opensre
spec:
  podSelector:
    matchLabels:
      app: opensre
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
      ports:
        - port: 8000
    # Allow from Alertmanager
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
        - podSelector:
            matchLabels:
              app: alertmanager
      ports:
        - port: 8000
  egress:
    # Allow to Prometheus
    - to:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - port: 9090
    # Allow to Ollama
    - to:
        - namespaceSelector:
            matchLabels:
              name: ollama
      ports:
        - port: 11434
    # Allow to Kubernetes API
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - port: 443
    # Allow DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
    # Allow Slack API
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - port: 443
```

## Pod Disruption Budget

```yaml
# pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: opensre
  namespace: opensre
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: opensre
```

## HPA

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: opensre
  namespace: opensre
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: opensre
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

## Deploying Ollama

If you need Ollama in-cluster:

```yaml
# ollama.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ollama
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ollama
  namespace: ollama
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
        - name: ollama
          image: ollama/ollama:latest
          ports:
            - containerPort: 11434
          volumeMounts:
            - name: ollama-data
              mountPath: /root/.ollama
          resources:
            requests:
              cpu: 2000m
              memory: 8Gi
            limits:
              cpu: 4000m
              memory: 16Gi
              # GPU support
              # nvidia.com/gpu: 1
      volumes:
        - name: ollama-data
          persistentVolumeClaim:
            claimName: ollama-data
---
apiVersion: v1
kind: Service
metadata:
  name: ollama
  namespace: ollama
spec:
  selector:
    app: ollama
  ports:
    - port: 11434
      targetPort: 11434
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ollama-data
  namespace: ollama
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
```

Pull model after deployment:

```bash
kubectl exec -it -n ollama deploy/ollama -- ollama pull llama3.1:8b
```

## Verification

```bash
# Check pods
kubectl get pods -n opensre

# Check logs
kubectl logs -n opensre -l app=opensre

# Test health
kubectl port-forward -n opensre svc/opensre 8000:8000
curl http://localhost:8000/health

# Check status
kubectl exec -it -n opensre deploy/opensre -- opensre status
```

## See Also

- [Docker Deployment](docker.md)
- [Configuration](../CONFIGURATION.md)
- [Security](../security.md)
