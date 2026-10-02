# Publishing to PyPI

How to release `datalens-ai` to [PyPI](https://pypi.org/project/datalens-ai/), so anyone can run
`pip install datalens-ai`. Releases go out from GitHub Actions with **Trusted Publishing**: PyPI trusts this
repository's workflow directly, so there is no API token to create, store or leak.

| | |
|---|---|
| Distribution name | `datalens-ai` (what people `pip install`) |
| Import name | `datalens` (what code imports) |
| Command | `datalens` |
| Version source | `__version__` in `src/datalens/__init__.py` (pyproject reads it) |
| Workflows | `.github/workflows/ci.yml` (every PR), `.github/workflows/publish.yml` (releases) |

The flow:

```
bump version + changelog ──► merge to main ──► push tag v1.0.0 ──► TestPyPI ──► check it installs
                                                                                     │
                                         PyPI ◄── publish GitHub Release v1.0.0 ◄────┘
```

---

## 1. Before the first release: things to take care of

Work through this list once. Items marked **irreversible** can't be undone after upload.

### Name and identity

- [ ] **The name is free.** `datalens-ai` is unregistered on PyPI and TestPyPI (checked 2026-10-01). PyPI treats
  `datalens-ai`, `datalens_ai` and `datalens.ai` as the same name. Register it soon (step 2) so nobody else takes it.
- [ ] **Import-name clash.** A different, unrelated package called
  [`datalens`](https://pypi.org/project/datalens/) (v0.1, "A small example package") already exists on PyPI.
  Installing both in one environment would make `import datalens` ambiguous. It's unlikely to matter in
  practice, but say so in the README if it ever comes up. Renaming the import package later is a breaking change,
  so decide now whether `datalens` is fine (recommended: yes).
- [ ] **Author metadata.** `authors` is "Datalens Contributors", with no email. Anything you add is public
  forever in every release's metadata. Don't use a work email unless that's intended.
- [ ] **Commit email.** Commits use `manu.mehrotra@tivo.com`. That's visible on GitHub, not PyPI, but check it's
  what you want before the repo gets attention: `git config user.email <your GitHub noreply address>`.

### Legal

- [ ] `LICENSE` is MIT, and pyproject declares `license = "MIT"` (a PEP 639 SPDX expression; the old
  license classifier was removed, as PEP 639 says not to combine the two).
- [ ] **Demo data stays in the repo, not the package.** The Cricsheet data (ODC-BY 1.0) under `test_data/` is
  excluded from both the wheel and the sdist, so the package carries no third-party data. Keep it that way.
- [ ] Check that no dependency's license conflicts with MIT for your use. All current ones are permissive
  (BSD, MIT, Apache-2.0).

### Contents (what actually ships)

- [ ] **Wheel** contains only `src/datalens` (Python files plus `py.typed`). The report's CSS, JS and logos are
  embedded in Python modules, so no data files are needed.
- [ ] **sdist** is an explicit allow-list in `pyproject.toml` (`[tool.hatch.build.targets.sdist]`): `src/`,
  `tests/`, `README.md`, `LICENSE`, `CHANGELOG.md` and `pyproject.toml`. That keeps out `.datalens/` (local
  configs), `.claude/`, `output/`, `tmp/`, `test_data/`, `docs/images/` and `examples/`.
  When you add a file that must ship, add it to that list.
- [ ] **Secrets.** Before every release, run the scan in [section 6](#6-pre-release-secret-scan). The repo was
  checked on 2026-10-01: only placeholders and `${ENV_VAR}` references.

### README on PyPI

- [ ] PyPI shows `README.md` as the project page. **Relative links and images don't work there**, so the README
  uses absolute URLs: `https://raw.githubusercontent.com/m8d8/datalens.ai/main/...` for images and
  `https://github.com/m8d8/datalens.ai/blob/main/...` for links. Keep new links absolute.
- [ ] Images load from the `main` branch, so merge the screenshots before you release.
- [ ] `twine check --strict` passes (CI runs it).

### Dependencies and Python versions

- [ ] `requires-python = ">=3.11"`. CI tests 3.11 to 3.14. Only list versions in `classifiers` that CI tests.
- [ ] **Core dependencies are heavy.** `pandas` and `pymongo` install for everyone, even file-only users.
  Moving `pymongo` into a `mongodb` extra would make the base install lighter, but it breaks MongoDB users.
  **Decide before tagging 1.0.0**: after that, the move has to wait for 2.0.
- [ ] Dependencies use lower bounds only (`>=`). That's normal for a library. Don't pin exact versions.
- [ ] `uv.lock` is git-ignored. That's fine for a published library, but committing it makes CI reproducible.
- [ ] Optional extras work: `ai`, `bigquery`, `cloud`, `alerts`, `metrics`, `all`, `dev`.

### Quality

- [ ] `uv run pytest` is green (300 passed, 8 skipped on 2026-10-01).
- [ ] *Optional:* `ruff check src` reports 579 issues, mostly trailing whitespace (`ruff check --fix` fixes
  420 of them). It isn't a CI gate yet. Clean it up in its own PR, then add `uv run ruff check src` to `ci.yml`.

### Irreversible

- [ ] **A version number can be uploaded only once.** Even after you delete it, PyPI never accepts `1.0.0`
  again. Try every release on TestPyPI first. To fix a bad release, publish `1.0.1`.
- [ ] **Prefer "yank" over "delete".** Yanking hides a broken release from `pip install` but keeps pinned
  installs working. Deleting breaks them, and still doesn't free the version number.

---

## 2. One-time setup

### 2.1 Accounts

1. Create accounts on [pypi.org](https://pypi.org/account/register/) and
   [test.pypi.org](https://test.pypi.org/account/register/). They're separate sites with separate accounts.
2. Turn on **two-factor authentication** on both (required for uploads). Save the recovery codes.

### 2.2 Register Trusted Publishers ("pending publishers")

The project doesn't exist on PyPI yet, so add a *pending* publisher. It creates the project on the first upload.

On **PyPI**: *Your account → Publishing → Add a new pending publisher → GitHub*:

| Field | Value |
|---|---|
| PyPI Project Name | `datalens-ai` |
| Owner | `m8d8` |
| Repository name | `datalens.ai` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Do the same on **TestPyPI** with environment name `testpypi`.

These values must match `.github/workflows/publish.yml` exactly, or the upload fails with
`invalid-publisher`.

### 2.3 GitHub environments

In the repo: *Settings → Environments → New environment*.

1. Create `testpypi`.
2. Create `pypi`. Under **Deployment protection rules**, add yourself as a **required reviewer**. Then every
   PyPI release waits for your click, even if someone else publishes a GitHub Release.
3. *Optional:* under each environment's **Deployment branches and tags**, allow only tags matching `v*`.

Also check *Settings → Actions → General → Workflow permissions* is left at **read** (the default). The publish
jobs ask for `id-token: write` themselves.

### 2.4 Protect the release path

- *Settings → Branches*: protect `main` (require PRs and the **CI** check).
- *Settings → Rules → Tags* (optional): only maintainers can create `v*` tags.

---

## 3. Every release

### 3.1 Prepare (on a branch)

1. **Pick the version** using [SemVer](https://semver.org/): `MAJOR.MINOR.PATCH`.
   - **PATCH** (1.0.1): bug fixes only.
   - **MINOR** (1.1.0): new features, flags or report sections; nothing existing breaks.
   - **MAJOR** (2.0.0): anything that breaks the public contract (see [section 7](#7-what-counts-as-a-breaking-change)).
2. **Bump it in one place**, `src/datalens/__init__.py`:
   ```python
   __version__ = "1.0.0"
   ```
3. **Update `CHANGELOG.md`.** Move items from *Unreleased* into a new `## [1.0.0] - YYYY-MM-DD` section, and
   update the compare links at the bottom.
4. **Build and check locally:**
   ```bash
   rm -rf dist
   uv build                                   # dist/datalens_ai-1.0.0.tar.gz + .whl
   uvx twine check --strict dist/*
   tar tzf dist/*.tar.gz | cut -d/ -f2 | sort -u   # only src, tests, README, LICENSE, CHANGELOG, pyproject
   ```
5. **Smoke-test the wheel in a clean environment:**
   ```bash
   uv venv /tmp/dl-smoke && uv pip install --python /tmp/dl-smoke/bin/python dist/*.whl
   /tmp/dl-smoke/bin/datalens version
   /tmp/dl-smoke/bin/datalens analyze -s file -p test_data/cricket/day1 --pattern "*.jsonl.gz" -o /tmp/dl-out
   ```
6. Run the [secret scan](#6-pre-release-secret-scan).
7. Open a PR, wait for **CI** to pass, and merge to `main`.

### 3.2 Publish to TestPyPI

```bash
git checkout main && git pull
git tag -a v1.0.0 -m "datalens-ai 1.0.0"
git push origin v1.0.0
```

The **Publish** workflow then:
1. checks the tag matches `__version__` (it fails if `v1.0.0` ≠ `1.0.0`);
2. runs the tests, then builds and checks the package;
3. uploads to TestPyPI.

Then check that it installs from TestPyPI. Dependencies come from real PyPI, hence the extra index:

```bash
uv venv /tmp/dl-test && source /tmp/dl-test/bin/activate
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "datalens-ai[ai]==1.0.0"
datalens version && datalens --help
deactivate
```

Look at the project page on https://test.pypi.org/project/datalens-ai/ : README, images, links and metadata.

### 3.3 Publish to PyPI

1. On GitHub: *Releases → Draft a new release*, choose tag `v1.0.0`, title `v1.0.0`, and paste the changelog
   section as the notes.
2. Click **Publish release**.
3. The **Publish** workflow rebuilds from the tag and waits for approval on the `pypi` environment. Approve it.
4. Check that it worked:
   ```bash
   pip install --no-cache-dir "datalens-ai==1.0.0" && datalens version
   ```
   Then check https://pypi.org/project/datalens-ai/.

### 3.4 After the release

- Add a fresh `## [Unreleased]` section to `CHANGELOG.md` if it isn't there.
- The PyPI badge in the README updates on its own.
- If something is broken: **yank** the release (*PyPI → Manage → Releases → Options → Yank*), fix it, and
  release the next patch version.

---

## 4. Manual fallback (no GitHub Actions)

Use this only if Actions is unavailable. It needs an API token.

1. On PyPI: *Account settings → API tokens → Add API token*, scoped to **project: datalens-ai** (after the
   first upload; until then, use an account-wide token and delete it straight after).
2. Upload:
   ```bash
   uv build
   uvx twine check --strict dist/*
   UV_PUBLISH_TOKEN=pypi-... uv publish --publish-url https://test.pypi.org/legacy/   # TestPyPI first
   UV_PUBLISH_TOKEN=pypi-... uv publish                                            # then PyPI
   ```
3. Never commit the token, and never put it in `secrets.yaml`, `.env` or the shell history. Revoke it when done.

---

## 5. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `invalid-publisher` | The trusted publisher's owner, repo, workflow file or environment name doesn't match. Compare step 2.2 with `publish.yml`. |
| `File already exists` | That version was uploaded before (perhaps then deleted). Bump the version. |
| `Tag matches package version` step fails | The tag and `__version__` differ. Delete the tag (`git push --delete origin v1.0.0`), fix it, and tag again. |
| Images broken on PyPI | A relative link crept into the README, or the image isn't on `main` yet. |
| `The description failed to render` | Run `uvx twine check --strict dist/*` locally and fix the Markdown. |
| `pip install` from TestPyPI can't find `pandas` | Add `--extra-index-url https://pypi.org/simple/`. |
| Wrong files in the sdist | Edit the allow-list in `[tool.hatch.build.targets.sdist]`. Patterns start with `/`, so they match only at the repo root. |

---

## 6. Pre-release secret scan

The wheel ships only `src/` and the sdist ships only the allow-listed files, so a leak can only come from
those. A quick check:

```bash
# token shapes: Anthropic, OpenAI, GitHub, AWS, Google, Slack, private keys
git ls-files src tests README.md CHANGELOG.md pyproject.toml | xargs grep -n -I -E \
  'sk-ant-[A-Za-z0-9_-]{20,}|sk-(proj-)?[A-Za-z0-9]{32,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[baprs]-|hooks\.slack\.com/services/T|BEGIN [A-Z ]*PRIVATE KEY' \
  && echo "REVIEW THE LINES ABOVE" || echo "clean"

# local paths or personal details
git ls-files src tests README.md | xargs grep -n -I -E '/Users/|/home/[a-z]|@tivo\.com|@xperi\.com' || echo "clean"
```

For a deeper scan, including git history, use [gitleaks](https://github.com/gitleaks/gitleaks):
`gitleaks detect --source . --log-opts="--all"`.

---

## 7. What counts as a breaking change

From 1.0.0 these are the public contract. Changing them incompatibly needs a new **major** version:

- **CLI:** command names, flag names and their meaning, and default behaviour.
- **Exit codes:** 0 ok, 1 warn, 2 fail, 3 error.
- **Config files:** app config (`-c`), connection configs (`--cc`), `secrets.yaml` keys, the `drift:` rules
  format and `x-datalens` blocks in expected schemas.
- **Machine-readable output:** `*-run-summary.json`, `*-drift-report.json`, `--format json` output, and the
  output file names that CI scripts read.
- **Python API:** `datalens.analyze()` and the fields of its result that the README documents.

Not part of the contract, so they can change in a minor release: the HTML report's layout and styling, score
wording, AI prompt text, and anything in a module whose name starts with `_`.

Adding things (new flags, new JSON fields, new tabs) is always a minor release. Deprecate before removing: keep
the old flag working with a warning for at least one minor release.
