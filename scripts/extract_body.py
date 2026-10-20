#!/usr/bin/env python3
"""Extract one pinned MIR body using bounded scans and exact byte slices.

Only selected objects are decoded; the large inputs are never loaded or hashed
in full. Offsets are zero-based, with an exclusive end. JSON keys in the input
schemas use their literal ASCII spelling (as emitted by the extractors).

Pass --out from output_paths.py prepare: OUTPUT_ROOT/<body-slug>/work/.
prepare archives prior contents before extraction; this script does not archive.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

CHUNK = 1024 * 1024
DECODER = json.JSONDecoder()
STRUCTURAL = re.compile(rb'[{}"\\]')
STAGE = 'mir_drops_elaborated_and_const_checked'


def decode(raw):
    text = raw.decode('utf-8')
    value, end = DECODER.raw_decode(text.lstrip())
    if text.lstrip()[end:].strip():
        raise ValueError('Trailing data after JSON object')
    return value


def key_offsets(path, key):
    needle = json.dumps(key).encode()
    with path.open('rb') as stream:
        tail = b''
        offset = 0
        while chunk := stream.read(CHUNK):
            data = tail + chunk
            base = offset - len(tail)
            pos = 0
            while True:
                pos = data.find(needle, pos)
                if pos < 0:
                    break
                yield base + pos, base + pos + len(needle)
                pos += len(needle)
            offset += len(chunk)
            tail = data[-(len(needle) - 1):]


def value_after(stream, offset):
    """Read just a key's value, including values spanning chunk boundaries."""
    stream.seek(offset)
    data = b''
    while chunk := stream.read(4096):
        data += chunk
        prefix = data.lstrip()
        if prefix and not prefix.startswith(b':'):
            return None
        value = prefix[1:].lstrip()
        try:
            return DECODER.raw_decode(value.decode('utf-8'))[0]
        except (ValueError, UnicodeDecodeError):
            continue
    raise ValueError('Incomplete JSON value')


def object_start(stream, offset):
    """Walk backward from a key outside strings to its enclosing opening brace."""
    depth = 0
    in_string = False
    end = offset
    while end:
        start = max(0, end - CHUNK)
        stream.seek(start)
        data = stream.read(end - start)
        for match in reversed(list(STRUCTURAL.finditer(data))):
            pos = match.start()
            token = data[pos]
            if token == 34:
                # Count backslashes even when the escape crosses a read boundary.
                p = pos - 1
                while p >= 0 and data[p] == 92:
                    p -= 1
                count = pos - p - 1
                absolute = start + p
                while p < 0 and absolute >= 0:
                    stream.seek(absolute)
                    if stream.read(1) != b'\\':
                        break
                    count += 1
                    absolute -= 1
                if count % 2 == 0:
                    in_string = not in_string
            elif not in_string:
                if token == 125:
                    depth += 1
                elif token == 123:
                    if depth == 0:
                        return start + pos
                    depth -= 1
        end = start
    raise ValueError('No enclosing object found')


def object_slice(stream, start):
    stream.seek(start)
    depth = 0
    in_string = False
    escaped = False
    chunks = []
    while data := stream.read(CHUNK):
        previous = -1
        for match in STRUCTURAL.finditer(data):
            pos = match.start()
            token = data[pos]
            if escaped:
                escaped = False
                if pos == previous + 1:
                    previous = pos
                    continue
            if in_string:
                if token == 92:
                    escaped = True
                elif token == 34:
                    in_string = False
            elif token == 34:
                in_string = True
            elif token == 123:
                depth += 1
            elif token == 125:
                depth -= 1
                if depth == 0:
                    chunks.append(data[:pos + 1])
                    return b''.join(chunks)
            previous = pos
        if previous != len(data) - 1:
            escaped = False
        chunks.append(data)
    raise ValueError('Unterminated JSON object')


def find_objects(path, key, wanted, definition=False):
    seen = set()
    with path.open('rb') as stream:
        for key_start, key_end in key_offsets(path, key):
            if value_after(stream, key_end) != wanted:
                continue
            start = object_start(stream, key_start)
            if definition and key == 'canonical_path':
                start = object_start(stream, start)
            if start in seen:
                continue
            seen.add(start)
            raw = object_slice(stream, start)
            obj = decode(raw)
            if definition:
                actual = obj.get('identity', {}).get(key) if key == 'canonical_path' else obj.get(key)
                if actual == wanted and 'representations' in obj and 'source' in obj:
                    yield obj, raw, start
            elif isinstance(obj, dict) and obj.get(key) == wanted:
                yield obj, raw, start


def unique(items, label):
    result = None
    count = 0
    for item in items:
        result = item
        count += 1
    if count != 1:
        raise ValueError(f'{label}: expected exactly one match, found {count}')
    return result


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def slice_pin(path, raw, offset):
    return {'path': str(path), 'size_bytes': path.stat().st_size,
            'hash_scope': 'slice',
            'slice': {'offset_bytes': offset, 'size_bytes': len(raw),
                      'sha256': digest(raw)}}


def workspace_commit(workspace):
    """Read local HEAD/ref metadata without invoking git or touching the repo."""
    marker = next((p / '.git' for p in (workspace, *workspace.parents)
                   if (p / '.git').exists()), None)
    if marker is None:
        raise ValueError('SOURCE_WORKSPACE has no local .git metadata')
    gitdir = marker
    if marker.is_file():
        pointer = marker.read_text().strip()
        if not pointer.startswith('gitdir: '):
            raise ValueError('Invalid .git pointer')
        gitdir = (marker.parent / pointer[8:]).resolve(strict=True)
    common = gitdir
    if (gitdir / 'commondir').is_file():
        common = (gitdir / (gitdir / 'commondir').read_text().strip()).resolve(strict=True)
    value = (gitdir / 'HEAD').read_text().strip()
    seen = set()
    while value.startswith('ref: '):
        ref = value[5:]
        if ref in seen or not ref.startswith('refs/') or '..' in Path(ref).parts:
            raise ValueError('Invalid or cyclic HEAD reference')
        seen.add(ref)
        loose = next((base / ref for base in (gitdir, common) if (base / ref).is_file()), None)
        if loose:
            value = loose.read_text().strip()
            continue
        packed = common / 'packed-refs'
        matches = [line.split()[0] for line in packed.read_text().splitlines()
                   if len(line.split()) == 2 and line.split()[1] == ref] if packed.is_file() else []
        if len(matches) != 1:
            raise ValueError(f'Cannot resolve local HEAD reference: {ref}')
        value = matches[0]
    if not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', value):
        raise ValueError('Invalid local HEAD object id')
    return value.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument('--resolved-row', help='resolver item JSON file path or inline JSON object')
    selector.add_argument('--definition-row', help='JSON file path or inline JSON object')
    selector.add_argument('--def-path-hash')
    selector.add_argument('--canonical-path')
    for name in ('definitions', 'mir-bodies', 'workspace', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    definitions = args.definitions.resolve(strict=True)
    mir = args.mir_bodies.resolve(strict=True)
    workspace = args.workspace.resolve(strict=True)
    out = args.out.resolve()
    inputs = {}
    resolved = None
    supplied = args.resolved_row or args.definition_row
    if supplied:
        if supplied.lstrip().startswith('{'):
            row_raw = supplied.encode('utf-8')
            inputs['definition_row'] = {'kind': 'inline', 'size_bytes': len(row_raw),
                                        'sha256': digest(row_raw)}
        else:
            row_path = Path(supplied).resolve(strict=True)
            row_raw = row_path.read_bytes()
            inputs['definition_row'] = {'path': str(row_path),
                                        'size_bytes': len(row_raw), 'sha256': digest(row_raw)}
        selected_payload = decode(row_raw)
        if args.resolved_row:
            resolved = selected_payload
            if resolved.get('status') != 'resolved' or not isinstance(resolved.get('definition_row'), dict):
                raise ValueError('--resolved-row requires one resolved resolver item')
            row = resolved['definition_row']
        else:
            row = selected_payload
    else:
        key = 'def_path_hash' if args.def_path_hash else 'canonical_path'
        wanted = args.def_path_hash or args.canonical_path
        row, row_raw, offset = unique(find_objects(definitions, key, wanted, definition=True), 'definition')
        inputs['definition_row'] = slice_pin(definitions, row_raw, offset)
    if row.get('representations', {}).get('mir', {}).get('body_available') is not True:
        raise ValueError('representations.mir.body_available must be true')

    # Decode only the leading meta.commit value, never the potentially large meta.
    with definitions.open('rb') as stream:
        prefix = stream.read(CHUNK)
        match = re.search(rb'"meta"\s*:\s*\{\s*"commit"', prefix)
        if not match:
            raise ValueError('Expected meta.commit at the beginning of definitions')
        commit = value_after(stream, match.end())
    head = workspace_commit(workspace)
    if not commit or head != commit:
        raise ValueError(f'Commit mismatch: definitions={commit}, workspace={head}')
    inputs['definitions'] = {'path': str(definitions), 'size_bytes': definitions.stat().st_size}
    # Pin only consumed metadata/records, not an unconsumed multi-GB container.
    inputs['definitions']['hash_scope'] = 'slice'
    inputs['definitions']['meta_commit'] = {'value': commit, 'sha256': digest(commit.encode('utf-8'))}
    if 'slice' not in inputs['definition_row']:
        selected, selected_raw, selected_offset = unique(
            find_objects(definitions, 'def_path_hash', row['def_path_hash'], definition=True), 'definition pin')
        if selected != row:
            raise ValueError('Provided definition row differs from definitions record')
        inputs['selected_definition'] = slice_pin(definitions, selected_raw, selected_offset)
    from mir_cache import load_cached, load_cached_locator
    cached = load_cached(mir, row, (out.parent.parent if out.name == 'work' else out.parent) / '_inputs' / 'mir-cache')
    body, raw, offset = cached or unique(
        (item for item in find_objects(mir, 'owner_def_path_hash', row['def_path_hash'])
         if 'basic_blocks' in item[0]
         and item[0].get('capture_stage') == STAGE and item[0].get('body_id') == 'main'),
        'MIR body')
    inputs['mir_cache'] = {'hit': cached is not None,
                           'manifest': str((out.parent.parent if out.name == 'work' else out.parent) / '_inputs/mir-cache/manifest.json')}
    if body.get('canonical_path') != row.get('canonical_path', row.get('identity', {}).get('canonical_path')):
        raise ValueError('Body canonical_path does not match definition')
    if not isinstance(body.get('basic_blocks'), list) or not body['basic_blocks']:
        raise ValueError('basic_blocks must be a nonempty list')
    shell_artifact = None
    locators = (resolved or {}).get('async_shell_preludes', [])
    if locators:
        if len(locators) != 1:
            raise ValueError('async-shell requires exactly one shell locator')
        locator = locators[0]
        if row.get('ownership', {}).get('parent_def_path_hash') != locator.get('def_path_hash'):
            raise ValueError('inner definition parent does not match shell locator')
        expected_inner_path = str(locator.get('canonical_path', '')) + '::{closure#0}'
        if body.get('canonical_path') != expected_inner_path:
            raise ValueError('inner canonical_path does not extend shell canonical_path')
        shell_definition, _, _ = unique(find_objects(
            definitions, 'def_path_hash', locator['def_path_hash'], definition=True),
            'shell definition')
        shell_canonical = shell_definition.get('canonical_path', shell_definition.get('identity', {}).get('canonical_path'))
        if shell_canonical != locator.get('canonical_path'):
            raise ValueError('shell locator differs from definitions record')
        shell_cached = load_cached_locator(
            mir, locator, (out.parent.parent if out.name == 'work' else out.parent) / '_inputs' / 'mir-cache')
        shell_body, shell_raw, shell_offset = shell_cached or unique(
            (item for item in find_objects(mir, 'owner_def_path_hash', locator['def_path_hash'])
             if 'basic_blocks' in item[0] and item[0].get('capture_stage') == STAGE
             and item[0].get('body_id') == 'main'), 'shell MIR body')
        expected_key = locator.get('body_key') or {}
        actual_key = {key: shell_body.get(key) for key in
                      ('owner_def_path_hash', 'capture_stage', 'body_id')}
        if (shell_body.get('canonical_path') != locator.get('canonical_path')
                or actual_key != expected_key
                or shell_offset != locator.get('mir_offset_bytes')):
            raise ValueError('shell MIR slice does not match resolver locator')
        shell_artifact = (shell_body, shell_raw, shell_offset, locator)
    inputs['mir_bodies'] = slice_pin(mir, raw, offset)
    source = (workspace / row['source']['file']).resolve(strict=True)
    if not source.is_relative_to(workspace):
        raise ValueError('source.file escapes SOURCE_WORKSPACE')
    source_raw = source.read_bytes()
    inputs['source'] = {'path': str(source), 'size_bytes': len(source_raw),
                        'sha256': digest(source_raw)}
    pins = {'definition_row': row, 'definition_row_raw': row_raw.decode('utf-8'),
            'body_key': {key: body[key] for key in
                         ('owner_def_path_hash', 'capture_stage', 'body_id')},
            'commit': commit, 'workspace': str(workspace), 'inputs': inputs,
            'function_body_line_range': row['source'].get('span', row['source'])}
    if shell_artifact:
        shell_body, shell_raw, shell_offset, locator = shell_artifact
        pins['async_shell_prelude'] = {
            'path': 'async-shell-prelude.raw-body.json',
            'sha256': digest(shell_raw),
            'def_path_hash': locator['def_path_hash']}
        inputs['async_shell_prelude'] = slice_pin(mir, shell_raw, shell_offset)
    # Resolve every destination before writing, rejecting symlinks outside OUT
    # and outputs that would overwrite an input.
    destinations = [out / 'raw-body.json', out / 'raw-body.slice-sha256.txt',
                    out / 'input-pins.json', out / 'source' / source.name]
    if shell_artifact:
        destinations.append(out / pins['async_shell_prelude']['path'])
    protected = {definitions, mir, source}
    if supplied and not supplied.lstrip().startswith('{'):
        protected.add(row_path)
    for dest in destinations:
        resolved = dest.resolve()
        if not resolved.is_relative_to(out) or resolved in protected:
            raise ValueError(f'Unsafe output destination: {dest}')
    (out / 'source').mkdir(parents=True, exist_ok=True)
    destinations[0].write_bytes(raw)
    destinations[1].write_text(f'{digest(raw)}  {len(raw)}\n', encoding='utf-8')
    destinations[2].write_text(json.dumps(pins, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    destinations[3].write_bytes(source_raw)
    if shell_artifact:
        destinations[4].write_bytes(shell_artifact[1])
    result = {'out': str(out), 'basic_blocks': len(body['basic_blocks']),
              'slice_sha256': digest(raw), 'slice_size_bytes': len(raw)}
    if shell_artifact:
        result['shell_slice_sha256'] = digest(shell_artifact[1])
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        sys.exit(1)
