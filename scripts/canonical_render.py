"""Project canonical semantic ledgers into the frozen renderer contract."""
from copy import deepcopy
import re
from canonical_evidence import Evidence
from derive_contract_fields import derive
from details_producer import build as detail_build
from source_ranges import attach_source
from ledger_lib import read, PACKAGE


def references(record):
    refs = record.get('sourceEvidenceRefs', record.get('evidenceRefs'))
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
        raise ValueError('Semantic record requires factual/source anchors: ' + str(record.get('id')))
    return refs


def phases_from(hierarchy, presentation):
    nodes, phases = hierarchy['nodes'], []
    aliases = {identity: key for key, identity in hierarchy.get('semantic_action_ids', {}).items()}
    render_ids = {}
    def render_id(identity):
        value = re.sub(r'[^A-Za-z0-9_.:-]', '_', identity)
        if not re.match(r'^[A-Za-z_]', value):
            value = 'r_' + value
        if value in render_ids and render_ids[value] != identity:
            raise ValueError('Ambiguous renderer identity: ' + identity)
        render_ids[value] = identity
        return value
    for phase_id in hierarchy['phase_order']:
        phase = dict(id=phase_id, label=nodes[phase_id]['name'], color='#327B98', goals=[], boundaryControlRefs=[])
        for goal_id in nodes[phase_id]['children']:
            goal = dict(id=goal_id, renderId=render_id(goal_id), label=nodes[goal_id]['name'], actions=[])
            for action_id in nodes[goal_id]['children']:
                action = dict(id=action_id, renderId=render_id(action_id), label=nodes[action_id]['name'],
                              controlRefs=presentation['ownerControls'].get(action_id, presentation['ownerControls'].get(aliases.get(action_id), [])))
                if nodes[action_id].get('broadRangeReason'):
                    action['broadRangeReason'] = nodes[action_id]['broadRangeReason']
                goal['actions'].append(action)
            if nodes[goal_id].get('broadRangeReason'):
                goal['broadRangeReason'] = nodes[goal_id]['broadRangeReason']
            phase['goals'].append(goal)
        phases.append(phase)
    return phases


def claim_record(record):
    return {key: deepcopy(value) for key, value in record.items() if key not in ('sourceEvidenceRefs', 'evidenceRefs')}


def execution(c, presentation, external, phases, evidence, root, symbol):
    nodes, edges, decisions = [], [], []
    aliases = c.load('stage2/hierarchy.json').get('semantic_action_ids', {})
    for record in presentation['executionNodes']:
        node = claim_record(record)
        kind = node['kind']
        targets = ([node['id']] if kind == 'action' else [root, symbol] if kind == 'entry'
                   else [node['decisionRef']] if kind == 'decision' else [node['outcome']])
        node['evidenceRefs'] = evidence.claim(kind, node.get('actionRef', node['id']), targets, references(record))
        nodes.append(node)
    for record in presentation['executionEdges']:
        edge = claim_record(record)
        for authored, rendered in [('source', 'from'), ('target', 'to')]:
            if authored in edge:
                if rendered in edge and edge[rendered] != edge[authored]:
                    raise ValueError('Conflicting execution endpoint: ' + edge['id'])
                edge[rendered] = edge.pop(authored)
        if 'from' not in edge or 'to' not in edge or 'guards' not in edge:
            raise ValueError('Execution edge requires canonical from/to/guards: '+edge['id'])
        conditions = [guard['decisionRef']+'='+guard['value'] for guard in edge['guards']]
        targets = [edge['from'], edge['to'], edge['kind']]
        if edge.get('taskId'):
            targets.append('task:' + edge['taskId'])
        if edge.get('readingScopeRef'):
            targets.append('scope:' + edge['readingScopeRef'])
        targets.extend('reset:' + ref for ref in edge.get('resetDecisionRefs', []))
        edge['evidenceRefs'] = evidence.claim('relation', edge['id'], targets, references(record), conditions)
        edges.append(edge)
    decision_fields = read(PACKAGE / 'assets/renderer/renderer-input.schema.json')['$defs']['Decision']['properties']
    for record in presentation.get('decisions', []):
        decision = {key: deepcopy(value) for key, value in record.items() if key in decision_fields and key != 'evidenceRefs'}
        targets = ['stability:'+decision['stability'], *decision['values']]
        for field, prefix in [('controlRef', 'control:'), ('readingScopeRef', 'scope:')]:
            if decision.get(field):
                targets.append(prefix+decision[field])
        conditions = [binding['branchRef']+'='+value for binding in decision.get('branchBindings', []) for value in binding['values']]
        conditions += ['take='+value for value in decision.get('takeValues', [])] + ['skip='+value for value in decision.get('skipValues', [])]
        decision['evidenceRefs'] = evidence.claim('decision', decision['id'], targets, references(record), conditions)
        decisions.append(decision)
    bindings = []
    for action_id, controls in presentation['ownerControls'].items():
        action_id = aliases.get(action_id, action_id)
        action = next(node for node in nodes if node.get('actionRef') == action_id)
        for control in controls:
            refs = presentation['controlEvidence'][control]
            bindings.append(dict(controlRef=control, nodeRef=action['id'],
                                 evidenceRefs=evidence.claim('control-binding', control, [action['id']], refs)))
    attachments = []
    for purpose in ([] if presentation.get('attachments') is not None else external['purposeProjections']):
        members = [member for member in external['business_members'] if member.get('purposeRef') == purpose['id']]
        if not members:
            raise ValueError('Purpose has no declared business member: '+purpose['id'])
        owner = members[0]['ownerActionRef']
        identity = 'attachment-'+purpose['id']
        refs = list(dict.fromkeys(ref for member in members for ref in references(member)))
        attachments.append(dict(id=identity, kind='purpose', ownerActionRef=owner, purposeRef=purpose['id'],
                                evidenceRefs=evidence.claim('attachment', identity, [owner, purpose['id']], refs)))
    actions = [action['id'] for phase in phases for goal in phase['goals'] for action in goal['actions']]
    controls = [control['id'] for control in presentation['controls']]
    if presentation.get('controlBindings') is not None:
        bindings = deepcopy(presentation['controlBindings'])
    if presentation.get('attachments') is not None:
        attachments = deepcopy(presentation['attachments'])
    inventory_file = c.inputs / 'ledgers/inventory-anchors.json'
    inventory = read(inventory_file) if inventory_file.exists() else presentation.get('inventory', {})
    inventory = dict(actionRefs=actions, controlRefs=controls,
                     evidenceRefs=evidence.claim('inventory', symbol, ['action:'+a for a in actions]+['control:'+co for co in controls], references(inventory)))
    if presentation.get('inventory') is not None:
        inventory = deepcopy(presentation['inventory'])
    for record in [inventory, *bindings, *attachments]:
        for ref in record['evidenceRefs']:
            if ref not in evidence.evidence_by_id:
                raise ValueError('Unresolved retained evidence identity: ' + ref)
    return dict(rootActorRef=root, entryNodeRef=next(node['id'] for node in nodes if node['kind'] == 'entry'),
                inventory=inventory, artifacts=evidence.artifacts, evidence=evidence.evidence, nodes=nodes,
                edges=edges, decisions=decisions, tasks=presentation.get('tasks', []),
                attachments=attachments, controlBindings=bindings)


def display_from(presentation, external, symbol, row):
    for source in (presentation, external):
        value=source.get('display')
        if value is not None:
            if not isinstance(value,dict):raise ValueError('display must be an object')
            return deepcopy(value)
    # Missing optional presentation metadata uses source identity, not invented semantics.
    return dict(title=symbol,description=row['identity']['canonical_path'],sourceLabel=row['source']['file'])


def build(c):
    hierarchy = c.load('stage2/hierarchy.json')
    presentation, external = c.load('stage4/presentation.json'), c.load('stage5/external.json')
    blocks, edges, calls = c.load('facts/blocks.json'), c.load('facts/edges.json'), c.load('facts/call-bindings.json')
    raw, row = c.load('raw-body.json'), c.load('input-pins.json')['definition_row']
    from body_labels import labels
    symbol = labels({'main':row})['main']
    root = external.get('mainActorRef', external.get('rootActorRef', external['actors'][0]['actorId']))
    phases = phases_from(hierarchy, presentation)
    if 'returnContracts' not in presentation or 'branchRoles' not in presentation:
        raise ValueError('Semantic ledger must declare returnContracts and branchRoles; no inferred business defaults')
    data = dict(profile='v6.1/1', deliveryMode='real-flow', dataKind='source-backed',
                semanticRoot=dict(actorRef=root, symbol=symbol), actors=external['actors'], messages=external['messages'],
                phases=phases, controls=presentation['controls'], purposeProjections=external['purposeProjections'],
                readingScopes=presentation.get('readingScopes', []), display=display_from(presentation, external, symbol, row),
                segments=external['segments'], branchRoles=presentation['branchRoles'], returnContracts=presentation['returnContracts'],
                initialState=presentation.get('initialState', dict(expandedActorIds=[], expandedPhaseIds=[], expandedGoalIds=[], expandedActionIds=[])))
    for name in ['rootControlRefs', 'rootAnchors', 'scopeAnnotations', 'caseIndex', 'definitionNotes', 'testBoundaries']:
        data[name] = presentation.get(name, [])
    data = derive(data)
    evidence = Evidence(c, blocks, edges, calls)
    # A body label and references to that source root share one projection rule.
    from body_labels import project_references
    project_references(data,row,symbol,root)
    project_references(evidence.evidence,row,symbol,root)
    data['execution'] = execution(c, presentation, external, phases, evidence, root, symbol)
    attach_source(data, c.work)
    details = detail_build(c, data, hierarchy['nodes'], blocks, raw)
    semantic_edges = c.load('stage4/edges.json')
    semantic_rows = semantic_edges if isinstance(semantic_edges, list) else semantic_edges['edges']
    relations = [dict(sourceRef=edge['id'], evidenceRefs=edge['members'],
                      representations=[dict(kind='summary', ref=edge.get('representationSummaryRef', edge['source']))])
                 for edge in semantic_rows]
    for clause in external.get('clauses', []):
        messages = [message['messageId'] for message in external['messages'] if message.get('invocationRef') == clause.get('invocationRef')]
        if not messages:
            raise ValueError('Clause has no invocation: '+clause['id'])
        relations.append(dict(sourceRef=clause['id'], evidenceRefs=references(clause),
                              representations=[dict(kind='message', ref=identity) for identity in messages]))
    c.save('stage6/principle-lineage.json', dict(relations=relations))
    outputs = {'renderer-input.json': data, 'reading-summaries.json': c.load('stage2/reading-summaries.json'), 'basic-block-details.json': details}
    for name, value in outputs.items():
        c.save(name, value)
    return outputs
