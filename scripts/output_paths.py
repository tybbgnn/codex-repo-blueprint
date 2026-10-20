#!/usr/bin/env python3
"""Manage per-body outputs using only the standard library (POSIX flock).

resolve creates the body directory; prepare moves old contents into work/.archive
and records running; publish builds the offline deliverable; record updates the index. resolve/prepare --dry-run write
nothing. record --dry-run explicitly writes a dry-run entry, never a passed one.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from extract_body import decode, find_objects, unique

SITE = 'deliverable/roundtrip/index.html'
JSON_FILES = ('renderer-input.json', 'reading-summaries.json', 'basic-block-details.json')


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def body_identity(row):
    if row.get('representations', {}).get('mir', {}).get('body_available') is not True:
        raise ValueError('representations.mir.body_available must be true')
    canonical = row.get('identity', {}).get('canonical_path')
    body_hash = row.get('def_path_hash')
    if not isinstance(canonical, str) or not canonical.strip():
        raise ValueError('identity.canonical_path must be nonempty')
    if not isinstance(body_hash, str) or not re.fullmatch(r'[0-9a-fA-F]{8,}', body_hash):
        raise ValueError('def_path_hash must contain at least 8 hex characters')
    # Preserve closure ordinal and generic/impl words, but no path separators,
    # braces, shell metacharacters, dots, or platform-reserved punctuation.
    readable = re.sub(r'[^A-Za-z0-9_-]', '', canonical.replace('::', '__'))
    readable = readable.strip('_-') or 'body'
    readable = readable[:180].rstrip('_-')
    return canonical, body_hash.lower(), readable + '__' + body_hash[:8].lower()


def select_row(args):
    if args.definition_row:
        value = args.definition_row
        row = decode(value.encode() if value.lstrip().startswith('{')
                     else Path(value).expanduser().read_bytes())
        if args.definitions:
            selected, _, _ = unique(find_objects(args.definitions, 'def_path_hash',
                                                 row['def_path_hash'], definition=True), 'definition')
            if selected != row:
                raise ValueError('Provided definition row differs from definitions record')
        return row
    if not args.definitions:
        raise ValueError('--definitions is required with a hash or canonical-path selector')
    key = 'def_path_hash' if args.def_path_hash else 'canonical_path'
    row, _, _ = unique(find_objects(args.definitions, key,
                                    args.def_path_hash or args.canonical_path,
                                    definition=True), 'definition')
    return row


def output_root(value):
    if not value or not value.strip():
        raise ValueError('OUTPUT_ROOT is required in the initial request (no default); finish failed if missing')
    return Path(value).expanduser().resolve()


def safe_child(path, directory=False):
    if path.is_symlink():
        raise ValueError(f'Refusing symlink management path: {path}')
    if path.exists() and (not path.is_dir() if directory else not path.is_file()):
        raise ValueError(f'Unexpected management path type: {path}')


@contextmanager
def locked(root):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.output-paths.lock'
    safe_child(lock)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def read_index(root):
    path = root / 'index.json'
    safe_child(path)
    if not path.exists():
        return {'version': 2, 'bodies': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') not in (1, 2) or not isinstance(data.get('bodies'), dict):
        raise ValueError('Unsupported index.json schema; refusing to overwrite it')
    for key, entry in data['bodies'].items():
        if not isinstance(entry, dict) or entry.get('def_path_hash') != key or not entry.get('slug'):
            raise ValueError('Invalid body entry in index.json')
    return data


def atomic_index(root, index):
    # The caller holds the stable root lock across read/modify/replace.
    safe_child(root / 'index.json')
    index['version'] = 2 if all('deliverable_path' in e for e in index['bodies'].values()) else 1
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                                     prefix='.index-', suffix='.tmp', delete=False) as stream:
        json.dump(index, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
        temp = stream.name
    if (root / 'index.json').exists():
        history = root / '.index-history'
        history.mkdir(exist_ok=True)
        import shutil
        shutil.copy2(root / 'index.json', history / (utc_now().replace(':', '') + '.json'))
    os.replace(temp, root / 'index.json')


def check_identity(index, canonical, body_hash, slug):
    for key, entry in index['bodies'].items():
        if key == body_hash and (entry['slug'] != slug or entry.get('canonical_path') != canonical):
            raise ValueError('Body identity changed for existing def_path_hash')
        if entry['slug'].casefold() == slug.casefold() and key != body_hash:
            raise ValueError('Slug collision: different bodies share the 8-hex prefix; refusing overwrite')


def make_entry(canonical, body_hash, slug, status, stage, summary):
    return {'slug': slug, 'canonical_path': canonical, 'def_path_hash': body_hash,
            'last_run': utc_now(), 'status': status, 'stage': stage,
            'acceptance_summary': summary, 'site_path': SITE,
            'deliverable_path': 'deliverable', 'entry_html': 'roundtrip/index.html',
            'work_path': 'work'}


def manage(root, row, command, *, dry_run=False, status=None, stage=None,
           summary=None, protected=()):
    root = output_root(str(root))
    canonical, body_hash, slug = body_identity(row)
    out = root / slug
    safe_child(out, directory=True)
    safe_child(out / 'work', directory=True)
    safe_child(out / 'deliverable', directory=True)
    safe_child(out / 'work' / '.archive', directory=True)
    for source in protected:
        if Path(source).resolve().is_relative_to(out):
            raise ValueError('Input lies inside body output; move the input before preparing a rerun')
    if command == 'record' and (not stage or not status):
        raise ValueError('record requires --status and --stage')
    if command == 'record' and summary is None:
        raise ValueError('record requires --acceptance-summary or --acceptance-file')
    result = {'slug': slug, 'out': str(out), 'index': str(root / 'index.json'),
              'site': str(out / SITE), 'work': str(out / 'work'),
              'deliverable': str(out / 'deliverable'), 'dry_run': dry_run}
    if dry_run and command != 'record':
        # No mkdir, lockfile, archive or index write in inspection mode.
        check_identity(read_index(root), canonical, body_hash, slug)
        return result
    with locked(root):
        index = read_index(root)
        check_identity(index, canonical, body_hash, slug)
        safe_child(out, directory=True)
        safe_child(out / 'work', directory=True)
        safe_child(out / 'deliverable', directory=True)
        safe_child(out / 'work' / '.archive', directory=True)
        if command == 'resolve':
            out.mkdir(exist_ok=True)
            return result
        if command == 'record':
            if dry_run:
                status = 'dry-run'
                existing = index['bodies'].get(body_hash)
                if existing and existing['status'] != 'dry-run':
                    raise ValueError('Dry-run cannot replace an actual run entry; use resolve --dry-run')
            elif not out.is_dir():
                raise ValueError('Body output directory is missing; run prepare first')
            if status == 'passed':
                required = (*JSON_FILES, 'data.js', 'README.md', 'roundtrip/index.html', 'roundtrip/style.css', 'roundtrip/app.bundle.js')
                if any(not (out / 'deliverable' / name).is_file() for name in required):
                    raise ValueError('Cannot record passed: published site is missing required files')
            index['bodies'][body_hash] = make_entry(canonical, body_hash, slug, status, stage, summary)
            atomic_index(root, index)
            result['entry'] = index['bodies'][body_hash]
            return result
        out.mkdir(exist_ok=True)
        entry = make_entry(canonical, body_hash, slug, 'running', 'prepare', None)
        index['bodies'][body_hash] = entry
        atomic_index(root, index)
        try:
            work = out / 'work'
            work.mkdir(exist_ok=True)
            contents = [p for p in out.iterdir() if p.name not in ('work', 'deliverable')]
            contents += [p for p in work.iterdir() if p.name != '.archive']
            delivery = out / 'deliverable'
            if delivery.exists() and any(delivery.iterdir()):
                contents.append(delivery)
            if contents:
                archive = work / '.archive' / utc_now().replace(':', '').replace('-', '')
                archive.mkdir(parents=True, exist_ok=False)
                result['archive'] = str(archive)
                for path in contents:
                    relative = Path('work') / path.name if path.parent == work else Path(path.name)
                    target = archive / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    path.rename(target)
            delivery.mkdir(exist_ok=True)
            (out / 'REPORT.md').write_text('# Body report\n\nStatus: running; stage: stage0.\n', encoding='utf-8')
            entry.update(stage='stage0', last_run=utc_now())
            atomic_index(root, index)
        except (OSError, ValueError) as exc:
            entry.update(status='failed', stage='prepare', last_run=utc_now(),
                         acceptance_summary={'error': str(exc), 'archive': result.get('archive')})
            atomic_index(root, index)
            raise
        result['entry'] = entry
        return result



def archive_paths(paths, directory):
    """Preserve selected generated artifacts during a stage/cache refresh."""
    directory = Path(directory).resolve()
    paths = [Path(p) for p in paths if Path(p).exists()]
    if not paths:
        return None
    for path in paths:
        if not path.resolve().is_relative_to(directory) or '.archive' in path.relative_to(directory).parts:
            raise ValueError('Archive path must be a live artifact under directory')
    archive = directory / '.archive' / utc_now().replace(':', '').replace('-', '')
    archive.mkdir(parents=True, exist_ok=False)
    for path in paths:
        relative = path.relative_to(directory)
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        path.rename(target)
    return archive

def publish(root, body, candidate, **kwargs):
    from publish_site import publish as publish_site
    return publish_site(root, body, candidate, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('resolve', 'prepare', 'record', 'publish'):
        sub = commands.add_parser(command)
        sub.add_argument('--output-root', default=os.environ.get('OUTPUT_ROOT'),
                         help='User-provided root; otherwise OUTPUT_ROOT env (no default path)')
        sub.add_argument('--definitions', type=Path)
        selector = sub.add_mutually_exclusive_group(required=True)
        selector.add_argument('--definition-row', help='JSON file or inline row; same as extract_body.py')
        selector.add_argument('--def-path-hash')
        selector.add_argument('--canonical-path')
        sub.add_argument('--dry-run', action='store_true')
        if command == 'publish':
            sub.add_argument('--candidate', type=Path, required=True, help='Renderer candidate under body/work')
        if command == 'record':
            sub.add_argument('--status', required=True, choices=('running', 'passed', 'failed', 'dry-run'))
            sub.add_argument('--stage', required=True, help='Stage reached, e.g. stage6, stage8 or resolve')
            summary = sub.add_mutually_exclusive_group(required=True)
            summary.add_argument('--acceptance-summary', help='Concise text; no inferred acceptance')
            summary.add_argument('--acceptance-file', type=Path, help='JSON acceptance summary')
    args = parser.parse_args()
    root = output_root(args.output_root)
    row = select_row(args)
    summary = getattr(args, 'acceptance_summary', None)
    acceptance = getattr(args, 'acceptance_file', None)
    if acceptance:
        summary = json.loads(acceptance.read_text(encoding='utf-8'))
    protected = [p for p in (args.definitions, acceptance) if p]
    if args.definition_row and not args.definition_row.lstrip().startswith('{'):
        protected.append(Path(args.definition_row).expanduser())
    status = getattr(args, 'status', None)
    if args.command == 'publish':
        out = root / body_identity(row)[2]
        print(json.dumps(publish(root, out, args.candidate, dry_run=args.dry_run), indent=2))
        return
    result = manage(root, row, args.command, dry_run=args.dry_run or status == 'dry-run',
                    status=status, stage=getattr(args, 'stage', None), summary=summary,
                    protected=protected if args.command == 'prepare' else ())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        sys.exit(1)
