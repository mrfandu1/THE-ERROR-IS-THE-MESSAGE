# Add phone-triggered repository export with verified media preservation


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/69  
State: open  
Created: 2026-09-13T10:00:10Z


Related to #60. This adds a dependency-free Python exporter and a one-button GitHub Actions workflow that saves issues, PR conversations and reviews, releases, tags, and uploaded files directly to a dedicated `repository-archive` branch. Team members can run it from a phone browser without installing software or creating a token.

A complete hosted demonstration against **attogram/THE-ERROR-IS-THE-MESSAGE** has finished successfully, including downloads, SHA-256 verification and publication:

- [Successful full Actions run](https://github.com/mrfandu1/THE-ERROR-IS-THE-MESSAGE/actions/runs/34750298572)
- [Published archive at its immutable commit](https://github.com/mrfandu1/THE-ERROR-IS-THE-MESSAGE/tree/aaec7791ce41260a153d142c38c3953128092531/archive)
- [Issue #60 demonstration: text, all 11 comments at collection time, and local media links](https://github.com/mrfandu1/THE-ERROR-IS-THE-MESSAGE/blob/aaec7791ce41260a153d142c38c3953128092531/archive/issues/60/README.md)
- [Completeness report](https://github.com/mrfandu1/THE-ERROR-IS-THE-MESSAGE/blob/aaec7791ce41260a153d142c38c3953128092531/archive/report.json)

The demonstration preserved **60 issues, 6 PRs, 169 conversation comments, 4 releases, 4 tags and 401 downloaded files totaling 1,895,824,852 bytes**, including all eight release source ZIP/TAR files. No API/download failures were reported. The source contained zero PR reviews/inline comments at export time; regression fixtures separately cover those records, including reply IDs and diff context.

Raw JSON preserves original text; readable pages link to local media. Files over 40 MiB are split into checksum-verified parts and can be restored byte for byte. Reruns verify cached downloads before reuse, invalidate changed release assets/tags, and retry failures. Publication uses small, retryable pushes with an explicit incomplete marker until its final commit. Tokens are restricted to GitHub's API and stripped on cross-origin redirects; downloaded content is never executed.

Validation: 20 tests pass locally and on [Windows/Linux CI](https://github.com/mrfandu1/THE-ERROR-IS-THE-MESSAGE/actions/runs/34750284487). The initial full hosted run was independently checked after publication: all 583 checksum-listed files existed remotely, every asset-part length matched the manifest, and 12 sampled remote files matched SHA-256. The latest hosted rerun verified the cached files again and preserved new PRs/comments. The latest archive index and issue #60 page were inspected in a real browser, including clickable saved audio/video links and localized HTML images. The source snapshot is sequential, not atomic; deleted records/historical edits unavailable through GitHub's APIs cannot be recovered. Full scope and phone instructions are in `REPOSITORY_DUMP.md`.

Submitted for the advertised EUR 100 bounty. AI-assisted implementation for @mrfandu1. Please confirm whether this demonstration meets the acceptance criteria and your preferred payout method for the accepted award.



## Reviews



### copilot-pull-request-reviewer[bot] — 2026-09-13T10:10:42Z


### 🟡 Changes recommended

Critical archive-branch and upload-trust issues, along with moderate publication, CI, link, and concurrency issues, remain unresolved.

*Get a fresh assessment by requesting another Copilot review.*

<details>
<summary>Pull request overview</summary>

Adds a dependency-free, phone-triggered GitHub repository exporter that preserves discussions, releases, tags, and media in an archive branch.

**Changes:**
- Exports and verifies repository records and uploaded files.
- Publishes archives incrementally with large-file handling.
- Adds tests, documentation, and cross-platform workflows.
</details>

<details>
<summary>File summaries</summary>

| File | Summary and review notes |
|---|---|
| `tools/repository_dump.py` | Export, download, verification, and restoration logic. **Critical (1 vote):** upload URL validation trusts attacker-controlled hosts. **Moderate (2 votes):** some bare media links are not clickable. **Moderate (1 vote):** concurrent media-map access can fail during checkpointing. |
| `tools/publish_archive.py` | Batched archive publication. **Moderate (2 votes):** generated metadata is not chunked and may exceed the archive file limit. |
| `tests/test_repository_dump.py` | Exporter and security test coverage. |
| `tests/test_publish_archive.py` | Publication test coverage. |
| `REPOSITORY_DUMP.md` | Usage and phone workflow documentation. |
| `.gitignore` | Ignores generated export artifacts. |
| `.github/workflows/test-repository-dump.yml` | Cross-platform test workflow. **Moderate (3 votes):** path filters omit publisher files, allowing publisher-only changes to bypass these tests. |
| `.github/workflows/repository-dump.yml` | Phone-triggered export and publication workflow. **Critical (2 votes):** orphan-branch initialization can include the source tree in the archive and bypass the large-file guard. |
</details>

<details>
<summary>Review details</summary>

### Suppressed comments (1)

**tools/repository_dump.py:367**
* With multiple upload workers, a worker can assign to `self.media` while the main thread constructs `dict(self.media)` here. Iterating a dict during a concurrent size change can raise `RuntimeError: dictionary changed size during iteration`, which `run()` records as an API-collection failure and makes an otherwise successful export incomplete. Serialize this checkpoint or protect all shared map access with a lock.
```
                # Each completed record is immutable; snapshot the map before serialization.
                write_json(self.output / 'assets.json', dict(self.media))
```

- **Files reviewed:** 7/8 changed files
- **Comments generated:** 5
- **Review effort level:** Lite
</details>

---

💡 <a href="/attogram/THE-ERROR-IS-THE-MESSAGE/new/main?filename=.github/skills/code-review/SKILL.md" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Add a `code-review` agent skill</a> or configure MCP servers for context-aware, tailored reviews. <a href="https://docs.github.com/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review?tool=webui#mcp-servers-and-agent-skills" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Learn more in the docs.</a>


## Inline review comments



### Copilot — 2026-09-13T10:10:41Z


When no archive branch exists, `git switch --orphan` leaves the checked-out source tree in the index/worktree. The publisher's first staged commit can therefore include every source file, so the supposedly dedicated archive branch duplicates the repository and can bypass the 40 MiB archive-file guard. Clear the orphan index/worktree before exporting.


File: `.github/workflows/repository-dump.yml`; line: 45; reply to: none



````diff
@@ -0,0 +1,91 @@
+name: Save repository history and media
+
+on:
+  workflow_dispatch:
+    inputs:
+      source_repository:
+        description: 'Repository to save (owner/name). Leave blank for this repository.'
+        required: false
+        type: string
+
+permissions:
+  contents: write
+  issues: read
+  pull-requests: read
+
+concurrency:
+  group: repository-archive
+  cancel-in-progress: false
+
+jobs:
+  archive:
+    runs-on: ubuntu-latest
+    timeout-minutes: 90
+    env:
+      ARCHIVE_BRANCH: repository-archive
+      SOURCE_REPOSITORY: ${{ inputs.source_repository || vars.REPOSITORY_DUMP_SOURCE || github.repository }}
+    steps:
+      - name: Get the export tool
+        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
+        with:
+          fetch-depth: 1
+
+      - name: Test the export tool
+        run: python3 -m unittest discover -s tests -v
+
+      - name: Prepare archive branch
+        shell: bash
+        run: |
+          archive_path="$RUNNER_TEMP/repository-archive"
+          if git ls-remote --exit-code --heads origin "$ARCHIVE_BRANCH" >/dev/null; then
+            git fetch origin "$ARCHIVE_BRANCH"
+            git worktree add --detach "$archive_path" FETCH_HEAD
+          else
+            git worktree add --detach "$archive_path" HEAD
+            git -C "$archive_path" switch --orphan archive-root
````



### Copilot — 2026-09-13T10:10:41Z


Any URL whose host starts with `github-production-user-asset-` is treated as an upload, while `trusted_download` accepts any matching S3 bucket. A repository commenter can therefore make the action fetch an attacker-controlled public object instead of a GitHub upload. Only accept GitHub upload URLs initially; keep the S3 pattern for redirects from GitHub storage (or otherwise bind the redirect origin).


File: `tools/repository_dump.py`; line: None; reply to: none



````diff
@@ -0,0 +1,478 @@
+#!/usr/bin/env python3
+"""Archive GitHub conversations and uploaded media. Python 3.10+, no dependencies."""
+from __future__ import annotations
+
+import argparse
+import hashlib
+import html
+import json
+import mimetypes
+import os
+from pathlib import Path
+import re
+import sys
+import time
+from datetime import datetime, timezone
+from concurrent.futures import ThreadPoolExecutor, as_completed
+from urllib.error import HTTPError, URLError
+from urllib.parse import urljoin, urlsplit, urlunsplit
+from urllib.request import Request, build_opener, HTTPRedirectHandler
+
+API = 'https://api.github.com'
+BLOCK_SIZE = 1024 * 1024
+PART_SIZE = 40 * BLOCK_SIZE  # GitHub's regular Git object limit is 100 MiB.
+URL_RE = re.compile(r'https://[^\s<>"\x27`]+')
+
+
+def timestamp():
+    return datetime.now(timezone.utc).isoformat()
+
+
+def digest(path):
+    with path.open('rb') as source:
+        return hashlib.file_digest(source, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _hash_stream(source)
+
+
+def _hash_stream(source):
+    result = hashlib.sha256()
+    for block in iter(lambda: source.read(BLOCK_SIZE), b''):
+        result.update(block)
+    return result.hexdigest()
+
+
+def write_json(path, value):
+    path.parent.mkdir(parents=True, exist_ok=True)
+    temporary = path.with_name(path.name + '.tmp')
+    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
+    temporary.replace(path)
+
+
+def safe_child(root, relative):
+    root = root.resolve()
+    path = (root / relative).resolve()
+    if path == root or root not in path.parents:
+        raise ValueError('Archive path escapes its destination')
+    return path
+
+
+def trusted_download(url):
+    value = urlsplit(url)
+    host = value.hostname or ''
+    if value.scheme != 'https' or value.username or value.password or value.port not in (None, 443):
+        return False
+    return (host in {'github.com', 'api.github.com', 'codeload.github.com', 'github-cloud.s3.amazonaws.com'}
+            or host.endswith('.githubusercontent.com')
+            or bool(re.fullmatch(r'github-production-[a-z0-9-]+\.s3\.amazonaws\.com', host)))
+
+
+class SafeRedirect(HTTPRedirectHandler):
+    def redirect_request(self, req, fp, code, msg, headers, newurl):
+        newurl = urljoin(req.full_url, newurl)
+        if not trusted_download(newurl):
+            raise ValueError('Refusing a redirect outside GitHub file storage')
+        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
+        if urlsplit(newurl).netloc != urlsplit(req.full_url).netloc:
+            redirected.remove_header('Authorization')
+        return redirected
+
+
+class GitHub:
+    def __init__(self, token=None, opener=None, sleep=time.sleep):
+        self.token = token
+        self.opener = opener or build_opener(SafeRedirect())
+        self.sleep = sleep
+        self.requests = 0
+
+    def open(self, url, binary=False):
+        if not trusted_download(url):
+            raise ValueError('Refusing an untrusted download URL')
+        parsed = urlsplit(url)
+        # Source-archive endpoints redirect to a binary but require the JSON
+        # media type at the API. octet-stream is specific to release assets.
+        asset_api = parsed.hostname == 'api.github.com' and '/releases/assets/' in parsed.path
+        accept = 'application/vnd.github+json'
+        if binary:
+            if asset_api:
+                accept = 'application/octet-stream'
+            elif parsed.hostname != 'api.github.com':
+                accept = '*/*'
+        headers = {'User-Agent': 'repository-dump/1.0',
+                   'Accept': accept,
+                   'X-GitHub-Api-Version': '2022-11-28'}
+        if self.token and parsed.hostname == 'api.github.com':
+            headers['Authorization'] = 'Bearer ' + self.token
+        for attempt in range(4):
+            try:
+                self.requests += 1
+                return self.opener.open(Request(url, headers=headers), timeout=60)
+            except HTTPError as error:
+                retryable = error.code in (429, 500, 502, 503, 504) or (error.code == 403 and error.headers.get('Retry-After'))
+                if not retryable or attempt == 3:
+                    raise RuntimeError(f'GitHub returned HTTP {error.code}; check access and rate limits') from None
+                delay = error.headers.get('Retry-After', str(2 ** attempt))
+                try:
+                    delay = float(delay)
+                except ValueError:
+                    delay = 2 ** attempt
+                if delay > 60:
+                    raise RuntimeError('GitHub requested a long rate-limit wait; rerun later') from None
+                self.sleep(max(0, delay))
+            except (URLError, TimeoutError):
+                if attempt == 3:
+                    raise RuntimeError('Network request failed after four attempts') from None
+                self.sleep(2 ** attempt)
+
+    def one(self, path):
+        with self.open(API + path) as response:
+            return json.load(response)
+
+    def pages(self, path):
+        url = API + path + ('&' if '?' in path else '?') + 'per_page=100'
+        seen = set()
+        result = []
+        while url:
+            if url in seen or urlsplit(url).netloc != 'api.github.com':
+                raise RuntimeError('Invalid GitHub pagination link')
+            seen.add(url)
+            with self.open(url) as response:
+                page = json.load(response)
+                if not isinstance(page, list):
+                    raise RuntimeError('GitHub returned an unexpected list response')
+                result.extend(page)
+                link = response.headers.get('Link', '')
+            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
+            url = match.group(1) if match else None
+        return result
+
+
+def uploaded_urls(text):
+    """GitHub uploads in Markdown, HTML, bare video URLs, and reference links."""
+    found = set()
+    for match in URL_RE.finditer(html.unescape(text or '')):
+        url = match.group().rstrip('.,;:!?')
+        # Markdown closing parentheses are not part of a bare GitHub upload URL.
+        while url.endswith(')') and url.count(')') > url.count('('):
+            url = url[:-1]
+        url = url.rstrip(']')
+        try:
+            parsed = urlsplit(url)
+            if not trusted_download(url):
+                continue
+        except ValueError:
+            continue
+        host = parsed.hostname or ''
+        uuid = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
+        is_upload = ((host == 'github.com' and
+                      (re.fullmatch(r'/user-attachments/assets/' + uuid, parsed.path) or
+                       re.match(r'^/user-attachments/files/[0-9]+/[^/]+', parsed.path) or
+                       re.match(r'^/[^/]+/[^/]+/files/[0-9]+/[^/]+', parsed.path) or
+                       re.fullmatch(r'/[^/]+/[^/]+/assets/[0-9]+/' + uuid, parsed.path)))
+                     or host in {'user-images.githubusercontent.com', 'private-user-images.githubusercontent.com', 'secured-user-images.githubusercontent.com'}
+                     or host.startswith('github-production-user-asset-'))
````



### Copilot — 2026-09-13T10:10:41Z


This workflow is the matrix that runs the Python test suite on both Linux and Windows, but neither the `pull_request` nor `push` path filters includes `tools/publish_archive.py` or `tests/test_publish_archive.py`. A publisher-only change can therefore merge without running the tests that cover it; add both files to each filter.


File: `.github/workflows/test-repository-dump.yml`; line: 16; reply to: none



````diff
@@ -0,0 +1,23 @@
+name: Test repository export tool
+on:
+  pull_request:
+    paths:
+      - 'tools/repository_dump.py'
+      - 'tests/test_repository_dump.py'
+      - '.github/workflows/*repository-dump.yml'
+  push:
+    paths:
+      - 'tools/repository_dump.py'
+      - 'tests/test_repository_dump.py'
+      - '.github/workflows/*repository-dump.yml'
````



### Copilot — 2026-09-13T10:10:42Z


Only downloaded media is split by `repository_dump.py`; generated metadata such as `issue-comments.json`, `issue-index.json`, and per-PR `files.json` is written as one file. A repository with enough discussion or patch data can exceed 40 MiB, causing this guard to abort publication even though the export is otherwise complete, contrary to the documented large-file handling. Chunk generated metadata as well (or use another size-safe representation) before enforcing the archive file limit.


File: `tools/publish_archive.py`; line: None; reply to: none



````diff
@@ -0,0 +1,77 @@
+"""Publish an archive in small, retryable pushes with an explicit pending state."""
+import argparse
+import json
+import os
+from pathlib import Path
+import subprocess
+import time
+
+
+def publish(root, branch='repository-archive', batch_bytes=64 * 1024 * 1024, sleep=time.sleep):
+    root = Path(root).resolve()
+    if branch != 'repository-archive':
+        raise ValueError('Only the dedicated repository-archive branch may be published')
+
+    def git(*args, capture=False, check=True):
+        return subprocess.run(['git', '-C', str(root), *args], check=check,
+                              stdout=subprocess.PIPE if capture else None)
+
+    def save(paths, message):
+        for offset in range(0, len(paths), 100):
+            git('add', '--', *paths[offset:offset + 100])
+        changed = git('diff', '--cached', '--quiet', check=False).returncode
+        if changed == 0:
+            return
+        if changed != 1:
+            raise RuntimeError('Could not inspect staged archive changes')
+        git('commit', '-m', message)
+        for attempt in range(3):
+            result = git('push', 'origin', f'HEAD:refs/heads/{branch}', check=False)
+            if result.returncode == 0:
+                return
+            if attempt < 2:
+                sleep(2 ** (attempt + 1))
+        raise RuntimeError('Archive push failed after three attempts; see Git output')
+
+    report_path = root / 'archive/report.json'
+    readme_path = root / 'archive/README.md'
+    final_report, final_readme = report_path.read_bytes(), readme_path.read_bytes()
+    report = json.loads(final_report)
+    report.update(complete=False, publication_in_progress=True)
+    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
+    readme_path.write_text('# Archive publication in progress\n\n'
+                          'This branch is incomplete until the final publication commit. '
+                          'Check the Actions run for its status.\n', encoding='utf-8')
+    save(['archive/report.json', 'archive/README.md'], 'Mark archive publication in progress')
+
+    changed = git('ls-files', '--others', '--modified', '--deleted',
+                  '--exclude-standard', '-z', '--', 'archive', capture=True).stdout
+    paths = sorted(set(os.fsdecode(p) for p in changed.split(b'\0') if p))
+    batch, weight = [], 0
+    for relative in paths:
+        if relative in ('archive/report.json', 'archive/README.md', 'archive/checksums.json'):
+            continue
+        path = root / relative
+        if path.is_symlink() or not path.resolve().is_relative_to(root / 'archive'):
+            raise ValueError('Archive contains an unsafe path')
+        size = path.stat().st_size if path.exists() else 0
+        if size > 40 * 1024 * 1024:
+            raise ValueError('Unexpected oversized archive file; export must split large assets')
````



### Copilot — 2026-09-13T10:10:42Z


The final replacement turns an inline bare upload such as `See <upload-url> for details` into plain `See ../../assets/<hash>` text. Relative paths are not autolinked by Markdown, so these supported bare media references are not clickable in the archived page; only whole-line URLs and angle autolinks are converted to links. Preserve the existing Markdown/HTML cases while wrapping remaining bare occurrences in a local Markdown link.


File: `tools/repository_dump.py`; line: None; reply to: none



````diff
@@ -0,0 +1,478 @@
+#!/usr/bin/env python3
+"""Archive GitHub conversations and uploaded media. Python 3.10+, no dependencies."""
+from __future__ import annotations
+
+import argparse
+import hashlib
+import html
+import json
+import mimetypes
+import os
+from pathlib import Path
+import re
+import sys
+import time
+from datetime import datetime, timezone
+from concurrent.futures import ThreadPoolExecutor, as_completed
+from urllib.error import HTTPError, URLError
+from urllib.parse import urljoin, urlsplit, urlunsplit
+from urllib.request import Request, build_opener, HTTPRedirectHandler
+
+API = 'https://api.github.com'
+BLOCK_SIZE = 1024 * 1024
+PART_SIZE = 40 * BLOCK_SIZE  # GitHub's regular Git object limit is 100 MiB.
+URL_RE = re.compile(r'https://[^\s<>"\x27`]+')
+
+
+def timestamp():
+    return datetime.now(timezone.utc).isoformat()
+
+
+def digest(path):
+    with path.open('rb') as source:
+        return hashlib.file_digest(source, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _hash_stream(source)
+
+
+def _hash_stream(source):
+    result = hashlib.sha256()
+    for block in iter(lambda: source.read(BLOCK_SIZE), b''):
+        result.update(block)
+    return result.hexdigest()
+
+
+def write_json(path, value):
+    path.parent.mkdir(parents=True, exist_ok=True)
+    temporary = path.with_name(path.name + '.tmp')
+    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
+    temporary.replace(path)
+
+
+def safe_child(root, relative):
+    root = root.resolve()
+    path = (root / relative).resolve()
+    if path == root or root not in path.parents:
+        raise ValueError('Archive path escapes its destination')
+    return path
+
+
+def trusted_download(url):
+    value = urlsplit(url)
+    host = value.hostname or ''
+    if value.scheme != 'https' or value.username or value.password or value.port not in (None, 443):
+        return False
+    return (host in {'github.com', 'api.github.com', 'codeload.github.com', 'github-cloud.s3.amazonaws.com'}
+            or host.endswith('.githubusercontent.com')
+            or bool(re.fullmatch(r'github-production-[a-z0-9-]+\.s3\.amazonaws\.com', host)))
+
+
+class SafeRedirect(HTTPRedirectHandler):
+    def redirect_request(self, req, fp, code, msg, headers, newurl):
+        newurl = urljoin(req.full_url, newurl)
+        if not trusted_download(newurl):
+            raise ValueError('Refusing a redirect outside GitHub file storage')
+        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
+        if urlsplit(newurl).netloc != urlsplit(req.full_url).netloc:
+            redirected.remove_header('Authorization')
+        return redirected
+
+
+class GitHub:
+    def __init__(self, token=None, opener=None, sleep=time.sleep):
+        self.token = token
+        self.opener = opener or build_opener(SafeRedirect())
+        self.sleep = sleep
+        self.requests = 0
+
+    def open(self, url, binary=False):
+        if not trusted_download(url):
+            raise ValueError('Refusing an untrusted download URL')
+        parsed = urlsplit(url)
+        # Source-archive endpoints redirect to a binary but require the JSON
+        # media type at the API. octet-stream is specific to release assets.
+        asset_api = parsed.hostname == 'api.github.com' and '/releases/assets/' in parsed.path
+        accept = 'application/vnd.github+json'
+        if binary:
+            if asset_api:
+                accept = 'application/octet-stream'
+            elif parsed.hostname != 'api.github.com':
+                accept = '*/*'
+        headers = {'User-Agent': 'repository-dump/1.0',
+                   'Accept': accept,
+                   'X-GitHub-Api-Version': '2022-11-28'}
+        if self.token and parsed.hostname == 'api.github.com':
+            headers['Authorization'] = 'Bearer ' + self.token
+        for attempt in range(4):
+            try:
+                self.requests += 1
+                return self.opener.open(Request(url, headers=headers), timeout=60)
+            except HTTPError as error:
+                retryable = error.code in (429, 500, 502, 503, 504) or (error.code == 403 and error.headers.get('Retry-After'))
+                if not retryable or attempt == 3:
+                    raise RuntimeError(f'GitHub returned HTTP {error.code}; check access and rate limits') from None
+                delay = error.headers.get('Retry-After', str(2 ** attempt))
+                try:
+                    delay = float(delay)
+                except ValueError:
+                    delay = 2 ** attempt
+                if delay > 60:
+                    raise RuntimeError('GitHub requested a long rate-limit wait; rerun later') from None
+                self.sleep(max(0, delay))
+            except (URLError, TimeoutError):
+                if attempt == 3:
+                    raise RuntimeError('Network request failed after four attempts') from None
+                self.sleep(2 ** attempt)
+
+    def one(self, path):
+        with self.open(API + path) as response:
+            return json.load(response)
+
+    def pages(self, path):
+        url = API + path + ('&' if '?' in path else '?') + 'per_page=100'
+        seen = set()
+        result = []
+        while url:
+            if url in seen or urlsplit(url).netloc != 'api.github.com':
+                raise RuntimeError('Invalid GitHub pagination link')
+            seen.add(url)
+            with self.open(url) as response:
+                page = json.load(response)
+                if not isinstance(page, list):
+                    raise RuntimeError('GitHub returned an unexpected list response')
+                result.extend(page)
+                link = response.headers.get('Link', '')
+            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
+            url = match.group(1) if match else None
+        return result
+
+
+def uploaded_urls(text):
+    """GitHub uploads in Markdown, HTML, bare video URLs, and reference links."""
+    found = set()
+    for match in URL_RE.finditer(html.unescape(text or '')):
+        url = match.group().rstrip('.,;:!?')
+        # Markdown closing parentheses are not part of a bare GitHub upload URL.
+        while url.endswith(')') and url.count(')') > url.count('('):
+            url = url[:-1]
+        url = url.rstrip(']')
+        try:
+            parsed = urlsplit(url)
+            if not trusted_download(url):
+                continue
+        except ValueError:
+            continue
+        host = parsed.hostname or ''
+        uuid = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
+        is_upload = ((host == 'github.com' and
+                      (re.fullmatch(r'/user-attachments/assets/' + uuid, parsed.path) or
+                       re.match(r'^/user-attachments/files/[0-9]+/[^/]+', parsed.path) or
+                       re.match(r'^/[^/]+/[^/]+/files/[0-9]+/[^/]+', parsed.path) or
+                       re.fullmatch(r'/[^/]+/[^/]+/assets/[0-9]+/' + uuid, parsed.path)))
+                     or host in {'user-images.githubusercontent.com', 'private-user-images.githubusercontent.com', 'secured-user-images.githubusercontent.com'}
+                     or host.startswith('github-production-user-asset-'))
+        if is_upload and trusted_download(url):
+            found.add(urlunsplit(parsed._replace(fragment='')))
+    return sorted(found)
+
+
+def text_fields(value):
+    if isinstance(value, dict):
+        for key, child in value.items():
+            if key in {'body', 'description'} and isinstance(child, str):
+                yield child
+            elif isinstance(child, (dict, list)):
+                yield from text_fields(child)
+    elif isinstance(value, list):
+        for child in value:
+            yield from text_fields(child)
+
+
+class Archive:
+    def __init__(self, github, repository, output, workers=4):
+        if (not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repository)
+                or repository.split('/')[-1] in {'.', '..'}):
+            raise ValueError('Repository must be owner/name')
+        self.github, self.repository, self.output = github, repository, Path(output)
+        self.workers = workers
+        self.prefix = '/repos/' + repository
+        self.output.mkdir(parents=True, exist_ok=True)
+        if any(path.is_symlink() for path in self.output.rglob('*')):
+            raise ValueError('Archive output contains symlinks; use a dedicated directory without symlinks')
+        self.media = {}
+        previous = self.output / 'assets.json'
+        self.previous = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else {}
+        self.report = {'repository': repository, 'started_at': timestamp(), 'complete': False,
+                       'errors': [], 'counts': {}, 'scope': 'Current accessible GitHub API records, including open and closed issues and PRs, reviews, release assets, and GitHub-hosted uploads. Deleted records and historical edits are not exposed by these APIs.'}
+
+    def cached(self, record):
+        try:
+            return bool(record.get('parts')) and all(
+                (path := safe_child(self.output, part['path'])).is_file()
+                and path.stat().st_size == part['bytes'] and digest(path) == part['sha256']
+                for part in record['parts'])
+        except (OSError, ValueError, KeyError):
+            return False
+
+    def download(self, url, name=None, expected_size=None, version=None):
+        if url in self.media:
+            return
+        previous = self.previous.get(url, {})
+        if previous.get('status') == 'saved' and previous.get('version') == version and self.cached(previous) and (expected_size is None or previous.get('bytes') == expected_size):
+            self.media[url] = previous
+            return
+        record = {'source': url, 'status': 'failed', 'parts': [], 'version': version}
+        temporary = self.output / 'assets' / (hashlib.sha256(url.encode()).hexdigest() + '.download')
+        temporary.parent.mkdir(parents=True, exist_ok=True)
+        try:
+            total = 0
+            full_hash = hashlib.sha256()
+            with self.github.open(url, binary=True) as response:
+                content_type = response.headers.get('Content-Type', 'application/octet-stream').split(';')[0]
+                if (content_type == 'text/html' and expected_size is None
+                        and 'attachment' not in response.headers.get('Content-Disposition', '').lower()
+                        and not urlsplit(url).path.lower().endswith(('.html', '.htm'))):
+                    raise ValueError('Expected an uploaded file, received an HTML page')
+                with temporary.open('wb') as target:
+                    while block := response.read(BLOCK_SIZE):
+                        target.write(block)
+                        full_hash.update(block)
+                        total += len(block)
+                declared = response.headers.get('Content-Length')
+                if declared is not None and total != int(declared):
+                    raise ValueError('Download is truncated (Content-Length mismatch)')
+                if expected_size is not None and total != expected_size:
+                    raise ValueError('Download size differs from release metadata')
+                disposition = response.headers.get('Content-Disposition', '')
+            remote_name = name or (re.search(r'filename="?([^";]+)', disposition).group(1) if re.search(r'filename="?([^";]+)', disposition) else Path(urlsplit(url).path).name)
+            if not Path(remote_name).suffix:
+                remote_name += mimetypes.guess_extension(content_type) or '.bin'
+            extension = Path(remote_name).suffix.lower()
+            if not re.fullmatch(r'\.[a-z0-9]{1,10}', extension):
+                extension = mimetypes.guess_extension(content_type) or '.bin'
+            extension = {'.jpe': '.jpg', '.jpeg': '.jpg'}.get(extension, extension)
+            stem = full_hash.hexdigest()
+            if total <= PART_SIZE:
+                destination = temporary.parent / (stem + extension)
+                temporary.replace(destination)
+                record['parts'] = [{'path': destination.relative_to(self.output).as_posix(), 'bytes': total, 'sha256': stem}]
+            else:
+                with temporary.open('rb') as source:
+                    part_number = 0
+                    while part := source.read(PART_SIZE):
+                        part_number += 1
+                        destination = temporary.parent / f'{stem}{extension}.part{part_number:04d}'
+                        destination.write_bytes(part)
+                        record['parts'].append({'path': destination.relative_to(self.output).as_posix(), 'bytes': len(part), 'sha256': hashlib.sha256(part).hexdigest()})
+                temporary.unlink()
+            record.update(status='saved', name=remote_name, bytes=total, sha256=stem, content_type=content_type)
+        except Exception as error:
+            temporary.unlink(missing_ok=True)
+            record['error'] = str(error)
+            self.report['errors'].append({'source': url, 'error': str(error)})
+        self.media[url] = record
+
+    def localize(self, body):
+        body = body or ''
+        for url in sorted(self.media, key=len, reverse=True):
+            asset = self.media[url]
+            if asset['status'] == 'saved' and len(asset['parts']) == 1:
+                local = '../../' + asset['parts'][0]['path']
+                link = '[Open saved attachment](' + local + ')'
+                # Relative paths are not autolinked by Markdown renderers.
+                # Preserve clickable bare video/audio URLs and <autolinks>.
+                body = re.sub(r'(?m)^[ \t]*' + re.escape(url) + r'[ \t]*\r?$',
+                              lambda match: link, body)
+                body = body.replace('<' + url + '>', link)
+                body = body.replace(url, local)
````

