#!/usr/bin/env python3
"""Resolve single/batch Rust identifiers to verified executable MIR bodies.

Standard library only. Scan large files in bounded chunks, decode only selected
records, and never infer identity from display names, source links or old body
hints. Exit 2 means some items are unresolved; exit 1 is an input/I/O error.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys

from extract_body import (STAGE, decode, key_offsets, object_slice,
                          object_start, value_after)
from output_paths import body_identity, check_identity, locked, output_root, read_index, safe_child
import classify

HASH = re.compile(r'[0-9a-fA-F]{8,}')
ITEM_ID = r'[A-Za-z]+\d+'
ASYNC = re.compile(r'^Coroutine\(Desugared\(Async\s*[,)]')


def clean(value):
    return value.strip().strip('`').strip()


def identifier(value):
    if isinstance(value, str):
        value = clean(value)
        if value.startswith('{'):
            return identifier(json.loads(value))
        return {'def_path_hash' if HASH.fullmatch(value) else 'canonical_path': value}
    if not isinstance(value, dict):
        raise ValueError('Each input must be an identifier string or object')
    item = {k: value[k] for k in ('id', 'canonical_path', 'def_path_hash', 'topic_ids') if k in value}
    if 'identity' in value:
        item['canonical_path'] = value['identity'].get('canonical_path')
    if 'representations' in value:
        item['definition_row'] = value
    if not item.get('canonical_path') and not item.get('def_path_hash'):
        raise ValueError('Item requires canonical_path or def_path_hash')
    if item.get('def_path_hash'):
        item['def_path_hash'] = item['def_path_hash'].lower()
    return item


def parse_markdown(text):
    """Join identity columns by item id, preserving conflicts for resolution.

    Topic headings/tables link references to known item ids. Only named identity
    columns are selectors: a neighboring historical-body hint is never an input.
    """
    items = {}
    headers = None
    for line in text.splitlines():
        if not line.lstrip().startswith('|'):
            headers = None
            continue
        cells = [clean(x.replace(r'\|', '|')) for x in re.split(r'(?<!\\)\|', line.strip())[1:-1]]
        normalized = [re.sub(r'[\s`]', '', x).lower() for x in cells]
        normalized = [next((key for key in ('canonical_path', 'def_path_hash') if key in x), x) for x in normalized]
        if any(x in ('canonical_path', 'def_path_hash') for x in normalized):
            headers = normalized
            continue
        if not headers or len(cells) != len(headers) or all(re.fullmatch(r':?-+:?', x) for x in cells):
            continue
        row = dict(zip(headers, cells))
        item_id = row.get('id', row.get('item_id', cells[0]))
        if not re.fullmatch(ITEM_ID, item_id):
            continue
        item = items.setdefault(item_id, {'id': item_id, 'topic_ids': []})
        for key in ('canonical_path', 'def_path_hash'):
            if key not in row or row[key] in ('', '-', '—'):
                continue
            val = row[key].lower() if key == 'def_path_hash' else row[key]
            if key in item and item[key] != val:
                item.setdefault('input_errors', []).append(f'Conflicting {key}: {item[key]} / {val}')
            else:
                item[key] = val
    topics = {}
    active = None
    for line in text.splitlines():
        if line.startswith('#'):
            heading = re.match(r'^#{1,6}\s+(' + ITEM_ID + r')\b(.*)', line)
            active = heading.group(1) if heading and heading.group(1) not in items else None
            if active:
                topics.setdefault(active, {'id': active, 'title': heading.group(2).strip(' ·:-'), 'item_ids': []})
        refs = re.findall(r'\b' + ITEM_ID + r'\b', line)
        table_topic = refs[0] if line.lstrip().startswith('|') and refs and refs[0] not in items else None
        topic_id = table_topic or active
        if topic_id:
            known = [ref for ref in refs if ref in items]
            if known:
                topic = topics.setdefault(topic_id, {'id': topic_id, 'title': '', 'item_ids': []})
                topic['item_ids'] = sorted(set(topic['item_ids'] + known))
    for topic in topics.values():
        for item_id in topic['item_ids']:
            items[item_id]['topic_ids'].append(topic['id'])
    if not items:
        # Simple Markdown lists of exact canonical paths/hashes are also valid.
        for line in text.splitlines():
            match = re.match(r'^\s*(?:[-*+] |\d+[.)] )\s*`?([^`]+)`?\s*$', line)
            if match:
                value = clean(match.group(1))
                if HASH.fullmatch(value) or '::' in value:
                    item = identifier(value)
                    item['id'] = f'item-{len(items) + 1:03d}'
                    items[item['id']] = item
    return list(items.values()), sorted(topics.values(), key=lambda x: x['id'])


def read_input(value=None, list_file=None):
    topics = []
    if list_file:
        path = Path(list_file).expanduser()
        text = path.read_text(encoding='utf-8')
        if path.suffix.lower() in ('.md', '.markdown'):
            items, topics = parse_markdown(text)
        elif path.suffix.lower() == '.json':
            data = json.loads(text)
            if isinstance(data, dict) and 'items' in data:
                topics = data.get('topics', [])
                data = data['items']
            items = [identifier(x) for x in (data if isinstance(data, list) else [data])]
        else:
            items = [identifier(line) for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    else:
        items = [identifier(value)]
    if not items:
        raise ValueError('Input contains no identifiers')
    ids = set()
    for n, item in enumerate(items, 1):
        item.setdefault('id', f'item-{n:03d}')
        item.setdefault('topic_ids', [])
        if item['id'] in ids:
            raise ValueError(f'Duplicate item id: {item["id"]}')
        ids.add(item['id'])
    for topic in topics:
        for ref in topic.get('item_ids', []):
            if ref not in ids:
                raise ValueError(f'Unknown topic item reference: {ref}')
            item = next(x for x in items if x['id'] == ref)
            item['topic_ids'] = sorted(set(item['topic_ids'] + [topic['id']]))
    return items, topics


def scan_definitions(path, key, wanted):
    """Yield (row, offset) once per matching definition, not nested type refs."""
    if not wanted:
        return
    seen = set()
    with path.open('rb') as stream:
        for start, end in key_offsets(path, key):
            value = value_after(stream, end)
            normalized = value.lower() if key.endswith('hash') and isinstance(value, str) else value
            if not isinstance(normalized, str) or normalized not in wanted:
                continue
            offset = object_start(stream, start)
            if key in ('canonical_path', 'parent_def_path_hash'):
                offset = object_start(stream, offset)
            if offset in seen:
                continue
            row = decode(object_slice(stream, offset))
            if not isinstance(row, dict) or not all(k in row for k in ('identity', 'representations', 'source', 'def_path_hash')):
                continue
            actual = (row.get('identity', {}).get(key) if key == 'canonical_path' else
                      row.get('ownership', {}).get(key) if key == 'parent_def_path_hash' else row.get(key))
            if isinstance(actual, str) and (actual.lower() if key.endswith('hash') else actual) in wanted:
                seen.add(offset)
                yield row, offset


def select_definitions(path, items):
    by_hash, by_path = defaultdict(list), defaultdict(list)
    rows = {}
    for key in ('def_path_hash', 'canonical_path'):
        wanted = {x[key] for x in items if x.get(key)}
        for row, offset in scan_definitions(path, key, wanted):
            rows[offset] = row
    for row in rows.values():
        by_hash[row['def_path_hash'].lower()].append(row)
        by_path[row['identity']['canonical_path']].append(row)
    selected = []
    for item in items:
        result = dict(item, status='unresolved', stage='resolve')
        result.pop('definition_row', None)
        try:
            if item.get('input_errors'):
                raise ValueError('; '.join(item['input_errors']))
            matches = []
            for key, index in (('def_path_hash', by_hash), ('canonical_path', by_path)):
                if item.get(key):
                    found = index.get(item[key], [])
                    if len(found) != 1:
                        raise ValueError(f'{key}: expected one definition, found {len(found)}')
                    matches.append(found[0])
            if not matches:
                raise ValueError('Missing canonical_path and def_path_hash')
            if any(row != matches[0] for row in matches[1:]):
                raise ValueError('Inconsistent def_path_hash and canonical_path: identify different definitions')
            row = matches[0]
            if 'definition_row' in item and item['definition_row'] != row:
                raise ValueError('Provided definition row differs from definitions record')
            result.update(requested_def_path_hash=row['def_path_hash'],
                          requested_canonical_path=row['identity']['canonical_path'], _row=row)
        except ValueError as exc:
            result['reason'] = str(exc)
        selected.append(result)
    return selected


def thin_coroutine_wrapper(body):
    return classify.thin_coroutine_wrapper(body)


def map_async(path, results, mir=None):
    # Walk only through ownership intermediaries. Stop at executable children:
    # nested closures/functions are distinct bodies, not their parent's async body.
    roots = {r['_row']['def_path_hash'] for r in results if '_row' in r and r['_row'].get('detail', {}).get('is_async') is True}
    wrappers = {}
    if mir is not None:
        sync = {r['_row']['def_path_hash']: r['_row'] for r in results
                if '_row' in r and r['_row'].get('rustc', {}).get('def_kind') in ('Fn', 'AssocFn')
                and r['_row']['def_path_hash'] not in roots}
        direct = defaultdict(list)
        for child, _ in scan_definitions(path, 'parent_def_path_hash', set(sync)):
            if ASYNC.match(child.get('detail', {}).get('closure_kind', '')):
                direct[child['ownership']['parent_def_path_hash']].append(child)
        own = scan_mir(mir, set(direct), include_body=True) if direct else {}
        for key, children in direct.items():
            matches = own.get(key, [])
            if len(matches) != 1 or matches[0]['canonical_path'] != sync[key]['identity']['canonical_path']:
                continue
            proof = thin_coroutine_wrapper(matches[0]['raw_body'])
            if proof:
                wrappers[key] = (children, proof, matches[0])
    frontier = {key: [(key,)] for key in roots}
    candidates = defaultdict(list)
    errors = defaultdict(list)
    visited = set()
    while frontier:
        following = defaultdict(list)
        for row, offset in scan_definitions(path, 'parent_def_path_hash', set(frontier)):
            parent = row['ownership']['parent_def_path_hash']
            child = row['def_path_hash']
            for chain in frontier[parent]:
                root = chain[0]
                if child in chain:
                    errors[root].append('Cycle in definition ownership chain')
                    continue
                if (root, offset) in visited:
                    continue
                visited.add((root, offset))
                next_chain = chain + (child,)
                if ASYNC.match(row.get('detail', {}).get('closure_kind', '')):
                    candidates[root].append((row, next_chain))
                elif row.get('rustc', {}).get('def_kind') not in ('Closure', 'Fn', 'AssocFn'):
                    following[child].append(next_chain)
        frontier = following
    for result in results:
        row = result.get('_row')
        if row is None:
            continue
        body_hash = row['def_path_hash']
        chain = (body_hash,)
        execution_form = ('coroutine' if ASYNC.match(row.get('detail', {}).get('closure_kind', ''))
                          else 'sync')
        body_classification = classify.classify_body(execution_form=execution_form)
        result['body_classification'] = body_classification
        result['async_mapped'] = False
        if body_hash in roots:
            found = candidates[body_hash]
            if errors[body_hash] or len(found) != 1:
                result['reason'] = '; '.join(errors[body_hash]) or f'Async executable coroutine: expected one owned candidate, found {len(found)}'
                result['candidates'] = [dict(def_path_hash=x['def_path_hash'], canonical_path=x['identity']['canonical_path'], ownership_chain=list(c)) for x, c in found]
                result.pop('_row')
                continue
            row, chain = found[0]
            body_classification = classify.classify_body(execution_form='coroutine')
            result['body_classification'] = body_classification
            result['async_mapped'] = True
            result['mapping_reason'] = 'declared_async_owned_coroutine'
        elif body_hash in wrappers:
            children, proof, shell_mir = wrappers[body_hash]
            if len(children) != 1:
                result['reason'] = f'Thin wrapper async coroutine: ambiguous; expected one direct candidate, found {len(children)}'
                result['candidates'] = [{'def_path_hash': c['def_path_hash'], 'canonical_path': c['identity']['canonical_path']} for c in children]
                result.pop('_row')
                continue
            row = children[0]
            if row['def_path_hash'] != proof['coroutine_def_path_hash']:
                result['reason'] = 'Thin wrapper constructed coroutine differs from direct child'
                result.pop('_row')
                continue
            chain = (body_hash, row['def_path_hash'])
            body_classification = classify.classify_body('strict-forward', 'sync')
            result['body_classification'] = body_classification
            result['async_mapped'] = body_classification['kind'] == 'async-shell'
            result['mapping_reason'] = body_classification['mappingMode']
            result['mapping_evidence'] = proof
            result.setdefault('async_shell_preludes', []).append({
                'def_path_hash': sync[body_hash]['def_path_hash'],
                'canonical_path': sync[body_hash]['identity']['canonical_path'],
                'body_key': shell_mir['body_key'],
                'mir_offset_bytes': shell_mir['mir_offset_bytes']})
        result['_row'] = row
        result['ownership_chain'] = list(chain)
        try:
            canonical, body_hash, slug = body_identity(row)
            result.update(def_path_hash=body_hash, canonical_path=canonical, slug=slug,
                          source=row['source'], definition_row=row)
        except ValueError as exc:
            result['reason'] = str(exc)
            result.pop('_row')



def map_instrumentation(path, results, mir):
    """Descend through one MIR-proven, directly-owned instrumented child."""
    from classification_registry import prove_instrumentation as prove_sync
    active = [r for r in results if '_row' in r]
    sync = {r['_row']['def_path_hash'] for r in active if not ASYNC.match(r['_row'].get('detail', {}).get('closure_kind', ''))}
    bodies = scan_mir(mir, sync, include_body=True) if sync else {}
    for result in active:
        matches = bodies.get(result['_row']['def_path_hash'], [])
        if len(matches) == 1 and matches[0]['canonical_path'] == result['canonical_path']:
            proof = prove_sync(matches[0]['raw_body'])
            if proof:
                result['instrumentation_classification'] = proof
    while active:
        roots = {r['_row']['def_path_hash'] for r in active
                 if ASYNC.match(r['_row'].get('detail', {}).get('closure_kind', ''))}
        children = defaultdict(list)
        for child, _ in scan_definitions(path, 'parent_def_path_hash', roots):
            if ASYNC.match(child.get('detail', {}).get('closure_kind', '')):
                children[child['ownership']['parent_def_path_hash']].append(child)
        shells = scan_mir(mir, set(children), include_body=True) if children else {}
        proposed = []
        for result in active:
            shell = result['_row']; owner = shell['def_path_hash']
            matches = shells.get(owner, []); direct = children.get(owner, [])
            if (len(matches) != 1 or matches[0]['canonical_path'] != result['canonical_path']
                    or len(direct) != 1):
                continue
            child = direct[0]
            binding, _ = classify.prove_async_shell_binding(
                matches[0]['raw_body'], child['def_path_hash'])
            if (not binding or child['def_path_hash'] in result['ownership_chain']
                    or child.get('representations', {}).get('mir', {}).get('body_available') is not True):
                continue
            proposed.append((result, shell, child, binding, matches[0]))
        inner = scan_mir(mir, {child['def_path_hash'] for _, _, child, _, _ in proposed}) if proposed else {}
        active = []
        for result, shell, child, binding, shell_mir in proposed:
            matches = inner.get(child['def_path_hash'], [])
            if (len(matches) != 1 or not matches[0]['bb_count']
                    or matches[0]['canonical_path'] != child['identity']['canonical_path']):
                continue
            canonical, owner, slug = body_identity(child)
            relation = {'shellBodyId': '|'.join([shell['def_path_hash'], STAGE, 'main']),
                        'innerDefPathHash': owner,
                        **binding,
                        'evidenceFailure': 'shell-pin-not-yet-supplied'}
            evidence = dict(binding, wrapper_def_path_hash=shell['def_path_hash'],
                            inner_bb_count=matches[0]['bb_count'], child_source=child['source'])
            result.setdefault('instrumentation_mapping_evidence', []).append(evidence)
            result.setdefault('async_shell_preludes', []).append({
                'def_path_hash': shell['def_path_hash'],
                'canonical_path': shell['identity']['canonical_path'],
                'body_key': shell_mir['body_key'],
                'mir_offset_bytes': shell_mir['mir_offset_bytes']})
            mode = ('strict-forward' if thin_coroutine_wrapper(shell_mir['raw_body'])
                    else 'retained-relation')
            result.update(_row=child, def_path_hash=owner, canonical_path=canonical, slug=slug,
                          source=child['source'], definition_row=child, async_mapped=True,
                          mapping_reason=mode)
            result['body_classification'] = classify.classify_body(
                mode, 'coroutine', 'needs-evidence', relation)
            result['ownership_chain'].append(owner)
            active.append(result)

def scan_mir(path, wanted, include_body=False):
    found = defaultdict(list)
    seen = set()
    with path.open('rb') as stream:
        for start, end in key_offsets(path, 'owner_def_path_hash'):
            value = value_after(stream, end)
            if not isinstance(value, str) or value.lower() not in wanted:
                continue
            offset = object_start(stream, start)
            if offset in seen:
                continue
            seen.add(offset)
            body = decode(object_slice(stream, offset))
            if 'basic_blocks' not in body or body.get('capture_stage') != STAGE or body.get('body_id') != 'main':
                continue
            blocks = body['basic_blocks']
            found[value.lower()].append({'canonical_path': body.get('canonical_path'),
                                        'bb_count': len(blocks) if isinstance(blocks, list) else 0,
                                        'body_key': {k: body.get(k) for k in ('owner_def_path_hash', 'capture_stage', 'body_id')},
                                        'mir_offset_bytes': offset,
                                        **({'raw_body': body} if include_body else {})})
    return found


def resolve(items, definitions, mir, root):
    results = select_definitions(definitions, items)
    map_async(definitions, results, mir)
    map_instrumentation(definitions, results, mir)
    wanted = {r['def_path_hash'] for r in results if '_row' in r}
    bodies = scan_mir(mir, wanted) if wanted else {}
    index = read_index(root)
    batch_slugs = {}
    for result in results:
        if result.pop('_row', None) is None:
            continue
        matches = bodies.get(result['def_path_hash'], [])
        try:
            if len(matches) != 1:
                raise ValueError(f'MIR main body at {STAGE}: expected one match, found {len(matches)}')
            body = matches[0]
            if body['canonical_path'] != result['canonical_path']:
                raise ValueError('MIR canonical_path differs from definition')
            if not body['bb_count']:
                raise ValueError('MIR basic_blocks must be a nonempty list')
            check_identity(index, result['canonical_path'], result['def_path_hash'], result['slug'])
            result.update(body, status='resolved', out=str(root / result['slug']))
            batch_slugs.setdefault(result['slug'].casefold(), []).append(result)
        except ValueError as exc:
            result['reason'] = str(exc)
    for group in batch_slugs.values():
        if len({r['def_path_hash'] for r in group}) > 1:
            for result in group:
                result.update(status='unresolved', reason='Slug collision between distinct batch bodies')
    return sorted(results, key=lambda r: (r.get('bb_count') is None, r.get('bb_count', 0), r['id']))


def markdown(report):
    def cell(value):
        return str(value).replace('|', r'\|').replace('\n', ' ')
    counts = report['counts']
    lines = ['# Resolved MIR bodies', '',
             f"Resolved: {counts['resolved']}; unresolved: {counts['unresolved']}; async mapped: {counts['async_mapped']}.",
             '', 'Sorted by BB count ascending; unknown counts last.', '',
             '| ID | Topics | Status | BBs | Executable canonical_path | Hash | File/span | Output / reason |',
             '|---|---|---|---:|---|---|---|---|']
    for row in report['items']:
        source = row.get('source', {})
        span = source.get('span', {})
        location = f"{source.get('file', '')}:{span.get('start_line', '')}-{span.get('end_line', '')}"
        lines.append('| ' + ' | '.join(cell(x) for x in (
            row['id'], ', '.join(row['topic_ids']), row['status'], row.get('bb_count', ''),
            row.get('canonical_path', row.get('requested_canonical_path', '')),
            row.get('def_path_hash', ''), location, row.get('reason', row.get('out', '')))) + ' |')
    if report['topics']:
        lines += ['', '## Topic references', '']
        lines += [f"- {t['id']} {t.get('title', '')}: {', '.join(t['item_ids'])}" for t in report['topics']]
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument('--input', help='Single hash, canonical_path or inline definitions row JSON')
    selector.add_argument('--list', type=Path, help='Batch .md/.json/.txt list (JSON may also be one definition row)')
    parser.add_argument('--definitions', type=Path, required=True)
    parser.add_argument('--mir-bodies', type=Path, required=True)
    parser.add_argument('--output-root', default=os.environ.get('OUTPUT_ROOT'))
    args = parser.parse_args()
    root = output_root(args.output_root)
    items, topics = read_input(args.input, args.list)
    results = resolve(items, args.definitions, args.mir_bodies, root)
    report = {'version': 1, 'inputs': {'list': str(args.list) if args.list else None,
              'definitions': str(args.definitions.resolve()), 'mir_bodies': str(args.mir_bodies.resolve())},
              'counts': {'total': len(results), 'resolved': sum(r['status'] == 'resolved' for r in results),
                         'unresolved': sum(r['status'] == 'unresolved' for r in results),
                         'async_mapped': sum(r['status'] == 'resolved' and r.get('async_mapped', False) for r in results)},
              'items': results, 'topics': topics}
    with locked(root):
        directory = root / '_inputs'
        safe_child(directory, directory=True)
        directory.mkdir(exist_ok=True)
        protected = {p.resolve() for p in (args.definitions, args.mir_bodies, args.list) if p}
        for name in ('bodies.json', 'bodies.md'):
            dest = directory / name
            safe_child(dest)
            if dest.resolve() in protected:
                raise ValueError('Output would overwrite an input')
        (directory / 'bodies.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (directory / 'bodies.md').write_text(markdown(report), encoding='utf-8')
    print(json.dumps(dict(report['counts'], json=str(directory / 'bodies.json'), markdown=str(directory / 'bodies.md'))))
    return 2 if report['counts']['unresolved'] else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        sys.exit(1)
