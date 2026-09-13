"""Publish an archive in small, retryable pushes with an explicit pending state."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

if __package__:
    from .repository_dump import read_json
else:
    from repository_dump import read_json


def publish(root, branch='repository-archive', batch_bytes=64 * 1024 * 1024, sleep=time.sleep):
    root = Path(root).resolve()
    if branch != 'repository-archive':
        raise ValueError('Only the dedicated repository-archive branch may be published')

    def git(*args, capture=False, check=True):
        return subprocess.run(['git', '-C', str(root), *args], check=check,
                              stdout=subprocess.PIPE if capture else None)

    if git('diff', '--cached', '--name-only', '-z', capture=True).stdout:
        raise ValueError('Archive worktree must have an empty staging index before publication')

    def save(paths, message):
        for offset in range(0, len(paths), 100):
            git('add', '--', *paths[offset:offset + 100])
        changed = git('diff', '--cached', '--quiet', check=False).returncode
        if changed == 0:
            return
        if changed != 1:
            raise RuntimeError('Could not inspect staged archive changes')
        git('commit', '-m', message)
        for attempt in range(3):
            result = git('push', 'origin', f'HEAD:refs/heads/{branch}', check=False)
            if result.returncode == 0:
                return
            if attempt < 2:
                sleep(2 ** (attempt + 1))
        raise RuntimeError('Archive push failed after three attempts; see Git output')

    report_path = root / 'archive/report.json'
    readme_path = root / 'archive/README.md'
    final_report, final_readme = report_path.read_bytes(), readme_path.read_bytes()
    read_json(report_path)  # Validate a possibly chunked final report before publication.
    report = {'complete': False, 'publication_in_progress': True,
              'errors': [{'source': 'publication', 'error': 'Publication has not finished; see the Actions run.'}]}
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    readme_path.write_text('# Archive publication in progress\n\n'
                          'This branch is incomplete until the final publication commit. '
                          'Check the Actions run for its status.\n', encoding='utf-8')
    save(['archive/report.json', 'archive/README.md'], 'Mark archive publication in progress')

    changed = git('ls-files', '--others', '--modified', '--deleted',
                  '--exclude-standard', '-z', '--', 'archive', capture=True).stdout
    paths = sorted(set(os.fsdecode(p) for p in changed.split(b'\0') if p))
    batch, weight = [], 0
    for relative in paths:
        if relative in ('archive/report.json', 'archive/README.md', 'archive/checksums.json'):
            continue
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root / 'archive'):
            raise ValueError('Archive contains an unsafe path')
        size = path.stat().st_size if path.exists() else 0
        if size > 40 * 1024 * 1024:
            raise ValueError('Unexpected oversized archive file; export must split large files')
        if batch and weight + size > batch_bytes:
            save(batch, 'Save repository archive files')
            batch, weight = [], 0
        batch.append(relative)
        weight += size
    if batch:
        save(batch, 'Save repository archive files')
    report_path.write_bytes(final_report)
    readme_path.write_bytes(final_readme)
    save(['archive/report.json', 'archive/README.md', 'archive/checksums.json'],
         'Finalize verified repository archive')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    args = parser.parse_args()
    publish(args.root)
