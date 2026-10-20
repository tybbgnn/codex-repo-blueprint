"""Canonical MIR facts and ownership graph; no profile or body lookup."""
from collections import Counter, defaultdict, deque
from copy import deepcopy
from pathlib import Path
import re
from ledger_lib import read, PACKAGE

OWNERSHIP = read(PACKAGE / 'references/stage-io.json')['stages']['S2']['ownership']
DEPTH = OWNERSHIP['depth']


def bb_order(values):
    return sorted(values, key=lambda value: int(value[2:]))


def edge_condition(term, index, target):
    kind, detail = term['kind'], term.get('detail') or {}
    if kind == 'SwitchInt':
        branches = detail.get('targets', [])
        return str(branches[index]['value']) if index < len(branches) else 'otherwise'
    choices = {'Call': ('normal_return', 'unwind'), 'Drop': ('normal', 'unwind'),
               'Assert': ('success', 'failure')}
    if kind in choices:
        normal, exceptional = choices[kind]
        return normal if target == detail.get('target') else exceptional
    return 'flow'


def stage1(c, proof=None):
    raw = c.load('raw-body.json')
    blocks = {f"bb{block['basic_block']}": block for block in raw['basic_blocks']}
    if len(blocks)!=len(raw['basic_blocks']):raise ValueError('model-duplicate-id: raw MIR BB')
    edges, calls, terminals = [], [], []
    for identity, block in blocks.items():
        number = block['basic_block']
        term = block['terminator']
        detail = term.get('detail') or {}
        for index, target in enumerate(term['successors']):
            edges.append(dict(id=f'm{number}.{index}', source=identity, target=f'bb{target}',
                              condition=edge_condition(term, index, target), terminator_kind=term['kind'],
                              successor_index=index, source_info=term.get('source_info')))
            if term['kind'] == 'Call':
                edges[-1]['bindingRef'] = f'call:{number}'
        if term['kind'] == 'Call':
            constant = detail['func'].get('detail', {}).get('constant', {})
            definition = constant.get('value', {}).get('detail', {}).get('definition', {})
            target = detail.get('target')
            calls.append(dict(id=f'call:{number}', bb=identity, callee=definition, func=detail['func'],
                              destination=detail.get('destination'), normal_successor=f'bb{target}' if target is not None else None,
                              unwind=detail.get('unwind'), source_info=term.get('source_info')))
        kinds = [term['kind']] if not term['successors'] else []
        unwind = (detail.get('unwind') or {}).get('kind')
        if unwind in ('Continue', 'Terminate'):
            kinds.append('Unwind' + unwind)
        for ordinal, kind in enumerate(kinds):
            terminals.append(dict(id=f't{number}.{ordinal}', kind=kind,
                                  source=identity, source_info=term.get('source_info')))
    dispatch, states = None, []
    first = raw['basic_blocks'][0]['terminator']
    if raw.get('is_coroutine') and first['kind'] == 'SwitchInt':
        dispatch = 'bb0'
        for branch in first['detail']['targets']:
            value = str(branch['value'])
            states.append(dict(value=value, entry=f"bb{branch['target']}",
                               role={'0': 'initial', '1': 'returned', '2': 'poisoned'}.get(value, 'resume')))
    summary = dict(bb_count=len(blocks), edge_count=len(edges), call_count=len(calls),
                   terminal_event_count=len(terminals), locals_count=len(raw['locals']),
                   terminators=dict(Counter(block['terminator']['kind'] for block in blocks.values())))
    from stage_engine import element_facts
    definitions = c.work / 'facts/definitions-index.json'
    index=read(definitions) if definitions.exists() else {}
    pins = c.load('input-pins.json')
    elements = element_facts(raw,index,pins,blocks,calls,proof)
    c.save('input-pins.json',pins)
    c.save('facts/definitions-index.json',index)
    # Frozen consumers keep their legacy call shape, projected from the element table.
    call_fields = ('id', 'bb', 'callee', 'func', 'destination', 'normal_successor', 'unwind', 'source_info')
    calls = [{key: row[key] for key in call_fields} for row in elements['items'] if row['kind'] == 'call']
    facts = {'elements': elements, 'blocks': blocks, 'edges': edges, 'call-bindings': calls, 'terminal-events': terminals,
             'async-states': dict(is_coroutine=bool(raw.get('is_coroutine')), dispatch=dispatch, states=states),
             'summary': summary}
    for name, value in facts.items():
        c.save('facts/' + name + '.json', value)
    return summary


def _execution_order(group, edges, blocks):
    """Return the deterministic order of one non-exceptional sequential path."""
    members = set(group['basic_block_refs'])
    def path_edge(edge):
        return (edge.get('condition') not in ('unwind', 'failure')
                and not blocks.get(edge.get('target'), {}).get('is_cleanup'))
    internal = [edge for edge in edges if path_edge(edge)
                and edge['source'] in members and edge['target'] in members]
    entries = bb_order({edge['target'] for edge in edges
                        if path_edge(edge) and edge['target'] in members and edge['source'] not in members})
    if not entries:
        targets = {edge['target'] for edge in internal}
        entries = bb_order(members - targets)
    if not entries:
        entries = group['basic_block_refs'][:1]
    if len(entries) != 1:
        raise ValueError('BB group must have exactly one entry: ' + group['id'])
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for edge in internal:
        outgoing[edge['source']].append(edge['target'])
        incoming[edge['target']].append(edge['source'])
    if any(len(outgoing[ref]) > 1 for ref in members):
        raise ValueError('BB group contains an internal branch: ' + group['id'])
    if any(len(incoming[ref]) > 1 for ref in members):
        raise ValueError('BB group contains an internal merge: ' + group['id'])
    order, seen, current = [], set(), entries[0]
    while current not in seen:
        seen.add(current)
        order.append(current)
        successors = outgoing[current]
        if not successors:
            current = None
            break
        current = successors[0]
    if seen != members:
        missing = ','.join(bb_order(members - seen))
        raise ValueError('Disconnected or non-path BB group members: ' + group['id'] + ': ' + missing)
    if current is not None and current != entries[0]:
        raise ValueError('BB group cycle must return to its entry: ' + group['id'])
    return order


def _technical_anchors_valid(refs, blocks, edges, evidence_root=None):
    """Resolve S2 evidence without depending on the independent checker."""
    known = set(blocks)
    known.update(edge['id'] for edge in edges)
    known.update('call:' + ref[2:] for ref, block in blocks.items()
                 if block.get('terminator', {}).get('kind') == 'Call')
    root = Path(evidence_root).resolve() if evidence_root is not None else None

    def valid(ref):
        if ref in known:
            return True
        match = re.fullmatch(r'(source/[^:]+):(\d+)(?:-(\d+))?', ref)
        if not match or root is None:
            return False
        path = (root / match[1]).resolve()
        source = root / 'source'
        if not path.is_relative_to(source) or not path.is_file():
            return False
        start, end = int(match[2]), int(match[3] or match[2])
        return 0 < start <= end <= len(path.read_bytes().splitlines())

    return bool(refs) and all(isinstance(ref, str) and valid(ref) for ref in refs)


def project_cfg(edges, blocks, retained):
    """Paths through omitted technical BBs become edges between retained BBs."""
    normal = defaultdict(list)
    for edge in edges:
        if (edge.get('condition') not in ('unwind', 'failure')
                and blocks[edge['source']].get('terminator', {}).get('kind') != 'Yield'
                and not blocks[edge['target']].get('is_cleanup')):
            normal[edge['source']].append(edge)
    result = []; order = {edge['id']:index for index,edge in enumerate(edges)}
    for start in bb_order(retained):
        pending = [(edge['target'], [edge['id']]) for edge in normal[start]]
        local = {edge['id']:edge for edge in normal[start]}; endpoints = {}; seen = set()
        while pending:
            target, path = pending.pop(0)
            if target in retained:
                endpoints.setdefault(target,path)
                continue
            if target in seen:
                continue
            seen.add(target)
            for edge in normal[target]:
                local[edge['id']] = edge
                pending.append((edge['target'],path+[edge['id']]))
        reverse = defaultdict(set)
        for edge in local.values():reverse[edge['target']].add(edge['source'])
        for target in bb_order(endpoints):
            can_reach = {target}; pending_back = [target]
            while pending_back:
                node = pending_back.pop()
                for source in reverse[node]:
                    if source not in can_reach:can_reach.add(source);pending_back.append(source)
            witness = [edge['id'] for edge in local.values()
                       if edge['source'] in can_reach and edge['target'] in can_reach]
            result.append(dict(id='bridge:'+start+':'+target,source=start,target=target,
                               condition='flow',path=endpoints[target],
                               cfgEdgeRefs=sorted(witness,key=order.__getitem__)))

    return result


def derive_group_order(nodes, edges, blocks):
    business = {ref for node in nodes.values() if node['kind']=='action' for ref in node['basic_block_refs']}
    projected = project_cfg(edges, blocks, business)
    edge_order = {edge['id']:index for index,edge in enumerate(edges)}
    for action in nodes.values():
        if action['kind'] != 'action':
            continue
        groups = {child: nodes[child] for child in action['children']}
        by_bb = {ref: child for child, node in groups.items() for ref in node['basic_block_refs']}
        relations = {}; evidence = defaultdict(set)
        for edge in projected:
            if edge['source'] not in by_bb or edge['target'] not in by_bb:
                continue
            source, target = by_bb[edge['source']], by_bb[edge['target']]
            if source != target:
                relations.setdefault((source, target), []).append(edge['path'])
                evidence[(source,target)].update(edge['cfgEdgeRefs'])
        action['group_order_basis'] = dict(method='normal CFG paths through technical BBs',
            edges=[dict(**{'from':source,'to':target},paths=paths,
                        cfgEdgeRefs=sorted(evidence[(source,target)],key=edge_order.__getitem__))
                   for (source,target), paths in sorted(relations.items())])


def ownership(ledger, blocks, edges, raw, event_macro_artifacts=None, evidence_root=None):
    from canonical_contract import validate
    errors = validate(ledger, read(PACKAGE / 'references/ledger-schema.json'))
    if errors:
        raise ValueError('Ledger schema: ' + '; '.join(errors[:12]))
    nodes, parents, declared = {}, {}, {}
    for authored in ledger['nodes']:
        node = deepcopy(authored)
        key = node['id']
        if key in nodes:
            raise ValueError('Duplicate semantic node: ' + key)
        if node['kind'] not in DEPTH:
            raise ValueError('Noncanonical node kind: ' + node['kind'])
        node.pop('owner_ref', None)
        if 'technical_reasons' in node:
            raise ValueError('Technical reasons are derived from S1 facts, not authored: ' + key)
        node.pop('technical', None)
        node['children'] = node.pop('members')
        node.pop('basic_block_order', None)  # generated below from the CFG
        declared[key] = []
        node['depth'] = DEPTH[node['kind']]
        nodes[key] = node
    for node in list(nodes.values()):
        for child in node['children']:
            if child in blocks:
                if node['kind'] not in ('root', 'bb_group'):
                    raise ValueError('BB member requires bb_group owner: ' + child)
                if child in nodes:
                    raise ValueError('Repeated or colliding BB ownership: ' + child)
                nodes[child] = dict(id=child, kind='bb', name=child, children=[], depth=DEPTH['bb'], evidence=[child])
                declared[child] = []
    for key, node in nodes.items():
        for child in node['children']:
            if child not in nodes:
                raise ValueError('Unresolved child: ' + child)
            if child in parents:
                raise ValueError('Repeated ownership: ' + child)
            parents[child] = key
    for key, node in nodes.items():
        parent_kind = nodes[parents[key]]['kind'] if key in parents else None
        if node['kind'] == 'bb_group' and parent_kind not in ('action', 'root'):
            raise ValueError('BB group requires action or ROOT technical owner: ' + key)
        if node['kind'] == 'bb' and parent_kind not in ('root', 'bb_group'):
            raise ValueError('BB leaf requires bb_group owner: ' + key)
    root = ledger['root']
    if not isinstance(root, str) or root not in nodes or nodes[root]['kind'] != 'root':
        raise ValueError('Ledger root must identify the root node')
    phases = ledger['phase_order']
    if len(set(phases)) != len(phases) or set(phases) != {key for key, node in nodes.items() if node['kind'] == 'phase'}:
        raise ValueError('phase_order must contain each phase exactly once')
    allowed = OWNERSHIP['children']
    for node in nodes.values():
        if any(nodes[child]['kind'] not in allowed[node['kind']] for child in node['children']):
            raise ValueError('Invalid child kind: ' + node['id'])
    active, finished = set(), set()

    def collect(key):
        if key in active:
            raise ValueError('Ownership cycle: ' + key)
        if key in finished:
            return nodes[key]['basic_block_refs']
        active.add(key)
        node = nodes[key]
        refs = {key} if node['kind'] == 'bb' else {ref for child in node['children'] for ref in collect(child)}
        if node['kind'] == 'bb' and (key not in blocks or node['children']):
            raise ValueError('Invalid BB leaf: ' + key)
        if declared[key] and set(declared[key]) != refs:
            raise ValueError('Declared membership disagrees with children: ' + key)
        node['basic_block_refs'] = bb_order(refs)
        node['reading_parent'] = parents.get(key)
        active.remove(key)
        finished.add(key)
        return node['basic_block_refs']

    collect(root)
    if finished != set(nodes) or {key for key, node in nodes.items() if node['kind'] == 'bb'} != set(blocks):
        raise ValueError('Incomplete BB coverage or orphaned ownership')
    business_edges = project_cfg(edges, blocks, {ref for n in nodes.values() if n['kind']=='action' for ref in n['basic_block_refs']})
    for node in nodes.values():
        if node['kind'] != 'bb_group':
            continue
        parent = nodes.get(parents.get(node['id']), {})
        if parent.get('kind') != 'root' and any(blocks[ref].get('is_cleanup') for ref in node['basic_block_refs']):
            raise ValueError('Business BB group cannot contain cleanup blocks: ' + node['id'])
        effective_edges = edges if parent.get('kind')=='root' else business_edges
        order = _execution_order(node, effective_edges, blocks)
        node['basic_block_order'] = order
        suffix = node['id'].rsplit('/', 1)[-1]
        expected = 'C' + order[0][2:]
        if suffix != expected:
            raise ValueError('BB group ID must end with execution-first ' + expected + ': ' + node['id'])

    records = ledger.get('granularity', {}).get('technicalBlocks', [])
    from classification_registry import technical_record_valid
    from technical_boundary import apply_review
    strict_categories = {'drop', 'instrumentation'}
    registry_categories = {'cleanup', 'state_dispatch', 'async_mechanism', 'unwind'}
    by_ref, technical, strict_records = {}, {}, []
    for record in records:
        ref = record.get('bbRef')
        if ref not in blocks or ref in by_ref:
            raise ValueError('Invalid or duplicate technical block record: ' + str(ref))
        category = record.get('category')
        if category in strict_categories:
            strict_records.append(record)
        elif category in registry_categories:
            if (not _technical_anchors_valid(record.get('evidenceRefs'), blocks, edges, evidence_root)
                    or not technical_record_valid(raw, blocks[ref], record, event_macro_artifacts)):
                raise ValueError('Invalid technical block proof: ' + ref)
            technical[ref] = dict(record)
        else:
            raise ValueError('Unsupported technical block category: ' + str(category))
        by_ref[ref] = record
    root_refs = {ref for child in nodes[root]['children']
                 if nodes[child]['kind'] in ('bb', 'bb_group')
                 for ref in nodes[child]['basic_block_refs']}
    missing = root_refs - set(by_ref)
    if missing:
        raise ValueError('ROOT technical BB lacks a valid record: ' + ','.join(bb_order(missing)))
    apply_review(blocks, {ref: parents.get(ref) for ref in root_refs}, technical,
                 strict_records, raw, event_macro_artifacts)
    def mark_technical(key):
        node = nodes[key]
        node['technical'] = True
        node['technical_reasons'] = [dict(type=by_ref[ref]['category'], evidence=evidence,
                                                  value=by_ref[ref]['reason'])
                                     for ref in node['basic_block_refs']
                                     for evidence in by_ref[ref]['evidenceRefs']]
        if not node['technical_reasons']:
            raise ValueError('Empty technical group: ' + key)
        for child in node['children']:
            mark_technical(child)
    for child in nodes[root]['children']:
        if nodes[child]['kind'] in ('bb', 'bb_group'):
            mark_technical(child)
    from reading_groups import validate_reading_groups
    validate_reading_groups(nodes, parents, blocks)
    derive_group_order(nodes, edges, blocks)
    return nodes, parents


def boundaries(nodes, edges, terminals):
    outgoing = defaultdict(list)
    for edge in edges:
        outgoing[edge['source']].append(edge)
    for node in nodes.values():
        if node['kind'] not in ('bb_group', 'technical_group'):
            continue
        members = set(node['basic_block_refs'])
        entries = bb_order({edge['target'] for edge in edges if edge['target'] in members and edge['source'] not in members})
        entries = entries or node['basic_block_refs'][:1]
        exits = [edge for edge in edges if edge['source'] in members and edge['target'] not in members]
        events = [event for event in terminals if event['source'] in members]
        ports = []
        for entry in entries:
            seen, pending = set(), [entry]
            while pending:
                current = pending.pop()
                if current not in seen:
                    seen.add(current)
                    pending.extend(edge['target'] for edge in outgoing[current] if edge['target'] in members)
            reachable = [edge for edge in exits if edge['source'] in seen]
            ports.append(dict(entry_block=entry, reachable_exit_blocks=bb_order({edge['source'] for edge in reachable}),
                              reachable_exit_edge_ids=[edge['id'] for edge in reachable],
                              reachable_terminal_event_ids=[event['id'] for event in events if event['source'] in seen]))
        node.update(entry_blocks=entries, exit_blocks=bb_order({edge['source'] for edge in exits}),
                    exit_edge_ids=[edge['id'] for edge in exits], terminal_event_ids=[event['id'] for event in events], port_transfer=ports)
    return outgoing


def validate_goal_contracts(nodes, ledger):
    from goal_contracts import contract_violations, fragmentation_runs
    records = ledger.get('granularity', {}).get('goalContracts', [])
    by_goal = {}
    for record in records:
        goal = record.get('goalRef')
        if goal in by_goal:
            raise ValueError('Duplicate goal contract: ' + str(goal))
        by_goal[goal] = record
    goals = {key: node for key, node in nodes.items() if node['kind'] == 'goal'}
    if set(by_goal) != set(goals):
        raise ValueError('Goal contracts must cover each goal exactly once')
    for goal, node in goals.items():
        violations = contract_violations(by_goal[goal], node['children'])
        if violations:
            raise ValueError('Goal contract violation for ' + goal + ': ' + '; '.join(violations))
    phases = []
    for phase_ref in ledger['phase_order']:
        phase = nodes[phase_ref]
        phases.append({'id': phase_ref, 'goals': [
            {'id': goal_ref, 'actions': [{'id': action_ref} for action_ref in nodes[goal_ref]['children']]}
            for goal_ref in phase['children']]})
    fragmented = [run for run in fragmentation_runs(phases, records)
                  if run.get('basis') == 'contractRef']
    if fragmented:
        raise ValueError('Three or more adjacent singleton goals share one contract: ' + str(fragmented))


def derived_instrumentation_records(proof):
    """Translate S1 proofs into the same witnesses used for shell instrumentation."""
    proof = proof or {}
    components = proof.get('regions', []) if proof.get('kind') == 'instrumentation_regions' else [proof]
    extension_refs = {f'bb{number}' for component in components
                      for key in ('source_less_goto_blocks', 'fake_return_blocks')
                      for number in component.get(key, [])}
    conflicts = set(proof.get('conflicts', []))
    records = []
    for ref in bb_order(set(proof.get('technical_blocks', {})) - conflicts):
        role = proof.get('block_roles', {}).get(ref)
        if proof.get('kind') == 'event_macro':
            role = 'event_macro'
        elif role != 'event_macro':
            role = 'span_wrapper_extension' if ref in extension_refs else 'instrumentation_base'
        record = dict(bbRef=ref, category='instrumentation',
                      reason=('tracing event macro expansion' if role == 'event_macro'
                              else 'generated tracing span wrapper'),
                      evidenceRefs=[ref], factSha256=proof['technical_blocks'][ref], blockRole=role)
        if role == 'event_macro':
            record['eventMacroProof'] = proof.get('block_proofs', {}).get(ref)
        records.append(record)
    return records


def validate_proven_instrumentation(ledger, proof):
    """Every proven BB must have a witness and exclusively ROOT technical ownership."""
    proof = proof or {}
    proven = set(proof.get('technical_blocks', {})) - set(proof.get('conflicts', []))
    if not proven:
        return
    records = {r.get('bbRef'): r for r in ledger.get('granularity', {}).get('technicalBlocks', [])}
    nodes = {n['id']: n for n in ledger['nodes']}
    parents = {child: n['id'] for n in ledger['nodes'] for child in n['members']}
    components = proof.get('regions', []) if proof.get('kind') == 'instrumentation_regions' else [proof]
    errors = []
    for ref in bb_order(proven):
        component = next((p for p in components if ref in p.get('technical_blocks', {})), proof)
        kind = component.get('kind', proof.get('kind'))
        site = proof.get('block_proofs', {}).get(ref, {}).get('callSite', component.get('proof'))
        context = f'region/call site={site}; bbs={ref}; proof kind={kind}'
        if records.get(ref, {}).get('category') != 'instrumentation':
            errors.append('Unclaimed proven instrumentation: ' + context)
        parent = parents.get(ref)
        if parent is None:
            errors.append('Unclaimed proven technical ownership: ' + context)
        seen = set()
        while parent and parent != ledger['root']:
            if parent in seen:
                raise ValueError('Ownership cycle: ' + parent)
            seen.add(parent)
            node = nodes.get(parent, {})
            if node.get('kind') in ('action', 'bb_group'):
                errors.append('Proven instrumentation in business group/action ' + parent + ': ' + context)
            parent = parents.get(parent)
    if errors:
        raise ValueError('\n'.join(errors))


def relocate_proven_blocks(ledger, proven):
    """Move proven instrumentation to ROOT; retain business actions and bridge via CFG later."""
    if not proven:
        return ledger, dict(movedBlocks=[], removedGroups=[], renamedGroups={})
    nodes = {node['id']: node for node in ledger['nodes']}
    root = nodes[ledger['root']]
    removed = set(); renamed = {}; moved = set()
    for key, node in list(nodes.items()):
        if node['kind'] != 'bb_group' or key in root['members']:
            continue
        selected = set(node['members']) & proven
        if not selected:
            continue
        moved.update(selected)
        node['members'] = [ref for ref in node['members'] if ref not in selected]
        for ref in selected:
            annotation = node.get('bb_annotations', {}).pop(ref, None)
            if annotation is not None:
                root.setdefault('bb_annotations', {})[ref] = annotation
        if not node['members']:
            removed.add(key)
            continue
        node['evidence'] = [ref for ref in node['evidence'] if ref in node['members']] or node['members'][:1]
        # Existing group members are a sequential path; its first remaining member is deterministic.
        first = node['members'][0]
        replacement = key.rsplit('/', 1)[0] + '/C' + first[2:]
        if replacement != key:
            renamed[key] = replacement
    for node in nodes.values():
        node['members'] = [ref for ref in node['members'] if ref not in removed]
        if node['kind'] == 'action' and not node['members']:
            raise ValueError('STOP-empty-action: ' + node['id'])
    root['members'].extend(ref for ref in bb_order(moved) if ref not in root['members'])
    ledger['nodes'] = [node for node in ledger['nodes'] if node['id'] not in removed]
    def rewrite(value):
        if isinstance(value, dict):
            return {renamed.get(key, key): rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return renamed.get(value, value) if isinstance(value, str) else value
    ledger = rewrite(ledger)
    return ledger, dict(movedBlocks=bb_order(moved), removedGroups=sorted(removed), renamedGroups=renamed)


def expand_technical_decisions(ledger, elements):
    """Only classification/reasons are authored; MIR witness shape comes from S1."""
    ledger=deepcopy(ledger)
    facts={row['id']:row for row in elements['items'] if row['kind']=='bb'}
    for record in ledger.get('granularity',{}).get('technicalBlocks',[]):
        ref=record['bbRef']
        if ref not in facts:raise ValueError('model-unknown-bb: '+str(ref))
        witness=facts[ref]['proofs']['mirWitness']
        if 'factSha256' in record and record['factSha256']!=witness['factSha256']:
            raise ValueError('model-stale-witness: '+ref)
        reason=record['reason'];overrides=record.pop('operationReasons',{})
        if any(not isinstance(value,str) or not value.strip() for value in overrides.values()):
            raise ValueError('model-proof-reason: '+ref)
        if 'terminatorReason' in record and (not isinstance(record['terminatorReason'],str) or not record['terminatorReason'].strip()):
            raise ValueError('model-proof-reason: '+ref)
        known={str(op['statementIndex']) for op in witness['operations']}
        if set(overrides)-known:raise ValueError('model-unknown-operation: '+ref)
        record['factSha256']=witness['factSha256']
        record['operationKinds']=[op['kind'] for op in witness['operations']]
        record['operationProofs']=[dict(op,reason=overrides.get(str(op['statementIndex']),reason)) for op in witness['operations']]
        record['terminatorProof']=dict(witness['terminator'],reason=record.pop('terminatorReason',reason))
    return ledger


def prepare_instrumentation_ledger(ledger, proof, elements=None):
    ledger = expand_technical_decisions(ledger,elements) if elements is not None else deepcopy(ledger)
    derived = derived_instrumentation_records(proof)
    records = ledger.setdefault('granularity', {}).setdefault('technicalBlocks', [])
    by_ref = {r.get('bbRef'): r for r in derived}
    for record in records:
        ref = record.get('bbRef')
        if ref in by_ref and record != by_ref[ref]:
            raise ValueError('Ledger conflicts with derived instrumentation record: ' + ref)
    authored = {r.get('bbRef') for r in records}
    records.extend(r for r in derived if r['bbRef'] not in authored)
    ledger, _ = relocate_proven_blocks(ledger, set(by_ref))
    validate_proven_instrumentation(ledger, proof)
    return ledger, derived


def canonical_selection(ledger, elements, hierarchy):
    """Project authored destinations onto the only BB ownership tree."""
    nodes = hierarchy['nodes']
    owners = {bb: key for key, node in nodes.items() if node['kind'] == 'action'
              for bb in node['basic_block_refs']}
    required = {row['id']: row for row in elements['items'] if row['kind'] in ('call', 'body')}
    authored = ledger['selection']
    decisions = {}
    for item in authored['items']:
        key = item.get('id')
        if key not in required:
            raise ValueError('model-unknown-id: ' + str(key))
        if key in decisions:
            raise ValueError('model-duplicate-id: ' + str(key))
        decisions[key] = deepcopy(item)
    rules = authored.get('foldRules', [])
    if len({rule.get('targetCategory') for rule in rules}) != len(rules):
        raise ValueError('model-duplicate-fold-rule: targetCategory')
    for rule in rules:
        if rule.get('targetCategory') not in ('std', 'third_party') or not rule.get('reason'):
            raise ValueError('model-fold-rule: only std/third_party with a reason')
        for key, element in required.items():
            if element['kind'] == 'call' and element['targetCategory'] == rule['targetCategory']:
                if key in decisions:
                    continue
                decisions[key] = dict(id=key, disposition='folded', reason=rule['reason'])
    if set(decisions) != set(required):
        raise ValueError('model-missing-id: ' + ', '.join(sorted(set(required)-set(decisions))))
    for key, decision in decisions.items():
        if decision.get('disposition') not in ('shown', 'technical', 'folded'):
            raise ValueError('model-destination: ' + key)
        if decision['disposition'] == 'folded' and not str(decision.get('reason', '')).strip():
            raise ValueError('model-fold-reason: ' + key)
        row = required[key]
        effect=row.get('proofs',{}).get('informationEffect')
        if effect:
            from check_model import information_destination
            expected=information_destination(effect)
            if decision['disposition']!='technical' and decision['disposition']!=expected:
                raise ValueError('model-information-destination: '+key)
            decision['reason']=effect['kind']+': '+effect['why']+'; '+str(effect.get('line',''))
            decision['informationEffect']=deepcopy(effect)
            decision['semanticRole']='business' if expected=='shown' else 'adapter'
            decision['sourceRefs']=[key]
        refs = [row['bb']] if row['kind'] == 'call' else row['bbRefs']
        action_refs = sorted({owners[ref] for ref in refs if ref in owners})
        action = action_refs[0] if len(action_refs) == 1 else None
        for field in ('ownerAction', 'ownerActionRef'):
            if field in decision and decision[field] != action:
                raise ValueError('model-owner-mismatch: ' + key)
            decision.pop(field, None)
        if action:
            decision['ownerActionRef'] = action
        if row['kind'] == 'call':
            decision['bindingRef'] = key
            if row['targetCategory'] in ('std','third_party'):
                decision.setdefault('sourceRefs',[key])
        if row['kind'] == 'call' and row['targetCategory'] == 'local_mir':
            if decision.get('semanticRole') not in ('business', 'adapter') or not decision.get('sourceRefs'):
                raise ValueError('model-local-source: ' + key)
            if decision['semanticRole'] == 'business' and decision['disposition'] != 'shown':
                raise ValueError('model-local-business: ' + key)
    return dict(items=[decisions[key] for key in required])


def derive_loop_ranges(presentation, hierarchy, fact_edges, blocks):
    """Derive minimal reading intervals; prove every enclosed exit from MIR."""
    nodes = hierarchy['nodes']
    order = []
    def visit(ref):
        node = nodes[ref]
        if node['kind'] == 'action':
            order.append(ref)
        else:
            for child in node.get('children', []):
                if child in nodes:
                    visit(child)
    for ref in hierarchy.get('phase_order', []):
        visit(ref)
    if not order:
        order = [key for key, node in nodes.items() if node['kind'] == 'action']
    adjacency, reverse = defaultdict(set), defaultdict(set)
    for edge in fact_edges:
        if edge.get('condition') in ('unwind', 'failure') or blocks.get(edge['target'], {}).get('is_cleanup'):
            continue
        adjacency[edge['source']].add(edge['target'])
        reverse[edge['target']].add(edge['source'])
    def reachable(starts, graph):
        seen = set(starts); pending = list(seen)
        while pending:
            for target in graph[pending.pop()]:
                if target not in seen:
                    seen.add(target); pending.append(target)
        return seen
    result = {}
    for scope in presentation.get('readingScopes', []):
        if scope.get('kind') != 'loop':
            continue
        entry = scope.get('repeat', {}).get('entryActionRef')
        if entry not in order or not nodes[entry].get('basic_block_refs'):
            raise ValueError('Loop scope has invalid entryActionRef: ' + str(entry))
        starts = set(nodes[entry]['basic_block_refs'])
        forward = reachable(starts, adjacency); backward = reachable(starts, reverse)
        core = forward & backward
        if not any(target in starts and (source == target or source in reachable({target}, adjacency))
                   for source in core for target in adjacency[source]):
            raise ValueError('Loop scope has no MIR return to entry: ' + scope['id'])
        real = [ref for ref in order if core.intersection(nodes[ref].get('basic_block_refs', []))]
        first, last = min(order.index(ref) for ref in real), max(order.index(ref) for ref in real)
        members = order[first:last + 1]
        extras = set(members) - set(real)
        common = scope.get('commonAfter', {}).get('actionRef')
        if common in members:
            raise ValueError('Loop commonAfter overlaps derived interval: ' + scope['id'])
        stops = set(nodes.get(common, {}).get('basic_block_refs', []))
        # A typed MIR terminal is a certificate; arbitrary graph sinks are not.
        stops.update(ref for ref, block in blocks.items() if not adjacency[ref]
                     and block.get('terminator', {}).get('kind') in
                     ('Return', 'UnwindResume', 'UnwindTerminate', 'CoroutineDrop', 'Unreachable'))
        other = {bb for ref in order if ref not in members and ref != common
                 for bb in nodes[ref].get('basic_block_refs', [])}
        for ref in sorted(extras):
            seeds = set(nodes[ref].get('basic_block_refs', []))
            if not seeds or seeds & backward or not seeds <= forward:
                raise ValueError('Loop in-loop exit is unrelated or can return to entry: ' + ref)
            reached = set(); pending = list(seeds)
            while pending:
                bb = pending.pop()
                if bb in stops or bb in reached:
                    continue
                if bb in other:
                    raise ValueError('Loop in-loop exit reaches unrelated action; split precise ranges: ' + ref)
                reached.add(bb); pending.extend(adjacency[bb])
            # Least fixed point rejects sinks and divergent cycles, even if one branch exits.
            proven = set(stops)
            while True:
                added = {bb for bb in reached - proven if adjacency[bb] and adjacency[bb] <= proven}
                if not added:
                    break
                proven.update(added)
            if not seeds <= proven:
                raise ValueError('Loop in-loop exit lacks commonAfter/terminal proof: ' + ref)
        scope['members'] = [dict(kind='action', ref=ref) for ref in members]
        result[scope['id']] = members
    return result


def stage2(c):
    ledger, derived = prepare_instrumentation_ledger(c.ledger(2), c.load('facts/instrumentation-candidates.json'), c.load('facts/elements.json'))
    blocks, edges = c.load('facts/blocks.json'), c.load('facts/edges.json')
    raw = c.load('raw-body.json')
    from classification_registry import load_event_macro_artifacts
    nodes, parents = ownership(ledger, blocks, edges, raw, load_event_macro_artifacts(c.work), c.work)
    validate_goal_contracts(nodes, ledger)
    outgoing = boundaries(nodes, edges, c.load('facts/terminal-events.json'))
    hierarchy = dict(root=ledger['root'], phase_order=ledger['phase_order'], nodes=nodes)
    if ledger.get('semantic_action_ids') is not None:
        hierarchy['semantic_action_ids'] = ledger['semantic_action_ids']
    loop_ranges = derive_loop_ranges(c.ledger(4), hierarchy, edges, blocks) if any(
        row.get('kind') == 'loop' for row in ledger['granularity'].get('ranges', [])) else {}
    for record in ledger['granularity'].get('ranges', []):
        if record.get('kind') == 'loop':
            ref = record.get('readingScopeRef', record.get('id'))
            if ref not in loop_ranges:
                raise ValueError('Loop range lacks readingScope: ' + str(ref))
            record['memberActionRefs'] = loop_ranges[ref]
    c.save('stage2/hierarchy.json', hierarchy)
    elements = c.load('facts/elements.json')
    ledger['selection'] = canonical_selection(ledger, elements, hierarchy)
    ledger['granularity']['technicalIntervals'] = [row['proofs']['technicalIntervals'] for row in elements['items']
        if row['kind']=='bb' and row.get('proofs',{}).get('technicalIntervals')]
    for name in ('selection', 'granularity'):
        c.save('stage2/' + name + '.json', ledger[name])
    lines = ['bb\tdirect_parent\tfull_path\tfactual_operations\treal_exits']
    for key in bb_order(blocks):
        path, parent = [key], parents.get(key)
        while parent:
            path.insert(0, parent)
            parent = parents.get(parent)
        block = blocks[key]
        operations = ','.join(statement['kind'] for statement in block['statements']) + ';' + block['terminator']['kind']
        exits = ','.join(edge['id'] + '->' + edge['target'] for edge in outgoing[key])
        lines.append('\t'.join([key, parents.get(key, ''), ' > '.join(path), operations, exits]))
    c.save('stage2/blocks-ledger.tsv', ('\n'.join(lines) + '\n').encode())
    source = c.inputs / 'ledgers/summaries.json'
    summaries = read(source) if source.exists() else {'units': {key: dict(kind=node['kind'], text=node.get('summary', node.get('result', '')))
                 for key, node in nodes.items() if node['kind'] in ('phase', 'goal', 'action')}}
    if 'units' not in summaries:
        raise ValueError('Summary ledger must use units with kind/text; migrate authored summaries explicitly')
    c.save('stage2/reading-summaries.json', summaries)
    return hierarchy
