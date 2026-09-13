# Save the repository's discussions and files

This tool saves every accessible open and closed issue, pull request, comment,
PR review, inline review comment, release, release asset, and GitHub-uploaded
attachment. The result is committed to the **repository-archive** branch of this
repository. Read it directly on GitHub or clone that branch for an offline copy.

## Run from a phone

After this change is merged:

1. Open this repository on **github.com** in your phone browser.
2. Open **Actions → Save repository history and media → Run workflow**.
3. Leave the repository field blank and press **Run workflow**.
4. Open the completed run and tap **Open the saved archive** in its summary.

Your account needs permission to run Actions and push the archive branch. The
workflow uses GitHub's built-in token; you do not need to create or paste a token.
On a new fork, enable Actions first if GitHub displays that prompt. Repository
rules that prohibit Actions from creating branches must allow
`repository-archive` before the workflow can save there.

For a demonstration on a fork, enter the original public `owner/repository` in
the optional field. Data still goes into **your fork**. An Actions token normally
cannot read a different private repository; export private data only from that
repository itself, with appropriate token access.

For repeated exports from the same different repository, a maintainer can set
the Actions repository variable `REPOSITORY_DUMP_SOURCE` to `owner/repository`.
Leaving the run field blank then uses that saved source; an explicit run field
overrides it. Without the variable, a blank field means this repository.

## What is saved

- Raw API JSON keeps original Unicode text and metadata without rewriting it.
- Each issue, PR, and release has a readable Markdown page.
- Issue comments and PR conversation comments are saved in full. PR reviews and
  inline comments are separate records, including reply IDs and diff context.
- PR commit metadata and file patches, release tags, uploaded release binaries,
  and GitHub's generated ZIP/TAR source archives are included.
- Markdown images, HTML media references, reference-style links, and bare
  GitHub upload URLs are discovered across all comment and review bodies.
- `assets.json` maps each original upload URL to its local file, byte length,
  media type, and SHA-256. Readable pages link to the local files.
- Every API list is paginated; there is no first-100-record cutoff.

This is a snapshot of records available from GitHub when the export runs.
GitHub does not expose deleted comments, all previous edit versions, or a
transactionally consistent snapshot during ongoing edits. The repository's
ordinary source files and Git history remain in their original branches; this
tool adds the discussions and media that a normal Git clone misses. Arbitrary
external websites linked in a discussion are not crawled.

## Completeness and reruns

`report.json` says whether the export completed and lists each failed API
request or download. A missing attachment, insufficient permission, rate limit,
or truncated binary makes the run **fail**, while preserving available data and
the failure report on the archive branch. A green checksum verification means
the saved bytes are intact; `report.json.complete` separately tells you whether
the requested export was complete.

Rerun the workflow to retry failures. Existing assets are reused only after
their size and hash are verified. Corrupted files are downloaded again. Earlier
records remain available on reruns, and previous archive commits retain prior
snapshots. No source branch is overwritten and no force push is used.

Downloads follow only HTTPS redirects to GitHub's API, upload storage, and
source archive hosts. Tokens are sent only to the API and stripped on cross-origin redirects and are
never written into the archive. Remote filenames cannot choose filesystem paths.
The workflow does not execute anything from the exported discussions or files.

## Run locally

Python 3.10 or newer is the only dependency. Set `GH_TOKEN` or `GITHUB_TOKEN` in
your environment for private repositories or the higher authenticated API quota.
The token needs read access to the source repository's contents, issues, and PRs.

```sh
python tools/repository_dump.py --repo OWNER/REPOSITORY --output repository-dump
python tools/repository_dump.py --verify repository-dump
```

The first command exits **0** for a complete export and **2** for an incomplete
export. `--verify` exits **1** if a saved file is missing or changed.

### Files larger than GitHub's per-file limit

The tool splits files larger than 40 MiB into numbered binary parts, each safely
below GitHub's 100 MiB Git object limit. It preserves the original full-file hash
as well as each part's hash. Restore the exact original bytes with:

```sh
python tools/repository_dump.py --restore repository-dump --destination restored-assets
```

Restoration verifies all saved files before writing any restored asset and checks
each reconstructed file's hash. Large files require this reconstruction step;
normal-sized images, audio, PDFs, and other attachments are directly readable in
the archive. During publication, the remote report explicitly stays incomplete until the final commit. The workflow pushes media in batches of at most 64 MiB, avoiding
GitHub's 2 GiB single-push limit. GitHub repository size quotas still apply to very
large archives. Downloads use four concurrent requests; use `--workers 1` locally
if you prefer lower network usage.

## Tests

```sh
python -m unittest discover -s tests -v
```

The tests cover closed issues and merged PRs, all comment types, pagination,
release binaries, JSON attachments, corruption recovery, unavailable files,
byte-exact reconstruction, safe paths, credential stripping, and rate-limit
retries. The test workflow runs on Windows and Linux.
