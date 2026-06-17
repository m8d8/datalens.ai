# AI Providers Guide

Configure AI to add narrative insights to your schema analysis reports. Choose between licensed providers (Claude Desktop, GitHub Copilot) or API-based providers (Anthropic, OpenAI).

---

## Quick Start

### 1. Claude Desktop (Fastest to set up)

If you have Claude Code or Claude Desktop installed and authenticated:

```bash
datalens analyze --source file --path data.csv --ai claude
```

Done! No configuration needed.

### 2. GitHub Copilot (If you have the subscription)

If you have GitHub CLI (`gh`) installed and authenticated:

```bash
datalens analyze --source file --path data.csv --ai copilot
```

Done! No configuration needed.

### 3. Anthropic API (Claude via API)

If you have an Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
datalens analyze --source file --path data.csv --ai anthropic
```

---

## Detailed Configuration

### Claude Desktop / Claude Code (License)

**What you need:**
- Claude Code or Claude Desktop installed
- Authenticated: `claude auth login` or logged into IDE

**Enable AI insights:**
```bash
datalens analyze --source file --path data.csv --ai claude
```

**How it works:**
- Datalens invokes the `claude` CLI with your analysis context
- Claude Desktop/Code chooses the model (based on your account)
- Runs locally through your authenticated session
- No API keys exposed
- Works offline (after initial authentication)

**Verify it's available:**
```bash
# Check if Claude CLI is authenticated
claude --version
# If it shows a version, you're good to go
```

**In connection configs:**
```yaml
# .datalens/connections/my_api.yaml
name: my_api
source_type: http
params:
  uri: "https://api.example.com/v1"
```

```bash
# Use with Claude insights
datalens analyze --cc my_api --ai claude
```

---

### GitHub Copilot (License via gh CLI)

**What you need:**
- GitHub CLI (`gh`) installed — [Install gh](https://cli.github.com/)
- GitHub account and Copilot subscription active
- Authenticated: `gh auth login`

**Enable AI insights:**
```bash
datalens analyze --source file --path data.csv --ai copilot
```

**How it works:**
- Datalens invokes `gh copilot` with your analysis context
- GitHub's Copilot service processes the request (typically uses GPT-4)
- Your Copilot subscription covers the cost
- No separate API keys needed

**Verify it's available:**
```bash
# Check GitHub authentication
gh auth status

# Check Copilot is available
gh copilot status
# Should show: Copilot service: OK
```

**In connection configs:**
```bash
# Same as Claude — just change the --ai flag
datalens analyze --cc my_api --ai copilot
```

---

### Anthropic API (Claude via API Key)

**What you need:**
- Anthropic API key — [Get one here](https://console.anthropic.com/account/keys)
- `anthropic` Python library (included in `[ai]` extras)

**Option 1: Environment variable (quickest)**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
datalens analyze --source file --path data.csv --ai anthropic
```

**Option 2: Secrets file (persistent)**

`.datalens/secrets.yaml`:
```yaml
anthropic:
  api_key: "sk-ant-..."
  model: "claude-opus-4-1"        # Optional: choose model
  timeout: 60                      # Optional: API timeout in seconds
```

Then run:
```bash
datalens analyze --source file --path data.csv --ai anthropic
# Datalens auto-loads secrets from .datalens/secrets.yaml
```

**Model selection:**
```yaml
# .datalens/secrets.yaml
anthropic:
  api_key: "sk-ant-..."
  model: "claude-opus-4-1"   # Most capable, slower, more expensive
  # model: "claude-sonnet-4-20250514"     # Balanced (default)
  # model: "claude-haiku-4-5-20251001"    # Fastest, cheapest
```

**Available models (latest):**
| Model | Speed | Cost | Best For |
|---|---|---|---|
| `claude-opus-4-1` | Slower | Higher | Complex analysis, edge cases |
| `claude-sonnet-4-20250514` | Balanced | Balanced | Default choice (recommended) |
| `claude-haiku-4-5-20251001` | Fastest | Lower | Simple insights, cost-conscious |

**In connection configs:**
```bash
datalens analyze --cc my_api --ai anthropic
# Uses model from secrets.yaml
```

**Pricing:** See [Anthropic pricing](https://www.anthropic.com/pricing/claude)

---

### OpenAI (GPT-4, GPT-3.5)

**What you need:**
- OpenAI API key — [Get one here](https://platform.openai.com/account/api-keys)
- `openai` Python library

**Setup:**
```bash
export OPENAI_API_KEY="sk-..."
datalens analyze --source file --path data.csv --ai openai
```

Or secrets file:
```yaml
# .datalens/secrets.yaml
openai:
  api_key: "sk-..."
```

**Note:** Model selection not currently configurable for OpenAI (uses `gpt-4-turbo`).

---

### Cursor IDE (If you use Cursor)

**What you need:**
- Cursor IDE installed
- Authenticated via `cursor-agent login`

**Enable:**
```bash
datalens analyze --source file --path data.csv --ai cursor
```

---

## Auto-detect (Recommended)

Let Datalens find the best available provider:

```bash
datalens analyze --source file --path data.csv --ai auto
```

**Priority order:**
1. Cursor (if logged in)
2. GitHub Copilot (if authenticated + subscription)
3. Claude Desktop (if authenticated)
4. Anthropic (if API key available)
5. OpenAI (if API key available)

If none available → AI disabled (analysis still works).

---

## Examples

### Example 1: Quick analysis with Claude Desktop

```bash
# No setup needed if Claude is installed and authenticated
datalens analyze --source file --path sales.csv --ai claude
```

**Output includes:**
- `sales-datalens-report.html` (with AI Insights tab)
- `sales-datalens-ai-insights.md` (insights as markdown)

### Example 2: Team using Anthropic API with model choice

Setup once in `.datalens/secrets.yaml`:
```yaml
anthropic:
  api_key: "${ANTHROPIC_API_KEY}"    # Reference env var
  model: "claude-opus-4-1"            # Use best model for complex data
```

Then team members:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."  # Your personal key
datalens analyze --cc my_api --ai anthropic
# Automatically uses Opus model from secrets
```

### Example 3: Connection config + Copilot

`.datalens/connections/prod_db.yaml`:
```yaml
name: prod_db
source_type: mongodb
params:
  db: analytics
  uri: "${MONGO_URI}"
  collections: users,orders
```

Run with Copilot:
```bash
datalens analyze --cc prod_db --ai copilot
```

### Example 4: Compare different models

```bash
# Analyze with Haiku (fast, cheap)
export DATALENS_ANTHROPIC_MODEL="claude-haiku-4-5-20251001"
datalens analyze --cc my_api --ai anthropic -o output/with-haiku

# Analyze with Opus (best, slower, expensive)
export DATALENS_ANTHROPIC_MODEL="claude-opus-4-1"
datalens analyze --cc my_api --ai anthropic -o output/with-opus

# Compare the insights!
```

---

## Troubleshooting

### "Claude CLI not available"

```bash
# Check if Claude is installed
claude --version

# If not installed:
# - Install Claude Code or Claude Desktop
# - Or: brew install claude (if available)

# If installed but not in PATH:
# Configure in secrets.yaml:
# claude:
#   cli_path: "/Applications/Claude.app/Contents/MacOS/claude"
```

### "GitHub Copilot not available"

```bash
# Check GitHub CLI is installed and authenticated
gh auth status

# If not authenticated:
gh auth login

# Check Copilot subscription is active
gh copilot status
```

### "Anthropic API not available"

```bash
# Check API key is set
echo $ANTHROPIC_API_KEY

# If not, set it:
export ANTHROPIC_API_KEY="sk-ant-..."

# Or add to .datalens/secrets.yaml:
# anthropic:
#   api_key: "sk-ant-..."
```

### "AI provider selected but failed to generate insights"

Check the error in the report output. Common causes:
- **API rate limits** — Wait and retry
- **Model not available** — Check model name is correct
- **Invalid API key** — Verify credentials
- **Network issues** — Check connectivity

---

## Cost Considerations

### Licensed Providers (Free with subscription)
- **Claude Desktop** — Free with Claude license
- **GitHub Copilot** — Included with Copilot subscription (~$20/month)
- **Cursor** — Included with Cursor subscription

### API-Based (Pay per use)
- **Anthropic** — ~$3 for Opus, ~$0.30 for Sonnet, ~$0.08 for Haiku per typical analysis
- **OpenAI** — Similar pricing to Anthropic

### Recommendation
- **Single user or exploration** → Use Claude Desktop (if you have it)
- **Team with Copilot subscription** → Use `--ai copilot`
- **Cost-conscious** → Use Haiku model (`claude-haiku-4-5-20251001`)
- **Best quality** → Use Opus model (`claude-opus-4-1`)
- **Balanced (default)** → Use Sonnet model (no config needed)

---

## Environment Variables Reference

| Variable | Purpose | Example |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API authentication | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI API authentication | `sk-...` |
| `DATALENS_ANTHROPIC_MODEL` | Override default Anthropic model | `claude-opus-4-1` |

All can be set in `.datalens/secrets.yaml` instead of env vars.

---

## See Also

- [Connection Config Guide](CONNECTION_CONFIG.md) — Store connection + AI settings together
- [Usage Guide](USAGE.md) — Full CLI reference
- [Anthropic Documentation](https://docs.anthropic.com/)
- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
