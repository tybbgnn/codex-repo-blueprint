#!/usr/bin/env python3
"""Derive stage-6 mechanical fields from a semantic renderer-input draft."""
import argparse
import copy
import json
from pathlib import Path


def walk_controls(controls):
    rows = []
    def visit(node, root, branch_path, invocation):
        current = node['id'] if node.get('invocationRef') else invocation
        rows.append((node, root, list(branch_path), current))
        for child in node.get('children', []):
            visit(child, root, branch_path, current)
        if node.get('kind') == 'alt':
            for branch in node.get('branches', []):
                for child in branch.get('children', []):
                    visit(child, root, branch_path + [branch['id']], current)
    for root in controls:
        visit(root, root['id'], [], root['id'])
    return rows


def derive(data):
    out = copy.deepcopy(data)
    out['fixture'] = {'actors': copy.deepcopy(out['actors']), 'messages': []}
    owners = []
    owners.extend({'controlRef': ref, 'owner': {'kind': 'root', 'ref': 'ROOT'}}
                  for ref in out.get('rootControlRefs', []))
    for phase in out.get('phases', []):
        owners.extend({'controlRef': ref, 'owner': {'kind': 'phase', 'ref': phase['id']}}
                      for ref in phase.get('boundaryControlRefs', []))
        for goal in phase.get('goals', []):
            for action in goal.get('actions', []):
                owners.extend({'controlRef': ref, 'owner': {'kind': 'action', 'ref': action['id']}}
                              for ref in action.get('controlRefs', []))
    out['controlOwners'] = owners
    placements, branch_roles = [], []
    old_roles = {row['branchRef']: row.get('role') for row in out.get('branchRoles', [])}
    invocation_refs = set()
    for node, root, path, _invocation in walk_controls(out.get('controls', [])):
        if node.get('invocationRef'):
            invocation_refs.add(node['invocationRef'])
        placements.extend({'messageRef': ref, 'controlRef': node['id'],
                           'rootControlRef': root, 'branchPath': path}
                          for ref in node.get('messages', []))
        for branch in node.get('branches', []):
            role = old_roles.get(branch['id'])
            if not role:
                raise ValueError('semantic ledger must supply role for branch ' + branch['id'])
            branch_roles.append({'branchRef': branch['id'], 'controlRef': node['id'], 'role': role})
    out['messagePlacements'] = placements
    out['branchRoles'] = branch_roles
    placement_by_message = {row['messageRef']: row for row in placements}
    old_returns = {row['messageRef']: row for row in out.get('returnContracts', [])}
    returns = []
    for message in out.get('messages', []):
        if message.get('kind') != 'return':
            continue
        if message['messageId'] not in old_returns:
            raise ValueError('semantic ledger must supply return meaning for ' + message['messageId'])
        row = copy.deepcopy(old_returns[message['messageId']])
        row['branchRef'] = (placement_by_message.get(message['messageId'], {}).get('branchPath') or [None])[-1]
        returns.append(row)
    out['returnContracts'] = returns
    all_messages = [ref for segment in out.get('segments', []) for ref in segment.get('messages', [])]
    wanted = [m['messageId'] for m in out.get('messages', [])]
    if len(all_messages) != len(set(all_messages)) or sorted(all_messages) != sorted(wanted):
        raise ValueError('semantic segment ledger must partition every message exactly once')
    actors = {}
    def add_actors(items):
        for actor in items:
            actors[actor['actorId']] = actor
            add_actors(actor.get('children', []))
    add_actors(out.get('actors', []))
    expanded = out.get('initialState', {}).get('expandedActorIds', [])
    if any(not actors.get(ref, {}).get('children') for ref in expanded):
        raise ValueError('expandedActorIds may contain only actor containers')
    for purpose in out.get('purposeProjections', []):
        refs = purpose.get('invocationRefs', []) + purpose.get('waitRefs', [])
        if not refs or any(ref not in invocation_refs for ref in refs):
            raise ValueError('purpose members must resolve to control invocationRef values')
    for scope in out.get('readingScopes', []):
        if 'commonAfter' not in scope:
            continue
        expected = ([b['id'] for b in scope.get('branches', []) if b.get('effect', {}).get('kind') != 'terminate-turn']
                    if scope['kind'] == 'alt' else ['taken', 'skipped'] if scope['kind'] == 'opt' else ['exit'])
        actual = [a['path'] for a in scope['commonAfter'].get('arrivals', [])]
        if sorted(actual) != sorted(expected):
            raise ValueError('commonAfter arrivals differ for ' + scope['id'])
    if out.get('execution'):
        artifacts = {a['id']: a for a in out['execution'].get('artifacts', [])}
        for evidence in out['execution'].get('evidence', []):
            artifact = artifacts.get(evidence.get('artifactRef'))
            if not artifact or evidence.get('quote', '') not in artifact.get('content', ''):
                raise ValueError('evidence quote is not a literal artifact substring: ' + evidence.get('id', ''))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = derive(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
