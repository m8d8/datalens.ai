# Connection Config Examples

Complete examples for all supported data source types. Copy any example and customize for your use case.

## Quick Links

- **HTTP/REST APIs** — Bearer Token, Basic Auth, API Key
- **MongoDB** — Atlas Cloud, Local/Self-Hosted
- **Amazon S3** — S3 Data Lakes
- **Local Files** — CSV, JSON, XML, Excel

---

## HTTP APIs

### Bearer Token (JWT, OAuth2)
📄 [http-bearer-token.yaml](http-bearer-token.yaml)

For APIs that use JWT tokens or OAuth2 bearer tokens.

```bash
export API_TOKEN="eyJhbGciOiJIUzI1NiIs..."
datalens analyze --cc api_bearer_example
```

### Basic Authentication
📄 [http-basic-auth.yaml](http-basic-auth.yaml)

For APIs that use username/password (HTTP Basic Auth).

```bash
export API_PASSWORD="your_secret_password"
datalens analyze --cc api_basic_auth_example
```

### API Key (Custom Header)
📄 [http-api-key.yaml](http-api-key.yaml)

For APIs that use API keys in custom headers (X-API-Key, etc.).

```bash
export API_KEY="sk-abc123def456"
datalens analyze --cc api_key_example
```

---

## MongoDB

### Atlas Cloud (Hosted)
📄 [mongodb-atlas.yaml](mongodb-atlas.yaml)

For MongoDB Atlas clusters (MongoDB's cloud service).

```bash
export MONGO_ATLAS_URI="mongodb+srv://admin:password@cluster.mongodb.net"
datalens analyze --cc mongo_atlas_prod
```

### Local/Self-Hosted
📄 [mongodb-local.yaml](mongodb-local.yaml)

For MongoDB instances running locally or on your own servers.

```bash
datalens analyze --cc mongo_local_dev
# Or with authentication:
export MONGO_LOCAL_URI="mongodb://admin:password@localhost:27017"
```

---

## Amazon S3

### S3 Data Lake
📄 [s3-bucket.yaml](s3-bucket.yaml)

For analyzing data stored in Amazon S3 buckets.

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI..."
datalens analyze --cc s3_data_lake
```

---

## Local Files

### CSV Files
📄 [file-csv.yaml](file-csv.yaml)

For local CSV files.

```bash
export DATA_DIR="/data/exports"
datalens analyze --cc local_csv_data
```

### JSON Files
📄 [file-json.yaml](file-json.yaml)

For JSON files with optional root path specification.

```bash
export DATA_DIR="/data/exports"
datalens analyze --cc local_json_data
```

### Excel Files
📄 [file-excel.yaml](file-excel.yaml)

For Excel spreadsheets (.xlsx, .xls) with sheet selection.

```bash
export DATA_DIR="/data/exports"
datalens analyze --cc local_excel_data
```

### XML Files
📄 [file-xml.yaml](file-xml.yaml)

For XML files with root element specification.

```bash
export DATA_DIR="/data/exports"
datalens analyze --cc local_xml_data
```

---

## How to Use These Examples

### 1. Copy an Example
```bash
cp examples/connection-configs/http-bearer-token.yaml .datalens/connections/my_api.yaml
```

### 2. Edit the Configuration
```bash
vi .datalens/connections/my_api.yaml
# Update: name, description, URI, etc.
```

### 3. Set Environment Variables
```bash
export API_TOKEN="your_actual_token"
# Or create .env file:
cat > .env << 'EOF'
API_TOKEN=your_actual_token
EOF
```

### 4. Verify Configuration
```bash
datalens connection-list
# Should show: my_api (http)
```

### 5. Run Analysis
```bash
datalens analyze --cc my_api
# Output: output/api_example_com_0611_033501/
```

---

## Common Patterns

### Pattern 1: Environment Variables for Secrets
```yaml
params:
  auth_token: "${API_TOKEN}"  # From environment
  api_key: "${API_KEY}"       # From environment
```

### Pattern 2: Override Sampling Defaults
```yaml
profiling:
  sample_size: 5000      # Override default 10000
  max_depth: 8           # Override default 10
```

### Pattern 3: Custom Headers
```yaml
params:
  custom_headers:
    Accept: "application/json"
    X-Client-ID: "datalens"
    User-Agent: "datalens/0.2"
```

### Pattern 4: Metadata for Tracking
```yaml
metadata:
  created: "2026-06-11"
  updated: "2026-06-11"
  owner: "data-team"
  tags: ["production", "analytics"]
```

---

## Security Best Practices

✅ **Do:**
- Store secrets in environment variables
- Use `.env` file (add to `.gitignore`)
- Keep configs in version control (no secrets!)
- Rotate tokens/keys regularly

❌ **Don't:**
- Hardcode credentials in YAML files
- Commit `.env` files to git
- Share configs with secrets exposed
- Use production tokens in development

---

## File Organization Tips

**Group by environment:**
```
.datalens/connections/
├── api_dev.yaml
├── api_staging.yaml
├── api_prod.yaml
├── mongo_dev.yaml
└── mongo_prod.yaml
```

**Group by source type:**
```
.datalens/connections/
├── http/
│   ├── api_prod.yaml
│   └── api_staging.yaml
├── mongodb/
│   ├── mongo_prod.yaml
│   └── mongo_local.yaml
└── s3/
    └── data_lake.yaml
```

**Global configs (shared):**
```
~/.datalens/connections/
├── api_personal.yaml
├── my_local_db.yaml
└── ...
```

---

## Troubleshooting

### "Connection config not found"
Check if the file exists in the correct location:
```bash
ls -la .datalens/connections/
ls -la ~/.datalens/connections/
```

### "Environment variable not found"
Verify the variable is set:
```bash
echo $API_TOKEN
# or check .env file
cat .env | grep API_TOKEN
```

### "Failed to connect"
Enable debug mode:
```bash
datalens analyze --cc my_api --debug
# Check logs for actual connection string used
```

---

## Next Steps

1. Copy an example that matches your data source
2. Customize with your connection details
3. Set environment variables for secrets
4. Run `datalens connection-list` to verify
5. Analyze: `datalens analyze --cc your_connection_name`

For more details, see [README_CONNECTION_CONFIG.md](../../README_CONNECTION_CONFIG.md)
