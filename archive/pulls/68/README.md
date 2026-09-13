# Add a mobile-triggered repository archive with verified attachment caching


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/68  
State: open  
Created: 2026-09-13T09:56:05Z


Implements #60 with a phone-triggered Actions workflow, a standard-library Python exporter, and a dedicated archive branch. It saves issue and PR conversations, reviews, releases (including generated source ZIP/TAR archives), tags and uploaded files, with readable pages and the original JSON. Re-runs verify cached files by SHA-256 before reusing them.

Validation: 19 local tests pass, including two real pushes to a temporary Git repository that preserve the source checkout and archive history. An earlier live API run collected 60 issues, 6 PRs, 168 comments, 4 releases and 4 tags; 392 uploaded files passed cache verification against those saved collections. One PDF remains excluded from this verification, so the full source-repository export is not yet demonstrated. Illustrative asset placeholders are ignored and legacy upload links are recognized. A separate live check downloaded and opened all eight source ZIP/TAR packages from releases 0000–0003 (78,859,745 bytes, no download failures). That check exposed an HTTP 415 caused by the request media type; this PR fixes it and adds a regression test. Archive member lists were checked against the inspected version trees. This is a bounded release-package check, not a rerun of the full repository export.

The [hosted workflow run](https://github.com/alidonghao118-commits/THE-ERROR-IS-THE-MESSAGE/actions/runs/34753821059) passed on my fork at `e1c006d`, including the current source-archive fixes. A clearly labeled test release supplied actual ZIP and TAR packages. The run passed regression tests, exported the release, uploaded a downloadable artifact, and saved the archive to the dedicated branch. This verifies the hosted pipeline with real release packages; the full source-repository verification remains as described above.

Run it from **Actions → Save repository conversations and attachments → Run workflow**. Local instructions are in `ARCHIVE_TOOL.md`.

A second [hosted run](https://github.com/alidonghao118-commits/THE-ERROR-IS-THE-MESSAGE/actions/runs/34756359241) also passed with nonempty, clearly labeled test discussions: one open and one closed issue, one open and one closed PR, three conversation comments, two review records, and a file review comment. I checked the saved JSON states and marker text, the PR commit/file records, and an actual uploaded TXT against its local SHA-256 and byte count. The [published archive](https://github.com/alidonghao118-commits/THE-ERROR-IS-THE-MESSAGE/tree/7df0a198a87b26b9fce4ccd582b03a7f5be202e6/repository-archive) reports complete with zero failures for this controlled fork; it also retains the test release and two previously verified source packages. These are synthetic fixtures, not independent reviews or a complete export of the upstream repository.
