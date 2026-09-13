# Repo Dump Tool - EUR 100 Bounty (closes #60)


Original: https://github.com/attogram/THE-ERROR-IS-THE-MESSAGE/pull/73  
State: open  
Created: 2026-09-13T12:07:27Z


Fixes #60

Complete implementation of the bounty specification — zero dependencies, pure Python stdlib:

- **Issues**: all open+closed with full bodies + complete comment threads (`dump/<ts>/issues/` + raw JSON)
- **Pull Requests**: all open+closed, comments + reviews + inline review comments (`dump/<ts>/pulls/`)
- **Releases**: notes, tags + all release artifacts downloaded (`dump/<ts>/releases/` + `media/`)
- **Media preservation**: every image/video/attachment embedded in issues, PRs, comments and releases (user-attachments, user-images, private-user-images, in-repo assets) downloaded into `media/`, all links rewritten to relative paths — the dump is fully self-contained and offline-readable
- **Direct repo dump**: the run commits the dump straight back into the repository
- **Mobile-friendly**: one-tap `workflow_dispatch` trigger from GitHub web/app — no computer required
- **Non-technical operation**: 2 taps, no CLI, no setup

**Demo (acceptance test 4.a — "consume this issue"):** the Actions run dumped `attogram/THE-ERROR-IS-THE-MESSAGE` into this fork — see the `dump/` commit: all issues including #60 itself, with its attached `bounty.repo.dump.0001.pdf` preserved under `media/`.

Payout address (Bitcoin, Bech32): `bc1qdl7lynawu0x0hx5674ldawk3upmd5gvz8rhjly`  
Backup address (Ethereum/ERC-20): `0xDa2C7911021E0e0a0ed7e4c73dfE823c3A1000fa`
