#!/usr/bin/env python3
"""Audit canonical renderer data, not evidence snapshots or cached copies.

JSON inventory C1-C6. Exit 1 for duplicates, 0 for clean or proven distinct
occurrences, 2 for invalid input. Counts count pairs (C1/C3/C4/C6) or fields
(C2/C5). Source identities and guard partitions distinguish real repetitions.
"""
import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import re


def norm(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def walk(controls, parent=None, ancestors=()):
    for c in controls:
        yield c, parent, ancestors
        yield from walk(c.get('children', []), c['id'], ancestors + (c['id'],))
        for b in c.get('branches', []):
            yield from walk(b.get('children', []), b['id'], ancestors + (c['id'],))


def messages(c):
    return [m for n, _, _ in walk([c]) for m in n.get('messages', [])]


def scope_alias(c, s):
    """One range identity may have an owner binding but no second body."""
    return (s.get('originControlRef') == c.get('id') and c.get('kind') == s.get('kind')
            and norm(c.get('condition')) == norm(s.get('condition'))
            and c.get('skip') == s.get('skip')
            and not any(c.get(k) for k in ('notes', 'after', 'children', 'messages', 'branches')))


def audit(data, details=None, granularity=None, summaries=None):
    details, granularity, summaries = details or {}, granularity or {}, summaries or {}
    found = {f'C{i}': [] for i in range(1, 7)}
    def add(cat, kind, ids, severity='error', **extra):
        found[cat].append(dict(kind=kind, ids=ids, severity=severity, **extra))
    units, action_parent, spans, descendants = {}, {}, {}, {}
    prelude_nodes = list((data.get('prelude') or {}).get('nodes', []))
    for node in prelude_nodes:
        units[node['id']] = (node, 'depth0.5', 'ROOT/prelude')
        descendants[node['id']] = [node['id']]
        spans[node['id']] = set(details.get('nodes', {}).get(
            node['id'], {}).get('basic_block_refs', node.get('basicBlockRefs', [])))
    for p in data.get('phases', []):
        units[p['id']] = (p, 'depth1', None)
        descendants[p['id']] = []
        for g in p.get('goals', []):
            units[g['id']] = (g, 'depth1.5', p['id'])
            descendants[g['id']] = []
            for a in g.get('actions', []):
                units[a['id']] = (a, 'depth2', g['id'])
                descendants[a['id']] = [a['id']]
                descendants[g['id']].append(a['id'])
                descendants[p['id']].append(a['id'])
                action_parent[a['id']] = g['id']
                spans[a['id']] = set(details.get('nodes', {}).get(a['id'], {}).get('basic_block_refs', a.get('basic_block_refs', [])))
    for uid in units:
        spans[uid] = set().union(*(spans.get(a, set()) for a in descendants[uid]))
    def expand(refs):
        return set(a for r in refs for a in descendants.get(r['ref'], []))
    def bb(actions):
        return set().union(*(spans.get(a, set()) for a in actions))
    owner = {o['controlRef']: o['owner']['ref'] for o in data.get('controlOwners', [])}
    controls = list(walk(data.get('controls', [])))
    byid = {c['id']: c for c, _, _ in controls}
    scopes = data.get('readingScopes', [])
    origins = {s['originControlRef']: s for s in scopes if s.get('originControlRef')}
    guards = defaultdict(list)
    for g in granularity.get('memberGuards', []):
        guards[g.get('controlRef')].append(g)
    records, text_records = [], []
    def texts(obj, path, identity):
        for k in ('label', 'condition', 'skip', 'outcome', 'notes', 'after', 'text'):
            v = obj.get(k)
            for i, t in enumerate(v if isinstance(v, list) else [v] if isinstance(v, str) else []):
                text_records.append((identity, path + '/' + k + (f'/{i}' if isinstance(v, list) else ''), t))
    canonical_aliases = []
    for c, parent, ancestors in controls:
        cid = c['id']; root = ancestors[0] if ancestors else cid
        own = owner.get(root)
        scope = origins.get(cid)
        actions = expand(scope['members']) if scope else set(descendants.get(own, []))
        alias = bool(scope and scope_alias(c, scope))
        if alias:
            canonical_aliases.append({'control': cid, 'scope': scope['id']})
        else:
            records.append(dict(id=cid, title=norm(c.get('condition')), parent=parent or own,
                                ancestors=ancestors, actions=actions, bbs=bb(actions), source='control'))
        texts(c, '/controls/' + cid, cid)
        labels = {norm(c.get('condition'))}
        for b in c.get('branches', []):
            texts(b, '/controls/' + cid + '/branches/' + b['id'], b['id'])
            labels.add(norm(b.get('condition')))
            if b.get('outcome') and norm(b['outcome']) == norm(b.get('condition')):
                add('C2', 'branch_condition_echo', [cid, b['id']], field='outcome', layer='sequence')
        for k in ('notes', 'after'):
            ts = c.get(k, [])
            if ts and not messages(c) and all(norm(t) in labels for t in ts):
                add('C2', 'message_free_label_echo', [cid], field=k, layer='sequence')
    for s in scopes:
        actions = expand(s.get('members', []))
        records.append(dict(id=s['id'], title=norm(s.get('condition')), parent=s.get('parentScopeRef'),
                            ancestors=(), actions=actions, bbs=bb(actions), source='scope'))
        texts(s, '/readingScopes/' + s['id'], s['id'])
        for b in s.get('branches', []):
            texts(b, '/readingScopes/' + s['id'] + '/branches/' + b['id'], b['id'])
    from canonicalize_controls import sole_action, same_text
    summary_units = summaries.get('units', summaries)
    for scope in scopes:
        for branch in scope.get('branches', []):
            ref = sole_action(branch)
            if not branch.get('outcome') and (branch.get('effect') or ref not in action_parent or not summary_units.get(ref, {}).get('text', '').strip()):
                add('C2', 'missing_alternative_outcome', [scope['id'], branch['id']],
                    field='outcome', layer='sequence/depth2')
            if ref in action_parent and same_text(branch.get('outcome'), summary_units.get(ref, {}).get('text')):
                add('C2', 'alternative_action_summary_echo', [scope['id'], branch['id'], ref],
                    field='outcome', layer='sequence/depth2')
    for a, b in combinations(records, 2):
        if not a['title'] or a['title'] != b['title']:
            continue
        overlap = a['bbs'] & b['bbs']
        same_parent = a['parent'] is not None and a['parent'] == b['parent']
        nested = a['id'] in b['ancestors'] or b['id'] in a['ancestors']
        linked = any(s.get('originControlRef') in (a['id'], b['id']) and s['id'] in (a['id'], b['id']) for s in scopes)
        if overlap and (same_parent or nested or linked or a['actions'] & b['actions']):
            add('C1', 'repeated_guard', [a['id'], b['id']], title=a['title'], bb_overlap=sorted(overlap),
                relation='origin_scope' if linked else 'nested' if nested else 'sibling_or_overlapping_range', layer='sequence')
    # Semantic same guards with different prose, including scope/invocation duplication.
    grouped = defaultdict(dict)
    for g in granularity.get('memberGuards', []):
        c = g.get('controlRef')
        if c in byid:
            grouped[(g.get('decisionRef'), tuple(sorted(g.get('takeValues', []))))][c] = g
    record_by_id = {r['id']: r for r in records}
    for gs in grouped.values():
        for a, b in combinations(gs, 2):
            ra = record_by_id.get(a) or record_by_id.get(origins.get(a, {}).get('id'))
            rb = record_by_id.get(b) or record_by_id.get(origins.get(b, {}).get('id'))
            if ra and rb and ra['bbs'] & rb['bbs'] and not any(set(v['ids']) == {a, b} for v in found['C1']):
                add('C1', 'repeated_decision_guard', [a, b], decision=gs[a]['decisionRef'],
                    bb_overlap=sorted(ra['bbs'] & rb['bbs']), layer='sequence')
    # Compare message occurrences within one owning action/control, never across depths.
    msg_by_id = {m['messageId']: m for m in data.get('messages', [])}
    grouped = defaultdict(list)
    for c, _, ancestors in controls:
        root = ancestors[0] if ancestors else c['id']
        for mid in c.get('messages', []):
            m = msg_by_id.get(mid, {})
            key = (owner.get(root, root), m.get('fromActorId'), m.get('toActorId'), norm(m.get('label')))
            grouped[key].append((mid, c['id'], m))
    for key, occurrences in grouped.items():
        for a, b in combinations(occurrences, 2):
            distinct = (a[0] != b[0] and a[2].get('bindingRef') and b[2].get('bindingRef')
                        and a[2]['bindingRef'] != b[2]['bindingRef'] and a[2].get('invocationRef') != b[2].get('invocationRef'))
            add('C3', 'same_endpoint_label', [a[0], b[0]], severity='info' if distinct else 'error',
                parent=key[0], controls=[a[1], b[1]], reason='distinct_call_bindings' if distinct else 'repeated_message', layer='sequence')
    # Also catch adjacent identical rows in the message registry across parents.
    for a, b in zip(data.get('messages', []), data.get('messages', [])[1:]):
        signature = lambda m: (m.get('fromActorId'), m.get('toActorId'), norm(m.get('label')))
        if signature(a) != signature(b): continue
        ids = [a['messageId'], b['messageId']]
        if any(f['ids'] == ids for f in found['C3']): continue
        distinct = (a.get('bindingRef') and b.get('bindingRef') and a['bindingRef'] != b['bindingRef']
                    and a.get('invocationRef') != b.get('invocationRef'))
        add('C3', 'adjacent_message_rows', ids, severity='info' if distinct else 'error',
            reason='distinct_call_bindings' if distinct else 'repeated_message', layer='sequence')
    titles = defaultdict(list)
    for uid, (u, depth, parent) in units.items():
        texts(u, '/units/' + uid, uid)
        titles[norm(u.get('label'))].append(uid)
    for title, ids in titles.items():
        if title:
            for a, b in combinations(ids, 2):
                add('C4', 'repeated_reading_title', [a, b], title=title, layers=[units[a][1], units[b][1]], bb_overlap=sorted(spans[a] & spans[b]))
    for mid, m in msg_by_id.items():
        texts(m, '/messages/' + mid, mid)
    for uid, u in summaries.get('units', summaries).items():
        if isinstance(u, dict):
            texts(u, '/reading-summaries/' + uid, uid)
            label = norm(units.get(uid, ({},))[0].get('label'))
            value = norm(u.get('text'))
            if label and (value == label or value.startswith(label + '；') or value.startswith(label + ';')):
                add('C2', 'reading_summary_title_echo', [uid], field='reading-summaries/text',
                    layer=units[uid][1])
    def extra_texts(obj, path, identity):
        if isinstance(obj, dict):
            identity = obj.get('id', identity)
            texts(obj, path, identity)
            for k, v in obj.items():
                if isinstance(v, (dict, list)) and k not in ('evidence', 'evidenceRefs'):
                    extra_texts(v, path + '/' + k, identity)
        elif isinstance(obj, list):
            for i, v in enumerate(obj): extra_texts(v, path + '/' + str(i), identity)
    for key in ('scopeAnnotations', 'purposeProjections', 'segments', 'display'):
        extra_texts(data.get(key, []), '/' + key, key)
    filler = re.compile(r'未满足.{0,16}条件时进入对应的其他业务路径|的处理结果$|的分支范围$|进入对应的其他业务路径|其他业务路径$')
    for uid, path, value in text_records:
        if filler.search(norm(value)):
            add('C5', 'boilerplate', [uid], path=path, text=value)
    execution = data.get('execution', {})
    eg = defaultdict(list)
    for e in execution.get('edges', []):
        eg[(e['from'], e['to'], norm(e.get('label')))].append(e)
    for group in eg.values():
        for a, b in combinations(group, 2):
            signature = lambda e: (e.get('kind'), sorted((g['decisionRef'], g['value']) for g in e.get('guards', [])), sorted(e.get('resetDecisionRefs', [])), e.get('readingScopeRef'), e.get('taskId'))
            distinct = signature(a) != signature(b)
            add('C6', 'same_endpoint_label_edges', [a['id'], b['id']], severity='info' if distinct else 'error',
                endpoints=[a['from'], a['to']], guards=[a.get('guards'), b.get('guards')],
                reason='distinct_guard_or_execution_effect' if distinct else 'duplicate_execution_edge', layer='execution')
    ng = defaultdict(list)
    evidence = {e['id']: e for e in execution.get('evidence', [])}
    for n in execution.get('nodes', []):
        ref = n.get('actionRef'); title = n.get('label') or units.get(ref, ({},))[0].get('label')
        if not title and n.get('decisionRef'):
            q = next((q for q in execution.get('decisions', []) if q['id'] == n['decisionRef']), {})
            title = byid.get(q.get('controlRef'), {}).get('condition') or next((s['condition'] for s in scopes if s['id'] == q.get('readingScopeRef')), None)
        blocks = spans.get(ref, set()) or set(re.findall(r'\bbb\d+\b', ';'.join(evidence.get(e, {}).get('locator', '') for e in n.get('evidenceRefs', []))))
        if title and blocks: ng[(norm(title), tuple(sorted(blocks)))].append(n['id'])
    for (title, blocks), ids in ng.items():
        for a, b in combinations(ids, 2): add('C6', 'same_title_span_nodes', [a, b], title=title, bbs=blocks, layer='execution')
    counts = {k: {'errors': sum(x['severity'] == 'error' for x in v), 'info': sum(x['severity'] == 'info' for x in v), 'total': len(v)} for k, v in found.items()}
    coverage = {'prelude': len(prelude_nodes)} if prelude_nodes else {}
    coverage.update({'depth1': len(data.get('phases', [])), 'depth1.5': sum(v[1] == 'depth1.5' for v in units.values()),
                     'depth2': len(action_parent), 'sequence_controls': len(controls), 'reading_scopes': len(scopes),
                     'messages': len(msg_by_id), 'execution_nodes': len(execution.get('nodes', [])), 'execution_edges': len(execution.get('edges', []))})
    return dict(format='duplicate-audit/1', passed=not any(c['errors'] for c in counts.values()), counts=counts,
                coverage=coverage,
                canonical_scope_aliases=canonical_aliases, inventory=found)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--suffix', default='', help='e.g. .pre-dupfix to audit original backups')
    p.add_argument('--report', type=Path)
    p.add_argument('--replace-report', action='store_true',
                   help='Replace only --out/stage7/duplicates.json, archiving previous bytes')
    args = p.parse_args()
    def read(name, optional=False):
        path = args.out / (name + args.suffix)
        if optional and not path.exists(): return {}
        return json.loads(path.read_text())
    try:
        result = audit(read('renderer-input.json'), read('basic-block-details.json'), read('stage2/granularity.json', True), read('reading-summaries.json', True))
        result['input'] = str(args.out / ('renderer-input.json' + args.suffix))
        encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.report:
            if args.replace_report:
                if args.report.resolve() != (args.out / 'stage7/duplicates.json').resolve():
                    raise ValueError('--replace-report is restricted to this run stage7/duplicates.json')
                from ledger_lib import write
                write(args.report, encoded.encode())
            else:
                if args.report.exists(): raise ValueError('report already exists; choose a new report path')
                args.report.write_text(encoded)
        else: print(encoded, end='')
        return 0 if result['passed'] else 1
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False)); return 2


if __name__ == '__main__':
    raise SystemExit(main())
