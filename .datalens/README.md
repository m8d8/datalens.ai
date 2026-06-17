# Datalens Configuration Directory

This directory contains all local Datalens configuration and state.

## Contents

### `connections/`
Local connection configs for data sources (HTTP APIs, MongoDB, S3, files).

**NOT tracked in git** (in `.gitignore`) — each developer creates their own.

To create: Copy from `../examples/connection-configs/` and edit for your environment.

Example: `connections/my_api.yaml`, `connections/prod_db.yaml`

See: [Connection Config Guide](../docs/CONNECTION_CONFIG.md)

### `secrets.yaml`
Sensitive credentials: API keys, database passwords, AWS credentials.

**NOT tracked in git** (in `.gitignore`).

To set up:
```bash
cp secrets.yaml.example secrets.yaml
# Edit secrets.yaml with your actual credentials
```

See: [Secrets Management](../docs/CONNECTION_CONFIG.md#secrets-management)

### `secrets.yaml.example`
Template showing what secrets.yaml should contain.

**Tracked in git** — use as reference when creating secrets.yaml.

### `.tmp/`
Temporary downloaded files and cache.

**Auto-managed by Datalens** — cleaned up automatically.

- `downloads/http/` — HTTP files (cleanup after 7 days)

## Usage

```bash
# List connections
datalens connection-list --verbose

# Analyze using a connection
datalens analyze --cc my_api

# Secrets are loaded automatically from:
# 1. .datalens/secrets.yaml (this directory)
# 2. ~/.datalens/secrets.yaml (fallback)
```

## Best Practices

✅ **Do:**
- Keep `.datalens/connections/` local (git-ignored)
- Copy examples from `../examples/connection-configs/` 
- Keep `.datalens/secrets.yaml` in `.gitignore`
- Use env var substitution in configs: `${VAR_NAME}`
- Reference env vars in secrets.yaml
- Share `.datalens/secrets.yaml.example` as template

❌ **Don't:**
- Commit `.datalens/connections/` to git
- Commit secrets.yaml to git
- Hardcode secrets in connection configs
- Share `.datalens/secrets.yaml` unencrypted
- Share actual connection endpoints (URLs can be infrastructure-specific)
