# `.datalens/`: this repo's demo config folder

Datalens reads its config from a **config folder** (`config.yaml`, `secrets.yaml`, `.env`, `connections/`).
This folder holds the repo's demo connections. It's used when you run Datalens from the repo root and no
`--config-dir` is given.

**Using Datalens for your own data?** Don't edit this folder. Create your own and point at it:

```bash
datalens init ~/my-datalens-config                 # or just `datalens init` for ~/.datalens
datalens --config-dir ~/my-datalens-config config-show
export DATALENS_CONFIG_DIR=~/my-datalens-config    # then every command uses only that folder
```

| File | Tracked in git | Purpose |
|---|---|---|
| `connections/*.yaml` | yes (demo only) | Example data sources: `datalens analyze --cc local_jsonl_data` |
| `config-dev.yaml` | yes | Example overlay for `--env dev` |
| `secrets.yaml.example` | yes | Template for `secrets.yaml` |
| `secrets.yaml`, `.env` | **no** (git-ignored) | Your credentials, if you add any here |
| `.tmp/` | no | Downloads and cache, managed by Datalens |

Lookup order and every option: [Setup Guide](../docs/SETUP.md) · [Setup Connections](../docs/CONNECTION_CONFIG.md).
