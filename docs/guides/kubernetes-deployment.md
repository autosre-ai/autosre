# Kubernetes Deployment

Deploy AutoSRE to your Kubernetes cluster.

## Prerequisites

- Kubernetes 1.25+
- kubectl configured
- Helm 3+ (optional)

## Quick Deploy with Helm

```bash
# Add the AutoSRE Helm repository
helm repo add autosre https://autosre.github.io/charts
helm repo update

# Install AutoSRE
helm install autosre autosre/autosre \
  --namespace autosre \
  --create-namespace \
  --set config.anthropic.apiKey=${ANTHROPIC_API_KEY}
```

## Manual Deployment

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: autosre
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: autosre-secrets
  namespace: autosre
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "your-api-key"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: autosre
  namespace: autosre
spec:
  replicas: 1
  selector:
    matchLabels:
      app: autosre
  template:
    metadata:
      labels:
        app: autosre
    spec:
      serviceAccountName: autosre
      containers:
        - name: autosre
          image: ghcr.io/autosre/autosre:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: autosre-secrets
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
```

### Service Account

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: autosre
  namespace: autosre
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: autosre-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "events", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: autosre-reader
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: autosre-reader
subjects:
  - kind: ServiceAccount
    name: autosre
    namespace: autosre
```

## Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: autosre
  namespace: autosre
spec:
  selector:
    app: autosre
  ports:
    - port: 8000
      targetPort: 8000
```

## Ingress (optional)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: autosre
  namespace: autosre
spec:
  rules:
    - host: autosre.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: autosre
                port:
                  number: 8000
```
