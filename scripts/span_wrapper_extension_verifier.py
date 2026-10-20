"""Independent proof for the two narrow #[instrument] span extensions.

This module intentionally imports no generator, registry, or source-range code.
It proves the surrounding span region and the extension shapes again from raw
MIR. Unknown syntax, locals, edges, or source provenance fail closed.
"""
import re


_MACROS = re.compile(r'(?:^|/)tracing-[^/]+/src/macros\.rs$')


def _span(op):
    return (op.get('source_info') or {}).get('span')


def _site(op):
    span = _span(op) or {}
    if not span.get('from_expansion'):
        return None
    call = span.get('call_site') or span
    return tuple(call.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))


def _span_key(span):
    if not span:
        return None
    return tuple(span.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))


def _function(term):
    typ = term.get('detail', {}).get('func', {}).get('detail', {}).get('constant', {}).get('type', {})
    if typ.get('kind') != 'FnDef':
        return ''
    match = re.search(r' \{((?:[A-Za-z_]\w*::|<).*)\}$', typ.get('display', ''))
    return match.group(1) if match else ''


def _tracing(name):
    return bool(name.startswith(('tracing::subscriber::Interest::', 'tracing::level_filters::LevelFilter::',
        'tracing::callsite::DefaultCallsite::', 'tracing::Metadata::', 'tracing::field::',
        'tracing::Span::', 'tracing::__macro_support::', 'tracing::dispatcher::'))
        or re.fullmatch(r'<tracing::(?:log::)?Level as std::cmp::PartialOrd<tracing::(?:log::|level_filters::)LevelFilter>>::le', name)
        or name == '<tracing::callsite::DefaultCallsite as tracing::Callsite>::metadata')


def _type_at(types, place):
    typ = types.get(place.get('local'), {})
    for step in place.get('projection', []):
        if step.get('kind') == 'Field':
            typ = step.get('detail', {}).get('field_type', {})
        elif step.get('kind') == 'Deref':
            typ = typ.get('detail', {}).get('pointee', {})
        elif step.get('kind') != 'Downcast':
            return {}
    return typ


def _core_regions(raw, blocks, types):
    enters = [b for b in blocks.values() if not b.get('is_cleanup')
              and b.get('terminator', {}).get('kind') == 'Call'
              and _function(b['terminator']) in ('tracing::Span::enter', 'tracing::Span::new')
              and _site(b['terminator'])]
    anchors = {_site(b['terminator']) for b in enters}
    regions = {}
    for anchor in anchors:
        members = set()
        for number, block in blocks.items():
            if block.get('is_cleanup'):
                continue
            valid = True; generated = False
            for statement in block.get('statements', []):
                if statement.get('kind') in ('StorageLive', 'StorageDead', 'Nop'):
                    continue
                detail = statement.get('detail', {}); dest = detail.get('destination', {})
                if (statement.get('kind') != 'Assign' or dest.get('projection')
                        or dest.get('local', 0) <= raw.get('arg_count', 0) or _site(statement) != anchor
                        or detail.get('rvalue', {}).get('kind') not in ('Use', 'Ref', 'Aggregate', 'Cast', 'UnaryOp', 'Discriminant')):
                    valid = False; break
                generated = True
            term = block.get('terminator', {}); kind = term.get('kind'); name = _function(term)
            if kind == 'Call':
                valid &= bool(_tracing(name) and _site(term) == anchor
                              and not term.get('detail', {}).get('destination', {}).get('projection'))
                generated = True
            elif kind == 'Drop':
                display = _type_at(types, term.get('detail', {}).get('place', {})).get('display', '')
                valid &= ('tracing::' in display or 'tracing_core::' in display)
                generated |= _site(term) == anchor
            elif kind in ('Goto', 'SwitchInt'):
                valid &= _site(term) == anchor or generated
            else:
                valid = False
            if valid:
                members.add(number)
        if any(b['basic_block'] in members for b in enters if _site(b['terminator']) == anchor):
            regions[anchor] = members
    return regions


def _macro_storage(statement, local_map, anchor):
    local = statement.get('detail', {}).get('local')
    op_span = _span(statement) or {}; local_span = ((local_map.get(local, {}).get('source_info') or {}).get('span') or {})
    path = (op_span.get('file_portable') or op_span.get('file') or '').replace('\\', '/')
    call = local_span.get('call_site') or {}
    local_site = tuple(call.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))
    return bool(isinstance(local, int) and op_span.get('from_expansion') and _MACROS.search(path)
                and local_span.get('from_expansion') and local_site == anchor)


def _debug_local(variable):
    value = variable.get('value', {}); place = value.get('detail', {}).get('place', {})
    return place.get('local') if value.get('kind') == 'Place' and not place.get('projection') else None


def prove(raw):
    raw_blocks = raw.get('basic_blocks', [])
    if not raw_blocks or any(not isinstance(b.get('basic_block'), int) for b in raw_blocks):
        return {'blocks': set(), 'sourceLessGotos': set(), 'fakeReturn': set(), 'candidates': set()}
    blocks = {b['basic_block']: b for b in raw_blocks}; types = {l['local']: l.get('type', {}) for l in raw.get('locals', [])}
    locals_by_id = {l['local']: l for l in raw.get('locals', [])}
    predecessors = {n: set() for n in blocks}
    for number, block in blocks.items():
        for target in block.get('terminator', {}).get('successors', []):
            if target in predecessors:
                predecessors[target].add(number)
    regions = _core_regions(raw, blocks, types); connectors = set(); proven = set()
    for anchor, core in regions.items():
        proven.update(core)
        for number, block in blocks.items():
            term = block.get('terminator', {}); successors = set(term.get('successors', []))
            storage_only = all(s.get('kind') == 'Nop' or
                (s.get('kind') in ('StorageLive', 'StorageDead') and _macro_storage(s, locals_by_id, anchor))
                for s in block.get('statements', []))
            if (number not in core and not block.get('is_cleanup') and term.get('kind') == 'Goto'
                    and _span(term) is None and predecessors[number] and successors
                    and predecessors[number] <= core and successors <= core and storage_only):
                connectors.add(number)
    proven.update(connectors)

    fake = set(); scopes = {s.get('source_scope'): s for s in raw.get('source_scopes', [])}
    debug = [v for v in raw.get('debug_variables', []) if v.get('name') == '__tracing_attr_fake_return']
    debug_local = _debug_local(debug[0]) if len(debug) == 1 else None
    debug_scope = (debug[0].get('source_info') or {}).get('scope') if len(debug) == 1 else None
    debug_bound = {_debug_local(v) for v in raw.get('debug_variables', [])}
    for anchor, core in regions.items():
        region = core | connectors
        def in_scope(scope):
            seen = set()
            while scope in scopes and scope not in seen:
                seen.add(scope); span = scopes[scope].get('span') or {}
                if span.get('from_expansion') and _site({'source_info': {'span': span}}) == anchor:
                    return True
                scope = scopes[scope].get('parent_scope')
            return False
        if debug_local is None or not in_scope(debug_scope):
            continue
        def wrapper_local(local):
            span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
            call = span.get('call_site') or {}
            return bool(span.get('from_expansion') and tuple(call.get(k) for k in
                ('file', 'start_line', 'end_line', 'start_column', 'end_column')) == anchor)
        for number, block in blocks.items():
            term = block.get('terminator', {}); detail = term.get('detail', {})
            discr = detail.get('discriminant', {}); selector = discr.get('detail', {}).get('place', {})
            if (block.get('is_cleanup') or term.get('kind') != 'SwitchInt' or discr.get('kind') not in ('Copy', 'Move')
                    or selector.get('projection') or not in_scope((term.get('source_info') or {}).get('scope'))):
                continue
            control = selector.get('local'); root_span = _span(term); root_key = _span_key(root_span); assignments = 0; valid = True
            for statement in block.get('statements', []):
                kind = statement.get('kind'); sd = statement.get('detail', {}); local = sd.get('local')
                if kind == 'Assign':
                    dest = sd.get('destination', {}); value = sd.get('rvalue', {}); operand = value.get('detail', {}).get('operand', {})
                    constant = operand.get('detail', {}).get('constant', {})
                    exact = (dest == {'local': control, 'projection': []} and value.get('kind') == 'Use'
                             and operand.get('kind') == 'Constant' and constant.get('type', {}).get('kind') == 'Bool'
                             and constant.get('value_debug') == 'Val(Scalar(0x00), bool)')
                    assignments += bool(exact); valid &= exact
                elif kind in ('StorageLive', 'StorageDead'):
                    local_span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
                    valid &= bool(local == control or wrapper_local(local)
                                  or (local not in debug_bound and _span_key(local_span) == root_key
                                      and types.get(local, {}).get('kind') in ('Tuple', 'Bool', 'Never')))
                elif kind != 'Nop':
                    valid = False
            false_targets = [x.get('target') for x in detail.get('targets', []) if str(x.get('value')) == '0']
            start = detail.get('otherwise')
            if (not valid or assignments != 1 or len(false_targets) != 1 or start is None or start == false_targets[0]
                    or not predecessors[number] or not predecessors[number] <= region):
                continue
            chain = []; current = start; previous = number
            while current not in chain:
                candidate = blocks.get(current)
                if not candidate or candidate.get('is_cleanup') or predecessors.get(current, set()) - {previous, current}:
                    valid = False; break
                chain.append(current)
                for statement in candidate.get('statements', []):
                    kind = statement.get('kind'); sd = statement.get('detail', {}); local = sd.get('local')
                    if kind in ('StorageLive', 'StorageDead'):
                        local_span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
                        valid &= bool(local == debug_local or (local not in debug_bound and _span_key(local_span) == root_key))
                    elif kind == 'Assign':
                        dest = sd.get('destination', {}); value = sd.get('rvalue', {}); operand = value.get('detail', {}).get('operand', {})
                        typ = operand.get('detail', {}).get('constant', {}).get('type', {})
                        valid &= bool(not dest.get('projection') and dest.get('local') not in debug_bound
                                      and types.get(dest.get('local'), {}).get('kind') == 'Tuple'
                                      and types.get(dest.get('local'), {}).get('detail', {}).get('elements') == []
                                      and value.get('kind') == 'Use' and operand.get('kind') == 'Constant'
                                      and typ.get('kind') == 'Tuple' and typ.get('detail', {}).get('elements') == []
                                      and _span_key(_span(statement)) == root_key)
                    elif kind != 'Nop':
                        valid = False
                    if not valid:
                        break
                end = candidate.get('terminator', {})
                if not valid or end.get('kind') != 'Goto':
                    valid = False; break
                target = end.get('detail', {}).get('target')
                if target == current:
                    break
                previous, current = current, target
            if (valid and chain and blocks[chain[-1]].get('terminator', {}).get('detail', {}).get('target') == chain[-1]
                    and any(any(s.get('detail', {}).get('local') == debug_local for s in blocks[n].get('statements', [])) for n in chain)):
                fake.update([number, *chain]); break
    proven.update(fake)

    # Relaxed shapes tell verify() which claimed records require this extension
    # proof even after a malicious mutation makes the exact proof fail.
    candidates = {n for n, b in blocks.items() if _span(b.get('terminator', {})) is None
                  and all(s.get('kind') in ('StorageLive', 'StorageDead', 'Nop') for s in b.get('statements', []))}
    for number, block in blocks.items():
        term = block.get('terminator', {}); detail = term.get('detail', {})
        if term.get('kind') != 'SwitchInt':
            continue
        selector = detail.get('discriminant', {}).get('detail', {}).get('place', {})
        if any(s.get('kind') == 'Assign' and s.get('detail', {}).get('destination') == selector
               for s in block.get('statements', [])):
            candidates.add(number); todo = [detail.get('otherwise')]; seen = set()
            while todo:
                current = todo.pop()
                if current in seen or current not in blocks:
                    continue
                seen.add(current); candidates.add(current)
                end = blocks[current].get('terminator', {})
                if end.get('kind') == 'Goto' and end.get('detail', {}).get('target') != current:
                    todo.append(end.get('detail', {}).get('target'))
    return {'blocks': proven, 'sourceLessGotos': connectors, 'fakeReturn': fake, 'candidates': candidates}


def verify(raw, records):
    proof = prove(raw); errors = []
    claimed = {r.get('bbRef') for r in records or []
               if r.get('category') == 'instrumentation' and r.get('blockRole') != 'event_macro'}
    for ref in sorted(claimed):
        if not isinstance(ref, str) or not re.fullmatch(r'bb\d+', ref):
            continue
        number = int(ref[2:])
        if number in proof['candidates'] and number not in proof['blocks']:
            errors.append({'code': 'unproven-span-wrapper-extension', 'bbRef': ref})
    return errors
