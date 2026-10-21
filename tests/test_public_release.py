"""A source release must exclude private data and be usable without Git."""
import contextlib
import io
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
release = runpy.run_path(str(ROOT / 'scripts/package_public_release.py'))


def fixture(root):
    for name in release['REQUIRED']:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('public fixture\n')


class PublicReleaseTests(unittest.TestCase):
    def test_snapshot_without_git_excludes_private_and_generated_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            extras = [
                '.env', '.git/config', 'private-release-notes/notes.md',
                'vocab-data/cambridge-senses.json', 'vocab-data/examples-data.json',
                'server/web/index.html', 'tests/node_modules/dependency/index.js',
                'backups/study.db',
            ]
            for name in extras:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('private fixture')
            names = {name for name, _, _ in release['candidates'](root)}
            self.assertEqual(names, release['REQUIRED'])
            self.assertTrue(names.isdisjoint(extras))

    def test_missing_required_file_and_public_symlink_block_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            (root / 'LICENSE').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing release files: LICENSE'):
                release['candidates'](root)
            (root / 'LICENSE').symlink_to(root / 'README.md')
            with self.assertRaisesRegex(ValueError, 'Symbolic link'):
                release['candidates'](root)

    def test_sensitive_values_are_detected_without_printing_them(self):
        samples = [
            (b'ghp_' + b'X' * 36, 'provider token'),
            (b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----', 'private-key marker'),
            (b'https://' + b'user:password' + b'@host.example/', 'authenticated URL'),
            (b'user' + b'@' + b'example.com', 'email address'),
            (b'/Users/' + b'person/file', 'personal home path'),
            (b'8.' + b'8.8.8', 'public IPv4 address'),
        ]
        for value, label in samples:
            self.assertIn(label, release['findings']('README.md', value))
        self.assertEqual(release['findings']('compose.yaml', b'http://127.0.0.1:8000'), [])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            token = samples[0][0]
            (root / 'README.md').write_bytes(token)
            globals_ = release['main'].__globals__
            with patch.dict(globals_, {
                'ROOT': root, 'candidates': lambda: release['candidates'](root),
                'tracked_violations': lambda: [],
            }), contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(release['main'](['--check']), 1)
            self.assertIn('README.md: provider token', stderr.getvalue())
            self.assertNotIn(token.decode(), stderr.getvalue())

    def test_git_tracking_cannot_bypass_public_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(release['tracked_violations'](root), [])
            (root / '.git').mkdir()
            globals_ = release['tracked_violations'].__globals__
            completed = subprocess.CompletedProcess([], 0, stdout=b'README.md\0.env\0')
            with patch.object(globals_['shutil'], 'which', return_value='git'), \
                    patch.object(globals_['subprocess'], 'run', return_value=completed):
                self.assertEqual(release['tracked_violations'](root), ['.env'])

    def test_archive_is_deterministic_and_preserves_only_public_permissions(self):
        files = [('README.md', b'public\n', False), ('deploy/backup.sh', b'#!/bin/sh\n', True)]
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / 'first.zip', Path(folder) / 'second.zip'
            release['write_archive'](files, first)
            release['write_archive'](files, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ['ielts-source/' + row[0] for row in files])
                self.assertEqual(archive.getinfo('ielts-source/deploy/backup.sh').external_attr >> 16,
                                 0o100755)
