"""Early classification stage; consumers read roles and attributes from here."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


POLICY = json.loads((Path(__file__).resolve().parents[1] / 'assets/renderer/classification-registry.mjs').read_text().split('export default ', 1)[1].strip().removesuffix(';'))
TECHNICAL_CATEGORIES = frozenset(POLICY['technicalCategories'])
ARTIFACT_KINDS = {'StorageLive', 'StorageDead', 'Drop', 'UnwindResume',
                  'UnwindTerminate', 'SetDiscriminant', 'Deinit', 'Nop'}


def fingerprint(block):
    return hashlib.sha256(json.dumps(block, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def classify_body(mapping_mode=None, execution_form='sync', status='verified', relation=None):
    modes = POLICY['roles']['body']['mappingModes']
    if mapping_mode is not None and mapping_mode not in modes:
        raise ValueError('Unknown body mapping mode: ' + str(mapping_mode))
    if execution_form not in POLICY['roles']['body']['executionForms']:
        raise ValueError('Unknown body execution form: ' + str(execution_form))
    if status not in ('verified', 'needs-evidence'):
        raise ValueError('Unknown body classification status: ' + str(status))
    return {'kind': 'async-shell' if mapping_mode else 'direct',
            'executionForm': execution_form, 'mappingMode': mapping_mode,
            'status': status, 'relation': relation}


def _body_id(raw):
    return '|'.join(str(raw.get(key, '')) for key in
                    ('owner_def_path_hash', 'capture_stage', 'body_id'))


def _async_constructions(raw):
    """Return unique closure/coroutine construction sites from raw MIR."""
    found = []
    for block in raw.get('basic_blocks', []):
        for statement in block.get('statements', []):
            rvalue = statement.get('detail', {}).get('rvalue', {})
            aggregate = rvalue.get('detail', {}).get('aggregate_kind', {})
            if aggregate.get('kind') not in ('Closure', 'Coroutine'):
                continue
            owner = aggregate.get('detail', {}).get('definition', {}).get('def_path_hash')
            if isinstance(owner, str):
                found.append((block.get('basic_block'), owner))
    return list(dict.fromkeys(found))


def _normal_successors(block, known):
    """Return normal (never unwind/cleanup) CFG successors for one MIR block."""
    term = block.get('terminator', {}); detail = term.get('detail', {})
    kind = term.get('kind'); targets = []
    if kind == 'SwitchInt':
        targets.extend(item.get('target') for item in detail.get('targets', []))
        targets.append(detail.get('otherwise'))
    elif kind in ('Goto', 'Call', 'Drop', 'Assert'):
        targets.append(detail.get('target'))
    elif kind in ('FalseEdge', 'FalseUnwind'):
        targets.append(detail.get('real_target'))
    elif kind == 'Yield':
        targets.append(detail.get('resume'))
    # rustc's resume/poison guards can be Assert self-loops.  They are not a
    # source-level cycle and are explicitly outside the shell-cycle rule.
    if kind == 'Assert':
        targets = [target for target in targets if target != block.get('basic_block')]
    return list(dict.fromkeys(target for target in targets if target in known))


def _cfg_components(blocks):
    """Tarjan SCCs over normal MIR edges."""
    graph = {number: _normal_successors(block, blocks)
             for number, block in blocks.items() if not block.get('is_cleanup')}
    index = 0; indices = {}; low = {}; stack = []; on_stack = set(); found = []

    def visit(node):
        nonlocal index
        indices[node] = index; low[node] = index; index += 1
        stack.append(node); on_stack.add(node)
        for target in graph.get(node, []):
            if target not in graph:
                continue
            if target not in indices:
                visit(target); low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component = set()
            while True:
                item = stack.pop(); on_stack.remove(item); component.add(item)
                if item == node:
                    break
            found.append(component)

    for node in graph:
        if node not in indices:
            visit(node)
    return graph, found


def _ready_place(place, poll_local):
    return (place.get('local') == poll_local
            and any(item.get('kind') == 'Downcast'
                    and item.get('detail', {}).get('variant_name') == 'Ready'
                    for item in place.get('projection', [])))


def _drop_target(name):
    """Return the single outer type argument of an exact drop_in_place call."""
    marker = 'drop_in_place::<'
    start = name.find(marker)
    if start < 0:
        return None
    start += len(marker); depth = 0
    for index in range(start, len(name)):
        char = name[index]
        if char == '<':
            depth += 1
        elif char == '>':
            if depth:
                depth -= 1
            else:
                return name[start:index] if name[index + 1:] == '}' else None
    return None


def _allowed_ready_call(term, inner_type):
    """Accept only Span or Instrumented around this exact inner closure type."""
    name = (term.get('detail', {}).get('func', {}).get('detail', {})
            .get('constant', {}).get('type', {}).get('display', ''))
    target = _drop_target(name)
    return (target == 'tracing::Span'
            or target == f'tracing::instrument::Instrumented<{inner_type}>')


def _ready_reaches_completion(blocks, poll_number, poll_local, inner_type):
    """Prove this poll's Ready payload moves to _0 with no later business call."""
    start = _normal_successors(blocks[poll_number], blocks)
    pending = list(start); seen = set(); ready = []
    while pending:
        number = pending.pop()
        if number in seen:
            continue
        seen.add(number); block = blocks[number]
        extracts = [statement for statement in block.get('statements', [])
                    if statement.get('kind') == 'Assign'
                    and any(_ready_place(place, poll_local) for place in
                            _places(statement.get('detail', {}).get('rvalue', {})))]
        if extracts:
            ready.append(number)
            continue
        term = block.get('terminator', {})
        if term.get('kind') not in ('Return', 'Unreachable', 'UnwindResume'):
            pending.extend(_normal_successors(block, blocks))
    if len(set(ready)) != 1:
        return False, set()
    ready_root = ready[0]; memo = {}; active = set()

    def complete(number, tainted):
        state = (number, tuple(sorted(tainted)))
        if state in memo:
            return memo[state]
        if number in active:
            return False
        active.add(number); block = blocks[number]; current = set(tainted)
        for statement in block.get('statements', []):
            if statement.get('kind') != 'Assign':
                continue
            detail = statement.get('detail', {}); destination = detail.get('destination', {})
            local = destination.get('local'); rvalue = detail.get('rvalue', {})
            if not isinstance(local, int) or destination.get('projection'):
                continue
            places = list(_places(rvalue))
            moves_ready = (rvalue.get('kind') == 'Use'
                           and (any(place.get('local') in current for place in places)
                                or any(_ready_place(place, poll_local) for place in places)))
            completes = (local == 0 and rvalue.get('kind') == 'Aggregate'
                         and any(place.get('local') in current for place in places))
            if moves_ready or completes:
                current.add(local)
            else:
                current.discard(local)
        term = block.get('terminator', {}); kind = term.get('kind')
        if kind == 'Return':
            result = 0 in current
        elif kind == 'Call' and not _allowed_ready_call(term, inner_type):
            result = False
        else:
            successors = _normal_successors(block, blocks)
            result = bool(successors) and all(complete(target, current)
                                              for target in successors)
        active.remove(number); memo[state] = result
        return result

    return complete(ready_root, set()), {ready_root}


def prove_async_shell_binding(shell, inner_owner):
    """Prove a one-shot child whose Ready output is the shell's output."""
    constructions = []
    for block in shell.get('basic_blocks', []):
        for statement in block.get('statements', []):
            detail = statement.get('detail', {}); rvalue = detail.get('rvalue', {})
            aggregate = rvalue.get('detail', {}).get('aggregate_kind', {})
            destination = detail.get('destination', {})
            if (aggregate.get('kind') == 'Coroutine'
                    and isinstance(destination.get('local'), int)):
                owner = aggregate.get('detail', {}).get('definition', {}).get('def_path_hash')
                constructions.append((block.get('basic_block'), owner, destination['local']))
    constructions = list(dict.fromkeys(constructions))
    if len(constructions) != 1 or constructions[0][1] != inner_owner:
        return None, len(constructions)
    construction_bb, _, seed = constructions[0]
    local_types = {item.get('local'): item.get('type', {}).get('display')
                   for item in shell.get('locals', [])}
    inner_type = local_types.get(seed)
    if not isinstance(inner_type, str) or not inner_type:
        return None, len(constructions)
    tainted = {seed}; changed = True
    while changed:
        changed = False
        for block in shell.get('basic_blocks', []):
            for statement in block.get('statements', []):
                detail = statement.get('detail', {}); destination = detail.get('destination', {})
                if (isinstance(destination.get('local'), int)
                        and any(place['local'] in tainted for place in _places(detail.get('rvalue', {})))
                        and destination['local'] not in tainted):
                    tainted.add(destination['local']); changed = True
            term = block.get('terminator', {}); detail = term.get('detail', {})
            destination = detail.get('destination', {})
            if (term.get('kind') == 'Call' and isinstance(destination.get('local'), int)
                    and any(place['local'] in tainted for place in _places(detail.get('args', [])))
                    and destination['local'] not in tainted):
                tainted.add(destination['local']); changed = True
    instrument = []; into_future = []; polls = []
    for block in shell.get('basic_blocks', []):
        term = block.get('terminator', {}); detail = term.get('detail', {})
        if (term.get('kind') != 'Call'
                or not any(place['local'] in tainted for place in _places(detail.get('args', [])))):
            continue
        name = (detail.get('func', {}).get('detail', {}).get('constant', {})
                .get('type', {}).get('display', ''))
        ref = f"shell:bb{block.get('basic_block')}"
        if ' as tracing::Instrument>::instrument}' in name:
            instrument.append(ref)
        if '::IntoFuture>::into_future}' in name:
            into_future.append(ref)
        if re.search(r' as (?:futures|std::future|core::future)::Future>::poll\}$', name):
            polls.append(ref)
    if not instrument or not into_future or not polls:
        return None, len(constructions)
    blocks = {block.get('basic_block'): block for block in shell.get('basic_blocks', [])
              if isinstance(block.get('basic_block'), int)}
    graph, components = _cfg_components(blocks)
    construction_chain = {construction_bb}
    construction_chain.update(int(ref[8:]) for ref in instrument + into_future)
    poll_numbers = {int(ref[8:]) for ref in polls}
    for component in components:
        cyclic = len(component) > 1 or any(node in graph.get(node, []) for node in component)
        if not cyclic:
            continue
        if component & construction_chain:
            return None, len(constructions)
        if component & poll_numbers:
            # The sole permitted poll cycle is the Pending re-poll of this
            # await: it may contain the poll, but no other call or shell setup.
            calls = {node for node in component
                     if blocks[node].get('terminator', {}).get('kind') == 'Call'}
            if not calls or not calls <= poll_numbers:
                return None, len(constructions)
    for poll_number in poll_numbers:
        destination = (blocks.get(poll_number, {}).get('terminator', {})
                       .get('detail', {}).get('destination', {}).get('local'))
        if not isinstance(destination, int):
            return None, len(constructions)
        complete, ready_roots = _ready_reaches_completion(
            blocks, poll_number, destination, inner_type)
        component = next((part for part in components if poll_number in part), set())
        if not complete or (len(component) > 1 and component & ready_roots):
            return None, len(constructions)
    return {'constructionBbRef': f'shell:bb{construction_bb}',
            'instrumentBbRefs': sorted(set(instrument)),
            'intoFutureBbRefs': sorted(set(into_future)),
            'pollBbRefs': sorted(set(polls))}, len(constructions)


def load_async_shell_prelude(out):
    """Load the exact-byte OUT-relative shell pin for a primary inner."""
    root = Path(out).resolve()
    try:
        pins = json.loads((root / 'input-pins.json').read_text())
    except (OSError, TypeError, ValueError):
        return None, 'missing-input-pins'
    pin = pins.get('async_shell_prelude')
    if not isinstance(pin, dict):
        return None, 'missing-shell-prelude-pin'
    try:
        path = (root / pin['path']).resolve()
        digest = pin['sha256']
        if (root not in path.parents or not re.fullmatch(r'[a-f0-9]{64}', digest)):
            return None, 'invalid-shell-pin'
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            return None, 'shell-pin-sha256-mismatch'
        shell = json.loads(content)
        if shell.get('owner_def_path_hash') != pin.get('def_path_hash'):
            return None, 'shell-pin-owner-mismatch'
        return {'raw': shell, 'sha256': digest, 'path': pin['path']}, None
    except (KeyError, OSError, TypeError, ValueError, UnicodeDecodeError):
        return None, 'invalid-shell-pin'


def classify_async_shell(raw, out):
    """Classify a primary inner from its pinned shell prelude."""
    artifact, reason = load_async_shell_prelude(out)
    if not artifact:
        return classify_body('retained-relation', 'coroutine', 'needs-evidence',
                             {'innerDefPathHash': raw.get('owner_def_path_hash'),
                              'evidenceFailure': reason})
    shell = artifact['raw']; inner_owner = raw.get('owner_def_path_hash')
    binding, count = prove_async_shell_binding(shell, inner_owner)
    thin = thin_coroutine_wrapper(shell)
    constructions = _async_constructions(shell)
    strict = bool(thin and thin.get('coroutine_def_path_hash') == inner_owner
                  and len(constructions) == 1 and constructions[0][1] == inner_owner)
    strict_construction = f'shell:bb{constructions[0][0]}' if strict else None
    if not binding and not strict:
        return classify_body('retained-relation', 'coroutine', 'needs-evidence',
                             {'shellBodyId': _body_id(shell),
                              'innerDefPathHash': raw.get('owner_def_path_hash'),
                              'constructionCandidates': count})
    proof = prove_instrumentation(shell, load_event_macro_artifacts(out))
    technical = []
    if not strict:
        extension_refs = set()
        for kind in POLICY['exceptions']['instrumentation']['proofKinds']:
            component = instrumentation_proof(shell, kind) or {}
            extension_refs.update(f'bb{number}'
                for key in ('source_less_goto_blocks', 'fake_return_blocks')
                for number in component.get(key, []))
        for ref, digest in sorted((proof or {}).get('technical_blocks', {}).items()):
            role = (proof or {}).get('block_roles', {}).get(ref)
            if (proof or {}).get('kind') == 'event_macro':
                role = 'event_macro'
            elif role != 'event_macro':
                role = ('span_wrapper_extension' if ref in extension_refs
                        else 'instrumentation_base')
            record = {'bbRef': 'shell:' + ref, 'category': 'instrumentation',
                      'reason': ('tracing event macro expansion' if role == 'event_macro'
                                 else 'generated tracing span wrapper'),
                      'evidenceRefs': ['shell:' + ref], 'factSha256': digest,
                      'blockRole': role}
            if role == 'event_macro':
                record['eventMacroProof'] = proof.get('block_proofs', {}).get(ref)
            technical.append(record)
    inner_bytes = (Path(out) / 'raw-body.json').read_bytes()
    binding = binding or {'constructionBbRef': strict_construction,
                          'instrumentBbRefs': [], 'intoFutureBbRefs': [], 'pollBbRefs': []}
    relation = {'shellBodyId': _body_id(shell),
                'innerDefPathHash': raw.get('owner_def_path_hash'),
                **binding, 'innerMirSha256': hashlib.sha256(inner_bytes).hexdigest(),
                'shellMirSha256': artifact['sha256'], 'technicalBlocks': technical}
    mode = 'strict-forward' if strict else 'retained-relation'
    return classify_body(mode, 'coroutine', relation=relation)


def classify_block(category=None, proof=None, bb_ref=None):
    if category is not None and category not in TECHNICAL_CATEGORIES:
        raise ValueError('Unknown technical category: ' + str(category))
    role = (proof or {}).get('block_roles', {}).get(bb_ref)
    return {'kind': role or POLICY['roles']['block']['technicalCategoryMap'].get(category, 'business'),
            'technicalCategory': category}


def classify_loop(scope, certificate=None):
    after = (scope.get('commonAfter') or {}).get('actionRef')
    terminal = scope.get('terminalOnly') or {}
    certified = bool(not after and terminal and certificate
                     and certificate.get('certificateKind') == 'terminal-loop'
                     and certificate.get('version') == 1
                     and certificate.get('scopeId') == scope.get('id')
                     and re.fullmatch(r'[a-f0-9]{64}', certificate.get('rawSha256', ''))
                     and certificate.get('memberBBs') and certificate.get('exitEdges')
                     and certificate.get('terminalBBs') and certificate.get('blocks'))
    return {'exitMode': 'commonAfter' if after else 'terminalOnly' if certified else None,
            'commonAfterActionRef': after, 'terminalOnlyCertificate': certificate if certified else None}


def _raw_sha256(raw, data):
    """Prefer the immutable MIR artifact bytes; fall back to canonical JSON."""
    for artifact in (data.get('execution') or {}).get('artifacts', []):
        if artifact.get('format') != 'mir':
            continue
        try:
            if json.loads(artifact.get('content', '')) == raw:
                digest = hashlib.sha256(artifact['content'].encode()).hexdigest()
                if digest == artifact.get('sha256'):
                    return digest
        except (TypeError, ValueError):
            pass
    encoded = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _scope_block_numbers(scope, data):
    phases = data.get('phases', [])
    actions = {a['id']: a for p in phases for g in p.get('goals', []) for a in g.get('actions', [])}
    goals = {g['id']: g for p in phases for g in p.get('goals', [])}
    by_phase = {p['id']: [a for g in p.get('goals', []) for a in g.get('actions', [])] for p in phases}
    selected = []
    for member in scope.get('members', []):
        if member.get('kind') == 'action' and member.get('ref') in actions:
            selected.append(actions[member['ref']])
        elif member.get('kind') == 'goal' and member.get('ref') in goals:
            selected.extend(goals[member['ref']].get('actions', []))
        elif member.get('kind') == 'phase':
            selected.extend(by_phase.get(member.get('ref'), []))
    refs = {r for a in selected for r in a.get('basicBlockRefs', []) if re.fullmatch(r'bb\d+', r)}
    return {int(r[2:]) for r in refs}


def _places(value):
    if isinstance(value, dict):
        if 'local' in value and 'projection' in value:
            yield value
        else:
            for child in value.values():
                yield from _places(child)
    elif isinstance(value, list):
        for child in value:
            yield from _places(child)


def _dead_locals(raw):
    reads = {p['local'] for v in raw.get('debug_variables', []) for p in _places(v)}
    written = set()
    for block in raw.get('basic_blocks', []):
        for op in [*block.get('statements', []), block.get('terminator', {})]:
            detail = op.get('detail', {}); destination = detail.get('destination', {})
            if destination and not destination.get('projection') and op.get('kind') in ('Assign', 'Call'):
                written.add(destination.get('local'))
                for key, value in detail.items():
                    if key != 'destination': reads.update(p['local'] for p in _places(value))
            elif op.get('kind') not in ('StorageLive', 'StorageDead', 'Nop'):
                reads.update(p['local'] for p in _places(detail))
    return {n for n in written if n is not None and n > raw.get('arg_count', 0) and n not in reads}


def _place_type(raw, place):
    types = {x['local']: x.get('type', {}) for x in raw.get('locals', [])}
    typ = types.get(place.get('local'), {})
    for step in place.get('projection', []):
        if step.get('kind') == 'Field':
            typ = step.get('detail', {}).get('field_type', {})
    return typ


def _side_effect_free_drop(display):
    compact = (display or '').replace(' ', '')
    exact = {'alloc::string::String', 'std::string::String',
             'codex_protocol::models::PermissionProfile'}
    if compact in exact:
        return True
    prefixes = ('std::vec::Vec<', 'alloc::vec::Vec<', 'std::vec::IntoIter<',
                'alloc::vec::IntoIter<', 'std::sync::Arc<', 'alloc::sync::Arc<',
                'std::rc::Rc<', 'alloc::rc::Rc<')
    if compact.startswith(prefixes):
        return True
    for wrapper in ('std::option::Option<', 'core::option::Option<',
                    'std::result::Result<', 'core::result::Result<'):
        if compact.startswith(wrapper) and compact.endswith('>'):
            inner = compact[len(wrapper):-1]
            # Result has two top-level parameters; both must independently pass.
            parts=[]; depth=0; start=0
            for i,ch in enumerate(inner):
                depth += ch == '<'; depth -= ch == '>'
                if ch == ',' and depth == 0: parts.append(inner[start:i]); start=i+1
            parts.append(inner[start:])
            return all(_side_effect_free_drop(x) or re.fullmatch(r'(?:u|i)(?:8|16|32|64|128|size)|bool|char|\(\)', x) for x in parts)
    return False


def prove_terminal_loop(raw, scope, data):
    """Prove an acyclic, cleanup-only union of every normal loop exit tail."""
    if scope.get('kind') != 'loop' or scope.get('commonAfter') or not scope.get('id'):
        return None
    blocks = {b['basic_block']: b for b in raw.get('basic_blocks', [])}
    members = _scope_block_numbers(scope, data)
    if not members or any(n not in blocks or blocks[n].get('is_cleanup') for n in members):
        return None
    def successors(block):
        term = block.get('terminator', {}); unwind = term.get('detail', {}).get('unwind', {})
        unwind_target = unwind.get('detail', {}).get('target') if isinstance(unwind, dict) else None
        return [n for n in term.get('successors', []) if n != unwind_target and n in blocks and not blocks[n].get('is_cleanup')]
    def suspension_tail(start):
        seen=set(); todo=[start]; pending=False; leaves=[]
        while todo:
            n=todo.pop()
            if n in seen or n in members: return False
            seen.add(n); block=blocks[n]; term=block.get('terminator', {})
            pending |= term.get('kind') == 'Yield'
            for statement in block.get('statements', []):
                d=statement.get('detail', {}); rd=d.get('rvalue', {}).get('detail', {})
                pending |= (d.get('destination') == {'local':0,'projection':[]}
                            and d.get('rvalue', {}).get('kind') == 'Aggregate'
                            and rd.get('aggregate_kind', {}).get('detail', {}).get('variant_index') == 1)
            children=successors(block)
            if children: todo.extend(children)
            else: leaves.append(term.get('kind'))
        return pending and bool(leaves) and all(k in ('Return','Yield') for k in leaves)
    excluded=[]; exits=[]
    for n in sorted(members):
        for target in successors(blocks[n]):
            if target in members:
                continue
            if blocks[target].get('terminator', {}).get('kind') == 'Unreachable' and not blocks[target].get('statements'):
                excluded.append({'from': n, 'to': target, 'reason': 'unreachable-sink'})
            elif suspension_tail(target):
                excluded.append({'from': n, 'to': target, 'reason': 'suspension'})
            else:
                exits.append((n, target))
    if not exits:
        return None
    tail=set(); visiting=set(); cycle=False
    def visit(n):
        nonlocal cycle
        if n in members: cycle=True; return
        if n in visiting: cycle=True; return
        if n in tail: return
        visiting.add(n); tail.add(n)
        for child in successors(blocks[n]): visit(child)
        visiting.remove(n)
    for _, target in exits: visit(target)
    if cycle:
        return None
    flags = compiler_drop_flags(raw); dead = _dead_locals(raw); roots = frame_aliases(raw)
    result_locals=set(); records=[]; terminals=[]
    for n in sorted(tail):
        block=blocks[n]; operations=[]
        for index, statement in enumerate(block.get('statements', [])):
            kind=statement.get('kind'); detail=statement.get('detail', {}); reason=None
            if kind in ('StorageLive', 'StorageDead', 'Nop'):
                reason='storage-or-nop'
            elif kind == 'Assign':
                destination=detail.get('destination', {}); rv=detail.get('rvalue', {}); rd=rv.get('detail', {})
                if place_key(destination) in flags:
                    reason='proven-drop-flag'
                elif not destination.get('projection') and destination.get('local') in dead:
                    operand=rd.get('operand', {}); place=rd.get('place', {})
                    safe_constant = rv.get('kind') == 'Use' and operand.get('kind') == 'Constant'
                    safe_discriminant = rv.get('kind') == 'Discriminant' and (not place.get('projection') or place.get('local') in roots)
                    if safe_constant or safe_discriminant: reason='dead-temporary'
                elif destination == {'local': 0, 'projection': []}:
                    operand=rd.get('operand', {}); place=operand.get('detail', {}).get('place', {})
                    aggregate=rd.get('aggregate_kind', {}).get('detail', {})
                    if rv.get('kind') == 'Use' and operand.get('kind') == 'Constant': reason='constant-return-slot'
                    elif rv.get('kind') == 'Use' and operand.get('kind') in ('Copy','Move') and not place.get('projection'):
                        result_locals.add(place.get('local')); reason='selected-result-return-slot'
                    elif rv.get('kind') == 'Aggregate' and aggregate.get('variant_index') == 0 and len(rd.get('operands', [])) == 1:
                        op=rd['operands'][0]; selected=op.get('detail', {}).get('place', {})
                        if op.get('kind') in ('Copy','Move') and not selected.get('projection'):
                            result_locals.add(selected.get('local')); reason='poll-ready-return-slot'
            elif kind == 'SetDiscriminant':
                place=detail.get('place', {})
                if raw.get('is_coroutine') and place.get('local') in roots and detail.get('variant_index') == 1:
                    reason='own-coroutine-completed-state'
            operations.append({'index': index, 'kind': kind, 'reason': reason})
            if reason is None:
                return None
        term=block.get('terminator', {}); kind=term.get('kind'); reason=None
        if kind == 'Goto': reason='transport'
        elif kind == 'Return': reason='terminal-return'; terminals.append(n)
        elif kind == 'Drop':
            display=_place_type(raw, term.get('detail', {}).get('place', {})).get('display', '')
            if _side_effect_free_drop(display): reason='side-effect-free-drop:'+display
        elif kind == 'SwitchInt':
            operand=term.get('detail', {}).get('discriminant', {}); place=operand.get('detail', {}).get('place', {})
            if place_key(place) in flags: reason='drop-flag-routing'
        if reason is None:
            return None
        records.append({'bb': n, 'operations': operations, 'terminator': {'kind': kind, 'reason': reason},
                        'normalSuccessors': successors(block)})
    leaves=[n for n in tail if not successors(blocks[n])]
    if not terminals or set(leaves) != set(terminals):
        return None
    return {'certificateKind': 'terminal-loop', 'version': 1, 'rawSha256': _raw_sha256(raw, data),
            'scopeId': scope['id'], 'memberBBs': ['bb'+str(n) for n in sorted(members)],
            'entryBBs': sorted({r for a in data.get('phases', []) for g in a.get('goals', []) for x in g.get('actions', [])
                               if x.get('id') == scope.get('repeat', {}).get('entryActionRef') for r in x.get('basicBlockRefs', [])}),
            'exitEdges': [{'from': 'bb'+str(a), 'to': 'bb'+str(b)} for a,b in exits],
            'excludedEdges': [{'from': 'bb'+str(e['from']), 'to': 'bb'+str(e['to']), 'reason': e['reason']} for e in excluded],
            'terminalBBs': ['bb'+str(n) for n in sorted(terminals)],
            'resultLocals': sorted(x for x in result_locals if x is not None), 'blocks': records}


def source_less(node):
    return not node.get('lineRanges') and all(bool(node.get(k)) and
        (not isinstance(node[k], str) or bool(node[k].strip()))
        for k in POLICY['exceptions']['source_less']['required'])


def instrumentation_proof(raw, kind):
    import instrumentation_wrapper
    spec = POLICY['instrumentationProofs'][kind]
    return getattr(instrumentation_wrapper, spec['function'])(raw)


def prove_forwarding(raw):
    return instrumentation_proof(raw, 'async_forwarding')


_TRACING_MACROS = re.compile(r'(?:^|/)tracing-[^/]+/src/macros\.rs$')


def _event_callsite(op):
    span = (op.get('source_info') or {}).get('span') or {}
    call = span.get('call_site') or {}
    if not span.get('from_expansion') or not call.get('file'):
        return None
    return tuple(call.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))


def _macro_span(op):
    span = (op.get('source_info') or {}).get('span') or {}
    return bool(span.get('from_expansion') and _TRACING_MACROS.search((span.get('file_portable') or span.get('file') or '').replace('\\', '/'))
                and _event_callsite(op))


def _fn_identity(term):
    constant = term.get('detail', {}).get('func', {}).get('detail', {}).get('constant', {})
    typ = constant.get('type', {})
    value = constant.get('value', {})
    if (typ.get('kind') != 'FnDef' or value.get('kind') != 'FnDef'
            or not typ.get('def_path_hash') or value.get('detail', {}).get('definition', {}).get('def_path_hash') != typ.get('def_path_hash')):
        return None
    match = re.search(r'FnDef\(DefId\([^~]+~\s*([A-Za-z_]\w*)\[[^]]+\]::([^),]+)', constant.get('value_debug', ''))
    return (match.group(1), match.group(2), typ, constant) if match else None


def _event_callee(term):
    identity = _fn_identity(term)
    if not identity:
        return None
    crate, path, typ, constant = identity
    if crate == 'tracing':
        if re.fullmatch(r'__macro_support::(?:__is_enabled|__tracing_log|__disabled_span)|span::\{impl#\d+\}::new', path):
            return ('tracing', None)
    if crate == 'tracing_core':
        allowed = (
            r'metadata::\{impl#\d+\}::(?:current|fields|target)',
            r'callsite::\{impl#\d+\}::interest', r'callsite::Callsite::metadata',
            r'subscriber::\{impl#\d+\}::(?:is_never|never)', r'dispatcher::has_been_set',
            r'dispatcher::\{impl#\d+\}::enabled',
            r'field::(?:debug|display)', r'field::\{impl#\d+\}::value_set_all',
            r'event::(?:Event|\{impl#\d+\})::dispatch')
        if any(re.fullmatch(pattern, path) for pattern in allowed):
            return ('tracing', None)
    if crate == 'log':
        if re.fullmatch(r'(?:max_level|logger|Log::enabled|\{impl#\d+\}::(?:builder|level|target|build))', path):
            return ('log', None)
    if crate == 'core' and path == 'cmp::PartialOrd::le':
        displays = [a.get('type', {}).get('display', '') for a in typ.get('generic_args', []) if a.get('kind') == 'Type']
        if len(displays) == 2 and all(x.startswith(('tracing::', 'tracing_core::')) for x in displays):
            return ('level-check', None)
    if crate in ('core', 'std') and re.fullmatch(r'fmt(?:::rt)?::\{impl#\d+\}::(?:new|new_display|new_debug|from_str)', path):
        return ('fmt', None)
    if (crate == 'core' and path == 'ops::function::Fn::call'
            or crate == 'tracing_core' and path == 'dispatcher::get_default'):
        closure = next((a.get('type', {}) for a in typ.get('generic_args', [])
                        if a.get('kind') == 'Type' and a.get('type', {}).get('kind') == 'Closure'), None)
        display = (closure or {}).get('display', '').replace('\\', '/')
        if closure and _TRACING_MACROS.search(display.split('@', 1)[-1].rsplit(':', 4)[0]):
            return ('closure', closure.get('def_path_hash'))
    return None


def _places(value):
    if isinstance(value, dict):
        if 'local' in value and 'projection' in value:
            yield value
        else:
            for child in value.values():
                yield from _places(child)
    elif isinstance(value, list):
        for child in value:
            yield from _places(child)


def _event_statement(statement, raw, anchor):
    if statement.get('kind') in ('StorageLive', 'StorageDead', 'Nop'):
        return True
    if statement.get('kind') != 'Assign' or _event_callsite(statement) not in (None, anchor):
        return False
    detail = statement.get('detail', {}); destination = detail.get('destination', {})
    if destination.get('projection') or destination.get('local', 0) <= raw.get('arg_count', 0):
        return False
    rv = detail.get('rvalue', {}); rd = rv.get('detail', {}); kind = rv.get('kind')
    if kind == 'Use':
        return rd.get('operand', {}).get('kind') in ('Copy', 'Move', 'Constant')
    if kind == 'Ref':
        place = rd.get('place', {})
        return (rd.get('borrow_kind') == 'Shared' or
                rd.get('borrow_kind', '').startswith('Mut')
                and all(step.get('kind') == 'Deref' for step in place.get('projection', []))
                and place.get('local', 0) > raw.get('arg_count', 0)) and isinstance(place.get('local'), int)
    if kind == 'Cast':
        return (rd.get('cast_kind', '').startswith('PointerCoercion(Unsize,')
                and rd.get('operand', {}).get('kind') in ('Copy', 'Move'))
    if kind == 'Aggregate':
        aggregate = rd.get('aggregate_kind', {}).get('kind')
        return aggregate in ('Tuple', 'Array', 'Adt') and all(op.get('kind') in ('Copy', 'Move', 'Constant') for op in rd.get('operands', []))
    if kind == 'Discriminant':
        place = rd.get('place', {})
        types = {item['local']: item.get('type', {}).get('display', '') for item in raw.get('locals', [])}
        return types.get(place.get('local'), '').startswith(('tracing::', 'tracing_core::'))
    return False


def _prior_drop_flag_write(statement, raw, anchor):
    """Recognize only a prior macro's bool drop-flag reset at a region entry."""
    if statement.get('kind') != 'Assign':
        return False
    callsite = _event_callsite(statement)
    if callsite is None or callsite == anchor or _macro_span(statement):
        return False
    detail = statement.get('detail', {}); rv = detail.get('rvalue', {})
    operand = rv.get('detail', {}).get('operand', {})
    constant = operand.get('detail', {}).get('constant', {})
    if (rv.get('kind') != 'Use' or operand.get('kind') != 'Constant'
            or constant.get('type', {}).get('kind') != 'Bool'):
        return False
    destination = detail.get('destination', {}); local = destination.get('local')
    if not isinstance(local, int):
        return False
    projection = destination.get('projection', [])
    if not projection:
        local_types = {item.get('local'): item.get('type', {}) for item in raw.get('locals', [])}
        return local > raw.get('arg_count', 0) and local_types.get(local, {}).get('kind') == 'Bool'
    kinds = [step.get('kind') for step in projection]
    if kinds not in (['Field'], ['Downcast', 'Field'], ['Deref', 'Field'], ['Deref', 'Downcast', 'Field']):
        return False
    field = projection[-1].get('detail', {})
    if (field.get('field_type', {}).get('kind') != 'Bool'
            or field.get('owner_type', {}).get('kind') != 'Coroutine'):
        return False
    local_types = {item.get('local'): item.get('type', {}) for item in raw.get('locals', [])}
    base = local_types.get(local, {})
    if kinds[0] == 'Deref':
        base = base.get('detail', {}).get('pointee', {}) if base.get('kind') == 'Ref' else {}
    return base.get('kind') == 'Coroutine'


def event_macro_artifact(content, sha256):
    """Decode an exact-byte pinned closure MIR artifact; invalid pins fail closed."""
    if not isinstance(content, (bytes, bytearray)) or hashlib.sha256(content).hexdigest() != sha256:
        return None
    try:
        raw = json.loads(content)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    return {'raw': raw, 'sha256': sha256}


def load_event_macro_artifacts(out):
    """Load only OUT-relative artifacts explicitly pinned by input-pins.json."""
    root = Path(out).resolve()
    try:
        pins = json.loads((root / 'input-pins.json').read_text())
    except (OSError, TypeError, ValueError):
        return []
    result = []
    for pin in pins.get('event_macro_closures', []):
        try:
            path = (root / pin['path']).resolve()
            if root not in path.parents or not re.fullmatch(r'[a-f0-9]{64}', pin['sha256']):
                return []
            artifact = event_macro_artifact(path.read_bytes(), pin['sha256'])
            if not artifact or (pin.get('def_path_hash') and artifact['raw'].get('owner_def_path_hash') != pin['def_path_hash']):
                return []
            result.append(artifact)
        except (KeyError, OSError):
            return []
    return result


def _closure_is_pure(raw, owner):
    if raw.get('owner_def_path_hash') != owner or not _macro_span({'source_info': {'span': raw.get('span', {})}}):
        return False
    for block in raw.get('basic_blocks', []):
        for statement in block.get('statements', []):
            if _event_statement(statement, raw, _event_callsite(statement)):
                continue
            detail = statement.get('detail', {}); destination = detail.get('destination', {})
            value = detail.get('rvalue', {}); operand = value.get('detail', {}).get('operand', {})
            if not (statement.get('kind')=='Assign' and destination.get('local')==0
                    and not destination.get('projection') and value.get('kind')=='Use'
                    and operand.get('kind') in ('Copy','Move','Constant')):
                return False
        term = block.get('terminator', {})
        if term.get('kind') == 'Call':
            callee = _event_callee(term)
            if not callee or callee[0] == 'closure':
                return False
        elif term.get('kind') not in ('Goto', 'SwitchInt', 'Return', 'Drop', 'Unreachable', 'UnwindResume', 'UnwindTerminate'):
            return False
    return True


def prove_event_macro(raw, artifacts=None):
    """Prove complete tracing event expansion regions from raw MIR and pinned closure MIR."""
    artifacts = [a for a in (artifacts or []) if a and isinstance(a.get('raw'), dict)]
    closure_artifacts = {a['raw'].get('owner_def_path_hash'): a for a in artifacts
                         if re.fullmatch(r'[a-f0-9]{64}', a.get('sha256', ''))}
    raw_blocks = raw.get('basic_blocks', [])
    if not raw_blocks or any(not isinstance(b.get('basic_block'), int) for b in raw_blocks):
        return None
    blocks = {b['basic_block']: b for b in raw_blocks}
    anchored = {}
    for number, block in blocks.items():
        if block.get('is_cleanup'):
            continue
        anchors = {_event_callsite(op) for op in [*block.get('statements', []), block.get('terminator', {})]
                   if op.get('kind') not in ('StorageLive', 'StorageDead', 'Nop')
                   if _macro_span(op)}
        if len(anchors) == 1:
            anchored[number] = anchors.pop()
    if not anchored:
        return None
    predecessors = {n: set() for n in blocks}
    for n, block in blocks.items():
        for target in block.get('terminator', {}).get('successors', []):
            if target in predecessors:
                predecessors[target].add(n)
    groups = {}
    for number, anchor in anchored.items():
        groups.setdefault(anchor, set()).add(number)
    # Include source-less compiler routing only when it is enclosed by one event region.
    for anchor, members in groups.items():
        changed = True
        while changed:
            changed = False
            for number, block in blocks.items():
                if number in members or number in anchored or block.get('is_cleanup'):
                    continue
                term = block.get('terminator', {})
                if (term.get('kind') in ('Goto', 'SwitchInt')
                        and predecessors[number] and predecessors[number] <= members
                        and set(term.get('successors', [])) & members
                        and all(_event_statement(s, raw, anchor) for s in block.get('statements', []))):
                    members.add(number); changed = True
    technical = {}; roles = {}; block_proofs = {}; regions = []
    for anchor, members in sorted(groups.items()):
        entries = [number for number in members if not (predecessors[number] & members)]
        entry = entries[0] if len(entries) == 1 else None
        closure_pins = {}; valid = True; saw_emitter = False; skipped_prior = {}
        for number in sorted(members):
            block = blocks[number]; term = block.get('terminator', {})
            statements = block.get('statements', []); start = 0; skipped = []
            if number == entry:
                for index, statement in enumerate(statements):
                    if statement.get('kind') in ('StorageLive', 'StorageDead', 'Nop'):
                        start = index + 1
                        continue
                    if _prior_drop_flag_write(statement, raw, anchor):
                        skipped.append(index); start = index + 1; continue
                    break
                if skipped:
                    skipped_prior['bb' + str(number)] = skipped
                else:
                    start = 0
            if any(not _event_statement(s, raw, anchor) for s in statements[start:]):
                valid = False; break
            if term.get('kind') == 'Call':
                callee = _event_callee(term)
                destination = term.get('detail', {}).get('destination', {})
                if (destination.get('projection') or destination.get('local',0)<=raw.get('arg_count',0)
                        or not callee or _event_callsite(term) != anchor):
                    valid = False; break
                if callee[0] == 'closure':
                    artifact = closure_artifacts.get(callee[1])
                    if not artifact or not _closure_is_pure(artifact['raw'], callee[1]):
                        valid = False; break
                    closure_pins[callee[1]] = artifact['sha256']; saw_emitter = True
                elif callee[0] == 'tracing' and (re.fullmatch(r'event::(?:Event|\{impl#\d+\})::dispatch', _fn_identity(term)[1])
                                                  or _fn_identity(term)[1] == '__macro_support::__tracing_log'):
                    saw_emitter = True
            elif term.get('kind') not in ('Goto', 'SwitchInt'):
                valid = False; break
        if not valid or not saw_emitter or not closure_pins:
            continue
        pin_records = [{'defPathHash': key, 'sha256': value} for key, value in sorted(closure_pins.items())]
        site = dict(zip(('file', 'startLine', 'endLine', 'startColumn', 'endColumn'), anchor))
        region_refs = ['bb' + str(n) for n in sorted(members)]
        regions.append({'callSite': site, 'bbRefs': region_refs, 'closureArtifacts': pin_records,
                        'skippedPriorDropFlagWrites': skipped_prior})
        witness = {'callSite': site, 'closureArtifacts': pin_records}
        for number in members:
            ref = 'bb' + str(number); technical[ref] = fingerprint(blocks[number]); roles[ref] = 'event_macro'; block_proofs[ref] = witness
    if not technical:
        return None
    return {'kind': 'event_macro', 'technical_blocks': dict(sorted(technical.items())),
            'block_roles': dict(sorted(roles.items())), 'block_proofs': dict(sorted(block_proofs.items())),
            'regions': regions,
            'proof': 'tracing event macro callsite; exact FnDef allowlist; temporary-only blocks; pinned pure macro closure'}


def prove_tracing_blocks(raw, artifacts=None):
    """Prove complete tracing BBs independently of mixed call-site neighbors."""
    artifacts = [a for a in (artifacts or []) if a and isinstance(a.get('raw'), dict)]
    closure_artifacts = {a['raw'].get('owner_def_path_hash'): a for a in artifacts
                         if re.fullmatch(r'[a-f0-9]{64}', a.get('sha256', ''))}
    if any(not isinstance(block.get('basic_block'),int) for block in raw.get('basic_blocks',[])):
        return None
    blocks = {block['basic_block']: block for block in raw.get('basic_blocks', [])}
    technical = {}; roles = {}; block_proofs = {}; regions = []
    invalid_sites = set()
    for block in blocks.values():
        term = block.get('terminator', {})
        callee = _event_callee(term) if term.get('kind') == 'Call' else None
        if callee and callee[0] == 'closure':
            artifact = closure_artifacts.get(callee[1])
            if not artifact or not _closure_is_pure(artifact['raw'], callee[1]):
                invalid_sites.add(_event_callsite(term))
    # Prove a complete BB even when its call-site region also contains business BBs.
    # Macro provenance alone is insufficient: every operation and call is checked.
    for number, block in blocks.items():
        ref = 'bb' + str(number)
        if ref in technical or block.get('is_cleanup'):
            continue
        term = block.get('terminator', {})
        substantive = [op for op in [*block.get('statements', []), term]
                       if op.get('kind') not in ('StorageLive', 'StorageDead', 'Nop')]
        anchors = {_event_callsite(op) for op in substantive}
        if (not substantive or len(anchors) != 1 or None in anchors
                or not all(_macro_span(op) for op in substantive)):
            continue
        anchor = anchors.pop()
        if anchor in invalid_sites:continue
        pins = {}; valid = True
        for statement in block.get('statements', []):
            if _event_statement(statement, raw, anchor):
                continue
            detail = statement.get('detail', {}); rv = detail.get('rvalue', {})
            rd = rv.get('detail', {}); aggregate = rd.get('aggregate_kind', {})
            owner = aggregate.get('detail', {}).get('definition', {}).get('def_path_hash')
            artifact = closure_artifacts.get(owner)
            destination = detail.get('destination', {})
            if (statement.get('kind') != 'Assign' or rv.get('kind') != 'Aggregate'
                    or aggregate.get('kind') != 'Closure' or not artifact
                    or not _closure_is_pure(artifact['raw'], owner)
                    or destination.get('projection') or destination.get('local', 0) <= raw.get('arg_count', 0)
                    or not all(op.get('kind') in ('Copy', 'Move', 'Constant') for op in rd.get('operands', []))):
                valid = False; break
            pins[owner] = artifact['sha256']
        if not valid:
            continue
        if term.get('kind') == 'Call':
            callee = _event_callee(term)
            destination = term.get('detail', {}).get('destination', {})
            if (not callee or destination.get('projection')
                    or destination.get('local', 0) <= raw.get('arg_count', 0)):
                continue
            if callee[0] == 'closure':
                artifact = closure_artifacts.get(callee[1])
                if not artifact or not _closure_is_pure(artifact['raw'], callee[1]):
                    continue
                pins[callee[1]] = artifact['sha256']
        elif term.get('kind') not in ('Goto', 'SwitchInt'):
            continue
        witness = dict(callSite=dict(zip(('file', 'startLine', 'endLine', 'startColumn', 'endColumn'), anchor)),
                       closureArtifacts=[dict(defPathHash=key, sha256=value) for key, value in sorted(pins.items())],
                       proofKind='pure_tracing_bb')
        technical[ref] = fingerprint(block); roles[ref] = 'event_macro'; block_proofs[ref] = witness
        regions.append(dict(witness, bbRefs=[ref]))
    return dict(kind='event_macro', technical_blocks=dict(sorted(technical.items())),
                block_roles=dict(sorted(roles.items())), block_proofs=dict(sorted(block_proofs.items())),
                regions=regions, proof='complete tracing BB: exact API identities, temporary writes, pinned closures') if technical else None


def _prove_instrumentation(raw, event_macro_artifacts=None):
    proofs = []
    for kind in POLICY['exceptions']['instrumentation']['proofKinds']:
        proof = instrumentation_proof(raw, kind)
        if proof:
            proofs.append(proof)
    event = prove_event_macro(raw, event_macro_artifacts)
    partial = prove_tracing_blocks(raw, event_macro_artifacts)
    if partial:
        occupied = {ref for proof in proofs for ref in proof.get('technical_blocks', {})}
        combined = dict(event) if event else dict(partial)
        if event:
            for name in ('technical_blocks', 'block_roles', 'block_proofs'):
                combined[name] = dict(event[name])
                combined[name].update({ref: value for ref, value in partial[name].items()
                                       if ref not in occupied and ref not in event['technical_blocks']})
            combined['regions'] = event['regions'] + [r for r in partial['regions']
                if not (set(r['bbRefs']) & (occupied | set(event['technical_blocks'])))]
        else:
            for name in ('technical_blocks', 'block_roles', 'block_proofs'):
                combined[name] = {ref: value for ref, value in partial[name].items() if ref not in occupied}
            combined['regions'] = [r for r in partial['regions'] if not (set(r['bbRefs']) & occupied)]
        event = combined if combined['technical_blocks'] else None
    if event:
        proofs.append(event)
    if not proofs:
        return None
    if len(proofs) == 1:
        return proofs[0]
    technical = {}; roles = {}; block_proofs = {}; conflicts = set()
    for proof in proofs:
        role = 'event_macro' if proof.get('kind') == 'event_macro' else 'span_wrapper'
        for ref, digest in proof.get('technical_blocks', {}).items():
            if ref in technical:
                conflicts.add(ref); continue
            technical[ref] = digest; roles[ref] = proof.get('block_roles', {}).get(ref, role)
            if ref in proof.get('block_proofs', {}): block_proofs[ref] = proof['block_proofs'][ref]
    for ref in conflicts:
        technical.pop(ref, None); roles.pop(ref, None); block_proofs.pop(ref, None)
    return {'kind': 'instrumentation_regions', 'regions': proofs,
            'technical_blocks': dict(sorted(technical.items())), 'block_roles': dict(sorted(roles.items())),
            'block_proofs': dict(sorted(block_proofs.items())), 'conflicts': sorted(conflicts)}


_INSTRUMENTATION_CACHE = {}


def prove_instrumentation(raw, event_macro_artifacts=None):
    """Reuse an exact content-addressed proof during repeated per-BB checks.

    Raw MIR, actual artifact MIR/SHAs, policy and prover identities are keyed;
    mutable inputs therefore cannot reuse a stale witness. Callers get copies.
    """
    artifacts = list(event_macro_artifacts or [])
    content = fingerprint(dict(raw=raw, artifacts=[
        {'raw':a.get('raw'), 'sha256':a.get('sha256')} for a in artifacts if a], policy=POLICY))
    key = (content, id(instrumentation_proof), id(prove_event_macro), id(prove_tracing_blocks))
    if key not in _INSTRUMENTATION_CACHE:
        result = _prove_instrumentation(raw, artifacts)
        _INSTRUMENTATION_CACHE.clear()
        _INSTRUMENTATION_CACHE[key] = deepcopy(result)
        return result
    return deepcopy(_INSTRUMENTATION_CACHE[key])


def tracing_intervals(raw, whole_proof=None):
    """Safe tracing operations in BBs that must remain whole business blocks."""
    whole = set((whole_proof or {}).get('technical_blocks', {}))
    result = []
    for block in raw.get('basic_blocks', []):
        ref = 'bb' + str(block['basic_block'])
        if ref in whole or block.get('is_cleanup'):
            continue
        indices = [statement.get('statement_index', index)
                   for index, statement in enumerate(block.get('statements', []))
                   if statement.get('kind') not in ('StorageLive', 'StorageDead', 'Nop')
                   and _macro_span(statement)
                   and _event_statement(statement, raw, _event_callsite(statement))]
        term = block.get('terminator', {})
        accepted = _event_callee(term) if term.get('kind') == 'Call' else None
        terminator = bool(_macro_span(term) and accepted and accepted[0] != 'closure')
        if indices or terminator:
            result.append(dict(bbRef=ref, statementIndices=indices, terminator=terminator,
                               proofKind='tracing_temporary_operations'))
    return result


def instrumentation_record_matches(block, record, proof):
    ref = record.get('bbRef'); role = (proof or {}).get('block_roles', {}).get(ref, 'span_wrapper')
    event_valid = (role != 'event_macro' or record.get('blockRole') == 'event_macro'
                   and record.get('eventMacroProof') == proof.get('block_proofs', {}).get(ref))
    return bool(proof and record.get('category') == 'instrumentation'
                and all(record.get(k) for k in POLICY['exceptions']['instrumentation']['required'])
                and record.get('factSha256') == fingerprint(block)
                and proof['technical_blocks'].get(ref) == fingerprint(block) and event_valid)


def instrumentation_record_valid(raw, block, record, event_macro_artifacts=None):
    return instrumentation_record_matches(block, record, prove_instrumentation(raw, event_macro_artifacts))


def technical_record_matches(record, instrumentation_valid):
    return bool(record.get('category') in TECHNICAL_CATEGORIES and record.get('reason')
                and record.get('evidenceRefs') and (record['category'] != 'instrumentation'
                    or instrumentation_valid()))


def technical_record_valid(raw, block, record):
    return technical_record_matches(record, lambda: instrumentation_record_valid(raw, block, record))


def classify_action(data, raw, action):
    from classification_registry import pure_blocks, prove_handoff
    # A source-anchored ignore/result arm is not a loop exception merely for
    # having a Goto terminator. Business facts continue to use ordinary rules.
    nodes = {n['id']: n for n in data.get('execution', {}).get('nodes', [])}
    loop_source = any(e.get('kind') == 'loop-continue' and
        nodes.get(e['from'], {}).get('actionRef') == action['id']
        for e in data.get('execution', {}).get('edges', []))
    candidate = (not action.get('lineRanges') or loop_source) and pure_blocks(raw, action.get('basicBlockRefs', []))
    proof = prove_handoff(data, raw, action) if candidate else None
    return dict(kind='pure_loop_handoff' if proof else 'ordinary', proof=proof,
                handoffCandidate=bool(candidate), sourceLess=source_less(action),
                loopHandoff=bool(proof))


def place_key(place):
    """Keep field/variant identity; a captured pointee is never the frame flag."""
    if not place.get('projection'):
        return place.get('local')
    steps = place['projection']
    if [x.get('kind') for x in steps] == ['Deref', 'Downcast', 'Field']:
        field = steps[-1].get('detail', {})
        owner = field.get('owner_type', {}).get('def_path_hash')
        if owner:
            return ('frame-field', owner, steps[1].get('detail', {}).get('variant_index'), field.get('field_index'))
    return (place.get('local'), json.dumps(steps, sort_keys=True))


def frame_aliases(raw):
    """Follow only copies of the coroutine self argument, never same-typed peers."""
    owner = raw.get('owner_def_path_hash')
    types = {l['local']: l.get('type', {}) for l in raw.get('locals', [])}
    def own_ref(t):
        return bool(owner and t.get('kind') == 'Ref' and t.get('detail', {}).get('pointee', {}).get('def_path_hash') == owner)
    first = types.get(1, {})
    direct = own_ref(first)
    pinned = (first.get('display', '').startswith(('std::pin::Pin<', 'core::pin::Pin<'))
              and any(own_ref(a.get('type', {})) for a in first.get('generic_args', [])))
    if not raw.get('is_coroutine') or raw.get('arg_count', 0) < 1 or not (direct or pinned):
        return set()
    writes = {}
    for b in raw.get('basic_blocks', []):
        for op in [*b.get('statements', []), b.get('terminator', {})]:
            d = op.get('detail', {}); dest = d.get('destination', {})
            if dest and not dest.get('projection'):
                writes.setdefault(dest['local'], []).append(op)
    roots = {1} if direct else set()
    for _ in range(len(writes) + 1):
        old = set(roots)
        for local, ops in writes.items():
            if not own_ref(types.get(local, {})): continue
            valid = True
            for op in ops:
                rv = op.get('detail', {}).get('rvalue', {}); operand = rv.get('detail', {}).get('operand', {})
                place = operand.get('detail', {}).get('place', {}); steps = place.get('projection', [])
                self_field = (pinned and place.get('local') == 1 and len(steps) == 1
                              and steps[0].get('kind') == 'Field' and steps[0].get('detail', {}).get('field_index') == 0
                              and own_ref(steps[0].get('detail', {}).get('field_type', {})))
                if (op.get('kind') != 'Assign' or rv.get('kind') != 'Use' or operand.get('kind') not in ('Copy', 'Move')
                        or not (self_field or (not steps and place.get('local') in roots))):
                    valid = False; break
            if valid: roots.add(local)
        if roots == old: break
    return roots


def frame_bool(place, raw, roots):
    steps = place.get('projection', [])
    if place.get('local') not in roots or [x.get('kind') for x in steps] != ['Deref', 'Downcast', 'Field']:
        return False
    types = {l['local']: l.get('type', {}) for l in raw.get('locals', [])}
    typ = types.get(place.get('local'), {})
    owner = raw.get('owner_def_path_hash')
    field = steps[-1].get('detail', {})
    return bool(owner and typ.get('kind') == 'Ref'
                and typ.get('detail', {}).get('pointee', {}).get('def_path_hash') == owner
                and field.get('owner_type', {}).get('def_path_hash') == owner
                and field.get('field_type', {}).get('kind') == 'Bool')


def compiler_drop_flags(raw):
    """Prove unbound Bool locals or own-frame fields used only for destructor routing.

    This affects source highlighting only, never BB membership or facts. A flag
    must have constant-bool writes and at least one read, every read must be a
    SwitchInt with a Drop arm joining its bypass, and no debug-variable binding,
    argument/return identity, captured-pointee write, escape or business use is allowed.
    """
    def places(value):
        if isinstance(value, dict):
            if 'local' in value and 'projection' in value:
                yield value
            else:
                for child in value.values():
                    yield from places(child)
        elif isinstance(value, list):
            for child in value:
                yield from places(child)

    if not isinstance(raw.get('debug_variables'), list):
        return set()
    frame_roots = frame_aliases(raw)
    named = {place_key(p) for v in raw.get('debug_variables', []) for p in places(v)}
    candidates = {l['local'] for l in raw.get('locals', [])
                  if l.get('type', {}).get('kind') == 'Bool'
                  and l['local'] > raw.get('arg_count', 0) and l['local'] not in named}
    # Debug bindings can refer to the same frame field through another alias.
    named_fields = {json.dumps(p.get('projection', [])[-2:], sort_keys=True)
                    for v in raw.get('debug_variables', []) for p in places(v)
                    if len(p.get('projection', [])) >= 2}
    candidates.update(place_key(p) for b in raw.get('basic_blocks', []) for p in places(b)
                      if frame_bool(p, raw, frame_roots) and place_key(p) not in named
                      and json.dumps(p['projection'][-2:], sort_keys=True) not in named_fields)
    bad, writes, reads, values = set(), set(), set(), {}
    blocks = {b.get('basic_block'): b for b in raw.get('basic_blocks', [])}
    for block in blocks.values():
        for op in block.get('statements', []):
            if op.get('kind') in ('StorageLive', 'StorageDead', 'Nop'):
                continue
            d = op.get('detail', {})
            dest = d.get('destination', {}) if op.get('kind') == 'Assign' else {}
            local = place_key(dest)
            if local in candidates:
                rv = d.get('rvalue', {}); operand = rv.get('detail', {}).get('operand', {})
                const = operand.get('detail', {}).get('constant', {})
                literal = const.get('value', {})
                bits = literal.get('detail', {}).get('bits')
                if ((dest.get('projection') and not frame_bool(dest, raw, frame_roots)) or rv.get('kind') != 'Use'
                        or operand.get('kind') != 'Constant' or const.get('type', {}).get('kind') != 'Bool'
                        or literal.get('kind') != 'ScalarInt' or bits not in ('0', '1')):
                    bad.add(local)
                else:
                    writes.add(local)
                    values.setdefault(local, set()).add(bits)
                # Do not count the assignment destination as a read.
                value = {k: val for k, val in d.items() if k != 'destination'}
            else:
                value = d
            bad.update(place_key(p) for p in places(value) if place_key(p) in candidates)
            # An unsupported projected use of a scalar candidate also invalidates it.
            bad.update(p['local'] for p in places(d) if p.get('projection') and p['local'] in candidates)
        term = block.get('terminator', {}); d = term.get('detail', {})
        used = [p for p in places(d) if place_key(p) in candidates or p['local'] in candidates]
        if not used:
            continue
        discr = d.get('discriminant', {})
        place = discr.get('detail', {}).get('place', {})
        targets = [t.get('target') for t in d.get('targets', [])] + [d.get('otherwise')]
        targets = list(dict.fromkeys(targets))
        guarded_drop = False
        if len(targets) == 2 and all(t in blocks for t in targets):
            for drop_id, bypass in (targets, targets[::-1]):
                arm = blocks[drop_id]
                end = arm.get('terminator', {})
                if (end.get('kind') == 'Drop' and end.get('detail', {}).get('target') == bypass
                        and all(st.get('kind') in ('StorageLive', 'StorageDead', 'Nop') for st in arm.get('statements', []))):
                    guarded_drop = True
        if (term.get('kind') == 'SwitchInt' and discr.get('kind') in ('Copy', 'Move')
                and place_key(place) in candidates and len(used) == 1 and guarded_drop):
            reads.add(place_key(place))
        else:
            bad.update(place_key(p) for p in used)
            bad.update(p['local'] for p in used if p['local'] in candidates)
    return {local for local in (candidates & writes & reads) - bad if values.get(local) == {'0', '1'}}


def is_unit_assignment(op, locals_by_id=None):
    if op.get('kind') != 'Assign':
        return False
    destination = op.get('detail', {}).get('destination', {})
    typ = (locals_by_id or {}).get(destination.get('local'), {}).get('type', {})
    if not destination.get('projection') and typ.get('kind') == 'Tuple' and typ.get('detail', {}).get('elements') == []:
        return True
    value = op.get('detail', {}).get('rvalue', {})
    operand = value.get('detail', {}).get('operand', {})
    typ = operand.get('detail', {}).get('constant', {}).get('type', {})
    return typ.get('kind') == 'Tuple' and typ.get('detail', {}).get('elements') == []


def signature_line(line, source):
    """Recognize the owning fn header through its opening brace, not body work."""
    import re
    header = []
    for number, text in enumerate(source.get('lines', []), source['startLine']):
        header.append(text)
        if '{' in text and re.search(r'\bfn\s+\w+', '\n'.join(header)):
            return line <= number and not text.split('{', 1)[1].strip().strip('}')
    return False


def classify_operation(op, locals_by_id=None, drop_flags=frozenset(), span=None, source=None):
    kind = op.get('kind')
    roles = []
    if kind == 'Assign' and place_key(op.get('detail', {}).get('destination', {})) in drop_flags:
        roles.append('proven_drop_flag')
    if kind in ARTIFACT_KINDS | {'Goto'}:
        roles.append('compiler_bookkeeping')
    if (span and source and source.get('lines') and is_unit_assignment(op, locals_by_id)
            and (span[0] != span[1] or signature_line(span[0], source))):
        roles.append('unit_context_or_signature')
    return {'kind': roles[0] if roles else 'business', 'roles': roles}


def thin_coroutine_wrapper(body):
    """Prove a straight-line coroutine-to-return value flow; fail closed.

    No BB-count threshold: only local copies/captures, one coroutine aggregate,
    unsizing, and Box::pin are allowed. Cleanup may only resume unwinding.
    Reject branches, cycles, stores through projections, other calls/rvalues,
    unused computation and returning a value unrelated to the coroutine.
    """
    blocks = body.get('basic_blocks', [])
    by_id = {b.get('basic_block'): b for b in blocks}
    if not blocks or len(by_id) != len(blocks):
        return None
    values, dependencies, assigned, used = {}, {}, set(), set()
    constructed, pins, visited = [], [], set()

    def operand(op, capture=False):
        if op.get('kind') not in ('Move', 'Copy'):
            raise ValueError('not a local operand')
        place = op.get('detail', {}).get('place', {})
        if (place.get('projection') and (not capture or any(p.get('kind') not in ('Field', 'Deref') for p in place['projection']))) or not isinstance(place.get('local'), int):
            raise ValueError('projected operand')
        local = place['local']
        used.add(local)
        return values.get(local), {local} | dependencies.get(local, set())

    current = 0
    try:
        while True:
            if current in visited or current not in by_id:
                return None
            visited.add(current)
            block = by_id[current]
            if block.get('is_cleanup'):
                return None
            for st in block.get('statements', []):
                if st.get('kind') in ('StorageLive', 'StorageDead', 'Nop'):
                    continue
                if st.get('kind') != 'Assign':
                    return None
                detail = st['detail']
                dest = detail['destination']
                if dest.get('projection') or not isinstance(dest.get('local'), int):
                    return None
                rv = detail['rvalue']; rd = rv.get('detail', {})
                deps = set()
                if rv['kind'] == 'Aggregate' and rd.get('aggregate_kind', {}).get('kind') == 'Coroutine':
                    token = rd['aggregate_kind']['detail']['definition']['def_path_hash']
                    constructed.append(token)
                    for op in rd.get('operands', []):
                        _, dep = operand(op, capture=True); deps |= dep
                elif rv['kind'] == 'Use':
                    token, deps = operand(rd['operand'])
                elif rv['kind'] == 'Cast' and re.fullmatch(r'PointerCoercion\(Unsize, (Implicit|AsCast)\)', rd.get('cast_kind', '')):
                    token, deps = operand(rd['operand'])
                    if token is None:
                        return None
                else:
                    return None
                local = dest['local']
                if local in assigned:
                    return None
                assigned.add(local); values[local] = token; dependencies[local] = deps
            term = block.get('terminator', {}); td = term.get('detail', {})
            kind = term.get('kind')
            if kind == 'Return':
                break
            if kind == 'Goto':
                current = td['target']; continue
            if kind != 'Call':
                return None
            constant = td.get('func', {}).get('detail', {}).get('constant', {})
            ty = constant.get('type', {})
            # Match the compiler's FnDef item suffix, never a substring of args.
            display = ty.get('display', '')
            if ty.get('kind') != 'FnDef' or not re.search(r' \{(?:std|alloc)::boxed::Box::<.*>::pin\}$', display):
                return None
            if len(td.get('args', [])) != 1:
                return None
            token, deps = operand(td['args'][0])
            dest = td['destination']
            if token is None or dest.get('projection') or dest['local'] in assigned:
                return None
            local = dest['local']; assigned.add(local)
            values[local] = token; dependencies[local] = deps
            pins.append(current)
            unwind = td.get('unwind', {})
            if unwind.get('kind') == 'Cleanup':
                cleanup = unwind.get('detail', {}).get('target')
                cb = by_id.get(cleanup, {})
                if not cb.get('is_cleanup') or cb.get('statements') or cb.get('terminator', {}).get('kind') != 'UnwindResume':
                    return None
                visited.add(cleanup)
            elif unwind.get('kind') not in ('Continue', 'Unreachable', 'Terminate'):
                return None
            current = td['target']
        if len(constructed) != 1 or values.get(0) != constructed[0] or visited != set(by_id):
            return None
        if assigned - ({0} | dependencies.get(0, set())):
            return None
        return {'coroutine_def_path_hash': constructed[0], 'wrapper_bb_count': len(blocks),
                'pin_call_blocks': pins,
                'proof': 'single acyclic normal path; local coroutine construction/copy/unsize/Box::pin only; coroutine reaches return; no branches or other calls'}
    except (KeyError, TypeError, ValueError):
        return None
