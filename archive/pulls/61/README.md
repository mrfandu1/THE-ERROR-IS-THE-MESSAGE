# feat: add mobile-friendly repository dump workflow


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/61  
State: open  
Created: 2026-09-13T08:36:28Z


## Summary

Implements the repository dump tool requested in #60.

- Adds a mobile-friendly `workflow_dispatch` workflow with `source_repository`, output directory, and attachment controls.
- Exports all issues, pull requests, issue comments, reviews, inline review comments, releases, release notes, tags, and release assets through the GitHub REST API.
- Downloads GitHub-hosted attachments referenced by discussions while leaving ordinary external links untouched.
- Writes deterministic JSON indexes plus a manifest with counts, hashes, and failed-download records.
- Uses only the Python standard library; no paid service or third-party dependency is required.

## Validation

- `python -m unittest discover -s tests -v`
- `python -m py_compile tools/repo_dump.py`
- `git diff --check`
- Authenticated read-only smoke run against this repository: 60 issues and 4 releases discovered.

The workflow can be started from GitHub's web or mobile Actions UI and commits the resulting dump into `repo-dump/`.



## Comments



### iliasaberkane6-lab — 2026-09-13T08:58:57Z


Follow-up commit `dc32aea` hardens attachment handling: API tokens are never sent to signed CDN URLs, malformed URL-like text is ignored, and tokens are redacted from errors.

Validation: 4/4 local tests pass; a real 10.6 MB GitHub-hosted attachment downloaded successfully. The workflow remains dependency-free and mobile-triggerable.


### iliasaberkane6-lab — 2026-09-13T13:09:01Z


Hosted validation completed on the fork after the workflow and attachment-parser fixes:\n\n- [Successful mobile-triggerable Actions run](https://github.com/iliasaberkane6-lab/THE-ERROR-IS-THE-MESSAGE/actions/runs/34758711188)\n- [Immutable published archive](https://github.com/iliasaberkane6-lab/THE-ERROR-IS-THE-MESSAGE/tree/fe3dbb8f003914153582b2fef6768d7d071c0c79/repo-dump-demo)\n- 60 issues, 14 pull requests, and 4 releases exported\n- 401 GitHub-hosted attachments found and downloaded, 0 failures (about 1.83 GB)\n- Local regression suite: 4/4 tests passing\n\nThe archive is committed directly into the fork and the workflow remains runnable from Actions on a phone. This is a demonstration for review; no acceptance or payout is assumed.
