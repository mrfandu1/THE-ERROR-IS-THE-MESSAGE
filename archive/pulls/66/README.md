# Add a resumable repository archive with checksummed media and manual Actions


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/66  
State: open  
Created: 2026-09-13T09:43:08Z


Adds a dependency-free exporter and manual Actions workflow for #60. Issues, PR conversations/reviews, releases, tags, README text, uploaded media and GitHub-generated release source ZIP/TAR files are preserved as JSON, readable pages and a checksummed manifest. The workflow commits to a dedicated archive branch, reuses verified media and reports missing files or budget exhaustion as failures.

**Final hosted run passed:** https://github.com/Manntouu/THE-ERROR-IS-THE-MESSAGE/actions/runs/34751238107
**Published archive:** https://github.com/Manntouu/THE-ERROR-IS-THE-MESSAGE/tree/18d5693c50c71db0d214389da6a2517c65831f76/repository-dump

The run saved 60 issues, 9 PRs, 172 conversation comments, 5 inline comments, 1 review, 4 releases/tags and 407 downloads (399 uploaded attachment URLs plus 8 release source archives), with zero failures. All 17 tests passed. Previous attachment hashes and remote media blobs stayed identical; all eight new ZIP/TAR files were independently downloaded, hash-checked and parsed successfully. Deduplication stores 350 unique files for 408 part references.

The generated archive and issue #60 were exercised in a browser; manual workflow controls were inspected and filled at a 390px phone-sized viewport. Actual dispatch was from desktop. See tools/REPOSITORY_ARCHIVE.md and tools/VALIDATION.md for reproduction, corrected failure cases and exact evidence.

Scope excludes inaccessible/deleted content, full edit histories, separate Discussions, wikis, projects, Actions artifacts and Git history. Snapshots are non-atomic.

€100 bounty claim, subject to maintainer acceptance and payment confirmation. AI-assisted implementation and validation by Codex, authorized for @Manntouu.

