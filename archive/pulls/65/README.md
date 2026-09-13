# Archive repository conversations and media with verifiable recovery


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/65  
State: open  
Created: 2026-09-13T09:24:30Z


For #60: a normal git clone does not preserve issue/PR conversations or uploaded media. This adds a Python standard-library exporter and a recovery utility, with raw JSON, readable Markdown, original files, source mappings and SHA-256 checksums.

## Successful hosted demonstration

[GitHub Actions run](https://github.com/nexicturbo/THE-ERROR-IS-THE-MESSAGE/actions/runs/34755492356) on source commit `a899ef94a7e35f1fda7e38985911818b34a66f5c` passed all 18 tests, restored the previous archive for verified reuse, exported `attogram/THE-ERROR-IS-THE-MESSAGE`, and published the resulting archive branch. The installed workflow is manual and available on the fork's default branch.

[Immutable archive](https://github.com/nexicturbo/THE-ERROR-IS-THE-MESSAGE/tree/e8c0a931d765474b2bf9200fb53da4a5ac71429f/archive) · [Issue 60 with local attachment links](https://github.com/nexicturbo/THE-ERROR-IS-THE-MESSAGE/tree/e8c0a931d765474b2bf9200fb53da4a5ac71429f/archive/issues/60.md) · [Manifest and checksums](https://github.com/nexicturbo/THE-ERROR-IS-THE-MESSAGE/tree/e8c0a931d765474b2bf9200fb53da4a5ac71429f/archive/manifest.json)

The snapshot ran from 2026-09-13T11:51:31.250611+00:00 to 2026-09-13T11:52:22.497795+00:00 and contains:

- 60 issues, 12 PRs and 184 issue/general PR comments.
- 4 releases, 4 tags and all 8 generated release ZIP/TAR source packages, pinned to the fetched tag commits.
- The main README, its original bytes and API metadata, plus its linked uploads.
- **415 saved files / 1,974,836,504 bytes, zero errors**, including 61 attachments linked from issue 60 and its comments.

After the hosted run published its result, I independently rehashed all 415 original files, including each ordered part and the concatenated whole for chunked files, directly from the published commit's Git objects. All hashes and byte sizes match the manifest, and this exact commit was verified as the public archive branch tip. The original README's Git blob also matches GitHub's source blob. This is a sequential snapshot; later activity belongs to a subsequent run.

## Implementation and validation

18 regression tests pass. Coverage includes pagination; complete comments, reviews and replies; uploaded release assets; README preservation; pinned release packages; credential removal on CDN redirects; failed/truncated downloads; corrupt or replaced caches; and byte-for-byte restoration through a real Git round trip with line-ending conversion enabled. The live snapshot preserves 1 PR review records and 5 inline review comments. It contains 0 uploaded release binaries; fixtures separately exercise that API path.

2 large files are stored as ordered 48 MiB parts below GitHub's ordinary file-size limit. The included recovery command checks each part and the full original. Missing or oversized files cause a nonzero exit and an explicitly incomplete manifest. Reruns hash cached data before reuse and refresh changed release assets or tag revisions. One explicit all-x illustrative URL is retained in the source and recorded under `ignored_urls`.

```sh
python3 -m unittest discover -s tools -v
python3 tools/repo_dump.py attogram/THE-ERROR-IS-THE-MESSAGE --output repository-archive
python3 tools/restore_archive.py repository-archive restored-files
```

## Run from a phone

The actual workflow is included at `.github/workflows/repository-archive.yml`. Once it is on a repository's default branch and Actions is enabled, open **Actions → Repository archive → Run workflow**. Leave the source blank to archive that repository or specify the public source. It writes to the dedicated `repository-archive` branch, preserves the source/default branch, and uses the existing repository-scoped GITHUB_TOKEN. It does not run automatically on merge. The hosted demonstration above tests the same workflow included in this PR.

The README documents public-data limitations, non-atomic timing, and exclusions such as native GitHub Discussions, wikis, projects, Actions logs/artifacts and full git history. No paid storage or external service is configured.

