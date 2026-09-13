#!/usr/bin/env python3
"""Archive GitHub conversations and uploaded media. Python 3.10+, no dependencies."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

API = 'https://api.github.com'
BLOCK_SIZE = 1024 * 1024
PART_SIZE = 40 * BLOCK_SIZE  # GitHub's regular Git object limit is 100 MiB.
URL_RE = re.compile(r'https://[^\s<>"\x27`]+')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _hash_stream(source)


def _hash_stream(source):
    result = hashlib.sha256()
    for block in iter(lambda: source.read(BLOCK_SIZE), b''):
        result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def safe_child(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError('Archive path escapes its destination')
    return path


def trusted_download(url):
    value = urlsplit(url)
    host = value.hostname or ''
    if value.scheme != 'https' or value.username or value.password or value.port not in (None, 443):
        return False
    return (host in {'github.com', 'api.github.com', 'codeload.github.com', 'github-cloud.s3.amazonaws.com'}
            or host.endswith('.githubusercontent.com')
            or bool(re.fullmatch(r'github-production-[a-z0-9-]+\.s3\.amazonaws\.com', host)))


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        newurl = urljoin(req.full_url, newurl)
        if not trusted_download(newurl):
            raise ValueError('Refusing a redirect outside GitHub file storage')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urlsplit(newurl).netloc != urlsplit(req.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


class GitHub:
    def __init__(self, token=None, opener=None, sleep=time.sleep):
        self.token = token
        self.opener = opener or build_opener(SafeRedirect())
        self.sleep = sleep
        self.requests = 0

    def open(self, url, binary=False):
        if not trusted_download(url):
            raise ValueError('Refusing an untrusted download URL')
        parsed = urlsplit(url)
        # Source-archive endpoints redirect to a binary but require the JSON
        # media type at the API. octet-stream is specific to release assets.
        asset_api = parsed.hostname == 'api.github.com' and '/releases/assets/' in parsed.path
        accept = 'application/vnd.github+json'
        if binary:
            if asset_api:
                accept = 'application/octet-stream'
            elif parsed.hostname != 'api.github.com':
                accept = '*/*'
        headers = {'User-Agent': 'repository-dump/1.0',
                   'Accept': accept,
                   'X-GitHub-Api-Version': '2022-11-28'}
        if self.token and parsed.hostname == 'api.github.com':
            headers['Authorization'] = 'Bearer ' + self.token
        for attempt in range(4):
            try:
                self.requests += 1
                return self.opener.open(Request(url, headers=headers), timeout=60)
            except HTTPError as error:
                retryable = error.code in (429, 500, 502, 503, 504) or (error.code == 403 and error.headers.get('Retry-After'))
                if not retryable or attempt == 3:
                    raise RuntimeError(f'GitHub returned HTTP {error.code}; check access and rate limits') from None
                delay = error.headers.get('Retry-After', str(2 ** attempt))
                try:
                    delay = float(delay)
                except ValueError:
                    delay = 2 ** attempt
                if delay > 60:
                    raise RuntimeError('GitHub requested a long rate-limit wait; rerun later') from None
                self.sleep(max(0, delay))
            except (URLError, TimeoutError):
                if attempt == 3:
                    raise RuntimeError('Network request failed after four attempts') from None
                self.sleep(2 ** attempt)

    def one(self, path):
        with self.open(API + path) as response:
            return json.load(response)

    def pages(self, path):
        url = API + path + ('&' if '?' in path else '?') + 'per_page=100'
        seen = set()
        result = []
        while url:
            if url in seen or urlsplit(url).netloc != 'api.github.com':
                raise RuntimeError('Invalid GitHub pagination link')
            seen.add(url)
            with self.open(url) as response:
                page = json.load(response)
                if not isinstance(page, list):
                    raise RuntimeError('GitHub returned an unexpected list response')
                result.extend(page)
                link = response.headers.get('Link', '')
            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
            url = match.group(1) if match else None
        return result


def uploaded_urls(text):
    """GitHub uploads in Markdown, HTML, bare video URLs, and reference links."""
    found = set()
    for match in URL_RE.finditer(html.unescape(text or '')):
        url = match.group().rstrip('.,;:!?')
        # Markdown closing parentheses are not part of a bare GitHub upload URL.
        while url.endswith(')') and url.count(')') > url.count('('):
            url = url[:-1]
        url = url.rstrip(']')
        try:
            parsed = urlsplit(url)
            if not trusted_download(url):
                continue
        except ValueError:
            continue
        host = parsed.hostname or ''
        uuid = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
        is_upload = ((host == 'github.com' and
                      (re.fullmatch(r'/user-attachments/assets/' + uuid, parsed.path) or
                       re.match(r'^/user-attachments/files/[0-9]+/[^/]+', parsed.path) or
                       re.match(r'^/[^/]+/[^/]+/files/[0-9]+/[^/]+', parsed.path) or
                       re.fullmatch(r'/[^/]+/[^/]+/assets/[0-9]+/' + uuid, parsed.path)))
                     or host in {'user-images.githubusercontent.com', 'private-user-images.githubusercontent.com', 'secured-user-images.githubusercontent.com'}
                     or host.startswith('github-production-user-asset-'))
        if is_upload and trusted_download(url):
            found.add(urlunsplit(parsed._replace(fragment='')))
    return sorted(found)


def text_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {'body', 'description'} and isinstance(child, str):
                yield child
            elif isinstance(child, (dict, list)):
                yield from text_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from text_fields(child)


class Archive:
    def __init__(self, github, repository, output, workers=4):
        if (not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repository)
                or repository.split('/')[-1] in {'.', '..'}):
            raise ValueError('Repository must be owner/name')
        self.github, self.repository, self.output = github, repository, Path(output)
        self.workers = workers
        self.prefix = '/repos/' + repository
        self.output.mkdir(parents=True, exist_ok=True)
        if any(path.is_symlink() for path in self.output.rglob('*')):
            raise ValueError('Archive output contains symlinks; use a dedicated directory without symlinks')
        self.media = {}
        previous = self.output / 'assets.json'
        self.previous = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else {}
        self.report = {'repository': repository, 'started_at': timestamp(), 'complete': False,
                       'errors': [], 'counts': {}, 'scope': 'Current accessible GitHub API records, including open and closed issues and PRs, reviews, release assets, and GitHub-hosted uploads. Deleted records and historical edits are not exposed by these APIs.'}

    def cached(self, record):
        try:
            return bool(record.get('parts')) and all(
                (path := safe_child(self.output, part['path'])).is_file()
                and path.stat().st_size == part['bytes'] and digest(path) == part['sha256']
                for part in record['parts'])
        except (OSError, ValueError, KeyError):
            return False

    def download(self, url, name=None, expected_size=None, version=None):
        if url in self.media:
            return
        previous = self.previous.get(url, {})
        if previous.get('status') == 'saved' and previous.get('version') == version and self.cached(previous) and (expected_size is None or previous.get('bytes') == expected_size):
            self.media[url] = previous
            return
        record = {'source': url, 'status': 'failed', 'parts': [], 'version': version}
        temporary = self.output / 'assets' / (hashlib.sha256(url.encode()).hexdigest() + '.download')
        temporary.parent.mkdir(parents=True, exist_ok=True)
        try:
            total = 0
            full_hash = hashlib.sha256()
            with self.github.open(url, binary=True) as response:
                content_type = response.headers.get('Content-Type', 'application/octet-stream').split(';')[0]
                if (content_type == 'text/html' and expected_size is None
                        and 'attachment' not in response.headers.get('Content-Disposition', '').lower()
                        and not urlsplit(url).path.lower().endswith(('.html', '.htm'))):
                    raise ValueError('Expected an uploaded file, received an HTML page')
                with temporary.open('wb') as target:
                    while block := response.read(BLOCK_SIZE):
                        target.write(block)
                        full_hash.update(block)
                        total += len(block)
                declared = response.headers.get('Content-Length')
                if declared is not None and total != int(declared):
                    raise ValueError('Download is truncated (Content-Length mismatch)')
                if expected_size is not None and total != expected_size:
                    raise ValueError('Download size differs from release metadata')
                disposition = response.headers.get('Content-Disposition', '')
            remote_name = name or (re.search(r'filename="?([^";]+)', disposition).group(1) if re.search(r'filename="?([^";]+)', disposition) else Path(urlsplit(url).path).name)
            if not Path(remote_name).suffix:
                remote_name += mimetypes.guess_extension(content_type) or '.bin'
            extension = Path(remote_name).suffix.lower()
            if not re.fullmatch(r'\.[a-z0-9]{1,10}', extension):
                extension = mimetypes.guess_extension(content_type) or '.bin'
            extension = {'.jpe': '.jpg', '.jpeg': '.jpg'}.get(extension, extension)
            stem = full_hash.hexdigest()
            if total <= PART_SIZE:
                destination = temporary.parent / (stem + extension)
                temporary.replace(destination)
                record['parts'] = [{'path': destination.relative_to(self.output).as_posix(), 'bytes': total, 'sha256': stem}]
            else:
                with temporary.open('rb') as source:
                    part_number = 0
                    while part := source.read(PART_SIZE):
                        part_number += 1
                        destination = temporary.parent / f'{stem}{extension}.part{part_number:04d}'
                        destination.write_bytes(part)
                        record['parts'].append({'path': destination.relative_to(self.output).as_posix(), 'bytes': len(part), 'sha256': hashlib.sha256(part).hexdigest()})
                temporary.unlink()
            record.update(status='saved', name=remote_name, bytes=total, sha256=stem, content_type=content_type)
        except Exception as error:
            temporary.unlink(missing_ok=True)
            record['error'] = str(error)
            self.report['errors'].append({'source': url, 'error': str(error)})
        self.media[url] = record

    def localize(self, body):
        body = body or ''
        for url in sorted(self.media, key=len, reverse=True):
            asset = self.media[url]
            if asset['status'] == 'saved' and len(asset['parts']) == 1:
                body = body.replace(url, '../../' + asset['parts'][0]['path'])
        return body

    def conversation(self, kind, number, item, comments, reviews=(), inline=()):
        directory = self.output / kind / str(number)
        write_json(directory / 'record.json', item)
        write_json(directory / 'comments.json', comments)
        sections = [f'# {item.get("title", "")}\n',
                    f'Original: {item.get("html_url", "")}  \nState: {item.get("state", "")}  \nCreated: {item.get("created_at", "")}\n', self.localize(item.get('body'))]
        for heading, records in [('Comments', comments), ('Reviews', reviews), ('Inline review comments', inline)]:
            if records:
                sections.append('\n## ' + heading + '\n')
            for record in records:
                author = (record.get('user') or {}).get('login', '[deleted user]')
                date = record.get('created_at') or record.get('submitted_at') or ''
                sections.extend([f'\n### {author} — {date}\n', self.localize(record.get('body'))])
                if record.get('path'):
                    sections.append(f'\nFile: `{record["path"]}`; line: {record.get("line")}; reply to: {record.get("in_reply_to_id", "none")}\n')
                if record.get('diff_hunk'):
                    sections.append('\n````diff\n' + record['diff_hunk'] + '\n````\n')
        (directory / 'README.md').write_text('\n\n'.join(sections) + '\n', encoding='utf-8')

    def run(self):
        write_json(self.output / 'report.json', self.report)
        try:
            self.collect()
        except Exception as error:
            self.report['errors'].append({'source': 'API collection', 'error': str(error)})
        self.report['finished_at'] = timestamp()
        self.report['api_requests_this_run'] = self.github.requests
        self.report['counts']['saved_assets'] = sum(item['status'] == 'saved' for item in self.media.values())
        self.report['counts']['failed_assets'] = sum(item['status'] != 'saved' for item in self.media.values())
        self.report['complete'] = not self.report['errors']
        write_json(self.output / 'assets.json', self.media)
        write_json(self.output / 'report.json', self.report)
        self.index()
        files = {p.relative_to(self.output).as_posix(): digest(p) for p in sorted(self.output.rglob('*')) if p.is_file() and p.name != 'checksums.json'}
        write_json(self.output / 'checksums.json', files)
        return self.report

    def collect(self):
        metadata = self.github.one(self.prefix)
        write_json(self.output / 'repository.json', metadata)
        print('Reading all issue and PR pages...', flush=True)
        all_issues = self.github.pages(self.prefix + '/issues?state=all&sort=created&direction=asc')
        comments = self.github.pages(self.prefix + '/issues/comments?sort=created&direction=asc')
        pulls = self.github.pages(self.prefix + '/pulls?state=all&sort=created&direction=asc')
        releases = self.github.pages(self.prefix + '/releases')
        tags = self.github.pages(self.prefix + '/tags')
        tag_versions = {tag['name']: tag['commit']['sha'] for tag in tags}
        write_json(self.output / 'tags.json', tags)
        write_json(self.output / 'issue-index.json', all_issues)
        write_json(self.output / 'issue-comments.json', comments)
        grouped = {}
        for comment in comments:
            grouped.setdefault(int(comment['issue_url'].rsplit('/', 1)[-1]), []).append(comment)
        issues = [item for item in all_issues if 'pull_request' not in item]
        pull_details = []
        for pull in pulls:
            number = pull['number']
            print(f'Reading PR #{number} reviews...', flush=True)
            detail = self.github.one(self.prefix + f'/pulls/{number}')
            reviews = self.github.pages(self.prefix + f'/pulls/{number}/reviews')
            inline = self.github.pages(self.prefix + f'/pulls/{number}/comments')
            commits = self.github.pages(self.prefix + f'/pulls/{number}/commits')
            files = self.github.pages(self.prefix + f'/pulls/{number}/files')
            directory = self.output / 'pulls' / str(number)
            for filename, data in [('reviews', reviews), ('review-comments', inline), ('commits', commits), ('files', files)]:
                write_json(directory / (filename + '.json'), data)
            pull_details.append((detail, reviews, inline))
        self.report['counts'].update(issues=len(issues), pull_requests=len(pulls), issue_comments=len(comments),
                                     reviews=sum(len(x[1]) for x in pull_details), review_comments=sum(len(x[2]) for x in pull_details), releases=len(releases), tags=len(tags))
        # Tuples in pull_details deliberately unpack: all review bodies must be scanned.
        sources = [all_issues, comments, releases] + [list(parts) for parts in pull_details]
        uploads = sorted({url for value in sources for body in text_fields(value) for url in uploaded_urls(body)})
        print(f'Downloading {len(uploads)} unique uploaded files...', flush=True)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            pending = [pool.submit(self.download, url) for url in uploads]
            for index, future in enumerate(as_completed(pending), 1):
                future.result()
                print(f'Upload {index}/{len(uploads)}', flush=True)
                # Each completed record is immutable; snapshot the map before serialization.
                write_json(self.output / 'assets.json', dict(self.media))
        for release in releases:
            assets = self.github.pages(self.prefix + f'/releases/{release["id"]}/assets')
            release['assets'] = assets
            directory = self.output / 'releases' / str(release['id'])
            write_json(directory / 'record.json', release)
            for asset in assets:
                self.download(asset['url'], name=asset['name'], expected_size=asset['size'], version=asset.get('digest') or asset.get('updated_at'))
            source_archives = []
            for field, extension in [('zipball_url', '.zip'), ('tarball_url', '.tar.gz')]:
                if release.get(field):
                    archive_name = release['tag_name'] + extension
                    # A moved tag must not silently reuse its old source archive.
                    self.download(release[field], name=archive_name, version=tag_versions.get(release['tag_name'], self.report['started_at']))
                    source_archives.append({'url': release[field], 'name': archive_name})
            sections = [f'# {release.get("name") or release["tag_name"]}',
                        'Tag: `' + release['tag_name'] + '`', self.localize(release.get('body')), '\n## Release assets\n']
            for asset in assets + source_archives:
                saved = self.media[asset['url']]
                for part in saved['parts']:
                    sections.append(f'- [{asset["name"]}](../../{part["path"]})')
                if saved['status'] != 'saved':
                    sections.append(f'- {asset["name"]}: DOWNLOAD FAILED (see report.json)')
            (directory / 'README.md').write_text('\n\n'.join(sections) + '\n', encoding='utf-8')
        for issue in issues:
            self.conversation('issues', issue['number'], issue, grouped.get(issue['number'], []))
        for detail, reviews, inline in pull_details:
            self.conversation('pulls', detail['number'], detail, grouped.get(detail['number'], []), reviews, inline)

    def index(self):
        status = 'COMPLETE' if self.report['complete'] else 'INCOMPLETE — inspect report.json'
        lines = [f'# Archive of {self.repository}', f'**Status: {status}**',
                 f'Last run: {self.report["finished_at"]}', self.report['scope'],
                 '\n[Export report](report.json) · [Asset manifest](assets.json) · [Checksums](checksums.json)\n',
                 '| Record type | Count |', '| --- | ---: |']
        lines.extend(f'| {key.replace("_", " ")} | {value} |' for key, value in self.report['counts'].items())
        for kind in ('issues', 'pulls', 'releases'):
            lines.append('\n## ' + kind.title() + '\n')
            for record in sorted((self.output / kind).glob('*/record.json'), key=lambda p: int(p.parent.name)):
                item = json.loads(record.read_text(encoding='utf-8'))
                title = (item.get('title') or item.get('name') or item.get('tag_name') or record.parent.name).replace('\n', ' ').replace('[', '\\[').replace(']', '\\]')
                lines.append(f'- [{record.parent.name}: {title}]({kind}/{record.parent.name}/README.md)')
        if self.report['errors']:
            lines += ['\n## Missing data\n', 'Some data could not be preserved. This is **not a complete export**. See [report.json](report.json) for each failure; rerunning retries failed assets.']
        lines += ['\n## Large files\n', 'Files over 40 MiB are saved as numbered parts to fit GitHub limits. The asset manifest preserves the original byte size and SHA-256. Reconstruct with `python tools/repository_dump.py --restore ARCHIVE_DIRECTORY --destination RESTORED_DIRECTORY`. No archive content is executed.',
                  '\nOlder exported records are retained on reruns; the current counts reflect the current API snapshot. GitHub does not offer a transactionally consistent snapshot while contributors are editing.']
        (self.output / 'README.md').write_text('\n\n'.join(lines) + '\n', encoding='utf-8')


def verify(root):
    root = Path(root)
    checksums = json.loads((root / 'checksums.json').read_text(encoding='utf-8'))
    errors = []
    for relative, expected in checksums.items():
        try:
            path = safe_child(root, relative)
            if not path.is_file() or digest(path) != expected:
                errors.append(relative)
        except (ValueError, OSError):
            errors.append(relative)
    return errors


def restore(root, destination):
    root, destination = Path(root), Path(destination)
    failures = verify(root)
    if failures:
        raise ValueError('Archive verification failed; do not restore corrupted files')
    destination.mkdir(parents=True, exist_ok=True)
    assets = json.loads((root / 'assets.json').read_text(encoding='utf-8'))
    for record in assets.values():
        if record['status'] != 'saved':
            continue
        # Digest prefix prevents collisions and untrusted filenames never become paths.
        filename = re.sub(r'[^A-Za-z0-9._-]', '_', record['name'])[:150] or 'asset'
        target = safe_child(destination, record['sha256'][:16] + '-' + filename)
        with target.open('wb') as output:
            for part in record['parts']:
                with safe_child(root, part['path']).open('rb') as source:
                    for block in iter(lambda: source.read(BLOCK_SIZE), b''):
                        output.write(block)
        if digest(target) != record['sha256']:
            target.unlink()
            raise ValueError('Restored asset checksum mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', help='GitHub owner/repository to export')
    parser.add_argument('--output', default='repository-dump')
    parser.add_argument('--verify', metavar='ARCHIVE')
    parser.add_argument('--restore', metavar='ARCHIVE')
    parser.add_argument('--destination', default='restored-assets')
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=4, help='Concurrent upload downloads (1-8, default 4)')
    args = parser.parse_args()
    if args.verify:
        failures = verify(args.verify)
        print(json.dumps({'verified': not failures, 'failed_files': failures}))
        return 1 if failures else 0
    if args.restore:
        restore(args.restore, args.destination)
        print('Assets restored and checksums verified.')
        return 0
    if not args.repo:
        parser.error('--repo is required for an export')
    report = Archive(GitHub(os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')), args.repo, args.output, args.workers).run()
    print(json.dumps(report, indent=2))
    return 0 if report['complete'] else 2


if __name__ == '__main__':
    sys.exit(main())
