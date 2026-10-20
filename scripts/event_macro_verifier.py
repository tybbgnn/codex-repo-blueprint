"""Independent tracing event-macro proof from raw MIR and exact artifact bytes.

This module intentionally shares no generator code or registry data.
"""
import hashlib
import json
import re


_MACROS = re.compile(r'(?:^|/)tracing-[^/]+/src/macros\.rs$')


def _site(op):
    span = (op.get('source_info') or {}).get('span') or {}
    call = span.get('call_site') or {}
    if not span.get('from_expansion') or not call.get('file'):
        return None
    return tuple(call.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))


def _macro(op):
    span = (op.get('source_info') or {}).get('span') or {}
    path = (span.get('file_portable') or span.get('file') or '').replace('\\', '/')
    return bool(span.get('from_expansion') and _MACROS.search(path) and _site(op))


def _identity(term):
    constant = term.get('detail', {}).get('func', {}).get('detail', {}).get('constant', {})
    typ = constant.get('type', {}); value = constant.get('value', {})
    if (typ.get('kind') != 'FnDef' or value.get('kind') != 'FnDef' or not typ.get('def_path_hash')
            or value.get('detail', {}).get('definition', {}).get('def_path_hash') != typ.get('def_path_hash')):
        return None
    match = re.search(r'FnDef\(DefId\([^~]+~\s*([A-Za-z_]\w*)\[[^]]+\]::([^),]+)', constant.get('value_debug', ''))
    return (match.group(1), match.group(2), typ) if match else None


def _callee(term):
    found = _identity(term)
    if not found:
        return None
    crate, path, typ = found
    if crate == 'tracing' and re.fullmatch(r'__macro_support::(?:__is_enabled|__tracing_log|__disabled_span)|span::\{impl#\d+\}::new', path):
        return ('tracing', None)
    if crate == 'tracing_core' and any(re.fullmatch(pattern, path) for pattern in (
            r'metadata::\{impl#\d+\}::(?:current|fields|target)',
            r'callsite::\{impl#\d+\}::interest', r'callsite::Callsite::metadata',
            r'subscriber::\{impl#\d+\}::(?:is_never|never)', r'dispatcher::has_been_set',
            r'dispatcher::\{impl#\d+\}::enabled',
            r'field::(?:debug|display)', r'field::\{impl#\d+\}::value_set_all',
            r'event::(?:Event|\{impl#\d+\})::dispatch')):
        return ('tracing', None)
    if crate == 'log' and re.fullmatch(r'(?:max_level|logger|Log::enabled|\{impl#\d+\}::(?:builder|level|target|build))', path):
        return ('log', None)
    if crate == 'core' and path == 'cmp::PartialOrd::le':
        args = [a.get('type', {}).get('display', '') for a in typ.get('generic_args', []) if a.get('kind') == 'Type']
        if len(args) == 2 and all(x.startswith(('tracing::', 'tracing_core::')) for x in args):
            return ('level', None)
    if crate in ('core', 'std') and re.fullmatch(r'fmt(?:::rt)?::\{impl#\d+\}::(?:new|new_display|new_debug|from_str)', path):
        return ('fmt', None)
    if (crate == 'core' and path == 'ops::function::Fn::call'
            or crate == 'tracing_core' and path == 'dispatcher::get_default'):
        closure = next((a.get('type', {}) for a in typ.get('generic_args', [])
                        if a.get('kind') == 'Type' and a.get('type', {}).get('kind') == 'Closure'), None)
        display = (closure or {}).get('display', '').replace('\\', '/')
        if closure and _MACROS.search(display.split('@', 1)[-1].rsplit(':', 4)[0]):
            return ('closure', closure.get('def_path_hash'))
    return None


def _statement(statement, body, anchor):
    kind = statement.get('kind')
    if kind in ('StorageLive', 'StorageDead', 'Nop'):
        return True
    if kind != 'Assign' or _site(statement) not in (None, anchor):
        return False
    detail = statement.get('detail', {}); destination = detail.get('destination', {})
    if destination.get('projection') or destination.get('local', 0) <= body.get('arg_count', 0):
        return False
    value = detail.get('rvalue', {}); rd = value.get('detail', {}); kind = value.get('kind')
    if kind == 'Use':
        return rd.get('operand', {}).get('kind') in ('Copy', 'Move', 'Constant')
    if kind == 'Ref':
        place = rd.get('place', {})
        return (isinstance(place.get('local'), int) and
                (rd.get('borrow_kind') == 'Shared' or rd.get('borrow_kind', '').startswith('Mut')
                 and place.get('local', 0) > body.get('arg_count', 0)
                 and all(step.get('kind') == 'Deref' for step in place.get('projection', []))))
    if kind == 'Cast':
        return rd.get('cast_kind', '').startswith('PointerCoercion(Unsize,') and rd.get('operand', {}).get('kind') in ('Copy', 'Move')
    if kind == 'Aggregate':
        return (rd.get('aggregate_kind', {}).get('kind') in ('Tuple', 'Array', 'Adt')
                and all(op.get('kind') in ('Copy', 'Move', 'Constant') for op in rd.get('operands', [])))
    if kind == 'Discriminant':
        types = {item['local']: item.get('type', {}).get('display', '') for item in body.get('locals', [])}
        return types.get(rd.get('place', {}).get('local'), '').startswith(('tracing::', 'tracing_core::'))
    return False


def _prior_drop_flag_write(statement, raw, anchor):
    """Recognize only a prior macro's bool drop-flag reset at a region entry."""
    if statement.get('kind') != 'Assign':
        return False
    callsite = _site(statement)
    if callsite is None or callsite == anchor or _macro(statement):
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


def _artifact_map(artifacts):
    result = {}
    for artifact in artifacts or []:
        content = artifact.get('content'); expected = artifact.get('sha256')
        if not isinstance(content, (bytes, bytearray)) or hashlib.sha256(content).hexdigest() != expected:
            return {}
        try:
            raw = json.loads(content)
        except (TypeError, ValueError, UnicodeDecodeError):
            return {}
        result[raw.get('owner_def_path_hash')] = {'raw': raw, 'sha256': expected}
    return result


def _pure_closure(body, owner):
    wrapper = {'source_info': {'span': body.get('span', {})}}
    if body.get('owner_def_path_hash') != owner or not _macro(wrapper):
        return False
    for block in body.get('basic_blocks', []):
        for operation in block.get('statements', []):
            if _statement(operation, body, _site(operation)):
                continue
            detail = operation.get('detail', {}); output = detail.get('destination', {})
            value = detail.get('rvalue', {}); operand = value.get('detail', {}).get('operand', {})
            if not (operation.get('kind')=='Assign' and output.get('local')==0
                    and not output.get('projection') and value.get('kind')=='Use'
                    and operand.get('kind') in ('Copy','Move','Constant')):
                return False
        term = block.get('terminator', {})
        if term.get('kind') == 'Call':
            accepted = _callee(term)
            if not accepted or accepted[0] == 'closure':
                return False
        elif term.get('kind') not in ('Goto', 'SwitchInt', 'Return', 'Drop', 'Unreachable', 'UnwindResume', 'UnwindTerminate'):
            return False
    return True


def prove(raw, artifacts):
    """Return independently proven event BB refs, or an empty result."""
    pinned = _artifact_map(artifacts)
    raw_blocks = raw.get('basic_blocks', [])
    if not raw_blocks or any(not isinstance(b.get('basic_block'), int) for b in raw_blocks):
        return {'blocks': {}, 'regions': []}
    blocks = {b['basic_block']: b for b in raw_blocks}
    anchored = {}
    for number, block in blocks.items():
        if block.get('is_cleanup'):
            continue
        anchors = {_site(op) for op in [*block.get('statements', []), block.get('terminator', {})]
                   if op.get('kind') not in ('StorageLive', 'StorageDead', 'Nop') and _macro(op)}
        if len(anchors) == 1:
            anchored[number] = anchors.pop()
    predecessors = {n: set() for n in blocks}
    for number, block in blocks.items():
        for target in block.get('terminator', {}).get('successors', []):
            if target in predecessors:
                predecessors[target].add(number)
    groups = {}
    for number, anchor in anchored.items():
        groups.setdefault(anchor, set()).add(number)
    for anchor, members in groups.items():
        changed = True
        while changed:
            changed = False
            for number, block in blocks.items():
                if number in members or number in anchored or block.get('is_cleanup'):
                    continue
                term = block.get('terminator', {})
                if (term.get('kind') in ('Goto', 'SwitchInt') and predecessors[number]
                        and predecessors[number] <= members and set(term.get('successors', [])) & members
                        and all(_statement(s, raw, anchor) for s in block.get('statements', []))):
                    members.add(number); changed = True
    proven = {}; regions = []
    for anchor, members in sorted(groups.items()):
        entries = [number for number in members if not (predecessors[number] & members)]
        entry = entries[0] if len(entries) == 1 else None
        closures = {}; valid = True; emitter = False
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
                if not skipped:
                    start = 0
            if any(not _statement(s, raw, anchor) for s in statements[start:]):
                valid = False; break
            if term.get('kind') == 'Call':
                accepted = _callee(term)
                destination = term.get('detail', {}).get('destination', {})
                if (destination.get('projection') or destination.get('local',0)<=raw.get('arg_count',0)
                        or not accepted or _site(term) != anchor):
                    valid = False; break
                identity = _identity(term)
                if accepted[0] == 'closure':
                    artifact = pinned.get(accepted[1])
                    if not artifact or not _pure_closure(artifact['raw'], accepted[1]):
                        valid = False; break
                    closures[accepted[1]] = artifact['sha256']; emitter = True
                elif accepted[0] == 'tracing' and (re.fullmatch(r'event::(?:Event|\{impl#\d+\})::dispatch', identity[1])
                                                    or identity[1] == '__macro_support::__tracing_log'):
                    emitter = True
            elif term.get('kind') not in ('Goto', 'SwitchInt'):
                valid = False; break
        if not valid or not emitter or not closures:
            continue
        refs = ['bb' + str(n) for n in sorted(members)]
        region = {'callSite': dict(zip(('file', 'startLine', 'endLine', 'startColumn', 'endColumn'), anchor)),
                  'bbRefs': refs,
                  'closureArtifacts': [{'defPathHash': key, 'sha256': value} for key, value in sorted(closures.items())]}
        regions.append(region)
        for ref in refs:
            proven[ref] = {'callSite': region['callSite'], 'closureArtifacts': region['closureArtifacts']}
    return {'blocks': proven, 'regions': regions}


def prove_blocks(raw, artifacts):
    """Independent complete-BB proof, in addition to whole-region proof."""
    pinned = _artifact_map(artifacts)
    if any(not isinstance(block.get('basic_block'),int) for block in raw.get('basic_blocks',[])):
        return {'blocks':{},'regions':[]}
    blocks = {block['basic_block']: block for block in raw.get('basic_blocks', [])}
    proven = {}; regions = []
    rejected = set()
    for candidate in blocks.values():
        term = candidate.get('terminator', {})
        accepted = _callee(term) if term.get('kind') == 'Call' else None
        if accepted and accepted[0] == 'closure':
            artifact = pinned.get(accepted[1])
            if artifact is None or not _pure_closure(artifact['raw'], accepted[1]):
                rejected.add(_site(term))
    # A mixed call-site does not invalidate its independently pure BBs.
    for number, block in blocks.items():
        ref = 'bb' + str(number)
        if ref in proven or block.get('is_cleanup'):
            continue
        term = block.get('terminator', {})
        operations = [op for op in [*block.get('statements', []), term]
                      if op.get('kind') not in ('StorageLive', 'StorageDead', 'Nop')]
        sites = {_site(op) for op in operations}
        if not operations or len(sites) != 1 or None in sites or any(not _macro(op) for op in operations):
            continue
        site = sites.pop()
        if site in rejected:continue
        used = {}; safe = True
        for statement in block.get('statements', []):
            if _statement(statement, raw, site):
                continue
            sd = statement.get('detail', {}); value = sd.get('rvalue', {})
            vd = value.get('detail', {}); aggregate = vd.get('aggregate_kind', {})
            key = aggregate.get('detail', {}).get('definition', {}).get('def_path_hash')
            artifact = pinned.get(key); output = sd.get('destination', {})
            if (statement.get('kind') != 'Assign' or value.get('kind') != 'Aggregate'
                    or aggregate.get('kind') != 'Closure' or artifact is None
                    or not _pure_closure(artifact['raw'], key)
                    or output.get('projection') or output.get('local', 0) <= raw.get('arg_count', 0)
                    or any(operand.get('kind') not in ('Copy', 'Move', 'Constant') for operand in vd.get('operands', []))):
                safe = False; break
            used[key] = artifact['sha256']
        if not safe:
            continue
        if term.get('kind') == 'Call':
            accepted = _callee(term); output = term.get('detail', {}).get('destination', {})
            if accepted is None or output.get('projection') or output.get('local', 0) <= raw.get('arg_count', 0):
                continue
            if accepted[0] == 'closure':
                artifact = pinned.get(accepted[1])
                if artifact is None or not _pure_closure(artifact['raw'], accepted[1]):
                    continue
                used[accepted[1]] = artifact['sha256']
        elif term.get('kind') not in ('Goto', 'SwitchInt'):
            continue
        evidence = {'callSite': dict(zip(('file', 'startLine', 'endLine', 'startColumn', 'endColumn'), site)),
                    'closureArtifacts': [{'defPathHash': key, 'sha256': value} for key, value in sorted(used.items())],
                    'proofKind': 'pure_tracing_bb'}
        proven[ref] = evidence
        regions.append(dict(evidence, bbRefs=[ref]))
    return {'blocks': proven, 'regions': regions}


def verify(raw, records, artifacts):
    proof = prove(raw, artifacts); errors = []
    partial = prove_blocks(raw, artifacts)
    for ref, evidence in partial['blocks'].items():
        proof['blocks'].setdefault(ref, evidence)
    claimed = {r.get('bbRef'): r for r in records or []
               if r.get('category') == 'instrumentation' and r.get('blockRole') == 'event_macro'}
    for ref, record in claimed.items():
        block = proof['blocks'].get(ref)
        if not block:
            errors.append({'code': 'unproven-event-macro', 'bbRef': ref})
        elif record.get('eventMacroProof') != block:
            errors.append({'code': 'event-macro-proof-mismatch', 'bbRef': ref})
    return errors
