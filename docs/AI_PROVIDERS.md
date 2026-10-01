# AI Providers Guide

Configure AI to add narrative insights to your Datalens reports. Choose between licensed providers (Claude Desktop, GitHub Copilot) or API-based providers (Anthropic, OpenAI).

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

### GitHub Copilot (License via the Copilot CLI)

**What you need** (one of):
- **Copilot CLI (preferred):** `npm i -g @github/copilot`, then run `copilot` once and log in.
- **GitHub CLI fallback:** `gh` with `gh auth login` and the Copilot extension.
- An active Copilot subscription either way.

**Enable AI insights:**
```bash
datalens analyze --source file --path data.csv --ai copilot
```

**How it works:**
- Datalens runs `copilot -p "<prompt>" -s --model auto --no-ask-user --no-custom-instructions`
  (or `gh copilot -p` when only `gh` is installed).
- The CLI runs in an empty temporary folder, so it can only answer: it can't read or change your files.
- Your Copilot subscription covers the cost. No API keys needed.
- Model: **auto** by default (Copilot picks). Set `--ai-model <id>` to choose one; `gh copilot` ignores it.

**Verify it's available:**
```bash
copilot --version            # Copilot CLI
# or, for the gh fallback:
gh auth status && gh copilot status
```

**secrets.yaml (optional):**
```yaml
copilot:
  cli_path: /opt/homebrew/bin/copilot   # if not on PATH
  model: auto
  timeout: 300
```

**In connection configs:**
```bash
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

**Model selection:** the default is **auto** — for the Anthropic API that's the newest Sonnet model your key can
use (falling back to `claude-sonnet-5-5`). Pin one only if you need to:

```yaml
# .datalens/secrets.yaml
anthropic:
  api_key: "sk-ant-..."
  model: "claude-opus-5-5"      # optional; omit (or "auto") to let Datalens pick
```

| Model | Speed | Cost | Best for |
|---|---|---|---|
| `claude-opus-5-5` | Slower | Higher | Complex, wide schemas; subtle cross-object reasoning |
| `claude-sonnet-5-5` | Balanced | Balanced | Default (what auto picks) |
| `claude-haiku-4-5-20251001` | Fastest | Lower | Quick, cost-conscious reviews |

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

### GitHub Copilot (License via the Copilot CLI)

**What you need** (one of):
- **Copilot CLI (preferred):** `npm i -g @github/copilot`, then run `copilot` once and log in.
- **GitHub CLI fallback:** `gh` with `gh auth login` and the Copilot extension.
- An active Copilot subscription either way.

**Enable AI insights:**
```bash
datalens analyze --source file --path data.csv --ai copilot
```

**How it works:**
- Datalens runs `copilot -p "<prompt>" -s --model auto --no-ask-user --no-custom-instructions`
  (or `gh copilot -p` when only `gh` is installed).
- The CLI runs in an empty temporary folder, so it can only answer: it can't read or change your files.
- Your Copilot subscription covers the cost. No API keys needed.
- Model: **auto** by default (Copilot picks). Set `--ai-model <id>` to choose one; `gh copilot` ignores it.

**Verify it's available:**
```bash
copilot --version            # Copilot CLI
# or, for the gh fallback:
gh auth status && gh copilot status
```

**secrets.yaml (optional):**
```yaml
copilot:
  cli_path: /opt/homebrew/bin/copilot   # if not on PATH
  model: auto
  timeout: 300
```

**In connection configs:**
```bash
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

## Choosing a model (default: auto)

Every provider defaults to **auto**, and the report shows the model that was used.

- **Claude / Cursor / Copilot CLIs:** `--model auto` (or no flag), so each CLI uses your account's default.
- **Anthropic API:** the newest Sonnet model the key can use.
- **OpenAI API:** its default chat model.

Set a model with `--ai-model <id>`, `ai_model: <id>` in the app config, or a provider's `model:` in secrets.yaml.
Precedence: CLI/app config → provider secret → `DATALENS_<PROVIDER>_MODEL` env var → auto.

**Wrong model?** If the provider rejects the configured model (unknown, unavailable, no access), Datalens logs a
warning, retries the same request on **auto**, and says so in the run warnings and at the top of the AI Review tab
("Configured model 'x' was rejected … switched to auto"). The run never fails because of a model name.
The standalone `copilot` CLI accepts `--model`; `gh copilot` doesn't, so a configured model is noted and ignored there.

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
- `sales-datalens-report.html` (with the Verdict → AI Review tab)
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
# Copilot CLI installed and logged in?
copilot --version            # install: npm i -g @github/copilot, then run `copilot` to log in

# Or the gh fallback:
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
