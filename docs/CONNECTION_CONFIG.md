# Connection Config System - Datalens

Store, reuse, and manage data source credentials with the connection config system. No more repeating credentials on the command line!

## Quick Start

```bash
# 1. Create a connection config
mkdir -p .datalens/connections
cat > .datalens/connections/my_api.yaml << 'EOF'
name: my_api
source_type: http
params:
  uri: "https://api.example.com/v1/data"
  auth_type: bearer
  auth_token: "${API_TOKEN}"
EOF

# 2. Set environment variable
export API_TOKEN=sk-abc123...

# 3. Analyze using the connection
datalens analyze --cc my_api
# Output: output/my_api_0611_040438/
```

---

## Two Approaches to Analysis

Datalens supports both **quick one-off analysis** and **reusable connection configs**. Choose what works best for your workflow:

| Approach | Command | Output Directory | Best For |
|----------|---------|------------------|----------|
| **Connection Config** (Recommended) | `datalens analyze --cc my_api` | `my_api_0611_040438/` | Teams, reusable, tracking credentials |
| **Direct HTTP** | `datalens analyze --source http --uri https://api.example.com/data` | `api_example_com_0611_040438/` | Quick one-off API analysis |
| **Direct File** | `datalens analyze --source file --path data.csv` | `data_0611_040438/` | Quick one-off file analysis |
| **Direct MongoDB** | `datalens analyze --source mongodb --db mydb --uri mongodb://...` | `mydb_0611_040438/` | Quick one-off database analysis |

### Key Differences

**Connection Config (`--cc`):**
- ✅ Store credentials once, reuse everywhere
- ✅ Cleaner command line (just `--cc my_api`)
- ✅ Easy to share with team
- ✅ Output directory uses config name (more meaningful)
- ✅ Metadata tracking (owner, tags, created date)

**Direct Analysis (`--source`):**
- ✅ No setup needed - analyze immediately
- ✅ Perfect for quick exploration
- ✅ Output directory extracted from source (URI domain, filename, etc.)
- ✅ Full backward compatibility

---

## Features

✅ **Store Credentials Securely** - Keep connection details in YAML files, secrets in env vars  
✅ **Reuse Across Projects** - Store globally in `~/.datalens/connections/`  
✅ **Support All Sources** - HTTP APIs, MongoDB, S3, Local Files  
✅ **Override Params** - Use config as base, override with CLI flags  
✅ **Auto-cleanup** - Download management with 7-day auto-cleanup  
✅ **Organized Output** - Each analysis in its own descriptive directory  
✅ **Environment Variables** - Secrets via `${VAR_NAME}` substitution  

---

## Directory Structure

```
.datalens/
├── connections/                       # Local connection configs (git-ignored, private)
│   ├── .gitkeep
│   ├── my_api.yaml
│   ├── prod_db.yaml
│   └── s3_data_lake.yaml
├── secrets.yaml                       # Local secrets (git-ignored)
├── secrets.yaml.example               # Template (tracked in git)
├── README.md                          # This directory guide
└── .tmp/
    └── downloads/
        └── http/                      # Auto-downloaded HTTP files (cleanup after 7 days)
            ├── 20250611_033501_catalogue.json
            └── ...

~/.datalens/
├── connections/                       # User-global connection configs (git-ignored)
│   └── ...
└── secrets.yaml                       # User-global secrets (git-ignored)

# Examples (for reference, tracked in git)
examples/
└── connection-configs/                # Ready-to-use examples
    ├── http-bearer-token.yaml
    ├── mongodb-atlas.yaml
    └── ...

output/
├── api_example_com_0611_033501/      # HTTP API analysis
├── prod_db_0611_033502/              # MongoDB analysis
└── my_data_0611_033503/              # File analysis
```

---

## Connection Config Format

### Basic Structure

```yaml
name: connection_name              # Must match filename
source_type: http|mongodb|s3|file # Data source type
description: "Optional description"

params:                            # Source-specific parameters
  # Varies by source type (see below)

profiling:                         # Optional: override defaults
  sample_size: 5000
  max_depth: 10

metadata:                          # Optional: for tracking
  created: "2026-06-11"
  tags: ["prod", "critical"]
```

### HTTP/REST API Connection

```yaml
name: api_prod
source_type: http
description: "Production API endpoint"

params:
  uri: "https://api.example.com/v1"
  
  # Choose ONE auth method:
  
  # Option 1: Bearer Token (OAuth2, JWT)
  auth_type: bearer
  auth_token: "${API_TOKEN}"
  
  # Option 2: Basic Auth (username/password)
  # auth_type: basic
  # username: "user"
  # password: "${API_PASSWORD}"
  
  # Option 3: API Key (custom header)
  # auth_type: api_key
  # api_key: "${API_KEY}"
  # api_key_header: "X-API-Key"     # default: X-API-Key
  
  # Optional: HTTP settings
  timeout: 30                       # Request timeout in seconds
  max_retries: 3                    # Retry attempts
  custom_headers:                   # Additional headers
    Accept: "application/json"
    X-Client-ID: "datalens"
```

### MongoDB Connection

```yaml
name: mongo_prod
source_type: mongodb
description: "Production MongoDB cluster"

params:
  db: "analytics"                   # Database name
  uri: "${MONGO_URI}"               # Connection string (env var)
  collections: "users,orders"       # Comma-separated collections

  # Optional: Query-based sampling
  # objects:
  #   - "users|{\"active\": true} -> ActiveUsers"
  #   - "orders|{\"status\": \"completed\"} -> Completed"
```

### S3 Bucket Connection

```yaml
name: s3_data_lake
source_type: s3
description: "S3 data lake bucket"

params:
  uri: "s3://my-bucket/data/"       # S3 path
  region: "us-east-1"               # AWS region
  access_key_id: "${AWS_ACCESS_KEY_ID}"
  secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
```

### Local File Connection

```yaml
name: local_data
source_type: file
description: "Local CSV file"

params:
  path: "${DATA_DIR}/export.csv"    # File path (supports env vars)
  # Optional for JSON/XML:
  # root: "items"                   # Root element path for JSON/XML
  # Optional for Excel:
  # sheets: "Sheet1,Sheet2"         # Comma-separated sheet names
```

---

## Connection Lookup Resolution

When you use `datalens analyze --cc my_api`, the system looks for the config in this order:

1. **Full Path** (if `my_api` contains `/`)
   - `/custom/path/to/config.yaml` → Load directly
   
2. **Project-Local** (first location checked)
   - `.datalens/connections/my_api.yaml` → Found! Use this
   
3. **User-Global** (fallback)
   - `~/.datalens/connections/my_api.yaml` → Found! Use this
   
4. **Not Found** → Error with helpful hints

**Best Practice:** Store shared team configs in `.datalens/connections/` (project) and personal credentials in `~/.datalens/connections/` (global).

---

## Secrets Management

Keep sensitive data (API keys, database passwords, AWS credentials) separate from config files.

### Option 1: Secrets File (Recommended for projects)

Create `.datalens/secrets.yaml` (git-ignored):

```yaml
# .datalens/secrets.yaml
mongodb:
  uri: "mongodb+srv://user:pass@cluster.mongodb.net"
anthropic:
  api_key: "sk-ant-..."
openai:
  api_key: "sk-..."
http:
  headers:
    Authorization: "Bearer ..."
```

Then reference in connection configs using env var substitution:

```yaml
# .datalens/connections/mongo_prod.yaml
name: mongo_prod
source_type: mongodb
params:
  db: analytics
  uri: "${MONGO_URI}"
  collections: users,orders
```

**Datalens automatically searches for secrets in:**
1. `.datalens/secrets.yaml` (project-local, checked first)
2. `~/.datalens/secrets.yaml` (user-global fallback)

No extra flags needed — just create the file and it's loaded automatically.

### Option 2: Environment Variables

Secrets are **never stored in config files**. Use environment variables instead:

```yaml
# .datalens/connections/api_prod.yaml
params:
  auth_token: "${API_TOKEN}"
```

### Load from Multiple Sources (in order):

1. **Shell environment** (highest priority)
   ```bash
   export API_TOKEN=sk-abc123...
   datalens analyze --cc api_prod
   ```

2. **.env file** (in project root)
   ```bash
   # Create .env
   cat > .env << 'EOF'
   API_TOKEN=sk-abc123...
   MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net
   AWS_ACCESS_KEY_ID=AKIA...
   EOF
   
   # No need to export; datalens reads .env automatically
   datalens analyze --cc api_prod
   ```

3. **Missing variable** → Error with hint
   ```
   Error: Environment variable 'API_TOKEN' not found.
   Set it with: export API_TOKEN=your_token
   ```

---

## Usage Examples

### 1. Analyze HTTP API

```bash
# Create connection
cat > .datalens/connections/jsonplaceholder.yaml << 'EOF'
name: jsonplaceholder
source_type: http
description: "JSONPlaceholder test API"
params:
  uri: "https://jsonplaceholder.typicode.com/users"
EOF

# Analyze
datalens analyze --cc jsonplaceholder
# Output: output/jsonplaceholder_0611_033501/
```

### 2. Analyze MongoDB with Auth

```bash
# Create connection
cat > .datalens/connections/prod_db.yaml << 'EOF'
name: prod_db
source_type: mongodb
params:
  db: "analytics"
  uri: "${MONGO_URI}"
  collections: "users,orders,products"
EOF

# Set credentials
export MONGO_URI="mongodb+srv://admin:SecureP@ss123@prod-cluster.mongodb.net"

# Analyze
datalens analyze --cc prod_db
# Output: output/prod_db_0611_033502/

# With overrides
datalens analyze --cc prod_db --sample-size 5000 --max-depth 8
```

### 3. Analyze CSV with Output Customization

```bash
# Create connection
cat > .datalens/connections/customer_data.yaml << 'EOF'
name: customer_data
source_type: file
params:
  path: "${DATA_DIR}/customers.csv"
EOF

# Set data directory
export DATA_DIR=/data/exports

# Analyze
datalens analyze --cc customer_data
# Output: output/customer_data_0611_033503/
```

### 4. Compare Against Previous Run (Drift Detection)

```bash
# First run
datalens analyze --cc my_api
# Output: output/api_example_com_0611_033501/
#   └── .history/20250611_033501/schema.json

# Later, detect drift against previous run
datalens analyze --cc my_api --detect-drift
# Compares against most recent run, highlights changes

# Or compare against specific run
datalens analyze --cc my_api --compare-to 20250611_033501
```

### 5. List Available Connections

```bash
$ datalens connection-list

Available Connections:
  api_prod           (http)
  customer_data      (file)
  prod_db            (mongodb)
  s3_data_lake       (s3)

Usage: datalens analyze --cc {connection_name}
```

---

## CLI Commands & Flags

### Analyze with Connection Config

```bash
# Required
datalens analyze --cc CONNECTION_NAME

# Optional flags (override config values)
datalens analyze --cc my_api \
  --sample-size 1000 \
  --max-depth 8 \
  --out-dir ./results \
  --ai anthropic \
  --detect-drift
```

### List Connections

```bash
datalens connection-list
```

### Output Directory Naming

Each analysis creates a **timestamped subdirectory** under `--out-dir` (default: `output/`). The directory name is generated based on how you invoke datalens:

**Connection Config** (recommended for teams):
```bash
datalens analyze --cc my_api
# → output/my_api_0611_040438/
```
✅ Uses the **connection config name** — clear and meaningful

**Direct HTTP Analysis** (quick one-off):
```bash
datalens analyze --source http --uri https://api.example.com/data
# → output/api_example_com_0611_040438/
```
✅ Extracts **domain from URI** — descriptive

**Direct File Analysis** (quick one-off):
```bash
datalens analyze --source file --path data.csv
# → output/data_0611_040438/
```
✅ Uses **filename** — descriptive

**Direct MongoDB** (quick one-off):
```bash
datalens analyze --source mongodb --db analytics --uri mongodb://...
# → output/analytics_0611_040438/
```
✅ Uses **database name** — descriptive

**Directory Format:** `{identifier}_{MMDD_HHMMSS}`
- `identifier`: Connection name, domain, filename, or db name
- `MMDD_HHMMSS`: Month-Day_Hour-Minute-Second (unique per second)

### Use Full Path to Config

```bash
# No need for .datalens/connections/ directory
datalens analyze --cc /custom/path/my_config.yaml
```

### Fallback to CLI Flags (No Config)

```bash
# Old behavior still works (backward compatible)
datalens analyze --source http \
  --uri https://api.example.com/data \
  --auth-token sk-abc123...
```

---

## Output Directory Structure

Each analysis creates a descriptive subdirectory:

```
output/
├── api_example_com_0611_033501/
│   ├── api_example_com-datalens-report.html    # Interactive HTML report
│   ├── api_example_com-datalens-schema.json    # Machine-readable schema
│   ├── api_example_com-datalens-summary.md     # Text summary
│   └── .history/
│       └── 20250611_033501/                    # For drift detection
│           └── schema.json
├── prod_db_0611_033502/
│   ├── prod_db-datalens-report.html
│   ├── prod_db-datalens-schema.json
│   ├── prod_db-datalens-summary.md
│   └── .history/...
└── my_data_0611_033503/
    ├── my_data-datalens-report.html
    ├── my_data-datalens-schema.json
    ├── my_data-datalens-summary.md
    └── .history/...
```

**Naming Pattern:** `{source_identifier}_{MMDD_HHMMSS}`

- Source identifier derived from: API domain, database name, or filename
- Timestamp suffix: Month-Day_Hour-Minute-Second (unique per second)
- No collisions: each run gets unique directory

---

## Tips & Tricks

### 1. Organize Configs by Environment

Create connections for each environment you work with:

```bash
.datalens/connections/
├── api_dev.yaml
├── api_staging.yaml
├── api_prod.yaml
├── mongo_dev.yaml
├── mongo_prod.yaml
└── s3_datalake.yaml
```

**Note:** All `.datalens/connections/` files are git-ignored (local/private).

### 2. Share Config Templates via Examples

Instead of committing actual connections, share **templates** via `examples/`:

```bash
# Tracked in git (templates)
examples/connection-configs/
├── http-bearer-token.yaml
├── http-basic-auth.yaml
├── mongodb-atlas.yaml
├── s3-bucket.yaml
└── README.md  # Instructions for each

# Local (each dev creates their own)
.datalens/connections/
├── my_api.yaml  # Based on http-bearer-token.yaml
├── prod_db.yaml # Based on mongodb-atlas.yaml
└── ...
```

Team members:
1. Copy examples from `examples/connection-configs/`
2. Edit for their environment (dev, staging, prod)
3. Save to `.datalens/connections/` (local only, git-ignored)

### 3. Use Environment Files per Environment

```bash
# Development
source .env.dev
datalens analyze --cc api_prod  # Uses dev overrides

# Staging
source .env.staging
datalens analyze --cc api_prod  # Uses staging endpoints
```

### 4. Monitor Drift Over Time

```bash
# Baseline run (establishes history)
datalens analyze --cc my_api --version-tag baseline_v1

# Later runs detect drift
datalens analyze --cc my_api --detect-drift
# Compares against most recent run automatically

# Or compare against specific baseline
datalens analyze --cc my_api --compare-to baseline_v1
```

### 5. Batch Analysis Script

```bash
#!/bin/bash
# analyze_all.sh - Analyze all connections

for config in .datalens/connections/*.yaml; do
  name=$(basename "$config" .yaml)
  echo "Analyzing: $name"
  datalens analyze --cc "$name" --ai anthropic
done
```

---

## Troubleshooting

### "Connection config not found"

```bash
# Make sure the file exists and is named correctly
ls -la .datalens/connections/
ls -la ~/.datalens/connections/

# Config name must match filename
# File: my_api.yaml → name: my_api ✓
# File: my_api.yaml → name: different ✗
```

### "Environment variable not found"

```bash
# Check variable is exported
echo $API_TOKEN

# Or set in .env file
cat .env | grep API_TOKEN

# Datalens reads both shell env and .env file
```

### "Failed to connect to database"

```bash
# Verify connection string
datalens analyze --cc my_api --debug

# Check logs for actual URI being used
# Connection strings are never logged in output
```

---

## Security Best Practices

✅ **Do:**
- Keep `.datalens/connections/` git-ignored (local/private)
- Use `examples/connection-configs/` for templates (tracked in git)
- Store secrets in `.datalens/secrets.yaml` (git-ignored)
- Use environment variables in connection configs: `${VAR_NAME}`
- Reference API endpoints via env vars for environment-specific URLs
- Use different creds for dev/staging/prod
- Rotate API tokens regularly
- Share `.env.example` or `secrets.yaml.example` as templates

❌ **Don't:**
- Commit `.datalens/connections/` to git
- Hardcode secrets in connection configs
- Commit `.datalens/secrets.yaml` to git
- Commit `.env` files to git
- Use production credentials in dev configs
- Share `.datalens/secrets.yaml` unencrypted
- Commit AWS keys, API tokens, or database passwords

---

## FAQ

**Q: Can I use connection configs for local files?**  
A: Yes! Use `source_type: file` with paths like `${DATA_DIR}/file.csv`

**Q: Can I override connection params from CLI?**  
A: Yes! CLI flags always override connection config values.

**Q: Where should I store global vs project configs?**  
A: Project-local (`.datalens/connections/`) for team configs, user home (`~/.datalens/connections/`) for personal overrides.

**Q: Do you support OAuth2?**  
A: Yes, via bearer tokens. OAuth providers are supported if they issue JWT tokens.

**Q: How do I update a connection config?**  
A: Edit the YAML file. No restart needed - changes take effect immediately.

**Q: Can I version control connection configs?**  
A: Yes! Configs are YAML files. Keep in git, but never commit `.env` with actual secrets.

---

## See Also

- [Example Connection Configs](../examples/connection-configs/README.md) — Ready-to-use examples for all source types
- [Connection Config Architecture](../.claude/projects/-Users-mmehrotra-Documents-code-co-de-etl-utils-agentic-datalens-ai/memory/connection_config_design.md) — Technical design
- [Output Organization](../.claude/projects/-Users-mmehrotra-Documents-code-co-de-etl-utils-agentic-datalens-ai/memory/output_organization.md) — Directory naming & structure
- [HTTP Download Strategy](../.claude/projects/-Users-mmehrotra-Documents-code-co-de-etl-utils-agentic-datalens-ai/memory/http_download_strategy.md) — Auto-download & format detection

