"""Group source-reviewed action contracts; never infer semantics from node counts."""

def partition_actions(actions, contracts, assignments):
    groups = []
    seen = set()
    for action in actions:
        key, phase = action['key'], action['phase']
        assignment = assignments[key]
        contract = contracts[assignment['contractRef']]
        signature = (phase, assignment['contractRef'], contract['entryMode'])
        if not groups or groups[-1]['signature'] != signature:
            if signature in seen:
                raise ValueError('Nonadjacent contract requires a separate execution occurrence: ' + str(signature))
            seen.add(signature)
            groups.append(dict(signature=signature, contractRef=signature[1], phase=phase, members=[]))
        groups[-1]['members'].append(key)
    if set(assignments) != {a['key'] for a in actions}:
        raise ValueError('Contract assignments must cover exactly the action inventory')
    return groups


def contract_violations(record, expected_actions):
    bad = []
    members = record.get('memberContracts', [])
    refs = [m.get('actionRef') for m in members]
    if set(refs) != set(expected_actions) or len(refs) != len(set(refs)):
        bad.append('member coverage or uniqueness')
    for field in ('contractRef', 'entryMode', 'completion', 'cohesionReason', 'evidenceRefs'):
        if not record.get(field):
            bad.append('missing ' + field)
    for m in members:
        if (m.get('contractRef'), m.get('entryMode')) != (record.get('contractRef'), record.get('entryMode')):
            bad.append('mixed completion contracts or entry modes: ' + str(m.get('actionRef')))
        if not m.get('evidenceRefs'):
            bad.append('missing member evidence: ' + str(m.get('actionRef')))
    return bad


def fragmentation_runs(phases, records):
    """Flag adjacent singleton goals; target/receiver matches require semantic review."""
    by_goal = {r.get('goalRef'): r for r in records}
    found = []
    for phase in phases:
        for field in ('contractRef', 'targetRef', 'receiverRef'):
            run, previous = [], None
            def flush():
                if len(run) >= 3:
                    found.append({'phaseRef': phase['id'], 'basis': field,
                                  'signature': list(previous), 'goalRefs': list(run)})
            for goal in phase.get('goals', []):
                record = by_goal.get(goal['id'], {})
                value, mode = record.get(field), record.get('entryMode')
                signature = (value, mode) if value and mode and len(goal.get('actions', [])) == 1 else None
                if signature != previous or signature is None:
                    flush(); run = []
                previous = signature
                if signature is not None:
                    run.append(goal['id'])
            flush()
    return found


def small_body_ratio(bb_count, goals, actions):
    """Diagnostic only: counts never determine semantic boundaries."""
    if 0 < bb_count <= 200 and actions >= 4 and goals / actions >= 0.8:
        return {'bbCount': bb_count, 'goals': goals, 'actions': actions,
                'ratio': goals / actions, 'threshold': 0.8, 'severity': 'warning'}
    return None
