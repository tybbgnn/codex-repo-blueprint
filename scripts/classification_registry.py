"""Compatibility API for the shared classification stage and proof algorithms."""
from classify import (POLICY, TECHNICAL_CATEGORIES, classify_action as _classify_action,
                      classify_async_shell, classify_body, classify_loop,
                      compiler_drop_flags, event_macro_artifact, fingerprint, instrumentation_proof,
                      instrumentation_record_matches, place_key, prove_forwarding,
                      prove_event_macro, prove_instrumentation, load_event_macro_artifacts,
                      source_less, technical_record_matches)


def classify_action(data, raw, action):
    result = _classify_action(data, raw, action)
    result.pop('loopHandoff')
    return result


def instrumentation_record_valid(raw, block, record, event_macro_artifacts=None):
    return instrumentation_record_matches(block, record, prove_instrumentation(raw, event_macro_artifacts))


def technical_record_valid(raw, block, record, event_macro_artifacts=None):
    return technical_record_matches(record, lambda: instrumentation_record_valid(raw, block, record, event_macro_artifacts))


def permits(consumer, capability, classification):
    exception = POLICY['exceptions'].get(classification['kind'], {})
    return bool(classification.get('proof') and consumer in exception.get('consumers', [])
                and capability in exception.get('allows', []))


def empty_snippets_allowed(data, raw, unit, detail_refs):
    c = classify_action(data, raw, unit)
    return (c['kind'] == POLICY['exceptions']['source_less']['detailException']
            and c['sourceLess'] and set(detail_refs) == set(unit.get('basicBlockRefs', []))
            and permits('P14', 'empty_detail_snippets', c))


def handoff_boundaries(data, raw, actions, goals):
    classified = {a['id']: classify_action(data, raw, a) for a in actions}
    candidates = {ref for ref, c in classified.items() if c['handoffCandidate']}
    errors = [ref for ref in sorted(candidates) if not classified[ref]['proof']]
    if 'standalone_goal' in POLICY['exceptions']['pure_loop_handoff']['forbids']:
        errors += [g['id'] for g in goals if g['actions'] and all(a['id'] in candidates for a in g['actions'])]
    return errors, len(candidates)


def pure_blocks(raw, refs):
    blocks = {f"bb{b['basic_block']}": b for b in raw.get('basic_blocks', [])}
    if not refs or any(r not in blocks or blocks[r].get('is_cleanup') or blocks[r].get('terminator', {}).get('kind') != 'Goto' for r in refs):
        return False
    flags = compiler_drop_flags(raw)
    def places(value):
        if isinstance(value, dict):
            if 'local' in value and 'projection' in value: yield value
            else:
                for v in value.values(): yield from places(v)
        elif isinstance(value, list):
            for v in value: yield from places(v)
    used = {p['local'] for v in raw.get('debug_variables', []) for p in places(v)}
    for b in blocks.values():
        used.update(p['local'] for p in places(b['terminator']))
        for st in b.get('statements', []):
            d = st.get('detail', {})
            used.update(p['local'] for p in places(d.get('rvalue', d)))
    if not refs or any(r not in blocks for r in refs):
        return False
    for ref in refs:
        b = blocks[ref]
        if b.get('is_cleanup') or b.get('terminator', {}).get('kind') != 'Goto':
            return False
        for st in b.get('statements', []):
            if st['kind'] in ('StorageLive', 'StorageDead', 'Nop'):
                continue
            d = st.get('detail', {}); dest = d.get('destination', {})
            rv = d.get('rvalue', {}); op = rv.get('detail', {}).get('operand', {})
            typ = op.get('detail', {}).get('constant', {}).get('type', {})
            unit = (not dest.get('projection') and dest.get('local', 0) > raw.get('arg_count', 0)
                    and rv.get('kind') == 'Use' and op.get('kind') == 'Constant'
                    and typ.get('kind') == 'Tuple' and typ.get('detail', {}).get('elements') == [])
            dead_discriminant = (not dest.get('projection') and dest.get('local', 0) > raw.get('arg_count', 0)
                                 and dest['local'] not in used and rv.get('kind') == 'Discriminant'
                                 and not rv.get('detail', {}).get('place', {}).get('projection'))
            if st['kind'] != 'Assign' or not (unit or dead_discriminant or place_key(dest) in flags):
                return False
    return True


def prove_handoff(data, raw, action):
    refs = set(action.get('basicBlockRefs', []))
    if action.get('controlRefs') or not pure_blocks(raw, refs):
        return None
    blocks = {f"bb{b['basic_block']}": b for b in raw['basic_blocks']}
    nodes = {n['id']: n for n in data.get('execution', {}).get('nodes', [])}
    scopes = {s['id']: s for s in data.get('readingScopes', []) if s['kind'] == 'loop'}
    actions = {a['id']: a for p in data.get('phases', []) for g in p['goals'] for a in g['actions']}
    def expand(members):
        result = set()
        for m in members:
            for p in data.get('phases', []):
                for g in p['goals']:
                    for a in g['actions']:
                        if m['ref'] in (p['id'], g['id'], a['id']): result.add(a['id'])
        return result
    outgoing = [e for e in data.get('execution', {}).get('edges', [])
                if nodes.get(e['from'], {}).get('actionRef') == action['id']]
    if not outgoing:
        return None
    proof = []
    for edge in outgoing:
        scope = scopes.get(edge.get('readingScopeRef'))
        target = nodes.get(edge['to'], {})
        if (edge.get('kind') != 'loop-continue' or not edge.get('evidenceRefs') or not scope
                or action['id'] not in expand(scope['members'])):
            return None
        entry = actions.get(scope.get('repeat', {}).get('entryActionRef'), {})
        target_refs = set(target.get('basicBlockRefs', []))
        # The exact Goto chain must reach the declared loop entry's BB evidence.
        if not target_refs or not target_refs & set(entry.get('basicBlockRefs', [])):
            return None
        exits = set()
        for ref in refs:
            seen = set(); current = ref
            while current in refs and current not in seen:
                seen.add(current)
                current = 'bb' + str(blocks[current]['terminator']['detail']['target'])
            if current in refs: return None
            exits.add(current)
        if not exits <= target_refs:
            return None
        # A back edge must close a real normal MIR cycle, not an arbitrary Goto.
        todo = list(exits); reached = set()
        while todo:
            ref = todo.pop()
            if ref in reached or ref not in blocks or blocks[ref].get('is_cleanup'): continue
            reached.add(ref)
            todo.extend('bb' + str(i) for i in blocks[ref]['terminator'].get('successors', []))
        if not refs <= reached:
            return None
        proof.append(edge['id'])
    return dict(actionRef=action['id'], bbRefs=sorted(refs), executionEdgeRefs=proof)
