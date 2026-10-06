# Install

[Setup Guide](SETUP.md) › **Install**

Datalens is a Python package, [`datalens-ai`](https://pypi.org/project/datalens-ai/), and needs **Python 3.11 or
newer**. It installs the `datalens` command. Pick one method. If you're unsure, use **pipx**.

| Method | Best for | macOS | Windows |
|---|---|---|---|
| [pipx](#pipx-recommended) | Using the `datalens` command | ✅ | ✅ |
| [uv](#uv) | Same as pipx, faster | ✅ | ✅ |
| [venv + pip](#venv--pip) | A project, or calling Datalens from Python code | ✅ | ✅ |
| [conda / mamba](#conda--mamba) | Teams already on Anaconda or Miniforge | ✅ | ✅ |
| [From source](#from-source-contributors) | Contributing, or running the demo | ✅ | ✅ |
| [WSL](#windows-subsystem-for-linux-wsl) | Windows users who prefer a Linux shell | — | ✅ |

**Contents:** [Get Python 3.11+](#step-1-get-python-311) · [Install Datalens](#step-2-install-datalens) ·
[Extras](#optional-extras) · [Check, upgrade, uninstall](#check-upgrade-uninstall) · [Troubleshooting](#troubleshooting)

---

## Step 1: Get Python 3.11+

Check what you have:

| macOS (Terminal) | Windows (PowerShell) |
|---|---|
| `python3 --version` | `py --version` (or `python --version`) |

If it says 3.11 or higher, skip to [step 2](#step-2-install-datalens). Note that **uv installs Python for you**, so
uv users can skip this step entirely.

### macOS

The built-in `/usr/bin/python3` is 3.9: too old, and don't install packages into it.

| Option | Command |
|---|---|
| Homebrew | `brew install python@3.12` (then use `python3.12`) |
| python.org installer | Download the macOS installer from [python.org/downloads](https://www.python.org/downloads/) |
| pyenv | `brew install pyenv && pyenv install 3.12 && pyenv global 3.12` |
| Miniforge (conda) | `brew install miniforge` (see [conda](#conda--mamba)) |

### Windows

| Option | Command / how |
|---|---|
| winget | `winget install Python.Python.3.12` |
| python.org installer | [python.org/downloads](https://www.python.org/downloads/). Tick **"Add python.exe to PATH"**; the `py` launcher is included. |
| Microsoft Store | Search "Python 3.12" and install |
| Scoop | `scoop install python` |
| Chocolatey | `choco install python312` |
| pyenv-win | Install it with the PowerShell one-liner from [pyenv-win](https://github.com/pyenv-win/pyenv-win#quick-start), then `pyenv install 3.12` |
| Miniforge (conda) | `winget install CondaForge.Miniforge3` (see [conda](#conda--mamba)) |

Open a **new** terminal after installing so the PATH change takes effect.

---

## Step 2: Install Datalens

### pipx (recommended)

pipx installs command-line tools into their own isolated environment and puts the command on your PATH.

**macOS**
```bash
brew install pipx
pipx ensurepath                 # then open a new terminal
pipx install datalens-ai        # pick a Python: pipx install --python python3.12 datalens-ai
datalens version
```

**Windows (PowerShell)**
```powershell
py -m pip install --user pipx
py -m pipx ensurepath           # then open a new terminal
pipx install datalens-ai        # pick a Python: pipx install --python 3.12 datalens-ai
datalens version
```

### uv

[uv](https://docs.astral.sh/uv/) is a fast Python package manager. It downloads a suitable Python if you don't have one.

**macOS**
```bash
brew install uv                  # or: curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install datalens-ai
datalens version
```

**Windows (PowerShell)**
```powershell
winget install astral-sh.uv      # or: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install datalens-ai
datalens version
```

To run it once without installing: `uvx --from datalens-ai datalens analyze --source file --path data.csv`.

### venv + pip

A virtual environment for one project. Use this when you'll also `import datalens` in your own code.

**macOS**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install datalens-ai
datalens version
```

**Windows (PowerShell)**
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1       # Command Prompt: .venv\Scripts\activate.bat
pip install datalens-ai
datalens version
```

If PowerShell says *running scripts is disabled*, run this once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

The `datalens` command only works while the venv is active, or call it directly: `.venv/bin/datalens` on macOS,
`.venv\Scripts\datalens.exe` on Windows.

### conda / mamba

Works the same on both systems (Anaconda Prompt or PowerShell on Windows):
```bash
conda create -n datalens python=3.12 -y      # or: mamba create …
conda activate datalens
pip install datalens-ai                      # Datalens is on PyPI, not conda-forge: install it with pip
datalens version
```

### From source (contributors)

**macOS**
```bash
git clone https://github.com/m8d8/datalens.ai.git && cd datalens.ai
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # or, with uv: uv sync --extra dev
pytest                           # run the tests
bash examples/demo/run_demo.sh   # the day 1 → day 2 cricket demo
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/m8d8/datalens.ai.git; cd datalens.ai
py -3.12 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```
The demo and scenario scripts are bash scripts. On Windows, run them from Git Bash or WSL.

### Windows Subsystem for Linux (WSL)

Prefer a Linux shell on Windows? Install WSL with `wsl --install` (in an admin PowerShell, then reboot). Open
Ubuntu, and follow the macOS steps with these swaps:
- `sudo apt install python3.12 python3.12-venv pipx` instead of `brew install …`;
- `pipx install datalens-ai`.

Your Windows drives are available under `/mnt/c/…`.

---

## Optional extras

Add them in square brackets with any method. Quote them on macOS (zsh) and in PowerShell:

| Extra | Adds |
|---|---|
| `ai` | Anthropic and OpenAI SDKs, for `--ai anthropic` / `--ai openai`. CLI logins (`claude`, `copilot`, `cursor`) need nothing extra. |
| `bigquery` | Google BigQuery connector |
| `cloud` | S3, HTTP/REST API and SFTP connectors |
| `alerts` / `metrics` | Slack, webhook and PagerDuty notifications; Prometheus, Datadog and CloudWatch metrics |
| `all` | Everything above |

```bash
pipx install "datalens-ai[ai,bigquery]"
pip install "datalens-ai[all]"
pipx inject datalens-ai anthropic          # add a package to an existing pipx install
```

---

## Check, upgrade, uninstall

| | pipx | uv | pip (venv / conda) |
|---|---|---|---|
| Check | `datalens version` | `datalens version` | `datalens version` |
| Upgrade | `pipx upgrade datalens-ai` | `uv tool upgrade datalens-ai` | `pip install -U datalens-ai` |
| Specific version | `pipx install datalens-ai==1.0.0 --force` | `uv tool install datalens-ai==1.0.0` | `pip install datalens-ai==1.0.0` |
| Uninstall | `pipx uninstall datalens-ai` | `uv tool uninstall datalens-ai` | `pip uninstall datalens-ai` |

Uninstalling leaves your config folder (`~/.datalens` on macOS, `%USERPROFILE%\.datalens` on Windows) and
your `output/` folders in place. Delete them by hand if you want them gone.

---

## Troubleshooting

| Message | Cause and fix |
|---|---|
| `No matching distribution found for datalens-ai` (often with *"Ignored the following versions that require a different python version"*) | Your `pip` belongs to a Python older than 3.11. On macOS it's usually the built-in 3.9. Check with `pip --version`, then use pipx or uv, or a venv made with a 3.11+ Python. |
| `externally-managed-environment` | Homebrew or Linux system Python blocks `pip install` into itself. Use pipx, uv or a venv. |
| `datalens: command not found` (macOS) / `datalens is not recognized…` (Windows) | The install folder isn't on PATH. Run `pipx ensurepath` (or `uv tool update-shell`) and open a new terminal. With a venv, activate it first. |
| `Defaulting to user installation because normal site-packages is not writeable` | Harmless on its own. Usually it means you're using a system Python; prefer pipx, uv or a venv. |
| Windows: `py` not found | Python came from the Microsoft Store or a manager without the launcher. Use `python` instead of `py`, or reinstall from python.org. |
| Windows: `running scripts is disabled on this system` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate the venv again. |
| Windows: long-path errors during install | Turn on long paths: `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force` (admin), or install to a shorter folder. |
| `zsh: no matches found: datalens-ai[ai]` | Quote extras: `pip install "datalens-ai[ai]"`. |

---

Next: [Setup Guide](SETUP.md) (config folder, connections, CI) · [Quick Start](QUICKSTART.md) · [FAQ](FAQ.md)
