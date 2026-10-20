#!/usr/bin/env python3
"""Extract all resolved MIR slices with one bounded index scan.

Fingerprint is local file identity/stat plus sampled content, not a whole-file
content digest. Exact slice SHA256 and identity are also checked on cache reads.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from extract_body import STAGE, key_offsets, value_after, object_start, object_slice, decode, digest
from output_paths import body_identity, archive_paths


def file_fingerprint(path):
    path = Path(path).resolve(strict=True)
    st = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for offset in sorted({0, max(0, st.st_size // 2 - 32768), max(0, st.st_size - 65536)}):
            f.seek(offset); h.update(f.read(65536))
    return dict(path=str(path), size=st.st_size, mtime_ns=st.st_mtime_ns,
                ctime_ns=st.st_ctime_ns, device=st.st_dev, inode=st.st_ino,
                sample_sha256=h.hexdigest(), scope='stat-and-three-64KiB-samples')


def _load_entry(mir, owner, canonical, directory, expected_slug=None):
    """Load one exact cached body by independently checked identity."""
    try:
        manifest = json.loads((directory / 'manifest.json').read_text())
        version = manifest.get('version')
        if version not in (1, 2) or manifest['mir_fingerprint'] != file_fingerprint(mir):
            return None
        entry = manifest['bodies'][owner]
        if entry['canonical_path'] != canonical or (expected_slug and entry['slug'] != expected_slug):
            return None
        path = directory / (entry['cache_file'] if version == 2 else entry['slug'] + '.json')
        if path.is_symlink():
            return None
        raw = path.read_bytes()
        if digest(raw) != entry['sha256'] or len(raw) != entry['size_bytes']:
            return None
        body = decode(raw)
        if (body.get('owner_def_path_hash'), body.get('canonical_path'), body.get('capture_stage'), body.get('body_id')) != (owner, canonical, STAGE, 'main'):
            return None
        if not isinstance(body.get('basic_blocks'), list) or not body['basic_blocks']:
            return None
        return body, raw, entry['offset_bytes']
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_cached(mir, row, directory):
    """Invalid/missing cache is a miss; extractor performs its original full scan."""
    try:
        canonical, owner, slug = body_identity(row)
        return _load_entry(mir, owner, canonical, directory, slug)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_cached_locator(mir, locator, directory):
    try:
        return _load_entry(mir, locator['def_path_hash'], locator['canonical_path'], directory)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def pre_extract(report, mir, directory):
    start = time.perf_counter()
    before = file_fingerprint(mir)
    wanted = {}
    has_shells = any(row.get('async_shell_preludes')
                     for row in report['items'] if row.get('status') == 'resolved')
    for row in report['items']:
        if row['status'] == 'resolved':
            canonical, owner, slug = body_identity(row['definition_row'])
            wanted[owner] = dict(canonical_path=canonical, slug=slug)
            if has_shells:
                wanted[owner].update(cache_file=slug + '.json', role='primary')
            for locator in row.get('async_shell_preludes', []):
                shell_owner = locator['def_path_hash']
                candidate = dict(canonical_path=locator['canonical_path'], slug=shell_owner,
                                 cache_file='shell-' + shell_owner + '.json', role='shell')
                if shell_owner in wanted and wanted[shell_owner] != candidate:
                    raise ValueError('Conflicting MIR cache identity: ' + shell_owner)
                wanted[shell_owner] = candidate
    found, seen = {}, set()
    directory.mkdir(parents=True, exist_ok=True)
    # Verify the complete scan before publishing any cache slices.
    with mir.open('rb') as f:
        for begin, end in key_offsets(mir, 'owner_def_path_hash'):
            owner = value_after(f, end)
            if owner not in wanted:
                continue
            offset = object_start(f, begin)
            if offset in seen:
                continue
            seen.add(offset)
            raw = object_slice(f, offset); body = decode(raw)
            if body.get('capture_stage') != STAGE or body.get('body_id') != 'main' or 'basic_blocks' not in body:
                continue
            if owner in found:
                raise ValueError('Duplicate MIR body: ' + owner)
            if body.get('canonical_path') != wanted[owner]['canonical_path'] or not body['basic_blocks']:
                raise ValueError('Invalid MIR body: ' + owner)
            found[owner] = (raw, offset, len(body['basic_blocks']))
    if set(found) != set(wanted):
        raise ValueError('Missing MIR bodies: ' + str(sorted(set(wanted) - set(found))))
    if before != file_fingerprint(mir):
        raise ValueError('MIR changed during extraction')
    manifest = dict(version=2 if has_shells else 1, mir_fingerprint=before, bodies={})
    for owner, (raw, offset, count) in found.items():
        entry = dict(wanted[owner], sha256=digest(raw), size_bytes=len(raw), offset_bytes=offset, bb_count=count)
        path = directory / (entry['cache_file'] if has_shells else entry['slug'] + '.json')
        if path.exists() and path.read_bytes() != raw:
            # Preserve prior generated cache revisions; never unlink user files.
            archive_paths([path], directory)
        if not path.exists():
            path.write_bytes(raw)
        manifest['bodies'][owner] = entry
    manifest['wall_seconds'] = time.perf_counter() - start
    path = directory / 'manifest.json'
    if path.exists():
        archive_paths([path], directory)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bodies',type=Path,required=True);p.add_argument('--mir-bodies',type=Path,required=True)
    p.add_argument('--output-root',type=Path,default=os.environ.get('OUTPUT_ROOT'))
    a=p.parse_args()
    if a.output_root is None:p.error('OUTPUT_ROOT is required')
    result=pre_extract(json.loads(a.bodies.read_text()),a.mir_bodies,a.output_root/'_inputs/mir-cache')
    print(json.dumps(dict(bodies=len(result['bodies']),wall_seconds=result['wall_seconds'],mir_fingerprint=result['mir_fingerprint'])))

if __name__=='__main__':main()
