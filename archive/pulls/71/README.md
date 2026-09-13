# Repo dump tool: issues+PRs+releases+media -> repo-dump/ (stdlib Python, Actions-triggerable) [closes #60]


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/71  
State: open  
Created: 2026-09-13T10:55:21Z


## Repo dump tool — bounty submission for #60

**What it is:** `tools/repo_dump.py` — Python 3 stdlib-only CLI that dumps a repo's issues, PRs (incl. review comments), releases, and ALL attached media into the repo itself as `repo-dump/` (markdown + `manifest.json` + indexed `README.md`). Resumable, budgeted, parallel media downloads; public media fetched tokenless (user-attachments URLs reject `Authorization` headers with HTTP 400 — found and fixed during testing).

**Trigger without a local machine:** `.github/workflows/repo-dump.yml` — Actions → **Repo Dump** → Run workflow (optional `target_repo` input to dump any repo from a phone).

**Test evidence (real run against this repo):**
```
DONE: 60 issues, 10 PRs, 4 releases, 345/346 media -> repo-dump/  [402s]
```
- 605 files written, 2.1 GB media, 1 failed URL reported in `manifest.json` (not silently dropped)
- resume check: re-run reused 114 MB cached media, zero re-downloads
- includes issue #60 itself (`repo-dump/issues/000060-*.md`)

**Run locally:** `GITHUB_TOKEN=ghp_xxx python3 tools/repo_dump.py --repo OWNER/NAME --out repo-dump --budget 900`

The full dump output is committed on this branch under `repo-dump/`.
