# systemd Deployment

Deploy OpenSRE as a systemd service on Linux systems.

## Prerequisites

- Linux with systemd
- Python 3.11+
- pip or pipx
- Access to Prometheus, Kubernetes, etc.

## Installation

### Install OpenSRE

```bash
# System-wide
sudo pip install opensre

# Or user-level with pipx
pipx install opensre

# Or from source
git clone https://github.com/srisainath/opensre.git
cd opensre
pip install -e .
```

### Create Service User

```bash
# Create dedicated user
sudo useradd -r -s /bin/false opensre

# Create directories
sudo mkdir -p /etc/opensre
sudo mkdir -p /var/lib/opensre
sudo mkdir -p /var/log/opensre

# Set ownership
sudo chown opensre:opensre /var/lib/opensre
sudo chown opensre:opensre /var/log/opensre
```

## Configuration

### Config File

```yaml
# /etc/opensre/opensre.yaml
log_level: INFO

llm:
  provider: ollama
  ollama:
    host: http://localhost:11434
    model: llama3.1:8b

prometheus:
  url: http://prometheus:9090

kubernetes:
  kubeconfig: /etc/opensre/kubeconfig

slack:
  bot_token: ${OPENSRE_SLACK_BOT_TOKEN}
  channel: "#incidents"

server:
  host: 127.0.0.1
  port: 8000

data_dir: /var/lib/opensre
```

### Environment File

```bash
# /etc/opensre/opensre.env
OPENSRE_CONFIG_PATH=/etc/opensre/opensre.yaml
OPENSRE_SLACK_BOT_TOKEN=xoxb-your-token
OPENSRE_API_KEY=your-api-key
OPENSRE_LOG_LEVEL=INFO
```

### Set Permissions

```bash
sudo chmod 600 /etc/opensre/opensre.env
sudo chmod 644 /etc/opensre/opensre.yaml
sudo chown opensre:opensre /etc/opensre/*
```

## systemd Service

### Service Unit

```ini
# /etc/systemd/system/opensre.service
[Unit]
Description=OpenSRE - AI-Powered Incident Response
Documentation=https://opensre.dev/docs
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=opensre
Group=opensre

# Environment
EnvironmentFile=/etc/opensre/opensre.env

# Working directory
WorkingDirectory=/var/lib/opensre

# Start command
ExecStart=/usr/local/bin/opensre start --foreground

# Restart policy
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/opensre /var/log/opensre
ReadOnlyPaths=/etc/opensre

# Resource limits
MemoryMax=2G
CPUQuota=200%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=opensre

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable at boot
sudo systemctl enable opensre

# Start service
sudo systemctl start opensre

# Check status
sudo systemctl status opensre
```

## Log Management

### View Logs

```bash
# Recent logs
sudo journalctl -u opensre -n 100

# Follow logs
sudo journalctl -u opensre -f

# Logs since today
sudo journalctl -u opensre --since today

# Error-level logs only
sudo journalctl -u opensre -p err
```

### Log Rotation

```bash
# /etc/logrotate.d/opensre
/var/log/opensre/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 opensre opensre
    postrotate
        systemctl reload opensre > /dev/null 2>&1 || true
    endscript
}
```

## Management Commands

```bash
# Start
sudo systemctl start opensre

# Stop
sudo systemctl stop opensre

# Restart
sudo systemctl restart opensre

# Reload config (graceful)
sudo systemctl reload opensre

# Status
sudo systemctl status opensre

# Logs
sudo journalctl -u opensre -f
```

## Socket Activation (Optional)

For on-demand startup:

```ini
# /etc/systemd/system/opensre.socket
[Unit]
Description=OpenSRE Socket

[Socket]
ListenStream=127.0.0.1:8000
Accept=no

[Install]
WantedBy=sockets.target
```

```ini
# /etc/systemd/system/opensre.service (modified)
[Unit]
Description=OpenSRE
Requires=opensre.socket
After=opensre.socket

[Service]
# ... rest of config
```

```bash
sudo systemctl enable opensre.socket
sudo systemctl start opensre.socket
```

## Monitoring

### Health Check Timer

```ini
# /etc/systemd/system/opensre-health.timer
[Unit]
Description=OpenSRE Health Check Timer

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/opensre-health.service
[Unit]
Description=OpenSRE Health Check

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -sf http://localhost:8000/health || systemctl restart opensre
```

```bash
sudo systemctl enable opensre-health.timer
sudo systemctl start opensre-health.timer
```

### Prometheus Metrics

If you have node_exporter with textfile collector:

```bash
#!/bin/bash
# /usr/local/bin/opensre-metrics.sh
METRICS_FILE=/var/lib/node_exporter/textfile_collector/opensre.prom

# Get metrics from OpenSRE
curl -s http://localhost:8000/metrics > $METRICS_FILE.tmp
mv $METRICS_FILE.tmp $METRICS_FILE
```

Add to cron:
```bash
* * * * * /usr/local/bin/opensre-metrics.sh
```

## Reverse Proxy

### nginx

```nginx
# /etc/nginx/sites-available/opensre
upstream opensre {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name opensre.example.com;

    ssl_certificate /etc/letsencrypt/live/opensre.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/opensre.example.com/privkey.pem;

    location / {
        proxy_pass http://opensre;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /webhook/ {
        proxy_pass http://opensre;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300;
    }
}
```

### caddy

```caddyfile
# /etc/caddy/Caddyfile
opensre.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

## Firewall

### UFW

```bash
# Allow from Alertmanager
sudo ufw allow from 10.0.0.0/8 to any port 8000

# Or allow from specific hosts
sudo ufw allow from alertmanager.example.com to any port 8000
```

### firewalld

```bash
# Create zone
sudo firewall-cmd --permanent --new-zone=opensre
sudo firewall-cmd --permanent --zone=opensre --add-source=10.0.0.0/8
sudo firewall-cmd --permanent --zone=opensre --add-port=8000/tcp
sudo firewall-cmd --reload
```

## Upgrades

```bash
# Stop service
sudo systemctl stop opensre

# Upgrade
sudo pip install --upgrade opensre

# Start service
sudo systemctl start opensre

# Verify
opensre --version
sudo systemctl status opensre
```

## Uninstall

```bash
# Stop and disable
sudo systemctl stop opensre
sudo systemctl disable opensre

# Remove service
sudo rm /etc/systemd/system/opensre.service
sudo systemctl daemon-reload

# Remove package
sudo pip uninstall opensre

# Clean up (optional)
sudo userdel opensre
sudo rm -rf /etc/opensre
sudo rm -rf /var/lib/opensre
sudo rm -rf /var/log/opensre
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u opensre -n 50

# Check config
sudo -u opensre opensre config validate

# Test manually
sudo -u opensre opensre start --foreground
```

### Permission Issues

```bash
# Check file ownership
ls -la /etc/opensre/
ls -la /var/lib/opensre/

# Fix ownership
sudo chown -R opensre:opensre /etc/opensre
sudo chown -R opensre:opensre /var/lib/opensre
```

### Port Already in Use

```bash
# Find process
sudo ss -tlnp | grep 8000

# Kill if needed
sudo fuser -k 8000/tcp
```

## See Also

- [Docker Deployment](docker.md)
- [Kubernetes Deployment](kubernetes.md)
- [Configuration](../CONFIGURATION.md)
