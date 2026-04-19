# Vault Skill

HashiCorp Vault secrets management.

## Configuration

```yaml
vault:
  url: https://vault.example.com
  token: ${VAULT_TOKEN}
  namespace: admin  # Optional, Enterprise only
  # Or use AppRole auth:
  auth_method: approle
  role_id: ${VAULT_ROLE_ID}
  secret_id: ${VAULT_SECRET_ID}
```

## Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| `read_secret` | Read a secret | `path`, `version` |
| `list_secrets` | List secrets at path | `path` |
| `get_health` | Get Vault health | |
| `get_seal_status` | Get seal status | |
| `list_auth_methods` | List auth methods | |
| `renew_token` | Renew current token | |

## Example Usage

```python
# Read a secret (KV v2)
result = await vault.read_secret(path="secret/data/myapp/config")

# List secrets
result = await vault.list_secrets(path="secret/metadata/myapp")

# Check Vault health
result = await vault.get_health()
if result.data.sealed:
    print("WARNING: Vault is sealed!")
```

## KV Paths

- **KV v1**: `secret/myapp/config`
- **KV v2**: `secret/data/myapp/config` (read), `secret/metadata/myapp/config` (list)

## Auth Methods

- `token` - Use a pre-existing token
- `approle` - Authenticate with role_id and secret_id
- `kubernetes` - Authenticate using K8s service account (in-cluster)
