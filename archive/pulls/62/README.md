# Archive repository conversations and media with checksummed recovery


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/62  
State: open  
Created: 2026-09-13T08:42:28Z


For #60, this exports repository conversations, releases and uploaded media into the repository, with a manually triggered workflow for mobile use.

Hosted demonstration now passed: https://github.com/sapph1re/THE-ERROR-IS-THE-MESSAGE/actions/runs/34750562832 completed export and publication in 4m7s. Its newer snapshot is https://github.com/sapph1re/THE-ERROR-IS-THE-MESSAGE/tree/f60a65c5619d227b59b928ded34367812fc2ebb8/archive (60 issues, 7 PRs, 4 releases, 401 assets, 1,895,824,852 bytes, zero failures). Local verification of the remote asset manifest and full Git tree matched all 406 hosted part blob IDs to SHA-256-verified bytes and all 401 full-file hashes. The workflow performs export and publication; restoration/integrity checks and the original 10 implementation tests were run locally. Earlier dispatch errors are resolved.

The Python implementation has no third-party dependencies. It paginates open and closed issues/PRs, conversation comments, reviews and inline review comments, release assets and tags. Original JSON and Markdown are retained alongside a readable index. Uploaded files are never executed. Assets use 40 MiB parts and checksums; restoration gives media usable filenames and extensions. Publication uses 256 MiB batches, with an incomplete marker until the final manifest is committed. A targeted retry command recovers failed assets without rereading successful metadata or redownloading successful files.

Validation: 11 local tests pass, covering pagination, attachment recognition, credential stripping on redirects, chunk reconstruction and corruption, download limits, incomplete metadata, targeted retries, restored filenames, and batched publication against a local bare Git remote. The live export initially exposed missing GitHub download hosts; those were corrected, and the eight release ZIP/tar downloads recovered on retry. The final snapshot has zero recorded failures. It is a dated, non-atomic API snapshot; the README documents scope and storage limits.

Restoration follow-up (9e4936e): a corrupt part previously left a partial destination file that blocked a retry. Output is now published only after verification; retry checks and skips completed files, removes failed temporary output, and refuses to overwrite differing user files. The new two-asset regression failed before the fix and passes afterward, including preservation of an edited destination. All 11 local tests pass. Atomic publication requires hard-link support, documented for APFS/ext4. The hosted export above ran at b5a314c; this follow-up changes only the local restore path, its tests, and documentation, not the exporter or workflow.

AI-assisted implementation by Codex for Roman Vinogradov (@sapph1re), submitted for the stated €100 bounty. Please confirm acceptance for the stated bounty and which payout method you support.

