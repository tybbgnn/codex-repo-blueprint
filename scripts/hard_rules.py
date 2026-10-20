#!/usr/bin/env python3
"""Independent readability rules; intentionally imports no generator module."""
import argparse
import json
from pathlib import Path


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _prelude_signature(node):
    # Identity/display text and the explicit exception are not content. BB
    # references are evidence locations, not a semantic distinction: the same
    # source read through different MIR blocks is still identical content.
    ignored = {'id', 'label', 'distinctionReason'}
    content_fields = sorted(k for k in node if k not in ignored)
    compared_values = {k: node[k] for k in content_fields if k != 'basicBlockRefs'}
    return json.dumps({'fields': content_fields, 'values': compared_values},
                      ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def check_prelude_distinctions(data):
    groups = {}
    for node in (data.get('prelude') or {}).get('nodes', []):
        groups.setdefault(_prelude_signature(node), []).append(node)
    errors = []
    for nodes in groups.values():
        if len(nodes) > 1 and any(not _text(n.get('distinctionReason')) for n in nodes):
            errors.append({'code': 'readability.preludeDistinct',
                           'path': 'prelude.nodes',
                           'message': 'identical prelude nodes must merge or every retained node must state distinctionReason',
                           'nodeRefs': [n.get('id') for n in nodes]})
    return errors


def _goal_records(granularity):
    rows = granularity.get('goalContracts', []) if isinstance(granularity, dict) else []
    return {r.get('goalRef'): r for r in rows if isinstance(r, dict) and r.get('goalRef')}


def check_goal_decisions(data, granularity=None):
    errors = []
    records = _goal_records(granularity or {})
    for phase in data.get('phases', []):
        goals = phase.get('goals', [])
        for goal in goals:
            contract = records.get(goal.get('id')) or {}
            has_merge_reason = (_text(goal.get('mergeReason')) or
                                _text(contract.get('cohesionReason')))
            if len(goal.get('actions', [])) > 1 and not has_merge_reason:
                errors.append({'code': 'readability.goalMergeReason', 'path': goal.get('id', ''),
                               'message': 'a goal merging multiple actions requires non-empty mergeReason or goal-contract cohesionReason'})
        split = set()
        for left, right in zip(goals, goals[1:]):
            a, b = records.get(left.get('id')), records.get(right.get('id'))
            if not a or not b:
                continue
            sa = (a.get('contractRef'), a.get('entryMode'))
            sb = (b.get('contractRef'), b.get('entryMode'))
            if all(sa) and sa == sb:
                split.update((left.get('id'), right.get('id')))
        for goal in goals:
            if goal.get('id') in split and not _text(goal.get('splitReason')):
                errors.append({'code': 'readability.goalSplitReason', 'path': goal.get('id', ''),
                               'message': 'adjacent goals sharing completion contract and entry mode require non-empty splitReason'})
    return errors


def validate(data, granularity=None):
    errors = check_prelude_distinctions(data) + check_goal_decisions(data, granularity)
    return {'valid': not errors, 'errors': errors}


def load_for_output(out):
    out = Path(out)
    data = json.loads((out / 'renderer-input.json').read_text())
    path = out / 'stage2/granularity.json'
    granularity = json.loads(path.read_text()) if path.is_file() else None
    return data, granularity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    data, granularity = load_for_output(args.out)
    result = validate(data, granularity)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if args.report:
        args.report.write_text(payload)
    print(payload, end='')
    return 0 if result['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
