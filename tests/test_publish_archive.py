import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publisher', Path(__file__).resolve().parents[1] / 'tools/publish_archive.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublicationTests(unittest.TestCase):
    def test_batched_publication_retries_and_only_final_commit_claims_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remote, work = root / 'remote.git', root / 'work'

            def git(*args, cwd=root):
                return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.DEVNULL).decode().strip()

            git('init', '--bare', str(remote))
            git('init', str(work))
            git('config', 'user.name', 'Archive test', cwd=work)
            git('config', 'user.email', 'test@example.invalid', cwd=work)
            git('config', 'commit.gpgsign', 'false', cwd=work)
            git('remote', 'add', 'origin', str(remote), cwd=work)
            archive = work / 'archive'
            archive.mkdir()
            (archive / 'report.json').write_text(json.dumps({'complete': True}))
            (archive / 'README.md').write_text('# Complete archive\n')
            (archive / 'checksums.json').write_text('{}')
            for n in range(3):
                (archive / f'file{n}').write_bytes(b'123456')
            real_run = subprocess.run
            rejected = []

            def flaky_push(args, **kwargs):
                if 'push' in args and len(rejected) < 2:
                    rejected.append(args)
                    return subprocess.CompletedProcess(args, 1)
                return real_run(args, **kwargs)

            with patch.object(publisher.subprocess, 'run', side_effect=flaky_push):
                publisher.publish(work, batch_bytes=8, sleep=lambda seconds: None)
            self.assertEqual(len(rejected), 2)
            commits = git('rev-list', '--reverse', 'repository-archive', cwd=remote).splitlines()
            self.assertGreaterEqual(len(commits), 5)
            for commit in commits[:-1]:
                report = json.loads(git('show', commit + ':archive/report.json', cwd=remote))
                self.assertFalse(report['complete'])
            final = json.loads(git('show', 'repository-archive:archive/report.json', cwd=remote))
            self.assertTrue(final['complete'])
            self.assertEqual(git('show', 'repository-archive:archive/file2', cwd=remote), '123456')
            (archive / 'file0').unlink()
            publisher.publish(work, batch_bytes=8, sleep=lambda seconds: None)
            self.assertNotIn('archive/file0', git('ls-tree', '-r', '--name-only', 'repository-archive', cwd=remote))


if __name__ == '__main__':
    unittest.main()
