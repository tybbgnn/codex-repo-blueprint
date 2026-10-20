#!/usr/bin/env python3
"""Check the five graph-structural regression assertions using output JSON only."""
import argparse
import json
import re
from pathlib import Path


FACT_TOKEN = re.compile(r'(?<![A-Za-z0-9_])(?:bb[0-9]+|m[0-9]+\.[0-9]+)(?![A-Za-z0-9_])')


def _actions(data):
    actions = {}
    for phase in data.get('phases', []):
        phase_actions = set()
        for goal in phase.get('goals', []):
            goal_actions = {row.get('id') for row in goal.get('actions', []) if row.get('id')}
            actions[('goal', goal.get('id'))] = goal_actions
            phase_actions.update(goal_actions)
            for action in goal.get('actions', []):
                actions[('action', action.get('id'))] = {action['id']}
        actions[('phase', phase.get('id'))] = phase_actions
    return actions


def _member_actions(index, members):
    result = set()
    for member in members:
        if isinstance(member, dict):
            result.update(index.get((member.get('kind'), member.get('ref')), set()))
    return result


def _components(node_ids, edges):
    adjacency = {node: [] for node in node_ids}
    for edge in edges:
        if edge.get('from') in adjacency and edge.get('to') in adjacency:
            adjacency[edge['from']].append(edge['to'])
    indexes, low, stack, active, components = {}, {}, [], set(), []

    def visit(node):
        indexes[node] = low[node] = len(indexes)
        stack.append(node)
        active.add(node)
        for target in adjacency[node]:
            if target not in indexes:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], indexes[target])
        if low[node] == indexes[node]:
            component = set()
            while True:
                item = stack.pop()
                active.remove(item)
                component.add(item)
                if item == node:
                    break
            components.append(component)

    for node in sorted(node_ids):
        if node not in indexes:
            visit(node)
    return {node: component for component in components for node in component}


def _evidence_facts(data, valid_facts):
    result = {}
    for row in data.get('execution', {}).get('evidence', []):
        tokens = set(FACT_TOKEN.findall(str(row.get('locator', ''))))
        result[row.get('id')] = tokens & valid_facts
    return result


def _has_factual_evidence(record, evidence):
    refs = record.get('evidenceRefs') if isinstance(record, dict) else None
    return bool(refs) and all(ref in evidence and evidence[ref] for ref in refs)


def validate_documents(data, stage4_edges, fact_edges, async_states):
    failures = []

    def fail(rule, obj, reason):
        failures.append({'assertion': rule, 'object': obj, 'reason': reason})

    execution = data.get('execution', {})
    nodes = {row.get('id'): row for row in execution.get('nodes', []) if row.get('id')}
    edges = execution.get('edges', [])
    edge_by_id = {row.get('id'): row for row in edges if row.get('id')}
    components = _components(set(nodes), edges)
    action_by_node = {key: row.get('actionRef') for key, row in nodes.items()
                      if row.get('kind') == 'action' and row.get('actionRef')}
    action_index = _actions(data)
    facts = {row.get('id') for row in fact_edges if row.get('id')}
    facts.update(row.get(field) for row in fact_edges for field in ('source', 'target') if row.get(field))
    evidence = _evidence_facts(data, facts)

    semantic_rows = stage4_edges if isinstance(stage4_edges, list) else stage4_edges.get('edges', [])
    for row in semantic_rows:
        unknown = [member for member in row.get('members', []) if member not in facts]
        if unknown:
            fail('R5', row.get('id'), 'stage4 semantic edge references unknown factual edges: ' + ', '.join(unknown))

    loop_context = {}
    for scope in data.get('readingScopes', []):
        if scope.get('kind') != 'loop':
            continue
        scope_id = scope.get('id')
        members = _member_actions(action_index, scope.get('members', []))
        back_edges = [row for row in edges if row.get('kind') == 'loop-continue'
                      and row.get('readingScopeRef') == scope_id]
        components_for_loop = []
        for edge in back_edges:
            source_component = components.get(edge.get('from'), set())
            if not source_component or components.get(edge.get('to')) is not source_component:
                fail('R3', edge.get('id'), 'loop back edge endpoints do not belong to one strongly connected component')
            else:
                components_for_loop.append(source_component)
        if not back_edges:
            fail('R3', scope_id, 'loop has no execution loop-continue edge')
        distinct = {frozenset(component) for component in components_for_loop}
        if len(distinct) > 1:
            fail('R3', scope_id, 'loop back edges determine different strongly connected components')
        component = set(next(iter(distinct))) if len(distinct) == 1 else set()
        component_actions = {action_by_node[node] for node in component if node in action_by_node}
        if component:
            order = [action['id'] for phase in data.get('phases', [])
                     for goal in phase.get('goals', []) for action in goal.get('actions', [])]
            positions = [order.index(action) for action in component_actions if action in order]
            interval = set(order[min(positions):max(positions) + 1]) if positions else set()
            if not interval or members != interval:
                fail('R3', scope_id, 'loop members differ from minimal contiguous SCC action interval')
            extra_nodes = {node for node, action in action_by_node.items() if action in members - component_actions}
            common = scope.get('commonAfter', {}).get('actionRef')
            stops = {node for node, action in action_by_node.items() if action == common}
            stops.update(node for node, row in nodes.items() if row.get('kind') == 'terminal'
                         and _has_factual_evidence(row, evidence))
            adjacency = {node: set() for node in nodes}
            for edge in edges:
                if edge.get('from') in adjacency:
                    adjacency[edge['from']].add(edge.get('to'))
            pending, reached = list(extra_nodes), set()
            while pending:
                node = pending.pop()
                if node in stops or node in reached:
                    continue
                reached.add(node)
                if node in component or (node in action_by_node and action_by_node[node] not in members):
                    fail('R3', scope_id, 'in-loop exit reaches entry SCC or unrelated action: ' + str(node))
                pending.extend(adjacency.get(node, ()))
            proven = set(stops)
            while True:
                added = {node for node in reached - proven if adjacency.get(node)
                         and adjacency[node] <= proven}
                if not added:
                    break
                proven.update(added)
            if not extra_nodes <= proven:
                fail('R3', scope_id, 'in-loop exits lack exhaustive commonAfter/terminal paths')
            for edge in edges:
                if edge.get('from') in reached and not _has_factual_evidence(edge, evidence):
                    fail('R3', edge.get('id'), 'in-loop exit path lacks factual MIR evidence')
            # Independently reject extra actions whose MIR can reach the entry action.
            action_blocks = {row['id']: set(row.get('basicBlockRefs', []))
                             for phase in data.get('phases', []) for goal in phase.get('goals', [])
                             for row in goal.get('actions', [])}
            backward = set(action_blocks.get(scope.get('repeat', {}).get('entryActionRef'), ()))
            while True:
                added = {row['source'] for row in fact_edges if row.get('target') in backward
                         and row.get('condition') not in ('unwind', 'failure')} - backward
                if not added:
                    break
                backward.update(added)
            for action in members - component_actions:
                if not action_blocks.get(action) or action_blocks[action] & backward:
                    fail('R3', action, 'in-loop exit is missing MIR blocks or can reach entry')
        loop_context[scope_id] = (scope, members, component)

        decision = scope.get('decision', {}).get('variable')
        exit_values = set(scope.get('repeat', {}).get('exitValues', []))
        exits = [row for row in edges if row.get('kind') == 'loop-exit'
                 and row.get('readingScopeRef') == scope_id]
        matched = [row for row in exits if any(guard.get('decisionRef') == decision
                   and guard.get('value') in exit_values for guard in row.get('guards', []))]
        for value in sorted(exit_values):
            value_edges = [row for row in exits if any(guard.get('decisionRef') == decision
                           and guard.get('value') == value for guard in row.get('guards', []))]
            if not value_edges:
                fail('R1', scope_id + ':' + value, 'exit value has no corresponding loop-exit edge')
            for edge in value_edges:
                target_action = action_by_node.get(edge.get('to'), edge.get('to'))
                if edge.get('to') in component or target_action in members:
                    fail('R1', edge.get('id'), 'loop exit target remains inside the loop SCC or member actions')
                if not _has_factual_evidence(edge, evidence):
                    fail('R5', edge.get('id'), 'loop exit value lacks evidence resolving to a factual edge or BB')

        common = scope.get('commonAfter')
        if isinstance(common, dict):
            action = common.get('actionRef')
            if action in members:
                fail('R2', scope_id + '.commonAfter', 'commonAfter action is also a loop member')
            target_nodes = {node for node, ref in action_by_node.items() if ref == action}
            incoming = [row for row in exits if row.get('to') in target_nodes]
            if not incoming or not any(_has_factual_evidence(row, evidence) for row in incoming):
                fail('R5', scope_id + '.commonAfter', 'commonAfter lacks a factual execution edge')
        exit_targets = {action_by_node.get(row.get('to'), row.get('to')) for row in exits}
        overlap = members & exit_targets
        if overlap:
            fail('R2', scope_id, 'loop exit targets overlap members: ' + repr(sorted(overlap)))

        terminal = scope.get('terminalOnly')
        if isinstance(terminal, dict):
            for ref in terminal.get('exitEdgeRefs', []):
                edge = edge_by_id.get(ref)
                if edge is None or not _has_factual_evidence(edge, evidence):
                    fail('R5', scope_id + '.terminalOnly', 'terminalOnly exit edge lacks factual evidence: ' + str(ref))

    resume_entries = {row.get('entry') for row in async_states.get('states', [])
                      if row.get('role') == 'resume' and row.get('entry')}
    semantic_resume_targets = {row.get('source') for row in semantic_rows
                               if row.get('kind') in ('resume_annotation', 'scope_handoff')}
    semantic_resume_targets.update(row.get('target') for row in semantic_rows
                                   if row.get('kind') in ('resume_annotation', 'scope_handoff'))
    for edge in edges:
        if edge.get('kind') != 'resume':
            continue
        target = nodes.get(edge.get('to'))
        if target is None:
            fail('R4', edge.get('id'), 'resume target node does not exist')
            continue
        blocks = set(target.get('basicBlockRefs', []))
        handoff = target.get('kind') == 'handoff' and target.get('event') in ('await', 'resume')
        original = target.get('id') in semantic_resume_targets or target.get('actionRef') in semantic_resume_targets
        if not (blocks & resume_entries or handoff or original):
            fail('R4', edge.get('id'), 'resume target is neither a recorded resume entry nor an original await/handoff node')
        refs = edge.get('evidenceRefs', [])
        supported = set().union(*(evidence.get(ref, set()) for ref in refs)) if refs else set()
        if not refs or not supported:
            fail('R4', edge.get('id'), 'resume edge has no factual evidence')
        unsupported = (blocks & facts) - supported
        if unsupported:
            fail('R4', edge.get('id'), 'resume target path contains BBs absent from its evidence: ' + repr(sorted(unsupported)))

    for scope in data.get('readingScopes', []):
        for branch in scope.get('branches', []):
            if not branch.get('effect'):
                continue
            values = set(branch.get('when', []))
            decisions = [row for row in execution.get('decisions', [])
                         if row.get('readingScopeRef') == scope.get('id')
                         and values & set(row.get('values', []))]
            if not decisions or not any(_has_factual_evidence(row, evidence) for row in decisions):
                fail('R5', str(branch.get('id')), 'branch effect lacks a factual execution decision')

    checks = [{'assertion': rule, 'status': 'fail' if any(row['assertion'] == rule for row in failures) else 'pass'}
              for rule in ('R1', 'R2', 'R3', 'R4', 'R5')]
    return {'valid': not failures, 'checks': checks, 'failures': failures}


def load_output(out):
    out = Path(out)
    return (json.loads((out / 'renderer-input.json').read_text()),
            json.loads((out / 'stage4/edges.json').read_text()),
            json.loads((out / 'facts/edges.json').read_text()),
            json.loads((out / 'facts/async-states.json').read_text()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate_documents(*load_output(args.out))
        exit_code = 0 if result['valid'] else 1
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {'valid': False, 'input_error': str(error), 'checks': [], 'failures': []}
        exit_code = 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    args.report.write_text(payload)
    print(payload, end='')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
