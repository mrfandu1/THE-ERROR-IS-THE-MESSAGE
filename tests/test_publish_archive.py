import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import publish_archive as publisher
from tools import repository_dump as dump


class PublicationTests(unittest.TestCase):
    def repository(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        remote, work = root / 'remote.git', root / 'work'

        def git(*args, cwd=work):
            return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.DEVNULL).decode().strip()

        git('init', '--bare', str(remote), cwd=root)
        git('init', str(work), cwd=root)
        git('config', 'user.name', 'Archive test')
        git('config', 'user.email', 'test@example.invalid')
        git('config', 'commit.gpgsign', 'false')
        git('remote', 'add', 'origin', str(remote))
        return root, remote, work, git

    def minimal_archive(self, work):
        archive = work / 'archive'
        archive.mkdir()
        dump.write_json(archive / 'report.json', {'complete': True})
        dump.write_text(archive / 'README.md', '# Complete archive\n')
        dump.write_json(archive / 'checksums.json', {})
        return archive

    def test_workflow_orphan_sequence_publishes_only_archive_files(self):
        root, remote, source, git = self.repository()
        (source / 'source.py').write_text('print("source only")\n')
        (source / '.github').mkdir()
        (source / '.github/workflow.yml').write_text('name: source workflow\n')
        git('add', '--', 'source.py', '.github')
        git('commit', '-m', 'Source commit')
        work = root / 'archive-worktree'
        git('worktree', 'add', '--detach', str(work), 'HEAD')
        git('switch', '--orphan', 'archive-root', cwd=work)
        self.assertFalse((work / 'source.py').exists())
        self.assertEqual(git('ls-files', cwd=work), '')
        self.minimal_archive(work)
        # Exercise the standalone script/import path used by Actions as well.
        subprocess.run([sys.executable, str(Path(publisher.__file__)), str(work)], check=True)
        paths = git('ls-tree', '-r', '--name-only', 'repository-archive', cwd=remote).splitlines()
        self.assertTrue(paths)
        self.assertTrue(all(path.startswith('archive/') for path in paths), paths)
        self.assertTrue((source / 'source.py').is_file())

    def test_prestaged_source_is_rejected_before_any_publication(self):
        root, remote, work, git = self.repository()
        archive = self.minimal_archive(work)
        (work / 'source.py').write_text('source only')
        git('add', '--', 'source.py')
        before = (archive / 'report.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'empty staging index'):
            publisher.publish(work)
        self.assertEqual(git('for-each-ref', '--format=%(refname)', cwd=remote), '')
        self.assertEqual((archive / 'report.json').read_bytes(), before)

    def test_chunked_final_metadata_publishes_with_exact_bytes(self):
        root, remote, work, git = self.repository()
        git('config', 'core.autocrlf', 'true')
        archive = work / 'archive'
        archive.mkdir()
        expected_report = {'complete': True, 'notes': '\u0928\u092e\u0938\u094d\u0924\u0947' * 300}
        expected_readme = '# Complete archive\r\n\r\n' + 'Unicode \U0001f30d, CRLF preserved.\r\n' * 100
        with patch.object(dump, 'DOCUMENT_PART_SIZE', 512):
            dump.write_text(archive / '.gitattributes', '* -text\n')
            dump.write_json(archive / 'report.json', expected_report)
            dump.write_text(archive / 'README.md', expected_readme)
            dump.write_json(archive / 'assets.json', {})
            inventory = {p.relative_to(archive).as_posix(): dump.digest(p)
                         for p in archive.rglob('*') if p.is_file()}
            dump.write_json(archive / 'checksums.json', inventory)
            publisher.publish(work, batch_bytes=1024, sleep=lambda seconds: None)
        commits = git('rev-list', '--reverse', 'repository-archive', cwd=remote).splitlines()
        self.assertGreater(len(commits), 3)
        for commit in commits[:-1]:
            self.assertFalse(json.loads(git('show', commit + ':archive/report.json', cwd=remote))['complete'])
        cloned = root / 'cloned'
        git('clone', '--branch', 'repository-archive', '--config', 'core.autocrlf=true', str(remote), str(cloned), cwd=root)
        self.assertEqual(dump.read_json(cloned / 'archive/report.json'), expected_report)
        self.assertEqual(dump.read_document(cloned / 'archive/README.md'), expected_readme.encode())
        self.assertEqual(dump.verify(cloned / 'archive'), [])
        self.assertTrue(all(p.stat().st_size <= 512 for p in (cloned / 'archive').rglob('*') if p.is_file()))

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
