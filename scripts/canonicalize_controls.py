"""Canonicalize stage-4 presentation using explicit guard identity, never prose.

Input objects are mutated before stage-6 evidence/ownership is emitted. A range
origin is a body-free binding of its readingScope; the scope paints the range.
Only adjacent sibling guards with identical decision partitions are coalesced.
Distinct invocations, edge guards, order, and evidence are retained.
"""
from collections import defaultdict


def canonicalize(presentation, member_guards, action_ids, summaries=None):
    controls = presentation['controls']
    byid = {c['id']: c for c in controls}
    owners = presentation['ownerControls']
    evidence = presentation['controlEvidence']
    scopes = presentation['readingScopes']
    decisions = presentation['decisions']
    guard_by_ref = defaultdict(list)
    for g in member_guards:
        if g.get('alternativeBranchRef'):
            continue  # Exhaustive alt branches retain their canonical scope/decision.
        guard_by_ref[g['controlRef']].append(g)
    def remove(ref):
        for refs in owners.values():
            if ref in refs: refs.remove(ref)
        controls[:] = [c for c in controls if c['id'] != ref]
        evidence.pop(ref, None)
    def signature(g):
        return g['decisionRef'], tuple(sorted(g['takeValues'])), tuple(sorted(g['skipValues']))
    # Scope aliases have no content and are rendered exactly once at the members.
    for scope in scopes:
        origin = byid.get(scope.get('originControlRef'))
        if not origin: continue
        if origin.get('notes') and origin['notes'] != [scope['condition']]:
            raise ValueError('Scope origin contains independent content: ' + origin['id'])
        origin.pop('notes', None)
        members = {m['ref'] for m in scope['members']}
        for key, refs in owners.items():
            if action_ids[key] not in members: continue
            for ref in list(refs):
                c = byid[ref]
                gs = guard_by_ref[ref]
                if (c['kind'] != 'opt' or not c.get('children') or not gs
                        or any(g['decisionRef'] != scope['decision']['variable']
                               or set(g['takeValues']) != set(scope.get('takeValues', [])) for g in gs)):
                    continue
                # Preserve the invocation roots and their exact original position.
                at = refs.index(ref)
                refs[at:at+1] = [ch['id'] for ch in c['children']]
                for child in c['children']:
                    controls.append(child); byid[child['id']] = child
                    evidence[child['id']] = evidence[ref]
                remove(ref)
                for g in gs:
                    g.update(controlRef=origin['id'], readingScopeRef=scope['id'],
                             condition=scope['condition'], skip=scope['skip'])
        # A local binary choice already expressed by the scope has no second box.
        q = next(q for q in decisions if q['id'] == scope['decision']['variable'])
        old = byid.get(q.get('controlRef'))
        if q.get('type') == 'local' and old and old['condition'] == scope['condition']:
            remove(old['id']); q.pop('controlRef', None); q.pop('branchBindings', None)
    # Same guard, same owner, consecutive calls: one opt with ordered children.
    for refs in owners.values():
        previous = None
        for ref in list(refs):
            gs = guard_by_ref[ref]
            c = byid[ref]
            if c['kind'] != 'opt' or not c.get('children') or not gs:
                previous = None; continue
            if previous and signature(guard_by_ref[previous][0]) == signature(gs[0]):
                byid[previous]['children'].extend(c['children'])
                evidence[previous] = list(dict.fromkeys(evidence[previous] + evidence[ref]))
                remove(ref)
                for g in gs: g['controlRef'] = previous
                guard_by_ref[previous].extend(gs)
            else: previous = ref
    # Opt carries its local decision partition directly; no empty sibling alt.
    for q in decisions:
        old = byid.get(q.get('controlRef'))
        if q.get('type') != 'local' or not old or old.get('kind') != 'alt': continue
        matches = [c for c in controls if c['kind'] == 'opt' and c.get('children')
                   and any(g['decisionRef'] == q['id'] for g in guard_by_ref[c['id']])]
        if len(matches) != 1: continue
        c = matches[0]; g = guard_by_ref[c['id']][0]
        q.update(controlRef=c['id'], takeValues=g['takeValues'], skipValues=g['skipValues'])
        q.pop('branchBindings', None)
        evidence[c['id']] = list(dict.fromkeys(evidence[c['id']] + evidence[old['id']]))
        remove(old['id'])
    # A branch condition already expresses the result when the texts are equal.
    def clean(c):
        for b in c.get('branches', []):
            if b.get('outcome') == b.get('condition'): b.pop('outcome')
            for child in b.get('children', []): clean(child)
        for child in c.get('children', []): clean(child)
    for c in controls: clean(c)
    # A sole action already owns this exact outcome in its collapsed synopsis.
    # Remove only the repeated display field; retain branches, guards and evidence.
    units = (summaries or {}).get('units', summaries or {})
    for scope in scopes:
        for branch in scope.get('branches', []):
            ref = sole_action(branch)
            text = units.get(ref, {}).get('text')
            if text and same_text(branch.get('outcome'), text) and not branch.get('effect'):
                branch.pop('outcome', None)
    return presentation


def same_text(a, b):
    return bool(a and b) and ' '.join(a.split()) == ' '.join(b.split())


def sole_action(branch):
    members = branch.get('members', [])
    if len(members) == 1 and members[0].get('kind') == 'action':
        return members[0]['ref']
    return None
