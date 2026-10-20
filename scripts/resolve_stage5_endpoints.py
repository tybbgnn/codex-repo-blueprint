#!/usr/bin/env python3
"""Resolve endpoint selectors with bounded definition/MIR scans and MIR cache reads."""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from mir_cache import load_cached
from resolve_bodies import scan_definitions, scan_mir


def _hash(row):
    return (row.get('def_path_hash') or row.get('owner_def_path_hash')
            or row.get('identity', {}).get('def_path_hash'))


def _path(row):
    return row.get('canonical_path') or row.get('identity', {}).get('canonical_path')


def _requests(ledger):
    requests = []
    for request in ledger.get('endpoints', []):
        selector = {key: request[key] for key in ('def_path_hash', 'canonical_path')
                    if request.get(key)}
        if len(selector) != 1:
            raise ValueError(f"endpoint {request.get('id')} requires exactly one real selector")
        key, wanted = next(iter(selector.items()))
        if key == 'def_path_hash':
            wanted = wanted.lower()
        requests.append((request, key, wanted))
    return requests


def _definition_indexes(path, requests):
    indexes = {'def_path_hash': defaultdict(list), 'canonical_path': defaultdict(list)}
    for key in indexes:
        wanted = {value for _, selector, value in requests if selector == key}
        for row, _ in scan_definitions(path, key, wanted):
            value = _hash(row).lower() if key == 'def_path_hash' else _path(row)
            indexes[key][value].append(row)
    return indexes


def resolve(ledger, definitions, mir_bodies, cache_directory, targets=None, pins=None):
    """Resolve exact definitions and executable MIR without loading either container."""
    requests = _requests(ledger)
    indexes = _definition_indexes(definitions, requests)
    selected = []
    unique_rows = {}
    for request, key, wanted in requests:
        matches = indexes[key].get(wanted, [])
        from endpoint_identity import select
        row = select(request,matches,targets)
        actual_hash = _hash(row)
        if not actual_hash:
            raise ValueError(f"endpoint {request.get('id')} definition has no def_path_hash")
        available = row.get('representations', {}).get('mir', {}).get(
            'body_available', row.get('detail', {}).get('has_body', False))
        if not available and pins is None:
            raise ValueError(f"endpoint {request.get('id')} has no MIR body")
        selected.append((request, row, actual_hash.lower()))
        unique_rows.setdefault(actual_hash.lower(), row)

    bodies = {}
    misses = set()
    locators={}
    if pins is not None:
        locators={p['def_path_hash']:p for p in pins.get('information_mir_slices',[])+pins.get('callee_mir_slices',[]) if 'offset_bytes' in p}
        main=pins.get('definition_row',{}).get('def_path_hash');source=pins.get('inputs',{}).get('mir_bodies',{})
        if main and source.get('slice'):
            locators[main]=dict(source['slice'],def_path_hash=main,path=source['path'])
    for actual_hash, row in unique_rows.items():
        if pins is not None:
            from stage_engine import read_callee_slice
            if actual_hash not in locators:raise ValueError('model-callee-pin: endpoint MIR pin missing: '+actual_hash)
            bodies[actual_hash]=[read_callee_slice(locators[actual_hash],pins)]
            continue
        cached = load_cached(mir_bodies, row, cache_directory)
        if cached is None:
            misses.add(actual_hash)
        else:
            bodies[actual_hash] = [cached[0]]
    if misses:
        for actual_hash, matches in scan_mir(mir_bodies, misses, include_body=True).items():
            bodies[actual_hash] = [match['raw_body'] for match in matches]

    resolved = []
    for request, row, actual_hash in selected:
        matches = bodies.get(actual_hash, [])
        if len(matches) != 1:
            raise ValueError(f"endpoint {request.get('id')} resolved to {len(matches)} MIR bodies")
        body = matches[0]
        if _hash(body).lower() != actual_hash or _path(body) != _path(row):
            raise ValueError(f"endpoint {request.get('id')} MIR identity differs from definition")
        if not isinstance(body.get('basic_blocks'), list) or not body['basic_blocks']:
            raise ValueError(f"endpoint {request.get('id')} MIR body has no basic_blocks")
        resolved.append({'id': request['id'], 'def_path_hash': _hash(row),
                         'canonical_path': _path(row), 'definition': row, 'mir': body})
    return {'endpoints': resolved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', required=True, type=Path)
    parser.add_argument('--definitions', required=True, type=Path)
    parser.add_argument('--mir-bodies', required=True, type=Path)
    parser.add_argument('--output-root', type=Path, default=os.environ.get('OUTPUT_ROOT'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--targets', type=Path)
    parser.add_argument('--pins', type=Path)
    args = parser.parse_args()
    if args.output_root is None:
        parser.error('--output-root or OUTPUT_ROOT is required')
    result = resolve(json.loads(args.ledger.read_text()), args.definitions, args.mir_bodies,
                     args.output_root / '_inputs' / 'mir-cache',
                     json.loads(args.targets.read_text()) if args.targets else None,
                     json.loads(args.pins.read_text()) if args.pins else None)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    main()
