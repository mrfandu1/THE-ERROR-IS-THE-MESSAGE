import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request
from urllib.error import HTTPError

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'repository_dump.py'
spec = importlib.util.spec_from_file_location('repository_dump', MODULE)
dump = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dump)


class Response(io.BytesIO):
    def __init__(self, data, headers=None):
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.headers = headers or {}


class Opener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FixtureAPI:
    def __init__(self):
        self.requests = 0
        self.upload = 'https://github.com/user-attachments/assets/image-id'
        self.review_upload = 'https://github.com/user-attachments/files/11/review.json'
        self.release_url = 'https://api.github.com/repos/example/repo/releases/assets/33'
        self.binary_calls = []
        self.comment = {'id': 1, 'issue_url': 'https://api.github.com/repos/example/repo/issues/7',
                        'body': f'![photo]({self.upload})', 'user': {'login': 'commenter'}}
        self.records = {
            '/issues': [{'number': 7, 'title': 'Closed issue', 'state': 'closed', 'body': 'Original text'},
                        {'number': 8, 'title': 'PR', 'pull_request': {}, 'body': ''}],
            '/issues/comments': [self.comment, {'id': 2, 'issue_url': 'https://api.github.com/repos/example/repo/issues/8', 'body': 'PR conversation'}],
            '/pulls': [{'number': 8}],
            '/pulls/8/reviews': [{'id': 10, 'body': 'Review body', 'state': 'APPROVED'}],
            '/pulls/8/comments': [{'id': 11, 'body': f'[json]({self.review_upload})', 'in_reply_to_id': 9, 'path': 'src/a.py', 'line': 4, 'diff_hunk': '@@ -1 +1 @@'}],
            '/pulls/8/commits': [{'sha': 'abc'}],
            '/pulls/8/files': [{'filename': 'src/a.py', 'patch': '-old\n+new'}],
            '/releases': [{'id': 9, 'name': 'v1', 'tag_name': 'v1', 'body': 'Release notes'}],
            '/releases/9/assets': [{'id': 33, 'url': self.release_url, 'name': '../../binary.dat', 'size': 6}],
            '/tags': [{'name': 'v1', 'commit': {'sha': 'abc'}}],
        }

    def one(self, path):
        self.requests += 1
        if path.endswith('/pulls/8'):
            return {'number': 8, 'title': 'Merged PR', 'state': 'closed', 'merged': True, 'body': 'PR body'}
        return {'full_name': 'example/repo'}

    def pages(self, path):
        self.requests += 1
        return self.records[path.split('?')[0].removeprefix('/repos/example/repo')]

    def open(self, url, binary=False):
        self.requests += 1
        self.binary_calls.append(url)
        if url == self.release_url:
            return Response(b'abcdef', {'Content-Type': 'application/octet-stream'})
        if url == self.review_upload:
            return Response(b'{"ok": true}', {'Content-Type': 'application/json'})
        return Response(b'image bytes', {'Content-Type': 'image/png'})


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'archive'

    def test_complete_archive_preserves_closed_records_comments_reviews_tags_assets(self):
        api = FixtureAPI()
        archive = dump.Archive(api, 'example/repo', self.root)
        report = archive.run()
        self.assertTrue(report['complete'], report)
        self.assertEqual(report['counts'], {'issues': 1, 'pull_requests': 1, 'issue_comments': 2,
                                         'reviews': 1, 'review_comments': 1, 'releases': 1, 'tags': 1,
                                         'saved_assets': 3, 'failed_assets': 0})
        self.assertEqual(json.loads((self.root / 'issues/7/record.json').read_text())['body'], 'Original text')
        pr = (self.root / 'pulls/8/README.md').read_text(encoding='utf-8')
        self.assertIn('PR conversation', pr)
        self.assertIn('Review body', pr)
        self.assertIn('reply to: 9', pr)
        self.assertIn('../../assets/', pr)
        self.assertTrue(json.loads((self.root / 'pulls/8/record.json').read_text())['merged'])
        self.assertEqual(dump.verify(self.root), [])

    def test_rerun_reuses_only_verified_downloads(self):
        api = FixtureAPI()
        dump.Archive(api, 'example/repo', self.root).run()
        api.binary_calls.clear()
        second = dump.Archive(api, 'example/repo', self.root)
        self.assertTrue(second.run()['complete'])
        self.assertEqual(api.binary_calls, [])
        part = second.media[api.upload]['parts'][0]
        (self.root / part['path']).write_bytes(b'corrupt')
        third = dump.Archive(api, 'example/repo', self.root)
        self.assertTrue(third.run()['complete'])
        self.assertEqual(api.binary_calls, [api.upload])
        self.assertEqual(dump.verify(self.root), [])

    def test_missing_file_is_not_a_success_and_is_retried(self):
        api = FixtureAPI()
        original = api.open
        def fail(url, binary=False):
            if url == api.upload:
                raise RuntimeError('file removed')
            return original(url, binary)
        api.open = fail
        report = dump.Archive(api, 'example/repo', self.root).run()
        self.assertFalse(report['complete'])
        self.assertEqual(report['counts']['failed_assets'], 1)
        self.assertIn('INCOMPLETE', (self.root / 'README.md').read_text(encoding='utf-8'))
        api.open = original
        self.assertTrue(dump.Archive(api, 'example/repo', self.root).run()['complete'])

    def test_api_failure_marks_existing_archive_incomplete(self):
        api = FixtureAPI()
        dump.Archive(api, 'example/repo', self.root).run()
        api.pages = lambda path: (_ for _ in ()).throw(RuntimeError('no API access'))
        report = dump.Archive(api, 'example/repo', self.root).run()
        self.assertFalse(report['complete'])
        self.assertIn('no API access', report['errors'][0]['error'])

    def test_large_file_parts_restore_exact_bytes_and_safe_filenames(self):
        api = FixtureAPI()
        with patch.object(dump, 'PART_SIZE', 4):
            report = dump.Archive(api, 'example/repo', self.root).run()
        self.assertTrue(report['complete'])
        assets = json.loads((self.root / 'assets.json').read_text())
        self.assertEqual(len(assets[api.release_url]['parts']), 2)
        restored = Path(self.temporary.name) / 'restored'
        dump.restore(self.root, restored)
        self.assertIn(b'abcdef', [path.read_bytes() for path in restored.iterdir()])
        self.assertFalse((Path(self.temporary.name) / 'binary.dat').exists())

    def test_tampering_is_detected_before_restore(self):
        dump.Archive(FixtureAPI(), 'example/repo', self.root).run()
        (self.root / 'issues/7/comments.json').write_text('[]')
        self.assertEqual(dump.verify(self.root), ['issues/7/comments.json'])
        with self.assertRaisesRegex(ValueError, 'verification failed'):
            dump.restore(self.root, Path(self.temporary.name) / 'restored')

    def test_malicious_checksum_path_cannot_escape_archive(self):
        self.root.mkdir()
        dump.write_json(self.root / 'checksums.json', {'../outside': 'abc'})
        self.assertEqual(dump.verify(self.root), ['../outside'])

    def test_truncated_release_asset_is_reported(self):
        api = FixtureAPI()
        api.records['/releases/9/assets'][0]['size'] = 99
        report = dump.Archive(api, 'example/repo', self.root).run()
        self.assertFalse(report['complete'])
        self.assertIn('size differs', report['errors'][0]['error'])

    def test_json_upload_is_preserved_as_a_file(self):
        api = FixtureAPI()
        archive = dump.Archive(api, 'example/repo', self.root)
        archive.download(api.review_upload)
        self.assertEqual(archive.media[api.review_upload]['status'], 'saved')

    def test_upload_link_forms_and_external_url_exclusion(self):
        a = 'https://github.com/user-attachments/assets/a'
        b = 'https://github.com/user-attachments/files/12/file.pdf'
        c = 'https://user-images.githubusercontent.com/1/image.png'
        d = 'https://github.com/owner/repo/files/22/file.zip'
        body = f'![a]({a}) <img src="{b}">\n{c}\n[old]({d})\n{a}\nhttps://example.com/private'
        self.assertEqual(dump.uploaded_urls(body), sorted([a, b, c, d]))


class HTTPTests(unittest.TestCase):
    def test_paginates_even_when_page_contains_fewer_than_100_items(self):
        opener = Opener([Response([{'id': 1}], {'Link': '<https://api.github.com/repos/a/b/issues?page=2>; rel="next"'}),
                         Response([{'id': 2}])])
        result = dump.GitHub(opener=opener).pages('/repos/a/b/issues?state=all')
        self.assertEqual(result, [{'id': 1}, {'id': 2}])
        self.assertEqual(len(opener.requests), 2)
        self.assertIn('state=all&per_page=100', opener.requests[0].full_url)

    def test_pagination_loop_fails_instead_of_hanging(self):
        url = 'https://api.github.com/repos/a/b/issues?per_page=100'
        opener = Opener([Response([], {'Link': '<' + url + '>; rel="next"'})])
        with self.assertRaisesRegex(RuntimeError, 'pagination'):
            dump.GitHub(opener=opener).pages('/repos/a/b/issues')

    def test_authentication_only_goes_to_github_api_or_web_origin(self):
        opener = Opener([Response(b'x'), Response(b'x')])
        api = dump.GitHub('test-token', opener)
        api.open('https://api.github.com/repos/a/b').close()
        api.open('https://user-images.githubusercontent.com/file').close()
        self.assertEqual(opener.requests[0].get_header('Authorization'), 'Bearer test-token')
        self.assertIsNone(opener.requests[1].get_header('Authorization'))

    def test_redirect_drops_auth_and_rejects_arbitrary_hosts(self):
        redirect = dump.SafeRedirect()
        request = Request('https://github.com/user-attachments/assets/a', headers={'Authorization': 'Bearer test-token'})
        target = redirect.redirect_request(request, None, 302, '', {}, 'https://private-user-images.githubusercontent.com/a')
        self.assertIsNone(target.get_header('Authorization'))
        for url in ['https://example.com/a', 'http://github.com/a', 'https://127.0.0.1/a', 'https://github.com.evil.test/a', 'https://github.com:8080/a']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                redirect.redirect_request(request, None, 302, '', {}, url)

    def test_transient_rate_limit_retries_with_requested_delay(self):
        error = HTTPError('https://api.github.com', 429, 'rate limit', {'Retry-After': '3'}, None)
        opener = Opener([error, Response({'ok': True})])
        delays = []
        result = dump.GitHub(opener=opener, sleep=delays.append).one('/repos/a/b')
        self.assertTrue(result['ok'])
        self.assertEqual(delays, [3])

    def test_repository_argument_cannot_inject_paths_or_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            for repo in ['a/b/../../c', 'a/b?token=x', 'a/b\nInjected', 'a b/c', '../a', 'a/..']:
                with self.subTest(repo=repo), self.assertRaises(ValueError):
                    dump.Archive(FixtureAPI(), repo, directory)


if __name__ == '__main__':
    unittest.main()
