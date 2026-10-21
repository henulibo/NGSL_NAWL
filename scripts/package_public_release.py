"""Validate and package the public source, including snapshots without Git."""
import argparse
import ipaddress
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'public-release' / 'ielts-source.zip'
ROOT_FILES = {
    '.dockerignore', '.editorconfig', '.env.example', '.gitattributes', '.gitignore',
    'Dockerfile', 'Makefile', 'README.md', 'LICENSE', 'NOTICE', 'compose.yaml',
    'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'CHANGELOG.md',
    'pyproject.toml',
}
PUBLIC_DATA = {
    'study-data.json', 'lookup-data.json', 'learner-definitions.json',
    'ngsl-official.csv', 'nawl-stats.csv', 'supplementary.csv', 'ecdict-license.txt',
}
PUBLIC_DOCS = {
    'docs/deployment/README.md', 'docs/public-release.md', 'docs/data.md',
}
SOURCE_DIRS = {
    'server': {'.py', '.txt'}, 'tests': {'.py', '.js', '.json'},
    'vocab-data': {'.py', '.js', '.html'}, 'deploy': {'.sh'}, 'scripts': {'.py'},
}
LOCAL_ONLY = {
    'cambridge-senses.json', 'core-senses.json', 'senses-extra.json',
    'examples-extra.json', 'examples-data.json', 'NGSL_NAWL_10天学习词表.html',
}
REQUIRED = ROOT_FILES | PUBLIC_DOCS | {'vocab-data/' + name for name in PUBLIC_DATA} | {
    'scripts/package_public_release.py', 'vocab-data/build.py',
    'vocab-data/public_corpus.py', 'vocab-data/learner.py',
    'vocab-data/page-template.html', 'vocab-data/entry.js', 'vocab-data/lookup.js',
    'vocab-data/speech.js', 'server/build_web.py', 'server/app.py', 'server/db.py',
    'server/manage.py', 'server/security.py', 'server/__init__.py',
    'server/requirements.txt', 'server/requirements-dev.txt', 'deploy/Caddyfile',
    '.github/workflows/ci.yml',
}
CHECKS = {
    'private-key marker': re.compile(rb'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----'),
    'provider token': re.compile(
        rb'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}'
        rb'|sk-[A-Za-z0-9_-]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16}'
        rb'|AIza[A-Za-z0-9_-]{35}|xox[baprs]-[A-Za-z0-9-]{10,})\b'),
    'authenticated URL': re.compile(
        rb'(?:https?|postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?)://[^\s/<>"\x27:]+:[^\s/<>"\x27]+@'),
    'personal home path': re.compile(rb'(?:/Users/|/home/)[A-Za-z0-9_.-]+/'),
    'email address': re.compile(rb'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    'JWT': re.compile(rb'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b'),
}
IPV4 = re.compile(rb'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
ASSIGNMENT = re.compile(
    rb'''(?i)(?:["']?\b(?:password|passwd|api_key|api_secret|access_token|client_secret)["']?)\s*[:=]\s*["'][^"'\r\n]{8,}["']''')


def allowed(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or path.name in LOCAL_ONLY:
        return False
    if name in ROOT_FILES | PUBLIC_DOCS or name == 'deploy/Caddyfile':
        return True
    if len(path.parts) == 2:
        folder = path.parts[0]
        if folder == 'vocab-data' and path.name in PUBLIC_DATA:
            return True
        if folder in SOURCE_DIRS:
            return path.suffix in SOURCE_DIRS[folder]
        if folder == '.github':
            return path.suffix in {'.yml', '.yaml', '.md'}
    if len(path.parts) == 3:
        if path.parts[:2] == ('server', 'static'):
            return path.suffix in {'.js', '.html', '.css'}
        if path.parts[:2] in {('.github', 'workflows'), ('.github', 'ISSUE_TEMPLATE')}:
            return path.suffix in {'.yml', '.yaml', '.md'}
    return False


def candidates(root=ROOT):
    """Read an explicit public file set; do not traverse private directories."""
    root = Path(root)
    paths = [root / name for name in ROOT_FILES]
    for folder in [*SOURCE_DIRS, 'docs', '.github']:
        directory = root / folder
        if directory.is_symlink():
            raise ValueError(f'Symbolic link in public path: {folder}')
        if directory.exists():
            paths.extend(directory.rglob('*'))
    files = []
    for path in sorted(set(paths)):
        name = path.relative_to(root).as_posix()
        if not allowed(name):
            continue
        if path.is_symlink() or any((root / parent).is_symlink()
                                   for parent in path.relative_to(root).parents
                                   if parent != Path('.')):
            raise ValueError(f'Symbolic link in public path: {name}')
        if path.is_file():
            files.append((name, path.read_bytes(), bool(path.stat().st_mode & 0o111)))
    missing = REQUIRED - {name for name, _, _ in files}
    if missing:
        raise ValueError('Missing release files: ' + ', '.join(sorted(missing)))
    return files


def tracked_violations(root=ROOT):
    """Also reject accidentally tracked private/generated files when Git exists."""
    root = Path(root)
    if not (root / '.git').exists() or not shutil.which('git'):
        return []
    result = subprocess.run(['git', 'ls-files', '--cached', '-z'], cwd=root,
                            check=True, stdout=subprocess.PIPE)
    return sorted(name for raw in result.stdout.split(b'\0') if raw
                  and not allowed(name := raw.decode('utf-8')))


def findings(name, data):
    hits = [label for label, pattern in CHECKS.items() if pattern.search(data)]
    for match in IPV4.finditer(data):
        try:
            address = ipaddress.ip_address(match.group().decode('ascii'))
        except ValueError:
            continue
        if address.is_global:
            hits.append('public IPv4 address')
            break
    # Tests intentionally contain fixed credentials for temporary accounts;
    # dictionary data can contain the vocabulary word "password".
    if name.startswith(('server/', 'deploy/', 'scripts/')) and ASSIGNMENT.search(data):
        hits.append('possible hardcoded credential')
    return hits


def write_archive(files, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data, executable in files:
                info = ZipInfo('ielts-source/' + name, date_time=(2026, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100755 if executable else 0o100644) << 16
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
    except Exception:
        output.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='validate without creating a ZIP')
    args = parser.parse_args(argv)
    if not args.check:
        OUTPUT.unlink(missing_ok=True)
    try:
        files = candidates()
        blocked = [(name, findings(name, data)) for name, data, _ in files]
        failures = [(name, hits) for name, hits in blocked if hits]
        failures += [(name, ['tracked file outside public allowlist']) for name in tracked_violations()]
        if failures:
            for name, hits in failures:
                print(f'BLOCKED {name}: {", ".join(hits)}', file=sys.stderr)
            return 1
        if args.check:
            print(f'Public release checks passed ({len(files)} files). Git history is not scanned.')
        else:
            write_archive(files, OUTPUT)
            print(f'Created {OUTPUT.relative_to(ROOT)} ({len(files)} files, no Git history).')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'BLOCKED: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
