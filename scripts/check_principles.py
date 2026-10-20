#!/usr/bin/env python3
"""Read-only display-principle audit. Standard library; no reference answers.

Exit 0: all required checks and agent decisions pass; warnings are reported.
Exit 1: at least one machine failure. Exit 2: missing/invalid required input.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from audit_duplicates import audit as audit_duplicates
import classification_registry as classifications


def rows(value):
    return list(value.values()) if isinstance(value, dict) else value or []


def tree(items):
    for item in items:
        yield item
        yield from tree(item.get('children', []))
        for branch in item.get('branches', []):
            yield from tree(branch.get('children', []))


def body_key(value):
    # Preserve capture stage/body id; discard only provenance prefixes.
    found = re.search(r'([0-9a-f]+\|[^|]+\|[^|]+)$', value or '')
    return found.group(1) if found else value


def strict_forward_shell(raw, inner_owner):
    """Independent G10 proof: branch-free construction/copy/cast/Box::pin shell."""
    constructions = []
    for block in raw.get('basic_blocks', []):
        if block.get('is_cleanup'):
            if block.get('statements') or block.get('terminator', {}).get('kind') != 'UnwindResume':
                return False
            continue
        for statement in block.get('statements', []):
            if statement.get('kind') in ('StorageLive','StorageDead','Nop'):
                continue
            detail = statement.get('detail', {}); rvalue = detail.get('rvalue', {})
            if statement.get('kind') != 'Assign' or detail.get('destination', {}).get('projection'):
                return False
            aggregate = rvalue.get('detail', {}).get('aggregate_kind', {})
            if aggregate.get('kind') == 'Coroutine':
                constructions.append(aggregate.get('detail', {}).get('definition', {}).get('def_path_hash'))
            elif rvalue.get('kind') not in ('Use','Cast'):
                return False
        term = block.get('terminator', {}); kind = term.get('kind')
        if kind == 'Call':
            name = (term.get('detail', {}).get('func', {}).get('detail', {})
                    .get('constant', {}).get('type', {}).get('display', ''))
            if not re.search(r'\{(?:std|alloc)::boxed::Box::<.*>::pin\}$', name):
                return False
        elif kind not in ('Goto','Return'):
            return False
    return constructions == [inner_owner]


def binding_key(value):
    found = re.search(r'(?:^|/)(call:\d+)$', value or '')
    return found.group(1) if found else value


def fields(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from fields(item, f'{path}/{i}')
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from fields(item, f'{path}/{key}')


def cyclic_components(nodes, edges):
    """Iterative Kosaraju: retain cycles, including single-node self loops."""
    forward, reverse = defaultdict(set), defaultdict(set)
    for source, target in edges:
        if source in nodes and target in nodes:
            forward[source].add(target)
            reverse[target].add(source)
    seen, order = set(), []
    for start in sorted(nodes):
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(sorted(forward[start])))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                order.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(sorted(forward[child]))))
    seen = set()
    for start in reversed(order):
        if start in seen:
            continue
        component, todo = set(), [start]
        seen.add(start)
        while todo:
            node = todo.pop()
            component.add(node)
            for parent in sorted(reverse[node]):
                if parent not in seen:
                    seen.add(parent)
                    todo.append(parent)
        if len(component) > 1 or start in forward[start]:
            yield component


class Audit:
    def __init__(self, out):
        self.out = out.resolve()
        self.inputs = {}
        self.checks = []
        self.reviews = []
        self.agent_review = self.read('stage7/agent-review.json') or {'items':[]}
        self.review_ledger = { (r.get('principle'),r.get('check')):r for r in self.agent_review.get('items',[])}
        if len(self.review_ledger)!=len(self.agent_review.get('items',[])):raise ValueError('duplicate agent review decision')
        self.data = self.read('renderer-input.json', required=True)
        self.summaries = self.read('reading-summaries.json', required=True)['units']
        self.details = self.read('basic-block-details.json', required=True)
        self.hierarchy = self.read('stage2/hierarchy.json')
        self.selection = self.read('stage2/selection.json')
        self.stage_edges = self.read('stage4/edges.json')
        self.fact_edges = self.read('facts/edges.json')
        self.fact_blocks = self.read('facts/blocks.json')
        self.calls = self.read('facts/call-bindings.json')
        self.definitions = self.read('facts/definitions-index.json')
        self.external = self.read('stage5/external.json')
        self.lineage = self.read('stage6/principle-lineage.json')
        self.granularity = self.read('stage2/granularity.json')
        # Optional historical sidecars; read local data, never follow their paths.
        self.conversion = self.read('conversion-lineage.json') or {}
        self.actors = list(tree(self.data['actors']))
        self.actor_by_id = {a['actorId']: a for a in self.actors}
        self.controls = list(tree(self.data['controls']))
        self.control_by_id = {c['id']: c for c in self.controls}
        self.phases = self.data['phases']
        self.goals = [g for p in self.phases for g in p['goals']]
        self.actions = [a for g in self.goals for a in g['actions']]
        self.prelude_nodes = list((self.data.get('prelude') or {}).get('nodes', []))
        self.units = [(p, 'phase') for p in self.phases] + [(g, 'goal') for g in self.goals] + [(a, 'action') for a in self.actions]
        self.messages = self.data['messages']
        self.execution = self.data.get('execution') or {}
        self.exec_nodes = {n['id']: n for n in self.execution.get('nodes', [])}
        self.exec_edges = {e['id']: e for e in self.execution.get('edges', [])}
        self.scopes = {s['id']: s for s in self.data.get('readingScopes', [])}
        self.branches = {b['id']: b for c in self.controls for b in c.get('branches', [])}
        roots = list(self.data.get('rootControlRefs', []))
        roots += [r for p in self.phases for r in p.get('boundaryControlRefs', [])]
        roots += [r for a in self.actions for r in a.get('controlRefs', [])]
        self.attached = set()
        for ref in roots:
            for c in tree([self.control_by_id[ref]] if ref in self.control_by_id else []):
                self.attached.add(c['id'])
        self.visible_messages = {m for c in self.controls if c['id'] in self.attached for m in c.get('messages', [])}
        self.texts = list(self.display_texts())

    def read(self, name, required=False):
        path = self.out / name
        if not path.exists() and not required:
            return None
        raw = path.read_bytes()
        self.inputs[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        return json.loads(raw)

    def result(self, p, name, bad, **evidence):
        # Text-only hints cannot change graph validity or initiate repair loops.
        wording = p == 'P7' and name in {'async_mechanism','low_level_identifier','evidence_as_content','code_condition'}
        self.checks.append({'principle': p, 'check': name, 'status': ('warning' if wording else 'fail') if bad else 'pass',
                            'evidence': {**evidence, 'failure_count': len(bad), 'examples': bad[:8]}})

    def review(self, p, name, reason, **evidence):
        from agent_review import decide
        item = decide(self.out, self.review_ledger.get((p,name)), p, name, reason, evidence)
        self.checks.append(item)
        self.reviews.append(item)

    def display_texts(self):
        # Whitelist rendered fields: never scan IDs, Rust, evidence, replacement metadata.
        for name in ('messages', 'segments', 'phases', 'scopeAnnotations', 'readingScopes'):
            yield from self.text_fields(self.data.get(name, []), '/' + name)
        yield from self.text_fields(self.data.get('controls', []), '/controls')
        yield from self.text_fields((self.data.get('execution') or {}).get('nodes', []), '/execution/nodes')
        for key, value in self.summaries.items():
            yield '/reading-summaries/units/' + key + '/text', value.get('text', '')

    def text_fields(self, value, path):
        text_keys = {'label', 'condition', 'outcome', 'outcomes', 'notes', 'after', 'skip', 'continue', 'exit', 'limit', 'meaning'}
        if isinstance(value, dict):
            for key, child in value.items():
                if key in text_keys:
                    yield from fields(child, path + '/' + key)
                elif isinstance(child, (dict, list)) and key not in {'evidence', 'sources', 'replacements'}:
                    yield from self.text_fields(child, path + '/' + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                yield from self.text_fields(child, f'{path}/{i}')

    def semantic_edges(self):
        if self.stage_edges is not None:
            return rows(self.stage_edges.get('edges', self.stage_edges) if isinstance(self.stage_edges, dict) else self.stage_edges)
        return self.conversion.get('source_internal_edges', [])

    def check_p1(self):
        bad = [u['id'] for u, _ in self.units if re.fullmatch(r'bb\d+', u['id'], re.I)]
        self.result('P1', 'reading_tree_separated', bad, reading_nodes=len(self.units), detail_blocks=len(self.details['blocks']))
        if self.fact_blocks is None:
            self.review('P1', 'complete_fact_tree', '没有 facts/blocks.json，无法证明全 BB 覆盖；详情数量不能代替事实全集。')
        else:
            value = self.fact_blocks
            if isinstance(value, dict) and 'blocks' in value:
                value = value['blocks']
            expected = set(value) if isinstance(value, dict) else {b.get('id', b.get('bb', f"bb{b.get('basic_block')}")) for b in value}
            expected.update(ref for node in self.prelude_nodes
                            for ref in node.get('basicBlockRefs', [])
                            if re.fullmatch(r'shell:bb[0-9]+', ref))
            actual = set(self.details['blocks'])
            self.result('P1', 'complete_fact_tree', sorted(expected-actual) + sorted(actual-expected), expected=len(expected), actual=len(actual), missing=len(expected-actual), extra=len(actual-expected))
        if not self.selection:
            self.review('P1', 'selection_basis', '缺少 selection.json，需审查每个业务节点/调用的选取与折入理由。')

    def check_p2(self):
        expected = (self.hierarchy or {}).get('phase_order')
        if expected is None:
            records = self.conversion.get('source_reading_records', {})
            roots = [n for n in records.values() if str(n.get('kind', '')).lower() == 'root']
            expected = roots[0].get('children') if len(roots) == 1 else None
        if expected is None:
            self.review('P2', 'source_phase_order', '缺少源阅读顺序，须沿源码与控制流核验。')
        else:
            actual = [p['id'] for p in self.phases]
            self.result('P2', 'source_phase_order', [] if actual == expected else [{'expected': expected, 'actual': actual}])

    def check_p3(self):
        edges = self.semantic_edges()
        if not edges and self.stage_edges is None:
            self.review('P3', 'lower_to_upper_projection', '缺少上游语义边集合。')
        else:
            bad = [{'id': e['id'], 'kind': e.get('kind'), 'depth': e.get('depth'), 'label': e.get('label')} for e in edges if e.get('kind') in {'runtime_annotation', 'resume_annotation', 'wait_annotation'}]
            self.result('P3', 'technical_edges_promoted', bad, semantic_edges=len(edges), kinds=dict(Counter(e.get('kind') for e in edges)))
        evidence = {e['id'] for e in self.execution.get('evidence', [])}
        bad = [{'edge': e['id'], 'missing': [r for r in e.get('evidenceRefs', []) if r not in evidence]} for e in self.exec_edges.values() if not e.get('evidenceRefs') or any(r not in evidence for r in e['evidenceRefs'])]
        self.result('P3', 'execution_edge_evidence', bad, edges=len(self.exec_edges))

    def check_p4(self):
        if self.fact_edges is None or self.stage_edges is None:
            self.review('P4', 'original_edge_identity', '缺原边表或 stage4 members，不能验证多重边条件身份。')
            return
        facts = rows(self.fact_edges)
        counts = Counter(e['id'] for e in facts)
        original = {e['id']: e for e in facts}
        bad = [{'id': key, 'duplicates': n} for key, n in counts.items() if n > 1]
        for e in self.semantic_edges():
            members = e.get('members', [])
            if not members or len(members) != len(set(members)) or any(r not in original for r in members):
                bad.append({'edge': e['id'], 'reason': 'missing/duplicate/unknown original IDs'})
            for c in e.get('clauses', []):
                ref = c.get('edgeRef')
                if ref and (ref not in members or any(c.get(k) != original.get(ref, {}).get(v) for k, v in [('source_bb', 'source'), ('target_bb', 'target'), ('bindingRef', 'bindingRef')] if k in c)):
                    bad.append({'edge': e['id'], 'clause': c, 'reason': 'original identity mismatch'})
        endpoint_groups = Counter((e['source'], e['target']) for e in facts)
        self.result('P4', 'original_edge_identity', bad, original_edges=len(facts), multiedge_endpoint_groups=sum(n > 1 for n in endpoint_groups.values()))

    def check_p5(self):
        # Exact technical roles/labels, not a substring blacklist of business returns.
        technical = {'EX', 'RET', 'cleanup', 'shared_cleanup', 'shared_return', 'return_container'}
        bad = [{'id': u['id'], 'label': u['label']} for u, _ in self.units if u['id'] in technical or u.get('label') in technical]
        nodes = (self.hierarchy or {}).get('nodes', {})
        excluded = {key for key, n in nodes.items() if n.get('kind') in technical or key in technical}
        bad += [{'edge': e['id'], 'endpoint': ref} for e in self.semantic_edges() for ref in [e.get('source'), e.get('target')] if ref in technical or ref in excluded]
        self.result('P5', 'technical_containers_absent', bad)
        if self.fact_blocks is not None and self.fact_edges is not None:
            blocks = self.fact_blocks.get('blocks', self.fact_blocks) if isinstance(self.fact_blocks, dict) else self.fact_blocks
            blocks = blocks if isinstance(blocks, dict) else {b.get('id', b.get('bb', f"bb{b.get('basic_block')}")): b for b in blocks}
            raw_edges = {e['id']: e for e in rows(self.fact_edges)}
            cleanup = []
            for e in self.semantic_edges():
                refs = [r for r in e.get('members', []) if blocks.get(raw_edges.get(r, {}).get('target'), {}).get('is_cleanup')]
                if refs and e.get('kind') == 'runtime_annotation':
                    cleanup.append({'edge': e['id'], 'cleanup_edge_refs': refs, 'depth': e.get('depth')})
            self.result('P5', 'cleanup_technical_lines', cleanup)

    def check_p6(self):
        used = {m[k] for m in self.messages for k in ('fromActorId', 'toActorId')}
        parents = {}
        def visit(items, parent=None):
            for a in items:
                parents[a['actorId']] = parent
                visit(a.get('children', []), a['actorId'])
        visit(self.data['actors'])
        required = set(used)
        for actor in used:
            parent = parents.get(actor)
            while parent is not None:
                required.add(parent)
                parent = parents.get(parent)
        actual = set(self.actor_by_id)
        bad = [{'unused_actor': x} for x in sorted(actual-required)] + [{'missing_actor': x} for x in sorted(required-actual)]
        counts = Counter(a['actorId'] for a in self.actors)
        bad += [{'duplicate_actor_id': k} for k, n in counts.items() if n > 1]
        self.result('P6', 'endpoint_ancestor_closure', bad, actors_top=len(self.data['actors']), actors_recursive=len(self.actors), endpoints=len(used))
        bodies = [a for a in self.actors if a['kind'] == 'body']
        declarations = [a for a in self.actors if a['kind'] == 'declaration']
        callables = bodies + declarations
        identities = defaultdict(list)
        for a in bodies:
            identities[body_key(a.get('bodyRef'))].append(a['actorId'])
        bad = [{'bodyRef': k, 'actors': v} for k, v in identities.items() if not k or len(v) != 1]
        bad += [{'actor': a['actorId'], 'reason': 'sourceNodeRef missing'} for a in self.actors if not a.get('sourceNodeRef')]
        self.result('P6', 'unique_body_identity', bad, body_actors=len(bodies))
        declaration_ids = defaultdict(list)
        bad = []
        for a in declarations:
            key = a.get('declarationRef')
            declaration_ids[key].append(a['actorId'])
            definition = (self.definitions or {}).get(key)
            if (not key or a.get('sourceNodeRef') != key or 'bodyRef' in a
                    or a.get('implementationStatus') != 'unresolved'
                    or not definition or definition.get('rustc', {}).get('def_kind') not in ('Fn', 'AssocFn')):
                bad.append({'actor': a['actorId'], 'reason': 'declaration must have exact callable definition, explicit unresolved implementation, and no bodyRef'})
        bad += [{'declarationRef': key, 'actors': ids} for key, ids in declaration_ids.items() if len(ids) != 1]
        self.result('P6', 'declaration_endpoint_identity', bad, declaration_actors=len(declarations))
        bad = []
        for a in callables:
            if a['actorId'] == self.data['semanticRoot']['actorRef']:
                continue
            chain, parent = [], parents.get(a['actorId'])
            while parent:
                chain.append(self.actor_by_id[parent]['kind'])
                parent = parents.get(parent)
            if not chain or chain[0] != 'module' or 'crate' not in chain:
                bad.append({'actor': a['actorId'], 'label': a['label'], 'ancestor_kinds': chain})
        self.result('P6', 'external_body_ancestors', bad)
        self.check_pairs('P6')
        if self.definitions is None:
            self.review('P6', 'definition_proof', '无本地 definitions 索引；真实端点、body_available、ownership 与完整来源身份须审查。')
        else:
            missing, invalid, wrong_ownership = [], [], []
            for a in callables:
                key = a.get('declarationRef') if a['kind'] == 'declaration' else body_key(a.get('bodyRef', '')) or ''
                definition = self.definitions.get(key.split('|')[0])
                if not definition:
                    missing.append(a['actorId'])
                elif a['kind'] == 'body' and definition.get('representations', {}).get('mir', {}).get('body_available') is not True:
                    invalid.append(a['actorId'])
                if definition and a['actorId'] != self.data['semanticRoot']['actorRef']:
                    owner = definition.get('ownership', {})
                    ancestors, parent = [], parents.get(a['actorId'])
                    while parent:
                        ancestors.append(self.actor_by_id[parent])
                        parent = parents.get(parent)
                    for kind, field in [('module', 'module_def_path_hash'), ('crate', 'crate_root_def_path_hash')]:
                        if owner.get(field) and not any(x['kind'] == kind and owner[field] in x.get('sourceNodeRef', '') for x in ancestors):
                            wrong_ownership.append({'actor': a['actorId'], 'kind': kind, 'expected_definition': owner[field]})
            self.result('P6', 'known_body_available', invalid, checked=sum((body_key(a.get('bodyRef', '')) or '').split('|')[0] in self.definitions for a in bodies))
            self.result('P6', 'definition_ownership', wrong_ownership)
            if missing:
                self.review('P6', 'missing_body_proof', '索引未命中不是无 body 的证明；这些 body 展示身份尚未获得证据。', count=len(missing), examples=missing[:8])
        registry = (self.external or {}).get('identity_registry')
        expected = {a['actorId']:a for a in self.actors}
        actual = {a.get('actorId'):a for a in registry or []} if isinstance(registry,list) else {}
        bad = [dict(actor=key,reason='missing or changed source identity') for key,actor in expected.items()
               if actual.get(key) != actor]
        bad += [dict(actor=key,reason='unknown identity') for key in actual.keys()-expected.keys()]
        if registry is None:bad.append(dict(reason='identity_registry missing'))
        if isinstance(registry,list) and len(actual)!=len(registry):bad.append(dict(reason='duplicate identity'))
        self.result('P6', 'full_source_identity_registry', bad, actors=len(expected))

    def check_pairs(self, principle):
        invocations = defaultdict(list)
        for m in self.messages:
            if m['kind'] in ('request', 'return'):
                invocations[m.get('invocationRef')].append(m)
        bad = []
        pair_inv = defaultdict(set)
        for inv, messages in invocations.items():
            kinds = Counter(m['kind'] for m in messages)
            reason = None
            if not inv or kinds != {'request': 1, 'return': 1}:
                reason = 'invocation must have one request and one return'
            else:
                req = next(m for m in messages if m['kind'] == 'request')
                ret = next(m for m in messages if m['kind'] == 'return')
                if not req.get('pair') or req['pair'] != ret.get('pair') or (req['fromActorId'], req['toActorId']) != (ret['toActorId'], ret['fromActorId']) or not req.get('bindingRef') or req.get('bindingRef') != ret.get('bindingRef'):
                    reason = 'pair/direction/binding mismatch'
                pair_inv[req.get('pair')].add(inv)
            if reason:
                bad.append({'invocation': inv, 'kinds': dict(kinds), 'reason': reason})
        bad += [{'pair': p, 'invocations': sorted(v)} for p, v in pair_inv.items() if len(v) > 1]
        self.result(principle, 'invocation_pair_integrity', bad, invocations=len(invocations))

    def check_p7(self):
        duplicate_report = audit_duplicates(self.data, self.details, self.granularity, {'units': self.summaries})
        for category, findings in duplicate_report['inventory'].items():
            self.result('P7', 'duplicates_' + category,
                        [f for f in findings if f['severity'] == 'error'],
                        counts=duplicate_report['counts'][category],
                        inventory=findings)

        # Definitive display leaks only; broad lexical heuristics become review items.
        patterns = {
            'async_mechanism': r'\b(?:poll|Pending|saved_state|construct_future|resume[-_ ]wait)\b|恢复等待|构造\s*future|future\s*构造',
            'low_level_identifier': r'\bbb\d+\b|\bm\d+\.\d+\b|\bcall:\d+\b',
            'evidence_as_content': r'@canonical:|\bedge_refs\b|\bbindingRef\b|\breplacements\b|\bbasic_block_refs\b',
            'code_condition': r'\bdiscriminant\s*\(|\b_\d+\b|unwind\s*=\s*\{',
        }
        matched = set()
        for category, pattern in patterns.items():
            bad = [{'pointer': p, 'text': text[:240]} for p, text in self.texts if re.search(pattern, text)]
            matched.update(x['pointer'] for x in bad)
            self.result('P7', category, bad, scanned_fields=len(self.texts))
        roles = [r for r in self.data.get('branchRoles', []) if r['role'] in {'ready', 'pending', 'unwind'}]
        contracts = [r for r in self.data.get('returnContracts', []) if r['meaning'] in {'future-handle', 'poll-pending'}]
        self.result('P7', 'runtime_display_structures', roles + contracts, runtime_branch_roles=len(roles), technical_returns=len(contracts), unique_noisy_text_fields=len(matched))
        heuristic = {
            'locks_iterators': r'\b(?:Mutex|RwLock|Iterator|IntoIterator)\b|::(?:lock|iter|next)\b|迭代器',
            'debug_process': r'\b(?:trace!|debug!|tracing::|debug_assert)\b|调试过程',
            'analyzer_notes': r'分析器|此 Call|真实入口到达才执行|可追溯|证据引用',
        }
        for name, pattern in heuristic.items():
            hits = [{'pointer': p, 'text': t[:200]} for p, t in self.texts if re.search(pattern, t)]
            if hits:
                self.review('P7', name, '词命中只用于审查，须区分业务含义与实现噪声。', count=len(hits), examples=hits[:8])
        counts = Counter(t for _, t in self.texts if len(t) > 120)
        duplicates = [{'text': t[:200], 'occurrences': n} for t, n in counts.items() if n > 1]
        if duplicates:
            self.review('P7', 'repeated_long_labels', '长度仅用于定位候选，不作为语义配额；逐项审查重复长标签。', count=len(duplicates), examples=duplicates[:8])

    def check_p8(self):
        if self.selection is None:
            self.review('P8', 'local_mechanism_columns', '缺少对象语义选择账本；不能按函数名自动裁定机制对象。')
            return
        local = [x for x in self.selection['items'] if x['disposition'] == 'local_mechanism']
        bad = [x for x in local if x.get('actorRef') in self.actor_by_id or x.get('ownerActionRef') not in {a['id'] for a in self.actions} or not x.get('businessMeaning') or not x.get('sourceRefs')]
        self.result('P8', 'local_mechanism_columns', bad, local_objects=len(local))

    def check_p9(self):
        by_basis = defaultdict(list)
        invs = {m.get('invocationRef') for m in self.messages}
        for m in self.messages:
            if m['kind'] == 'request':
                key = (binding_key(m.get('bindingRef')), (self.actor_by_id.get(m['toActorId'], {}).get('declarationRef') or body_key(self.actor_by_id.get(m['toActorId'], {}).get('bodyRef'))))
                by_basis[key].append(m['messageId'])
        duplicates = [{'basis': k, 'requests': v} for k, v in by_basis.items() if len(v) > 1]
        # A static call may have distinct proven protocol roles; only fail if canonical
        # member data proves duplication, otherwise demand review rather than merging.
        members = (self.external or {}).get('business_members') or self.conversion.get('members')
        if members is not None:
            canonical = defaultdict(list)
            for m in members:
                key = m.get('canonical_key')
                if key is None:
                    key = [m.get('purposeRef'), m.get('targetActorRef'), m.get('stageRole'), m.get('basis')]
                canonical[json.dumps(key, sort_keys=True)].append(m.get('invocationRef'))
            bad = [{'canonical_key': k, 'invocations': v} for k, v in canonical.items() if len(v) > 1]
            self.result('P9', 'canonical_member_uniqueness', bad, members=len(members))
        if duplicates:
            self.review('P9', 'same_call_endpoint_requests', '相同调用依据/端点有多个请求，需核验是否独立角色或跨层副本。', count=len(duplicates), examples=duplicates[:8])
        else:
            self.result('P9', 'same_call_endpoint_requests', [], request_members=len(by_basis))
        bad = [{'purpose': p['id'], 'invocation': inv} for p in self.data.get('purposeProjections', []) for inv in p.get('invocationRefs', []) if inv not in invs and inv not in {c.get('invocationRef') for c in self.controls}]
        self.result('P9', 'purpose_member_references', bad)

    def check_p10(self):
        bad, bound = [], 0
        for d in self.execution.get('decisions', []):
            values = set(d['values'])
            covered = set()
            c = self.control_by_id.get(d.get('controlRef'))
            if c and c['id'] in self.attached and c['kind'] in {'alt', 'opt', 'loop'}:
                if c['kind'] == 'opt':
                    take, skip = set(d.get('takeValues', [])), set(d.get('skipValues', []))
                    if take and skip and not take & skip:
                        covered.update(take | skip)
                branch_ids = {b['id'] for b in c.get('branches', [])}
                for binding in d.get('branchBindings', []):
                    if binding['branchRef'] in branch_ids:
                        covered.update(binding['values'])
            scope = self.scopes.get(d.get('readingScopeRef'))
            if scope and self.scope_valid(scope):
                if scope['kind'] == 'loop':
                    covered.update(scope.get('repeat', {}).get('continueValues', []))
                    covered.update(scope.get('repeat', {}).get('exitValues', []))
                elif scope['kind'] == 'opt':
                    covered.update(scope.get('takeValues', [])); covered.update(scope.get('skipValues', []))
                else:
                    covered.update(v for b in scope.get('branches', []) for v in b.get('when', []))
            if values != covered:
                bad.append({'decision': d['id'], 'missing_values': sorted(values-covered), 'extra_values': sorted(covered-values), 'controlRef': d.get('controlRef'), 'readingScopeRef': d.get('readingScopeRef')})
            else:
                bound += 1
        self.result('P10', 'decision_visible_value_coverage', bad, decisions=len(self.execution.get('decisions', [])), fully_bound=bound)
        bad = [{'id': u['id'], 'kind': kind} for u, kind in self.units if self.summaries.get(u['id'], {}).get('kind') != kind or not self.summaries.get(u['id'], {}).get('text', '').strip()]
        self.result('P10', 'collapsed_summary_coverage', bad, reading_nodes=len(self.units))
        hidden = [m['messageId'] for m in self.messages if m['messageId'] not in self.visible_messages]
        self.result('P10', 'message_render_attachments', hidden, messages=len(self.messages))
        if self.lineage is None:
            self.review('P10', 'source_to_visible_reconciliation', '缺少通用关系对账表；已有 decision 绑定不能证明全部源业务关系均可见。')
            return
        expected = {e['id'] for e in self.semantic_edges()}
        for c in (self.external or {}).get('clauses', []):
            ref = c.get('id') or c.get('invocationRef')
            if ref:
                expected.add(ref)
        records = self.lineage.get('relations', [])
        indexed = {r['sourceRef']: r for r in records}
        bad = [{'missing_source': r} for r in sorted(expected-set(indexed))]
        bad += [{'duplicate_source': key} for key, n in Counter(r['sourceRef'] for r in records).items() if n > 1]
        for r in records:
            reps = r.get('representations', [])
            if not r.get('evidenceRefs') or not reps or any(not self.representation_valid(v) for v in reps):
                bad.append({'source': r['sourceRef'], 'representations': reps, 'reason': 'missing evidence or nonvisible target'})
        self.result('P10', 'source_to_visible_reconciliation', bad, required_relations=len(expected), mapped_relations=len(records))
        if self.stage_edges is None or self.external is None:
            self.review('P10', 'reconciliation_inventory_completeness', '缺上游边/协作清单，不能证明对账表的源全集。')

    def scope_valid(self, scope):
        units = {u['id'] for u, _ in self.units}
        return bool(scope.get('condition') and scope.get('members')) and all(m['ref'] in units for m in scope['members'])

    def representation_valid(self, rep):
        kind, ref = rep.get('kind'), rep.get('ref')
        if kind == 'message':
            return ref in self.visible_messages
        if kind == 'control':
            c = self.control_by_id.get(ref, {})
            return ref in self.attached and any(c.get(k) for k in ['messages', 'condition', 'notes', 'after', 'branches', 'children'])
        if kind == 'readingScope':
            return ref in self.scopes and self.scope_valid(self.scopes[ref])
        if kind == 'outcome':
            if ref in self.branches:
                attached = any(c['id'] in self.attached and ref in {b['id'] for b in c.get('branches', [])} for c in self.controls)
                return attached and rep.get('field') == 'outcome' and bool(self.branches[ref].get('outcome'))
            return ref in self.attached and rep.get('field') in {'skip', 'notes', 'after'} and bool(self.control_by_id[ref].get(rep['field']))
        if kind == 'destination':
            return ref in self.marker_edge_refs()
        if kind == 'summary':
            return ref in {u['id'] for u, _ in self.units} and bool(self.summaries.get(ref, {}).get('text'))
        return False

    def marker_edge_refs(self):
        """Mirror loop-markers' edge selection, without inventing routes."""
        edges = list(self.exec_edges.values())
        decisions = {d['id']: d for d in self.execution.get('decisions', [])}
        owners = {o['controlRef']: o['owner'] for o in self.data.get('controlOwners', [])}
        # Nested controls inherit the unique root reading owner, as in renderer.
        for root in self.data.get('controls', []):
            owner = owners.get(root['id'])
            if owner:
                for control in tree([root]):
                    owners.setdefault(control['id'], owner)
        visible = set()

        def source_action(edge):
            n = self.exec_nodes.get(edge['from'], {})
            d = decisions.get(n.get('decisionRef'), {})
            owner = owners.get(d.get('controlRef'), {})
            return n.get('actionRef') or (owner.get('ref') if owner.get('kind') == 'action' else None)

        def compatible(a, b):
            return not any(g['decisionRef'] == h['decisionRef'] and g['value'] != h['value'] for g in a.get('guards', []) for h in b.get('guards', []))

        for scope in self.scopes.values():
            if scope['kind'] != 'loop':
                continue
            member_refs={m['ref'] for m in scope['members']}
            members={a['id'] for p in self.phases for g in p['goals'] for a in g['actions']
                     if a['id'] in member_refs or g['id'] in member_refs or p['id'] in member_refs}
            boundary = [e for e in edges if e.get('readingScopeRef') == scope['id'] and e['kind'] in {'loop-continue', 'loop-exit'}]
            back = [e for e in boundary if e['kind'] == 'loop-continue' and self.exec_nodes.get(e['to'], {}).get('actionRef') == scope['repeat'].get('entryActionRef')]
            if not back:
                continue
            visible.add(back[0]['id'])  # explicit loop entry marker
            def decision_paths(node_ref, guards, seen=frozenset()):
                if node_ref in seen or self.exec_nodes.get(node_ref, {}).get('kind') != 'decision':
                    return []
                paths=[]
                for first in edges:
                    if first['to'] != node_ref or first['kind'] == 'loop-continue' or not compatible(first, {'guards':guards}):
                        continue
                    if self.exec_nodes.get(first['from'], {}).get('kind') == 'action': paths.append([first])
                    else: paths.extend([*path, first] for path in decision_paths(first['from'], guards, seen | {node_ref}))
                return paths
            for end in boundary:
                if not self.exec_nodes.get(end['to'], {}).get('actionRef'):
                    continue
                if self.exec_nodes.get(end['from'], {}).get('kind') != 'decision':
                    if source_action(end) in members:
                        visible.add(end['id'])
                    continue
                for first in edges:
                    if first['to'] != end['from'] or first['kind'] == 'loop-continue' or not compatible(first, end):
                        continue
                    if source_action(first) in members:
                        visible.update([first['id'], end['id']])
                    if end['kind'] == 'loop-continue' and self.exec_nodes.get(first['from'], {}).get('kind') == 'action':
                        visible.update(arrival['id'] for arrival in edges if arrival['to'] == first['from'] and arrival['kind'] != 'loop-continue' and source_action(arrival) in members)
            for edge in edges:
                if self.exec_nodes.get(edge['to'], {}).get('kind') != 'terminal': continue
                if self.exec_nodes.get(edge['from'], {}).get('kind') == 'decision':
                    for path in decision_paths(edge['from'], edge.get('guards', [])):
                        if source_action(path[0]) in members: visible.update(e['id'] for e in [*path, edge])
                elif source_action(edge) in members: visible.add(edge['id'])
        return {ref for ref in visible if self.exec_edges[ref].get('evidenceRefs')}

    def check_p11(self):
        from terminal_loop_verifier import verify_terminal_loop
        bad = []
        loops = [s for s in self.scopes.values() if s['kind'] == 'loop']
        action_ids = {a['id'] for a in self.actions}
        for s in loops:
            member_refs={m['ref'] for m in s['members']}
            members={a['id'] for p in self.phases for g in p['goals'] for a in g['actions']
                     if a['id'] in member_refs or g['id'] in member_refs or p['id'] in member_refs}
            loop_classification = classifications.classify_loop(s)
            after = loop_classification['commonAfterActionRef']
            entry = s.get('repeat', {}).get('entryActionRef')
            linked = [e for e in self.exec_edges.values() if e.get('readingScopeRef') == s['id']]
            back = [e for e in linked if e['kind'] == 'loop-continue' and self.exec_nodes.get(e['to'], {}).get('actionRef') == entry]
            if s.get('terminalOnly'):
                declared=set(s['terminalOnly'].get('exitEdgeRefs', [])); terminals=set(s['terminalOnly'].get('terminalNodeRefs', []))
                exits=[e for e in linked if e['kind'] == 'loop-exit' and e['id'] in declared and e['to'] in terminals]
                proof_bad=verify_terminal_loop(self.data, self.read('raw-body.json') or {}, s)
                artifacts={a['id']:a for a in self.execution.get('artifacts', [])}; evidences={e['id']:e for e in self.execution.get('evidence', [])}
                ref=s['terminalOnly'].get('proofRef'); artifact=artifacts.get(ref) or artifacts.get(evidences.get(ref, {}).get('artifactRef'))
                try: certificate=json.loads(artifact['content']) if artifact else None
                except (TypeError, ValueError): certificate=None
                loop_classification=classifications.classify_loop(s, certificate if not proof_bad else None)
                member_bbs=set((certificate or {}).get('memberBBs', [])); incoming=defaultdict(list)
                for edge in self.exec_edges.values(): incoming[edge.get('to')].append(edge)
                def member_node(node): return node.get('kind') == 'action' and node.get('actionRef') in members
                def scope_decision(node, seen=frozenset()):
                    refs=node.get('basicBlockRefs', [])
                    if node.get('kind') != 'decision' or node.get('id') in seen or not refs or not set(refs) <= member_bbs: return False
                    parents=incoming[node.get('id')]
                    return bool(parents) and all(member_node(self.exec_nodes.get(e.get('from'), {})) or scope_decision(self.exec_nodes.get(e.get('from'), {}), seen | {node.get('id')}) for e in parents)
                def valid_terminal_exit(edge):
                    source=self.exec_nodes.get(edge.get('from'), {}); target=self.exec_nodes.get(edge.get('to'), {})
                    guard=source.get('kind') == 'decision' and any(g.get('decisionRef') == source.get('decisionRef') for g in edge.get('guards', []))
                    return ((member_node(source) or scope_decision(source) and guard)
                            and target.get('kind') == 'terminal' and target.get('outcome') in {'return','error'})
                valid_exit=(loop_classification['exitMode'] == 'terminalOnly' and bool(exits)
                            and declared == {e['id'] for e in linked if e['kind'] == 'loop-exit'}
                            and all(valid_terminal_exit(e) for e in exits))
            else:
                exits = [e for e in linked if e['kind'] == 'loop-exit' and self.exec_nodes.get(e['to'], {}).get('actionRef') == after]
                valid_exit=after in action_ids and after not in members and bool(exits)
                proof_bad=[]
            if not self.scope_valid(s) or entry not in members or not back or not valid_exit:
                bad.append({'scope': s['id'], 'entry': entry, 'after': after, 'back_edges': len(back), 'exit_edges': len(exits)})
            bad.extend({'scope':s['id'], 'proof':x} for x in proof_bad)
        for e in self.exec_edges.values():
            if e['kind'] in {'loop-continue', 'loop-exit'} and (e.get('readingScopeRef') not in self.scopes or not e.get('evidenceRefs')):
                bad.append({'edge': e['id'], 'reason': 'missing loop scope/evidence'})
        self.result('P11', 'loop_destinations', bad, loop_scopes=len(loops))
        if not loops:
            self.review('P11', 'business_loop_completeness', '当前无 loop scope；需核对源码是否存在遗漏的业务循环，不能从零数量推断没有循环。')

    def check_p12(self):
        nodes = self.details['nodes']
        bad = []
        for g in self.goals:
            expected = {bb for a in g['actions'] for bb in nodes.get(a['id'], {}).get('basic_block_refs', [])}
            actual = set(nodes.get(g['id'], {}).get('basic_block_refs', []))
            if actual != expected:
                bad.append({'goal': g['id'], 'missing': sorted(expected-actual), 'extra': sorted(actual-expected)})
        self.result('P12', 'goal_inherits_action_blocks', bad, goals=len(self.goals))
        if self.fact_edges is None or self.stage_edges is None:
            self.review('P12', 'internal_edges_not_goal_self_loops', '缺原边表或 goal 提升记录，需审查自环的入口/出口依据。')
            return
        facts = {e['id']: e for e in rows(self.fact_edges)}
        bad = []
        for e in self.semantic_edges():
            if e.get('depth') != 1.5 or e['source'] != e['target']:
                continue
            bbs = set(nodes.get(e['source'], {}).get('basic_block_refs', []))
            members = [facts[r] for r in e.get('members', []) if r in facts]
            if members and all(m['source'] in bbs and m['target'] in bbs for m in members):
                bad.append({'edge': e['id'], 'goal': e['source'], 'members': e['members'], 'kind': e['kind']})
        self.result('P12', 'internal_edges_not_goal_self_loops', bad, goal_self_edges=sum(e.get('depth') == 1.5 and e['source'] == e['target'] for e in self.semantic_edges()))
        unresolved = [e for e in self.semantic_edges() if e.get('depth') == 1.5 and e['source'] == e['target'] and e['id'] not in {b['edge'] for b in bad}]
        if unresolved:
            self.review('P12', 'goal_self_edge_roles', '这些自环并非两端均在 goal 内的原边；须审查是否将跨边界技术入口/出口伪装为自环，不自动当作业务循环。', count=len(unresolved), kinds=dict(Counter(e['kind'] for e in unresolved)))

    def check_p13(self):
        bad = [{'id': u['id'], 'label': u['label']} for u in self.goals + self.actions if not re.search(r'[\u3400-\u9fff]', u['label'])]
        self.result('P13', 'chinese_semantic_labels', bad, nodes=len(self.goals)+len(self.actions))
        names = {a['id']: a.get('label', '') for a in self.actions}
        bad = [{'id': n['id'], 'label': n.get('label')} for n in self.execution.get('nodes', [])
               if not re.search(r'[\u3400-\u9fff]', n.get('label') or names.get(n.get('actionRef'), ''))]
        self.result('P13', 'execution_semantic_labels', bad, nodes=len(self.execution.get('nodes', [])))
        if self.definitions is None:
            self.review('P13', 'original_body_names', '无 definitions 原名表；必须以源码身份核对函数名。')
            return
        from body_labels import actor_definitions, labels
        expected = labels(actor_definitions(self.data['actors'], self.definitions))
        bad = [dict(actor=a['actorId'],label=a['label'],expected=expected.get(a['actorId']))
               for a in self.actors if a['kind'] in ('body','declaration')
               and a['label'] != expected.get(a['actorId'])]
        checked = len(expected)
        self.result('P13', 'original_body_names', bad, checked=checked)

    def check_p14(self):
        from source_ranges import check_source
        self.read('input-pins.json', required=True)
        self.read('stage4/presentation.json', required=True)
        source_path = (self.out / self.data.get('functionSource', {}).get('sourcePath', 'source')).resolve()
        if source_path.is_relative_to(self.out / 'source') and source_path.is_file():
            raw = source_path.read_bytes()
            self.inputs[str(source_path.relative_to(self.out))] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.result('P14', 'full_function_source_and_node_ranges', check_source(self.data, self.out))
        from verify_source_evidence import verify, load_independent_context
        independent_context = load_independent_context(self.out)
        self.result('P14', 'independent_operation_source_bounds',
                    verify(self.data, self.read('raw-body.json') or {}, independent_context))
        from async_shell_verifier import verify_out as verify_async_shell
        async_shell_result = verify_async_shell(self.out)
        if async_shell_result.get('status') != 'not-applicable':
            self.result('P14', 'independent_async_shell_relation',
                        async_shell_result.get('failures', []))
        nodes = self.details['nodes']
        prelude_nodes = getattr(self, 'prelude_nodes', [])
        expected = {u['id']: depth for units, depth in [
            (prelude_nodes, 0.5), (self.goals, 1.5), (self.actions, 2)] for u in units}
        bad = [{'missing_node': ref} for ref in sorted(set(expected)-set(nodes))]
        bad += [{'unexpected_detail_node': ref} for ref in sorted(set(nodes)-set(expected))]
        raw = self.read('raw-body.json') or {}
        reading = {u['id']: u for u in prelude_nodes + self.goals + self.actions}
        for ref, depth in expected.items():
            n = nodes.get(ref, {})
            bbs = n.get('basic_block_refs', [])
            source = self.details.get('node_sources', {}).get(ref, {})
            snippets = source.get('rust_snippets', [])
            unit = reading[ref]
            source_less_handoff = (False if ref in {n['id'] for n in prelude_nodes}
                                   else classifications.empty_snippets_allowed(self.data, raw, unit, bbs))
            if n.get('depth') != depth or not bbs or len(bbs) != len(set(bbs)) or any(bb not in self.details['blocks'] for bb in bbs) or (not snippets and not source_less_handoff) or any(not s.get('code', '').strip() for s in snippets):
                bad.append({'node': ref, 'depth': n.get('depth'), 'bb_count': len(bbs), 'missing_blocks': sorted(set(bbs)-set(self.details['blocks'])), 'source_snippets': len(snippets)})
        self.result('P14', 'detail_scope_and_source', bad, expected_nodes=len(expected), actual_nodes=len(nodes), phase_details=sum(p['id'] in nodes for p in self.phases))

    def action_message_owners(self):
        owners = defaultdict(set)
        for action in self.actions:
            for ref in action.get('controlRefs', []):
                for control in tree([self.control_by_id[ref]] if ref in self.control_by_id else []):
                    for message in control.get('messages', []):
                        owners[message].add(action['id'])
        return owners

    def anchors_valid(self, refs):
        """Resolve evidence locally; a nonempty invented string is not evidence."""
        known = set(self.details['blocks']) | set(self.exec_edges)
        known.update(e['id'] for e in self.execution.get('evidence', []))
        known.update(e['id'] for e in rows(self.fact_edges))
        known.update(c['id'] for c in rows(self.calls))
        def valid(ref):
            if ref in known:
                return True
            match = re.fullmatch(r'(source/[^:]+):(\d+)(?:-(\d+))?', ref)
            if not match:
                return False
            path = (self.out / match[1]).resolve()
            if not path.is_relative_to(self.out / 'source') or not path.is_file():
                return False
            raw = path.read_bytes()
            self.inputs[match[1]] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            start, end = int(match[2]), int(match[3] or match[2])
            return 0 < start <= end <= len(raw.splitlines())
        return bool(refs) and all(isinstance(r, str) and valid(r) for r in refs)

    def check_g1(self):
        owners = self.action_message_owners()
        pairs = defaultdict(list)
        for m in self.messages:
            if m['kind'] in {'request', 'return'}:
                pairs[m.get('pair')].append(m)
        bad = []
        for pair, ms in pairs.items():
            sets = [owners[m['messageId']] for m in ms]
            if len(ms) != 2 or {m['kind'] for m in ms} != {'request', 'return'} or any(len(s) != 1 for s in sets) or len(set.union(set(), *sets)) != 1:
                bad.append({'pair': pair, 'owners': [sorted(s) for s in sets]})
        self.result('G1', 'unique_action_per_business_pair', bad, pairs=len(pairs))

    def check_g2(self):
        owners = self.action_message_owners()
        calls = set.union(set(), *(owners[m['messageId']] for m in self.messages if m['kind'] == 'request'))
        facts = (self.granularity or {}).get('businessFacts', [])
        valid = {'call', 'decision', 'state_change', 'business_result'}
        proven = {f.get('actionRef') for f in facts if f.get('kind') in valid and self.anchors_valid(f.get('evidenceRefs')) and f.get('claim')}
        bad = [f for f in facts if f.get('kind') not in valid or not self.anchors_valid(f.get('evidenceRefs')) or not f.get('claim') or f.get('actionRef') not in {a['id'] for a in self.actions}]
        self.result('G2', 'business_fact_records', bad, call_backed_actions=len(calls), declared_facts=len(facts))
        raw = self.read('raw-body.json') or {}
        exemptions = {a['id'] for a in self.actions if classifications.permits('G2', 'independent_fact_exception',
                      classifications.classify_action(self.data, raw, a))}
        missing = [a['id'] for a in self.actions if a['id'] not in calls | proven | exemptions]
        if missing:
            if self.granularity is None:
                self.review('G2', 'independent_fact_per_action', '无消息不等于无业务事实；需提供业务判断、状态变化或结果交付的源码证据。', actions=missing)
            else:
                self.result('G2', 'independent_fact_per_action', missing)
        else:
            self.result('G2', 'independent_fact_per_action', [], actions=len(self.actions))
        self.review('G2', 'action_boundary_semantics', '逐 action 核验独立业务效果；同一失败处理中连续的保全状态、报告事件、返回结果合为一个 action，除非中间被业务判断分开；正常与恢复路径仍分开。参数准备和直接取结果可留本 action。')

    def check_g3(self):
        from goal_contracts import fragmentation_runs, small_body_ratio
        records = (self.granularity or {}).get('goalContracts') or []
        runs = fragmentation_runs(self.phases, records)
        self.result('G3', 'consecutive_single_action_goals',
                    [r for r in runs if r['basis'] == 'contractRef'])
        suspicious = [r for r in runs if r['basis'] != 'contractRef']
        if suspicious:
            self.review('G3', 'repeated_goal_target_receiver',
                        '相邻单 action goals 共享目标或接收者；核对是否同一完成合同，不能用 callee 差异充当边界。', runs=suspicious)
        fact_blocks = getattr(self, 'fact_blocks', None)
        if isinstance(fact_blocks, dict) and 'blocks' in fact_blocks:
            fact_blocks = fact_blocks['blocks']
        if fact_blocks is None:
            block_count = sum(bool(re.fullmatch(r'bb[0-9]+', ref))
                              for ref in self.details.get('blocks', {}))
        else:
            block_count = len(fact_blocks)
        ratio = small_body_ratio(block_count, len(self.goals), len(self.actions))
        if ratio:
            self.review('G3', 'small_body_goal_action_ratio',
                        '小 body 的 goal/action 比例偏高；按源码合同审查过度拆分，比例本身不判失败。', **ratio)
        boundaries = (self.granularity or {}).get('boundaries')
        if boundaries is None:
            self.review('G3', 'goal_phase_boundaries', '缺少目的完成条件与阶段交接证据；不能由节点数量或标签证明边界。')
            return
        index = {b.get('ref'): b for b in boundaries}
        bad = []
        for unit in self.goals + self.phases:
            b = index.get(unit['id'], {})
            if not all(b.get(k) for k in ['purpose', 'completion', 'entry', 'exit']) or not self.anchors_valid(b.get('evidenceRefs')):
                bad.append(unit['id'])
        self.result('G3', 'goal_phase_boundaries', bad)
        from goal_contracts import contract_violations
        records = (self.granularity or {}).get('goalContracts')
        if records is None:
            self.review('G3', 'goal_completion_contracts', '缺少逐 action 完成合同账本；无法排除上位目的吞并独立状态承诺、恢复或终止协议。')
        else:
            known = {g['id']: g for g in self.goals}
            by_goal = {r.get('goalRef'): r for r in records}
            failures = []
            if len(by_goal) != len(records) or set(by_goal) != set(known):
                failures.append({'reason': 'goal coverage/uniqueness', 'missing': sorted(set(known)-set(by_goal)), 'extra': sorted(set(by_goal)-set(known))})
            for gid, goal in known.items():
                record = by_goal.get(gid, {})
                issues = contract_violations(record, [a['id'] for a in goal['actions']])
                if not self.anchors_valid(record.get('evidenceRefs')) or any(not self.anchors_valid(m.get('evidenceRefs')) for m in record.get('memberContracts', [])):
                    issues.append('unresolved contract evidence')
                if issues:
                    failures.append({'goalRef': gid, 'issues': issues})
            self.result('G3', 'goal_completion_contracts', failures, goals=len(known), records=len(records))

        self.review('G3', 'boundary_meaning', '核对 goal 的共同完成条件、phase 的生命周期交接及真实路径；分支类别或调用规模不能单独决定阶段。')

    def check_g4(self):
        start = len(self.checks)
        review_start = len(self.reviews)
        # Reuse value/attachment validation, but only import its decision check.
        self.check_p10()
        added = self.checks[start:]
        del self.checks[start:]
        del self.reviews[review_start:]
        for c in added:
            if c['check'] == 'decision_visible_value_coverage':
                self.checks.append({**c, 'principle': 'G4'})
        inventory = (self.granularity or {}).get('decisions')
        if inventory is None:
            self.review('G4', 'source_decision_inventory', '缺少源业务判断清单；已选 decision 全覆盖不能证明没有漏选源码分支。')
            return
        known = {d['id'] for d in self.execution.get('decisions', [])}
        bad = [r for r in inventory if not self.anchors_valid(r.get('evidenceRefs')) or (r.get('disposition') == 'business' and r.get('decisionRef') not in known) or (r.get('disposition') == 'mechanism' and not r.get('foldedInto')) or r.get('disposition') not in {'business', 'mechanism'}]
        self.result('G4', 'source_decision_inventory', bad, decisions=len(inventory))

    def check_g5(self):
        guards = (self.granularity or {}).get('memberGuards')
        opts = [c for c in self.controls if c['kind'] == 'opt' and c['id'] in self.attached]
        if guards is None:
            self.review('G5', 'member_guard_coverage', '缺少业务 guard 与绕过路径清单，须回源码逐成员核对；单侧可选成员需要 opt；完整互斥业务替代可用经证明的 alt。', visible_opts=len(opts))
            return
        bad, unresolved, proven, alternatives = [], [], [], []
        owners = self.action_message_owners()
        decisions = {d['id']: d for d in self.execution.get('decisions', [])}
        actions = {a['id'] for a in self.actions}
        for g in guards:
            inv = g.get('invocationRef')
            msgs = {m['messageId'] for m in self.messages if inv and m.get('invocationRef') == inv}
            members = set(g.get('memberActionRefs', []))
            decision = decisions.get(g.get('decisionRef'), {})
            take, skip = set(g.get('takeValues', [])), set(g.get('skipValues', []))
            partition = bool(take and skip) and not take & skip and take | skip == set(decision.get('values', []))
            # A missing proof is review, never evidence that a member is mandatory.
            if (not partition or not g.get('condition') or not g.get('skip')
                    or not (msgs or members and members <= actions)
                    or not self.anchors_valid(g.get('evidenceRefs'))
                    or not self.anchors_valid(g.get('bypassEvidenceRefs'))):
                unresolved.append(g)
                continue
            proven.append(g)
            scope = self.scopes.get(g.get('readingScopeRef'), {})
            if g.get('alternativeBranchRef'):
                branch = next((b for b in scope.get('branches', []) if b.get('id') == g['alternativeBranchRef']), {})
                groups = [self.expand_reading_members(b.get('members', [])) for b in scope.get('branches', [])]
                domains = [set(b.get('when', [])) for b in scope.get('branches', [])]
                branch_members = self.expand_reading_members(branch.get('members', []))
                valid_alt = (scope.get('kind') == 'alt' and self.scope_valid(scope)
                    and decision.get('readingScopeRef') == scope.get('id')
                    and len(groups) >= 2 and all(groups) and all(domains)
                    and sum(map(len, domains)) == len(set.union(set(), *domains))
                    and set.union(set(), *domains) == set(decision.get('values', []))
                    and sum(map(len, groups)) == len(set.union(set(), *groups))
                    and set.union(set(), *groups) == self.expand_reading_members(scope.get('members', []))
                    and take == set(branch.get('when', []))
                    and branch.get('condition') == g['condition']
                    and (not members or members <= branch_members)
                    and all(owners[m] and owners[m] <= branch_members for m in msgs))
                if valid_alt:
                    alternatives.append(g)
                else:
                    bad.append({**g, 'reason': 'alternative exemption requires exhaustive disjoint nonempty business branches and exact guarded-member coverage'})
                continue
            ref = g.get('controlRef') or scope.get('originControlRef') or decision.get('controlRef')
            c = self.control_by_id.get(ref, {})
            enclosed = {m for node in tree([c]) for m in node.get('messages', [])}
            visible_opt = (c.get('kind') == 'opt' and c.get('id') in self.attached
                           and c.get('condition') == g['condition'] and c.get('skip') == g['skip'])
            covered = bool(msgs) and msgs <= enclosed
            if members:
                # Local state/result members need an explicit scope-to-control link;
                # merely owning an optional message does not make an action optional.
                scope_members = self.expand_reading_members(scope.get('members', []))
                covered = (covered or not msgs) and (scope.get('kind') == 'opt'
                    and scope.get('originControlRef') == c.get('id')
                    and decision.get('readingScopeRef') == scope.get('id')
                    and take == set(scope.get('takeValues', []))
                    and skip == set(scope.get('skipValues', [])) and members <= scope_members)
            if msgs and scope.get('kind') == 'opt':
                # A body-free origin is painted once by its range projection.
                scope_members = self.expand_reading_members(scope.get('members', []))
                covered = (covered or (
                    scope.get('originControlRef') == c.get('id')
                    and decision.get('readingScopeRef') == scope.get('id')
                    and take == set(scope.get('takeValues', []))
                    and skip == set(scope.get('skipValues', []))
                    and all(owners[m] and owners[m] <= scope_members for m in msgs)))
            if not visible_opt or not covered:
                bad.append({**g, 'reason': 'guarded business member requires an enclosing visible opt control'})
        self.result('G5', 'member_guard_coverage', bad, guarded_members=len(guards), proven_members=len(proven))
        self.result('G5', 'guarded_members_require_nonzero_opt',
                    [{'guarded_members': len(proven)-len(alternatives), 'visible_opts': 0}] if len(proven)>len(alternatives) and not opts else [],
                    proven_members=len(proven), alternative_members=len(alternatives), visible_opts=len(opts))
        if unresolved:
            self.review('G5', 'member_guard_evidence', '缺少可解析的成员、业务 guard 或绕过证据；逐项补证后再判断 opt 覆盖。', count=len(unresolved), members=unresolved)
        self.review('G5', 'source_guard_inventory_completeness', '核对源码中配置可选准备、预算超限压缩、配置 hook 等业务 guard 是否全部进入清单；互斥替代必须逐成员登记 alternativeBranchRef；空清单或已有 opt/alt 不能证明没有遗漏。')

    def expand_reading_members(self, members):
        by_ref = {a['id']: {a['id']} for a in self.actions}
        by_ref.update({g['id']: {a['id'] for a in g['actions']} for g in self.goals})
        by_ref.update({p['id']: {a['id'] for g in p['goals'] for a in g['actions']} for p in self.phases})
        return set.union(set(), *(by_ref.get(m['ref'], set()) for m in members))

    def check_g6(self):
        loops = [s for s in self.scopes.values() if s['kind'] == 'loop']
        loop_members = {s['id']: self.expand_reading_members(s['members']) for s in loops}
        missing_loops = []
        for c in self.controls:
            if c['kind'] != 'loop' or c['id'] not in self.attached:
                continue
            owners = {a['id'] for a in self.actions for ref in a.get('controlRefs', [])
                      if any(n['id'] == c['id'] for n in tree([self.control_by_id[ref]]))}
            # An enclosing loop is not proof of this local business loop's scope.
            matches = [s for s in loops if
                       (s.get('originControlRef') == c['id'] and owners <= loop_members[s['id']])
                       or (owners and owners == loop_members[s['id']]
                           and s.get('repeat', {}).get('entryActionRef') in owners)]
            if not matches:
                missing_loops.append({'control': c['id'], 'owner_actions': sorted(owners)})
        for component in cyclic_components(self.exec_nodes, [(e['from'], e['to']) for e in self.exec_edges.values()]):
            actions = {self.exec_nodes[n]['actionRef'] for n in component if self.exec_nodes[n].get('actionRef')}
            if actions and not any(actions <= members for members in loop_members.values()):
                missing_loops.append({'scc_actions': sorted(actions)})
        self.result('G6', 'business_loop_reading_scopes', missing_loops)
        declared = (self.granularity or {}).get('ranges')
        if declared is None:
            self.review('G6', 'declared_ranges', '缺少源范围账本；图上的候选范围不能替代源业务范围证明。')
        else:
            bad = []
            decisions = {d['id']: d for d in self.execution.get('decisions', [])}
            for r in declared:
                s = self.scopes.get(r.get('readingScopeRef'), {})
                c = self.control_by_id.get(r.get('controlRef'), {})
                q = decisions.get(r.get('decisionRef'), {})
                exact = bool(s) and s.get('kind') == r.get('kind') and set(r.get('memberActionRefs', [])) == self.expand_reading_members(s.get('members', [])) and q.get('readingScopeRef') == s.get('id')
                if r.get('memberActionRefs'):
                    order = [a['id'] for a in self.actions]
                    refs = r['memberActionRefs']
                    positions = [order.index(a) for a in refs if a in order]
                    exact = exact and len(positions) == len(refs) and positions == list(range(min(positions), max(positions)+1))
                # Only local message conditions may use controls; business loops
                # and cross-action ranges always require reading scopes.
                if r.get('kind') != 'loop' and not r.get('memberActionRefs') and r.get('invocationRefs') and c.get('kind') == r.get('kind') and c.get('id') in self.attached:
                    exact = set(r['invocationRefs']) <= {node.get('invocationRef') for node in tree([c])}
                if not exact or not self.anchors_valid(r.get('evidenceRefs')):
                    bad.append(r)
            self.result('G6', 'declared_ranges', bad, ranges=len(declared))
        # A conservative branch-exclusive frontier: remove explicit iteration back
        # edges, retain all other branches, and stop at re-evaluation of this query.
        # This proves graph structure only, not authenticity of source claims.
        outgoing = defaultdict(list)
        for e in self.exec_edges.values():
            if e['kind'] != 'loop-continue':
                outgoing[e['from']].append(e)
        action_order = [a['id'] for a in self.actions]
        missing, candidates, inferred = [], [], []
        for q in self.execution.get('decisions', []):
            if self.scopes.get(q.get('readingScopeRef'), {}).get('kind') == 'loop':
                continue
            starts = [n['id'] for n in self.exec_nodes.values() if n.get('decisionRef') == q['id']]
            direct = {self.exec_nodes.get(e['to'], {}).get('actionRef') for ref in starts for e in outgoing[ref]}
            direct.discard(None)
            reached = {}
            for value in q['values']:
                seen, todo, acts = set(), list(starts), set()
                while todo:
                    ref = todo.pop()
                    if ref in seen:
                        continue
                    seen.add(ref)
                    node = self.exec_nodes.get(ref, {})
                    if node.get('actionRef'):
                        acts.add(node['actionRef'])
                    for e in outgoing[ref]:
                        if e['to'] in starts or q['id'] in e.get('resetDecisionRefs', []):
                            continue
                        if not any(g['decisionRef'] == q['id'] and g['value'] != value for g in e.get('guards', [])):
                            todo.append(e['to'])
                reached[value] = acts
            covered = set.union(set(), *(self.expand_reading_members(s['members']) for s in self.scopes.values() if s['id'] == q.get('readingScopeRef') or s.get('originControlRef') == q.get('controlRef') and q.get('controlRef')))
            for value, acts in reached.items():
                exclusive = acts - set.union(set(), *(a for v, a in reached.items() if v != value))
                # One branch may contain separated ranges; never enclose the gap.
                runs = []
                for a in action_order:
                    if a in exclusive:
                        if not runs or action_order.index(a) != action_order.index(runs[-1][-1]) + 1:
                            runs.append([])
                        runs[-1].append(a)
                for run in runs:
                    if not run:
                        continue
                    record = {'decision': q['id'], 'value': value, 'actions': run}
                    candidates.append(record)
                    if not set(run) <= covered:
                        inferred.append(record)
                    # Bounded branch entries are more focused review candidates:
                    # an earlier
                    # direct action alternative is conditionally skipped before a
                    # later direct alternative. Entire surviving tails after an
                    # early return are NOT automatically scope obligations.
                    bounded = [a for a in run if a in direct and any(action_order.index(b) > action_order.index(a) for b in direct)]
                    for a in bounded:
                        target_nodes = {n['id'] for n in self.exec_nodes.values() if n.get('actionRef') == a}
                        shared_entry = any(e['to'] in target_nodes and e['from'] not in starts for e in self.exec_edges.values())
                        if a not in covered and not shared_entry:
                            missing.append({**record, 'actions': [a]})
        if missing:
            self.review('G6', 'bounded_conditional_entries', '这些较早的条件入口没有绑定同一 decision 的范围；需回源码判定为遗漏、局部条件表达或其他等价范围，不凭图形候选直接判错。', candidate_ranges=len(candidates), count=len(missing), examples=missing)
        else:
            self.result('G6', 'bounded_conditional_entries', [], candidate_ranges=len(candidates))
        if inferred:
            self.review('G6', 'inferred_ranges', '可达性候选不自动等于展示义务：须区分提前退出后的正常尾部、复用 guard 与真正条件范围。', count=len(inferred), examples=inferred[:8])
        self.review('G6', 'source_range_inventory', '核对源码中跨成员条件和业务循环的入口、汇合、回边；逐项注入、step 循环即使只重复一个 action 也须有 readingScope。仅局部消息条件可用 control；execution 中未建的判断须回源码查漏。')

    def check_g7(self):
        owners = self.action_message_owners()
        action_goal = {a['id']: g['id'] for g in self.goals for a in g['actions']}
        inv_goals = defaultdict(set)
        for m in self.messages:
            if m['kind'] == 'request':
                inv_goals[m.get('invocationRef')].update(action_goal[a] for a in owners[m['messageId']])
        covered = defaultdict(set)
        for p in self.data.get('purposeProjections', []):
            for inv in p.get('invocationRefs', []) + p.get('waitRefs', []):
                covered[inv].update([p.get('goalRef'), *p.get('relatedGoalRefs', [])])
        bad = [{'invocation': inv, 'missing_goals': sorted(gs-covered[inv])} for inv, gs in inv_goals.items() if not gs <= covered[inv]]
        self.result('G7', 'purpose_covers_business_members', bad, business_goals=len(set.union(set(), *inv_goals.values())), local_only_goals=len(self.goals)-len(set.union(set(), *inv_goals.values())))

    def check_g8(self):
        bad = []
        by_id = {m['messageId']: m for m in self.messages}
        for a in self.actions:
            ordered = [m for ref in a.get('controlRefs', []) for c in tree([self.control_by_id[ref]]) for m in c.get('messages', [])]
            for i, ref in enumerate(ordered):
                m = by_id.get(ref, {})
                if m.get('kind') == 'return' and not any(by_id.get(r, {}).get('kind') == 'request' and by_id[r].get('pair') == m.get('pair') for r in ordered[:i]):
                    bad.append({'action': a['id'], 'return': ref})
        self.result('G8', 'sequence_preserves_call_order', bad)
        self.review('G8', 'control_shape_semantics', 'sequence 表示实际先后，alt 表示互斥业务结果，有业务 guard 与绕过路径的成员必须用 opt（由 G5 逐成员机检）；例如配置启用才准备、预算超限才压缩、配置 hook 才执行。逐调用为 Result/Option 处理包装 opt 是反例，skip 不能复述进入条件。')

    def check_g9(self):
        groups = (self.granularity or {}).get('purposeGroups')
        if groups is None:
            self.review('G9', 'purpose_group_boundaries', '缺少对象—业务目的—阶段/条件—结果分组依据；一个 goal 可以有多个目的组，不能直接按 goal 或 callee 聚合。')
            return
        refs = {p['id'] for p in self.data.get('purposeProjections', [])}
        bad = [g for g in groups if g.get('projectionRef') not in refs or not all(g.get(k) for k in ['object', 'purpose', 'result']) or not self.anchors_valid(g.get('evidenceRefs'))]
        bad += [{'missing_projection_basis': ref} for ref in refs - {g.get('projectionRef') for g in groups}]
        self.result('G9', 'purpose_group_boundaries', bad)
        self.review('G9', 'purpose_group_meaning', '核对成员共享业务目的、条件和结果；不同请求目的不能因同 goal 或同参与者而合并。')

    def check_g10(self):
        blocks = self.fact_blocks
        if blocks is None:
            blocks = {ref: block for ref, block in self.details['blocks'].items()
                      if re.fullmatch(r'bb[0-9]+', ref)}
            self.review('G10', 'complete_business_inventory', '缺少 facts/blocks.json；覆盖差集仅针对详情中已有 BB，不能据此宣称整个 body 已覆盖。')
        elif isinstance(blocks, dict):
            blocks = blocks.get('blocks', blocks)
        universe = set(blocks) if isinstance(blocks, dict) else {
            b.get('id', b.get('bb', f"bb{b.get('basic_block')}")) for b in blocks}
        assigned = {bb for a in self.actions for bb in
                    self.details['nodes'].get(a['id'], {}).get('basic_block_refs', [])}
        raw = self.read('raw-body.json') or {}
        event_macro_artifacts = classifications.load_event_macro_artifacts(self.out) if hasattr(self, 'out') else []
        block_map = blocks if isinstance(blocks, dict) else {b.get('id', b.get('bb', f"bb{b.get('basic_block')}")): b for b in blocks}
        technical, invalid = {}, []
        for record in (self.granularity or {}).get('technicalBlocks', []):
            bb = record.get('bbRef')
            if (bb not in universe or bb in technical or not self.anchors_valid(record.get('evidenceRefs'))
                    or not classifications.technical_record_valid(raw, block_map[bb], record, event_macro_artifacts)):
                invalid.append(record)
            else:
                technical[bb] = record['category']
        self.result('G10', 'technical_block_ledger', invalid, categories=dict(Counter(technical.values())))
        # Absence of an action is never evidence of a technical exemption.
        # In particular, Drop/Return terminators can accompany business effects.
        missing = sorted(universe - assigned - technical.keys())
        self.result('G10', 'reading_tree_bb_coverage', missing, blocks=len(universe),
                    assigned_blocks=len(universe & assigned), technical_exemptions=len(technical),
                    unassigned_without_technical_exemption=missing)
        self.check_shell_prelude_g10()
        bad_handoffs, handoff_count = classifications.handoff_boundaries(self.data, raw, self.actions, self.goals)
        self.result('G10', 'pure_loop_handoff_boundary', bad_handoffs, handoff_actions=handoff_count)
        self.review('G10', 'technical_purity_and_common_tail', '核对技术豁免逐块纯度与类别；笼统的 cleanup/state/terminal/drop 说明不构成类别证明。循环回入口前共同收尾必须有 action，不能由 continue 标记替代。')

    def check_shell_prelude_g10(self):
        """Apply the primary-body G10 ledger rule to a retained shell pin."""
        if not hasattr(self, 'out'):
            return
        pins = self.read('input-pins.json')
        pin = (pins or {}).get('async_shell_prelude')
        if not isinstance(pin, dict):
            return
        failures = []
        try:
            path = (self.out / pin['path']).resolve()
            expected = pin['sha256']
            if (self.out not in path.parents
                    or not re.fullmatch(r'[a-f0-9]{64}', expected)):
                raise ValueError('invalid pin')
            content = path.read_bytes()
            actual = hashlib.sha256(content).hexdigest()
            self.inputs[str(path.relative_to(self.out))] = {
                'bytes': len(content), 'sha256': actual}
            if actual != expected:
                failures.append({'code': 'shell-pin-sha256-mismatch',
                                 'expected': expected, 'actual': actual})
            shell = json.loads(content)
            if shell.get('owner_def_path_hash') != pin.get('def_path_hash'):
                failures.append({'code': 'shell-pin-owner-mismatch'})
        except (KeyError, OSError, TypeError, ValueError, UnicodeDecodeError):
            shell = None
            failures.append({'code': 'invalid-shell-pin'})
        prelude = self.data.get('prelude')
        claim = self.read('classification.json') or {}
        relation = claim.get('relation')
        if not isinstance(relation, dict):
            failures.append({'code': 'missing-shell-relation'})
            self.result('G10', 'shell_prelude_ledger', failures, technical_records=0)
            self.result('G10', 'shell_prelude_bb_coverage', failures,
                        shell_blocks=0, prelude_blocks=0, technical_blocks=0)
            return
        mode = claim.get('mappingMode')
        if mode == 'retained-relation' and (not isinstance(prelude, dict) or not prelude.get('nodes')):
            failures.append({'code': 'missing-retained-shell-prelude'})
        if mode == 'strict-forward' and prelude is not None:
            failures.append({'code': 'strict-forward-prelude-must-be-absent'})
        if isinstance(prelude, dict) and prelude.get('relation') != relation:
            failures.append({'code': 'prelude-relation-mismatch'})
        records = relation.get('technicalBlocks') or []
        blocks = ({f"shell:bb{b.get('basic_block')}": b for b in shell.get('basic_blocks', [])}
                  if isinstance(shell, dict) else {})
        artifacts = classifications.load_event_macro_artifacts(self.out)
        valid = {}; invalid = list(failures)
        for record in records if isinstance(records, list) else []:
            ref = record.get('bbRef') if isinstance(record, dict) else None
            local = ({**record, 'bbRef': ref[6:],
                      'evidenceRefs': [value[6:] for value in record.get('evidenceRefs', [])]}
                     if isinstance(ref, str) and re.fullmatch(r'shell:bb[0-9]+', ref)
                     and all(re.fullmatch(r'shell:bb[0-9]+', value)
                             for value in record.get('evidenceRefs', [])) else None)
            if (local is None or ref not in blocks or ref in valid or record.get('evidenceRefs') != [ref]
                    or record.get('factSha256') != classifications.fingerprint(blocks[ref])
                    or not classifications.technical_record_valid(
                        shell, blocks[ref], local, artifacts)):
                invalid.append(record)
            else:
                valid[ref] = record
        if not isinstance(records, list):
            invalid.append({'code': 'invalid-shell-technical-ledger-shape'})
        self.result('G10', 'shell_prelude_ledger', invalid,
                    technical_records=len(records) if isinstance(records, list) else 0,
                    valid_technical_records=len(valid))
        if mode == 'strict-forward':
            strict_failures = list(failures)
            proof = strict_forward_shell(shell, relation.get('innerDefPathHash')) if isinstance(shell, dict) else False
            if not proof:
                strict_failures.append({'code': 'strict-forward-shell-proof-failed'})
            self.result('G10', 'shell_prelude_bb_coverage', strict_failures,
                        shell_blocks=len(blocks), prelude_blocks=0,
                        technical_blocks=len(valid), mapping_mode=mode)
            return
        refs = [ref for node in (prelude or {}).get('nodes', [])
                for ref in node.get('basicBlockRefs', [])]
        prelude_refs = set(refs)
        coverage = []
        if len(refs) != len(prelude_refs):
            coverage.append({'code': 'duplicate-shell-prelude-bb'})
        overlap = prelude_refs & set(valid)
        if overlap:
            coverage.append({'code': 'shell-business-technical-overlap',
                             'bbRefs': sorted(overlap)})
        unexplained = set(blocks) - prelude_refs - set(valid)
        extra = (prelude_refs | set(valid)) - set(blocks)
        if unexplained:
            coverage.append({'code': 'unexplained-shell-bb',
                             'bbRefs': sorted(unexplained)})
        if extra:
            coverage.append({'code': 'unknown-shell-bb', 'bbRefs': sorted(extra)})
        self.result('G10', 'shell_prelude_bb_coverage', coverage,
                    shell_blocks=len(blocks), prelude_blocks=len(prelude_refs),
                    technical_blocks=len(valid))

    def check_g11(self):
        if not self.exec_nodes or not self.exec_edges:
            self.review('G11', 'cross_phase_loop_scope', '缺少 execution 图，无法检查跨 phase 循环及执行顺序。')
            return
        action_phase = {a['id']: p['id'] for p in self.phases for g in p['goals'] for a in g['actions']}
        loops = [s for s in self.scopes.values() if s['kind'] == 'loop']
        bad, components = [], []
        for component in cyclic_components(self.exec_nodes, [(e['from'], e['to']) for e in self.exec_edges.values()]):
            actions = {self.exec_nodes[n]['actionRef'] for n in component if self.exec_nodes[n].get('actionRef')}
            phases = {action_phase[a] for a in actions if a in action_phase}
            if len(phases) <= 1:
                continue
            matching = []
            for scope in loops:
                members = self.expand_reading_members(scope.get('members', []))
                entry = scope.get('repeat', {}).get('entryActionRef')
                back = [e for e in self.exec_edges.values() if e['kind'] == 'loop-continue'
                        and e.get('readingScopeRef') == scope['id']
                        and e['from'] in component and e['to'] in component
                        and self.exec_nodes[e['to']].get('actionRef') == entry
                        and self.anchors_valid(e.get('evidenceRefs'))]
                if actions <= members and entry in members and self.scope_valid(scope) and back:
                    matching.append(scope['id'])
            record = {'actions': sorted(actions), 'phases': sorted(phases), 'loop_scopes': matching}
            components.append(record)
            if not matching:
                bad.append(record)
        self.result('G11', 'cross_phase_loop_scope', bad, cross_phase_components=components)
        # Follow through decision/entry nodes to the next action. Explicit loop
        # back edges are the only exemption from forward phase execution order.
        order = {p['id']: i for i, p in enumerate(self.phases)}
        outgoing = defaultdict(list)
        for edge in self.exec_edges.values():
            if edge['kind'] != 'loop-continue':
                outgoing[edge['from']].append(edge['to'])
        backwards = []
        for ref, node in self.exec_nodes.items():
            source = node.get('actionRef')
            if source not in action_phase:
                continue
            seen, todo = {ref}, list(outgoing[ref])
            while todo:
                target_ref = todo.pop()
                if target_ref in seen:
                    continue
                seen.add(target_ref)
                target = self.exec_nodes.get(target_ref, {}).get('actionRef')
                if target in action_phase:
                    if order[action_phase[target]] < order[action_phase[source]]:
                        backwards.append({'from_action': source, 'to_action': target,
                                          'from_phase': action_phase[source], 'to_phase': action_phase[target]})
                else:
                    todo.extend(outgoing[target_ref])
        self.result('G11', 'phase_execution_order', backwards)
        self.review('G11', 'lifecycle_handoff_and_result_paths', '循环可在生命周期交接点跨多个 phase，按执行顺序排列；SCC 不限制 phase 数。须回源码核对交接与 execution 完整性，不能只按成功、错误等结果类别拆 phase。')

    def run(self):
        rules_path = Path(__file__).resolve().parents[1] / 'resources/rules.json'
        rules = json.loads(rules_path.read_text())
        principles = []
        for rule in rules['display_principles'] + rules.get('granularity_standards', []):
            getattr(self, 'check_' + rule['id'].lower())()
            for check in rule.get('checks', []):
                if check['mode'] == 'review':
                    self.review(rule['id'], check['id'], check['method'], **dict(pass_condition=check['pass_condition'], **({'environment_gate':check['environment_gate']} if 'environment_gate' in check else {})))
            checks = [c for c in self.checks if c['principle'] == rule['id']]
            status = 'fail' if any(c['status'] == 'fail' for c in checks) else 'pass'
            principles.append({'id': rule['id'], 'status': status, 'source_section': rule['source_section'], 'function': 'check_' + rule['id'].lower(), 'agent_decision_complete': not any(c['status']=='fail' for c in checks)})
        requests = [m for m in self.messages if m['kind'] == 'request']
        counts = {'actors_top': len(self.data['actors']), 'actors_recursive': len(self.actors), 'actor_kinds': dict(Counter(a['kind'] for a in self.actors)),
                  'phases': len(self.phases), 'goals': len(self.goals), 'actions': len(self.actions), 'messages': len(self.messages), 'message_kinds': dict(Counter(m['kind'] for m in self.messages)),
                  'request_pairs': len(requests), 'requests_with_await_ref': sum(bool(m.get('awaitRef')) for m in requests), 'requests_without_await_ref': sum(not m.get('awaitRef') for m in requests),
                  'request_stages': dict(Counter(m.get('stage', 'unspecified') for m in requests)),
                  'controls_top': len(self.data['controls']), 'controls_recursive': len(self.controls), 'execution_decisions': len(self.execution.get('decisions', [])), 'reading_scopes': len(self.scopes)}
        failed = [p['id'] for p in principles if p['status'] == 'fail']
        return {'format': 'display-principles/1', 'out': str(self.out), 'inputs': self.inputs,
                'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'rules_sha256': hashlib.sha256(rules_path.read_bytes()).hexdigest(),
                'counts': counts, 'machine_passed': not failed,
                'failed_principles': failed, 'acceptance_complete': False, 'principle_decisions_complete': not failed, 'principles': principles, 'checks': self.checks, 'review_items': self.reviews, 'warnings':[c for c in self.checks if c['status']=='warning'],
                'limitations': ['agent decisions require current evidence; browser checks are separate', 'counts are diagnostic, never quotas', 'missing correctness evidence is a failure']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--report', type=Path, help='Write report here; default stdout. Never overwrites an input.')
    args = parser.parse_args()
    try:
        audit = Audit(args.out)
        report = audit.run()
        if args.report and args.report.resolve() in {(args.out / p).resolve() for p in audit.inputs}:
            raise ValueError('report path would overwrite an audited input')
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(encoded)
            print(json.dumps({'report': str(args.report), 'machine_passed': report['machine_passed'], 'failed_principles': report['failed_principles'], 'review_items': len(report['review_items'])}, ensure_ascii=False))
        else:
            print(encoded, end='')
        return 0 if report['machine_passed'] else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error), 'status': 'input_error'}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
