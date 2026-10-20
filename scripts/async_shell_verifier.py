"""Independent async-shell/inner binding and shell-prelude verification.

Standard library only. The checker reads and hashes both MIR byte streams
itself and imports no generator or classification implementation.
"""
import hashlib
import json
from pathlib import Path
import re
from event_macro_verifier import verify as verify_event_macro
from span_wrapper_extension_verifier import verify as verify_span_wrapper


def _body_id(raw):
    return '|'.join(str(raw.get(key, '')) for key in
                    ('owner_def_path_hash', 'capture_stage', 'body_id'))


def _fingerprint(block):
    return hashlib.sha256(json.dumps(block, sort_keys=True,
        ensure_ascii=False).encode()).hexdigest()


def _base_instrumentation_block(block):
    """Independent, block-local fail-closed proof for generated tracing work."""
    allowed_calls = ('tracing::', 'tracing_core::', 'log::', 'std::fmt::',
                     'core::fmt::', 'core::cmp::PartialOrd')
    anchored = False
    for operation in [*block.get('statements', []), block.get('terminator') or {}]:
        if operation.get('kind') in ('StorageLive','StorageDead','Nop'):
            continue
        if operation.get('kind') in ('Goto','SwitchInt','Drop'):
            pass
        elif operation.get('kind') == 'Assign':
            aggregate = (operation.get('detail', {}).get('rvalue', {}).get('detail', {})
                         .get('aggregate_kind', {}))
            if aggregate.get('kind') in ('Coroutine','Closure'):
                return False
        elif operation.get('kind') == 'Call':
            if not any(token in _callee(operation) for token in allowed_calls):
                return False
        else:
            return False
        span = (operation.get('source_info') or {}).get('span') or {}
        call_site = span.get('call_site') or {}
        if not span.get('from_expansion') or not call_site.get('file'):
            return False
        anchored = True
    return anchored


def _places(value):
    if isinstance(value, dict):
        if isinstance(value.get('local'), int) and isinstance(value.get('projection'), list):
            yield value
        else:
            for child in value.values():
                yield from _places(child)
    elif isinstance(value, list):
        for child in value:
            yield from _places(child)


def _callee(term):
    return (term.get('detail', {}).get('func', {}).get('detail', {})
            .get('constant', {}).get('type', {}).get('display', ''))


def _normal_successors(block, known):
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
    if kind == 'Assert':
        targets = [target for target in targets if target != block.get('basic_block')]
    return list(dict.fromkeys(target for target in targets if target in known))


def _cfg_components(blocks):
    graph = {number: _normal_successors(block, blocks)
             for number, block in blocks.items() if not block.get('is_cleanup')}
    next_index = 0; indices = {}; low = {}; stack = []; stacked = set(); components = []

    def visit(node):
        nonlocal next_index
        indices[node] = next_index; low[node] = next_index; next_index += 1
        stack.append(node); stacked.add(node)
        for target in graph.get(node, []):
            if target not in graph:
                continue
            if target not in indices:
                visit(target); low[node] = min(low[node], low[target])
            elif target in stacked:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component = set()
            while True:
                item = stack.pop(); stacked.remove(item); component.add(item)
                if item == node:
                    break
            components.append(component)

    for node in graph:
        if node not in indices:
            visit(node)
    return graph, components


def _is_ready_place(place, poll_local):
    return (place.get('local') == poll_local
            and any(item.get('kind') == 'Downcast'
                    and item.get('detail', {}).get('variant_name') == 'Ready'
                    for item in place.get('projection', [])))


def _drop_target(name):
    marker = 'drop_in_place::<'
    start = name.find(marker)
    if start < 0:
        return None
    start += len(marker); nesting = 0
    for offset, char in enumerate(name[start:], start):
        if char == '<':
            nesting += 1
        elif char == '>':
            if nesting:
                nesting -= 1
            else:
                return name[start:offset] if name[offset + 1:] == '}' else None
    return None


def _drop_glue_only(term, inner_type):
    name = _callee(term)
    target = _drop_target(name)
    return (target == 'tracing::Span'
            or target == f'tracing::instrument::Instrumented<{inner_type}>')


def _poll_completes_shell(blocks, poll_number, poll_local, inner_type):
    frontier = list(_normal_successors(blocks[poll_number], blocks))
    seen = set(); ready_blocks = []
    while frontier:
        number = frontier.pop()
        if number in seen:
            continue
        seen.add(number); block = blocks[number]
        if any(statement.get('kind') == 'Assign'
               and any(_is_ready_place(place, poll_local) for place in
                       _places(statement.get('detail', {}).get('rvalue', {})))
               for statement in block.get('statements', [])):
            ready_blocks.append(number)
            continue
        if block.get('terminator', {}).get('kind') not in (
                'Return', 'Unreachable', 'UnwindResume'):
            frontier.extend(_normal_successors(block, blocks))
    if len(set(ready_blocks)) != 1:
        return False, set()
    ready_root = ready_blocks[0]; cached = {}; visiting = set()

    def reaches_return(number, tainted):
        state = (number, tuple(sorted(tainted)))
        if state in cached:
            return cached[state]
        if number in visiting:
            return False
        visiting.add(number); block = blocks[number]; current = set(tainted)
        for statement in block.get('statements', []):
            if statement.get('kind') != 'Assign':
                continue
            detail = statement.get('detail', {}); destination = detail.get('destination', {})
            local = destination.get('local'); rvalue = detail.get('rvalue', {})
            if not isinstance(local, int) or destination.get('projection'):
                continue
            sources = list(_places(rvalue))
            local_move = (rvalue.get('kind') == 'Use'
                          and (any(place.get('local') in current for place in sources)
                               or any(_is_ready_place(place, poll_local)
                                      for place in sources)))
            completion = (local == 0 and rvalue.get('kind') == 'Aggregate'
                          and any(place.get('local') in current for place in sources))
            if local_move or completion:
                current.add(local)
            else:
                current.discard(local)
        term = block.get('terminator', {}); kind = term.get('kind')
        if kind == 'Return':
            result = 0 in current
        elif kind == 'Call' and not _drop_glue_only(term, inner_type):
            result = False
        else:
            successors = _normal_successors(block, blocks)
            result = bool(successors) and all(reaches_return(target, current)
                                              for target in successors)
        visiting.remove(number); cached[state] = result
        return result

    return reaches_return(ready_root, set()), {ready_root}


def _binding(shell, inner_owner):
    """Independently prove a one-shot child returning the shell's output."""
    constructions = []
    for block in shell.get('basic_blocks', []):
        for statement in block.get('statements', []):
            detail = statement.get('detail', {}); rvalue = detail.get('rvalue', {})
            aggregate = rvalue.get('detail', {}).get('aggregate_kind', {})
            if aggregate.get('kind') != 'Coroutine':
                continue
            owner = aggregate.get('detail', {}).get('definition', {}).get('def_path_hash')
            destination = detail.get('destination', {})
            if isinstance(owner, str) and isinstance(destination.get('local'), int):
                constructions.append((block.get('basic_block'), owner, destination['local']))
    constructions = list(dict.fromkeys(constructions))
    if len(constructions) != 1 or constructions[0][1] != inner_owner:
        return None, len(constructions)
    construction_bb, _, seed = constructions[0]
    types = {entry.get('local'): entry.get('type', {}).get('display')
             for entry in shell.get('locals', [])}
    inner_type = types.get(seed)
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
        name = _callee(term); ref = f"shell:bb{block.get('basic_block')}"
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
    fixed_chain = {construction_bb}
    fixed_chain.update(int(ref[8:]) for ref in instrument + into_future)
    poll_numbers = {int(ref[8:]) for ref in polls}
    for component in components:
        is_cycle = len(component) > 1 or any(node in graph.get(node, []) for node in component)
        if not is_cycle:
            continue
        if component & fixed_chain:
            return None, len(constructions)
        if component & poll_numbers:
            calls = {node for node in component
                     if blocks[node].get('terminator', {}).get('kind') == 'Call'}
            if not calls or not calls <= poll_numbers:
                return None, len(constructions)
    for poll_number in poll_numbers:
        poll_local = (blocks.get(poll_number, {}).get('terminator', {})
                      .get('detail', {}).get('destination', {}).get('local'))
        if not isinstance(poll_local, int):
            return None, len(constructions)
        complete, ready_blocks = _poll_completes_shell(
            blocks, poll_number, poll_local, inner_type)
        component = next((part for part in components if poll_number in part), set())
        if not complete or (len(component) > 1 and component & ready_blocks):
            return None, len(constructions)
    return {'constructionBbRef': f'shell:bb{construction_bb}',
            'instrumentBbRefs': sorted(set(instrument)),
            'intoFutureBbRefs': sorted(set(into_future)),
            'pollBbRefs': sorted(set(polls))}, len(constructions)


def _strict_forward(shell, inner_owner):
    """Narrow independent proof for a branch-free returned child future."""
    blocks = shell.get('basic_blocks', []); constructions = []
    tainted = set(); assigned = set(); valid = True
    for block in blocks:
        if block.get('is_cleanup'):
            valid &= (not block.get('statements')
                      and block.get('terminator', {}).get('kind') == 'UnwindResume')
            continue
        for statement in block.get('statements', []):
            if statement.get('kind') in ('StorageLive', 'StorageDead', 'Nop'):
                continue
            detail = statement.get('detail', {}); destination = detail.get('destination', {})
            rvalue = detail.get('rvalue', {}); aggregate = rvalue.get('detail', {}).get('aggregate_kind', {})
            if statement.get('kind') != 'Assign' or destination.get('projection'):
                valid = False; continue
            local = destination.get('local'); assigned.add(local)
            if aggregate.get('kind') == 'Coroutine':
                owner = aggregate.get('detail', {}).get('definition', {}).get('def_path_hash')
                constructions.append((block.get('basic_block'), owner)); tainted.add(local)
            elif rvalue.get('kind') in ('Use', 'Cast') and any(
                    place['local'] in tainted for place in _places(rvalue)):
                tainted.add(local)
            else:
                valid = False
        term = block.get('terminator', {}); detail = term.get('detail', {})
        if term.get('kind') == 'Call':
            name = _callee(term); destination = detail.get('destination', {})
            if ('::boxed::Box::<' not in name or not name.endswith('>::pin}')
                    or destination.get('projection')
                    or not any(place['local'] in tainted for place in _places(detail.get('args', [])))):
                valid = False
            else:
                tainted.add(destination.get('local'))
        elif term.get('kind') not in ('Goto', 'Return'):
            valid = False
    unique = list(dict.fromkeys(constructions))
    return (valid and len(unique) == 1 and unique[0][1] == inner_owner and 0 in tainted,
            f"shell:bb{unique[0][0]}" if len(unique) == 1 else None)


def _load_claim(out):
    for relative in ('classification.json', 'stage2/granularity.json'):
        try:
            data = json.loads((out / relative).read_bytes())
            claim = data if relative == 'classification.json' else data.get('bodyClassification')
            if isinstance(claim, dict):
                return claim
        except (OSError, TypeError, ValueError, UnicodeDecodeError):
            pass
    return None


def _load_shell(root, pin, failures):
    try:
        path = (root / pin['path']).resolve(); expected = pin['sha256']
        if root not in path.parents or not re.fullmatch(r'[a-f0-9]{64}', expected):
            raise ValueError('invalid pin')
        content = path.read_bytes(); actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            failures.append({'code': 'shell-pin-sha256-mismatch',
                             'expected': expected, 'actual': actual})
        shell = json.loads(content)
        if shell.get('owner_def_path_hash') != pin.get('def_path_hash'):
            failures.append({'code': 'shell-pin-owner-mismatch',
                             'pinnedOwner': pin.get('def_path_hash'),
                             'rawOwner': shell.get('owner_def_path_hash')})
        return shell, expected
    except (KeyError, OSError, TypeError, ValueError, UnicodeDecodeError):
        failures.append({'code': 'invalid-shell-pin'})
        return None, None


def _load_event_artifacts(root, pins):
    artifacts = []
    try:
        for pin in pins.get('event_macro_closures', []):
            path = (root / pin['path']).resolve()
            if root not in path.parents or not re.fullmatch(r'[a-f0-9]{64}', pin.get('sha256', '')):
                return []
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != pin['sha256']:
                return []
            artifacts.append({'content': content, 'sha256': pin['sha256']})
    except (KeyError, OSError, TypeError):
        return []
    return artifacts


def _verify_prelude(data, shell, mode, relation, artifacts):
    failures = []; prelude = data.get('prelude')
    if mode == 'strict-forward':
        if prelude is not None:
            failures.append({'code': 'strict-forward-prelude-must-be-absent'})
        return failures
    if not isinstance(prelude, dict) or not prelude.get('nodes'):
        return [{'code': 'missing-retained-shell-prelude'}]
    if prelude.get('shellBodyId') != _body_id(shell):
        failures.append({'code': 'prelude-shell-body-mismatch'})
    if prelude.get('relation') != relation:
        failures.append({'code': 'prelude-relation-mismatch'})
    blocks = {f"shell:bb{b.get('basic_block')}": b for b in shell.get('basic_blocks', [])}
    records = relation.get('technicalBlocks') or []
    technical = {}
    duplicate_records = []
    for record in records:
        ref = record.get('bbRef') if isinstance(record, dict) else None
        if ref in technical:
            duplicate_records.append(ref)
        else:
            technical[ref] = record
    if duplicate_records:
        failures.append({'code': 'duplicate-shell-technical-bb',
                         'bbRefs': sorted(set(duplicate_records))})
    bad_fingerprints = sorted(ref for ref, record in technical.items()
                              if ref not in blocks
                              or record.get('factSha256') != _fingerprint(blocks[ref]))
    if bad_fingerprints:
        failures.append({'code': 'invalid-shell-technical-proof', 'bbRefs': bad_fingerprints})
    local_records = [{**record, 'bbRef': record.get('bbRef', '')[6:],
                      'evidenceRefs': [ref[6:] for ref in record.get('evidenceRefs', [])]}
                     for record in records if isinstance(record, dict)
                     and re.fullmatch(r'shell:bb[0-9]+', record.get('bbRef', ''))
                     and all(re.fullmatch(r'shell:bb[0-9]+', ref)
                             for ref in record.get('evidenceRefs', []))]
    if len(local_records) != len(records):
        failures.append({'code': 'invalid-shell-technical-namespace'})
    failures.extend(verify_event_macro(shell, local_records, artifacts))
    failures.extend(verify_span_wrapper(shell, [record for record in local_records
                    if isinstance(record, dict)
                    and record.get('blockRole') == 'span_wrapper_extension']))
    relation_refs = {relation.get('constructionBbRef'),
                     *relation.get('instrumentBbRefs', []),
                     *relation.get('intoFutureBbRefs', []),
                     *relation.get('pollBbRefs', [])}
    unproven_base = sorted(record.get('bbRef') for record in local_records
                           if record.get('blockRole') == 'instrumentation_base'
                           and (not _base_instrumentation_block(
                               blocks.get('shell:' + record['bbRef'], {}))
                                or 'shell:' + record['bbRef'] in relation_refs))
    if unproven_base:
        failures.append({'code': 'unproven-shell-instrumentation-base',
                         'bbRefs': unproven_base})
    if bad_fingerprints or duplicate_records:
        return failures
    expected = set(blocks) - set(technical)
    refs = [ref for node in prelude.get('nodes', []) for ref in node.get('basicBlockRefs', [])]
    actual = set(refs)
    if len(refs) != len(actual):
        failures.append({'code': 'duplicate-prelude-bb'})
    if expected - actual:
        failures.append({'code': 'prelude-missing-business-bb',
                         'bbRefs': sorted(expected - actual)})
    if actual - expected:
        failures.append({'code': 'prelude-extra-bb',
                         'bbRefs': sorted(actual - expected)})
    return failures


def verify_out(out, claim=None):
    """Re-prove an async-shell claim from primary inner and pinned shell bytes."""
    root = Path(out).resolve(); failures = []
    try:
        inner_bytes = (root / 'raw-body.json').read_bytes(); inner = json.loads(inner_bytes)
        data = json.loads((root / 'renderer-input.json').read_bytes())
    except (OSError, TypeError, ValueError, UnicodeDecodeError):
        return {'status': 'needs-evidence', 'failures': [{'code': 'missing-primary-inner'}]}
    claim = claim if claim is not None else _load_claim(root)
    try:
        pins = json.loads((root / 'input-pins.json').read_bytes())
    except (OSError, TypeError, ValueError, UnicodeDecodeError):
        pins = {}
    pin = pins.get('async_shell_prelude')
    relevant = bool((isinstance(claim, dict) and claim.get('kind') == 'async-shell') or pin)
    if not relevant:
        return {'status': 'not-applicable', 'failures': []}
    if not isinstance(pin, dict):
        return {'status': 'needs-evidence',
                'failures': [{'code': 'missing-shell-prelude-pin'}]}
    shell, shell_sha = _load_shell(root, pin, failures)
    if failures or shell is None:
        return {'status': 'needs-evidence', 'failures': failures}
    for role, body in (('shell', shell), ('inner', inner)):
        if (body.get('capture_stage') != 'mir_drops_elaborated_and_const_checked'
                or body.get('body_id') != 'main' or not body.get('basic_blocks')):
            failures.append({'code': 'invalid-' + role + '-mir'})
    inner_owner = inner.get('owner_def_path_hash'); shell_owner = shell.get('owner_def_path_hash')
    expected_path = str(shell.get('canonical_path', '')) + '::{closure#0}'
    if inner.get('canonical_path') != expected_path:
        failures.append({'code': 'inner-canonical-path-mismatch', 'expected': expected_path,
                         'actual': inner.get('canonical_path')})
    definition = pins.get('definition_row') or {}
    if (definition.get('def_path_hash') != inner_owner
            or definition.get('ownership', {}).get('parent_def_path_hash') != shell_owner):
        failures.append({'code': 'inner-owner-relation-mismatch'})
    binding, construction_count = _binding(shell, inner_owner)
    strict, strict_construction = _strict_forward(shell, inner_owner)
    if not binding and not strict:
        failures.append({'code': 'async-shell-binding-failed',
                         'constructionCount': construction_count})
        return {'status': 'needs-evidence', 'failures': failures}
    claimed_relation = (claim or {}).get('relation') or {}
    mode = 'strict-forward' if strict else 'retained-relation'
    inner_sha = hashlib.sha256(inner_bytes).hexdigest()
    binding = binding or {'constructionBbRef': strict_construction,
                          'instrumentBbRefs': [], 'intoFutureBbRefs': [], 'pollBbRefs': []}
    relation = {'shellBodyId': _body_id(shell), 'innerDefPathHash': inner_owner,
                'constructionBbRef': binding['constructionBbRef'],
                'innerMirSha256': inner_sha, 'shellMirSha256': shell_sha,
                'instrumentBbRefs': binding['instrumentBbRefs'],
                'intoFutureBbRefs': binding['intoFutureBbRefs'],
                'pollBbRefs': binding['pollBbRefs'],
                'technicalBlocks': claimed_relation.get('technicalBlocks') or []}
    computed = {'kind': 'async-shell', 'executionForm': 'coroutine',
                'mappingMode': mode, 'status': 'verified', 'relation': relation}
    if isinstance(claim, dict):
        for field in ('kind', 'executionForm', 'mappingMode', 'status'):
            if claim.get(field) != computed[field]:
                failures.append({'code': 'async-shell-claim-mismatch', 'field': field,
                                 'claimed': claim.get(field), 'proved': computed[field]})
        for field, value in relation.items():
            if claimed_relation.get(field) != value:
                failures.append({'code': 'async-shell-relation-mismatch', 'field': field,
                                 'claimed': claimed_relation.get(field), 'proved': value})
    failures.extend(_verify_prelude(data, shell, mode, relation,
                                    _load_event_artifacts(root, pins)))
    if ((claim or {}).get('mappingMode') == 'strict-forward'
            and data.get('prelude') is not None and mode != 'strict-forward'):
        failures.append({'code': 'strict-forward-prelude-must-be-absent'})
    return {**computed, 'failures': failures}
