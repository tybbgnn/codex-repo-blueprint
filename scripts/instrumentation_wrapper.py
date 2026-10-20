"""Conservative proof for a coroutine forwarding one instrumented async child.

No source/body identifiers or size heuristics. Unknown operations fail closed.
Tracing on/off arms may poll the same constructed child at two static sites.
"""
import re


_TRACING_MACROS = re.compile(r'(?:^|/)tracing-[^/]+/src/macros\.rs$')


def function_item(ty):
    if ty.get('kind') != 'FnDef':
        return ''
    m = re.search(r' \{((?:[A-Za-z_]\w*::|<).*)\}$', ty.get('display', ''))
    return m.group(1) if m else ''


def prove(body):
    blocks = body.get('basic_blocks', [])
    local_types = {x['local']: x['type'] for x in body.get('locals', [])}
    owner = body.get('owner_def_path_hash')
    if not blocks or not local_types or not body.get('is_coroutine'):
        return None

    def place_type(p):
        t = local_types.get(p.get('local'), {})
        for step in p.get('projection', []):
            if step['kind'] == 'Deref': t = t.get('detail', {}).get('pointee', {})
            elif step['kind'] == 'Field': t = step['detail'].get('field_type', {})
            elif step['kind'] != 'Downcast': return {}
        return t

    def frame(p):
        """Only stores in this coroutine's own frame, never captured pointees."""
        t = local_types.get(p.get('local'), {})
        derefs = 0
        for step in p.get('projection', []):
            if step['kind'] == 'Deref':
                derefs += 1; t = t.get('detail', {}).get('pointee', {})
                if derefs != 1 or t.get('def_path_hash') != owner:return False
            elif step['kind'] == 'Field':
                if t.get('def_path_hash') != owner:return False
                t = step['detail'].get('field_type', {})
            elif step['kind'] != 'Downcast':return False
        return derefs == 1

    def key(p):
        return (p.get('local'), tuple((x['kind'], x.get('detail', {}).get('field_index'), x.get('detail', {}).get('variant_index')) for x in p.get('projection', [])))

    def trace(t):
        display=t.get('display','')
        return display.startswith(('tracing::','tracing_core::')) or ('tracing::' in display and display.startswith(('&','[','std::option::Option<','core::option::Option<')))

    def dispatch_type(t):
        return t.get('def_path_hash') == owner or t.get('display','').startswith(('std::task::Poll<','core::task::Poll<')) or trace(t)

    constructions=[]; assignments=[]; calls=[]; branches=[]; trace_calls=[]; polls=[]; ready=[]
    try:
        for block in blocks:
            bb=block['basic_block']
            for st in block.get('statements', []):
                kind=st['kind'];d=st.get('detail',{})
                if kind in ('StorageLive','StorageDead','Nop'):continue
                if kind=='SetDiscriminant':
                    if not frame(d['place']):return None
                    continue
                if kind!='Assign':return None
                dest=d['destination'];rv=d['rvalue'];rd=rv.get('detail',{});typ=place_type(dest)
                if dest.get('projection') and not frame(dest):return None
                if rv['kind']=='Aggregate' and rd.get('aggregate_kind',{}).get('kind')=='Coroutine':
                    constructions.append((bb,rd['aggregate_kind']['detail']['definition']['def_path_hash'],typ.get('display'),key(dest)))
                elif rv['kind']=='Aggregate':
                    if not (trace(typ) or typ.get('display')=='()' or typ.get('display','').startswith(('std::task::Poll<','core::task::Poll<'))):return None
                    if typ.get('display','').startswith(('std::task::Poll<','core::task::Poll<')):
                        # Ready holds exactly the forwarded child output; Pending is empty.
                        ops=rd.get('operands',[])
                        if ops:ready.append(ops)
                elif rv['kind']=='Cast':
                    if not (trace(typ) and rd.get('cast_kind','').startswith('PointerCoercion(Unsize,')):return None
                elif rv['kind']=='UnaryOp':
                    if rd.get('operator')!='Not' or typ.get('kind')!='Bool':return None
                elif rv['kind']=='Discriminant':
                    if not dispatch_type(place_type(rd['place'])):return None
                elif rv['kind']=='Use':
                    op=rd['operand']
                    if op['kind']=='Constant':
                        ct=op['detail']['constant']['type']
                        if ct.get('kind') not in ('Bool','Uint','Int') and ct.get('display')!='()' and not trace(ct) and not ct.get('display','').startswith('&tracing::') and ct.get('display','').lstrip('&')!='str':return None
                    elif op['kind'] not in ('Copy','Move'):return None
                elif rv['kind']=='Ref':
                    # References may read captures for span fields; mutable access only to machinery.
                    if rd.get('borrow_kind','').startswith('Mut'):
                        pt=place_type(rd['place']);pd=pt.get('display','')
                        if not (frame(rd['place']) or trace(pt) or 'async block@' in pd or 'task::Context' in pd):return None
                else:return None
                assignments.append((key(dest),rv))
            term=block['terminator'];td=term.get('detail',{});kind=term['kind']
            if kind=='Call':calls.append((bb,td))
            elif kind=='SwitchInt':branches.append((bb,td['discriminant']))
            elif kind=='Assert':
                # rustc's resumed-after-return/panic guards are coroutine state checks.
                if bb < 1 or 'resum' not in str(td.get('message','')).lower():return None
            elif kind not in ('Goto','Drop','Return','Unreachable','UnwindResume','UnwindTerminate'):return None
        if len(constructions)!=1:return None
        cb,child,display,constructed=constructions[0]
        if not child or not display:return None
        direct=display;instrumented='tracing::instrument::Instrumented<'+display+'>'
        poll_items={f'<{t} as {tr}>::poll' for t in (direct,instrumented) for tr in ('futures::Future','std::future::Future','core::future::Future')}
        into_items={f'<{t} as {tr}>::into_future' for t in (direct,instrumented) for tr in ('std::future::IntoFuture','core::future::IntoFuture')}
        tags={};copies=[]
        def add(k,tag):tags.setdefault(k,set()).add(tag)
        for bb,td in calls:
            item=function_item(td.get('func',{}).get('detail',{}).get('constant',{}).get('type',{}))
            dest=td.get('destination',{})
            if dest.get('projection') and not frame(dest):return None
            if item in poll_items:
                polls.append(bb);add(key(dest),'poll')
            elif item in into_items or item==f'<{direct} as tracing::Instrument>::instrument' or (item.startswith(('std::pin::Pin::<','core::pin::Pin::<')) and item.endswith('>::new_unchecked') and direct in item):
                pass
            elif item.startswith(('tracing::subscriber::Interest::','tracing::level_filters::LevelFilter::','tracing::callsite::DefaultCallsite::','tracing::Metadata::','tracing::field::','tracing::Span::','tracing::__macro_support::','tracing::dispatcher::')) or re.fullmatch(r'<tracing::(?:log::)?Level as std::cmp::PartialOrd<tracing::(?:log::|level_filters::)LevelFilter>>::le',item) or item=='<tracing::callsite::DefaultCallsite as tracing::Callsite>::metadata':
                trace_calls.append({'bbRef':f'bb{bb}','callee':item});add(key(dest),'trace')
            else:return None
        if not trace_calls or not polls:return None
        for dest,rv in assignments:
            rd=rv.get('detail',{});kind=rv['kind']
            if kind=='Discriminant':add(dest,'control')
            elif kind=='Use':
                op=rd['operand']
                if op['kind']=='Constant':
                    if op['detail']['constant']['type'].get('kind')=='Bool':add(dest,'flag')
                else:copies.append((dest,key(op['detail']['place'])))
            elif kind=='UnaryOp':copies.append((dest,key(rd['operand']['detail']['place'])))
        # Finite copy closure supports coroutine frame aliases/resume locals.
        for _ in range(len(assignments)+1):
            changed=False
            for dest,src in copies:
                old=len(tags.get(dest,set()));tags.setdefault(dest,set()).update(tags.get(src,set()));changed |= old!=len(tags[dest])
            if not changed:break
        for bb,op in branches:
            if op.get('kind') not in ('Move','Copy'):return None
            p=op['detail']['place']
            if not tags.get(key(p),set()) & {'trace','control','flag'}:return None
        # Ready source must trace back to a field of a poll result, not a fabricated result.
        result_keys=set()
        for dest,src in copies:
            if src[1] and 'poll' in tags.get((src[0],()),set()):result_keys.add(dest)
        for _ in range(len(copies)+1):
            old=len(result_keys)
            result_keys.update(dest for dest,src in copies if src in result_keys)
            if old==len(result_keys):break
        for ops in ready:
            if len(ops)!=1 or ops[0].get('kind') not in ('Move','Copy') or key(ops[0]['detail']['place']) not in result_keys:return None
        if not ready:return None
        return dict(coroutine_def_path_hash=child,wrapper_bb_count=len(blocks),
                    construction_blocks=[cb],poll_blocks=polls,tracing_calls=trace_calls,
                    branch_blocks=[bb for bb,_ in branches],
                    proof='one constructed child; only tracing, instrument/IntoFuture/Pin/poll calls; control discriminants and frame-local writes; Ready forwards child output')
    except (KeyError,TypeError,ValueError):return None


def _prove_span(body, asynchronous=False):
    """Classify generated span machinery around retained work.

    Unlike the async forwarding proof, this never changes body identity: rustc
    may inline the wrapped expression. Every exempted BB is checked in full;
    mixed business/trace blocks remain business-owned.
    """
    from source_ranges import compiler_drop_flags, place_key
    from classification_registry import fingerprint
    if bool(body.get('is_coroutine')) != asynchronous or not body.get('basic_blocks'):
        return None
    blocks = body['basic_blocks']
    types = {l['local']: l.get('type', {}) for l in body.get('locals', [])}
    locals_by_id = {l['local']: l for l in body.get('locals', [])}
    flags = compiler_drop_flags(body)
    def item(term):
        return function_item(term.get('detail', {}).get('func', {}).get('detail', {}).get('constant', {}).get('type', {}))
    def tracing(name):
        return (name.startswith(('tracing::subscriber::Interest::', 'tracing::level_filters::LevelFilter::',
                'tracing::callsite::DefaultCallsite::', 'tracing::Metadata::', 'tracing::field::',
                'tracing::Span::', 'tracing::__macro_support::', 'tracing::dispatcher::'))
                or re.fullmatch(r'<tracing::(?:log::)?Level as std::cmp::PartialOrd<tracing::(?:log::|level_filters::)LevelFilter>>::le', name)
                or name == '<tracing::callsite::DefaultCallsite as tracing::Callsite>::metadata')
    def anchor(op):
        span = (op.get('source_info') or {}).get('span') or {}
        if not span.get('from_expansion'): return None
        span = span.get('call_site') or span
        return tuple(span.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))
    def raw_span(op):
        return (op.get('source_info') or {}).get('span')
    def span_key(span):
        if not span: return None
        return tuple(span.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))
    def macro_storage(statement, expected_anchor):
        local = statement.get('detail', {}).get('local')
        op_span = raw_span(statement) or {}; local_span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
        op_path = (op_span.get('file_portable') or op_span.get('file') or '').replace('\\', '/')
        local_call = local_span.get('call_site') or {}
        local_anchor = tuple(local_call.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column'))
        return bool(isinstance(local, int) and op_span.get('from_expansion') and _TRACING_MACROS.search(op_path)
                    and local_span.get('from_expansion') and local_anchor == expected_anchor)
    enters = [b for b in blocks if b['terminator']['kind'] == 'Call'
              and item(b['terminator']) == ('tracing::Span::new' if asynchronous else 'tracing::Span::enter')
              and anchor(b['terminator'])]
    anchors = {anchor(b['terminator']) for b in enters}
    if not enters: return None
    business = [b for b in blocks if not b.get('is_cleanup') and b['terminator']['kind'] == 'Call'
                and item(b['terminator']) and not tracing(item(b['terminator']))
                and (asynchronous or anchor(b['terminator']) not in anchors)]
    if not business: return None
    by_id = {b['basic_block']: b for b in blocks}
    # The span-enter path must actually lead to real inner work.
    todo = [b['terminator']['detail'].get('target') for b in enters]; reachable = set()
    while todo:
        bb = todo.pop()
        if bb in reachable or bb not in by_id or by_id[bb].get('is_cleanup'): continue
        reachable.add(bb); todo.extend(by_id[bb]['terminator'].get('successors', []))
    if not any(b['basic_block'] in reachable for b in business): return None
    def places(value):
        if isinstance(value, dict):
            if 'local' in value and 'projection' in value: yield value
            else:
                for v in value.values(): yield from places(v)
        elif isinstance(value, list):
            for v in value: yield from places(v)
    def trace_type(t):
        return 'tracing::' in t.get('display', '') or 'tracing_core::' in t.get('display', '')
    candidates = {}; writes = {}
    for b in blocks:
        if b.get('is_cleanup'): continue
        bid = b['basic_block']; dests = set(); valid = True; generated = False
        for st in b.get('statements', []):
            if st['kind'] in ('StorageLive', 'StorageDead', 'Nop'): continue
            d = st.get('detail', {}); dest = d.get('destination', {}); rv = d.get('rvalue', {}); rd = rv.get('detail', {})
            if st['kind'] != 'Assign' or dest.get('projection') or dest.get('local', 0) <= body.get('arg_count', 0):
                valid = False; break
            flag = place_key(dest) in flags
            if anchor(st) not in anchors and not flag:
                valid = False; break
            generated |= anchor(st) in anchors
            if rv.get('kind') not in ('Use', 'Ref', 'Aggregate', 'Cast', 'UnaryOp', 'Discriminant'):
                valid = False; break
            if rv['kind'] == 'Ref' and rd.get('borrow_kind') != 'Shared':
                valid = False; break
            if rv['kind'] == 'UnaryOp' and rd.get('operator') != 'Not':
                valid = False; break
            if rv['kind'] == 'Cast' and not rd.get('cast_kind', '').startswith('PointerCoercion(Unsize,'):
                valid = False; break
            if rv['kind'] == 'Aggregate' and not (trace_type(types.get(dest['local'], {}))
                    or types.get(dest['local'], {}).get('kind') in ('Tuple', 'Array')):
                valid = False; break
            dests.add(dest['local'])
        term = b['terminator']; td = term.get('detail', {})
        if term['kind'] == 'Call':
            if not asynchronous and anchor(term) in anchors and not tracing(item(term)): return None
            valid &= bool(tracing(item(term)) and anchor(term) in anchors
                          and not td.get('destination', {}).get('projection')
                          and td.get('destination', {}).get('local', 0) > body.get('arg_count', 0))
            if valid: dests.add(td['destination']['local']); generated = True
        elif term['kind'] == 'Drop':
            p = td.get('place', {}); valid &= not p.get('projection') and trace_type(types.get(p.get('local'), {}))
        elif term['kind'] not in ('Goto', 'SwitchInt'): valid = False
        elif anchor(term) not in anchors and not (term['kind'] == 'Goto' and generated): valid = False
        if valid:
            candidates[bid] = b; writes[bid] = dests
    # No traced value may flow into business work, a return, or captured memory.
    # Storage ends and destructor flag routing do not consume business values.
    while True:
        unsafe = set()
        for b in blocks:
            if b['basic_block'] in candidates: continue
            for st in b.get('statements', []):
                if st['kind'] in ('StorageLive', 'StorageDead', 'Nop'): continue
                d = st.get('detail', {})
                unsafe.update(p['local'] for p in places(d.get('rvalue', d)))
            term = b['terminator']; td = term.get('detail', {})
            if term['kind'] == 'Drop' and trace_type(types.get(td.get('place', {}).get('local'), {})): continue
            if term['kind'] == 'SwitchInt' and place_key(td.get('discriminant', {}).get('detail', {}).get('place', {})) in flags: continue
            unsafe.update(p['local'] for p in places(td))
        remove = {bid for bid in candidates if writes[bid] & unsafe}
        if not remove: break
        for bid in remove: candidates.pop(bid)
    # rustc can split macro-temporary storage cleanup into source-less Goto
    # blocks. Admit one only when both sides are already in this exact span
    # region and every touched local was itself defined by tracing's macro.
    connector_blocks = []
    if len(anchors) == 1:
        region_anchor = next(iter(anchors)); core = set(candidates)
        predecessors = {number: set() for number in by_id}
        for number, block in by_id.items():
            for target in block.get('terminator', {}).get('successors', []):
                if target in predecessors: predecessors[target].add(number)
        for bid, block in by_id.items():
            term = block.get('terminator', {}); successors = set(term.get('successors', []))
            storage_only = all(st.get('kind') == 'Nop' or
                (st.get('kind') in ('StorageLive', 'StorageDead')
                 and macro_storage(st, region_anchor))
                for st in block.get('statements', []))
            if (bid not in core and not block.get('is_cleanup') and term.get('kind') == 'Goto'
                    and raw_span(term) is None and predecessors[bid] and successors
                    and predecessors[bid] <= core and successors <= core and storage_only):
                candidates[bid] = block; connector_blocks.append(bid)

    # #[instrument] emits `if false { let __tracing_attr_fake_return =
    # loop {}; ... }`. The dead arm is accepted only through that exact debug
    # binding, a constant-false selector, macro-scope ancestry, and a closed
    # Goto chain ending in a self-loop. The false/normal successor is retained.
    fake_return_blocks = []; fake_return_local = None
    if len(anchors) == 1:
        region_anchor = next(iter(anchors))
        scopes = {s.get('source_scope'): s for s in body.get('source_scopes', [])}
        debug = [v for v in body.get('debug_variables', []) if v.get('name') == '__tracing_attr_fake_return']
        def debug_place(variable):
            value = variable.get('value', {}); place = value.get('detail', {}).get('place', {})
            return place.get('local') if value.get('kind') == 'Place' and not place.get('projection') else None
        def in_instrument_scope(scope):
            seen = set()
            while scope in scopes and scope not in seen:
                seen.add(scope); span = scopes[scope].get('span') or {}
                if span.get('from_expansion') and anchor({'source_info': {'span': span}}) == region_anchor:
                    return True
                scope = scopes[scope].get('parent_scope')
            return False
        debug_local = debug_place(debug[0]) if len(debug) == 1 else None
        debug_scope = (debug[0].get('source_info') or {}).get('scope') if len(debug) == 1 else None
        debug_bound = {debug_place(v) for v in body.get('debug_variables', [])}
        def wrapper_local(local):
            span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
            call = span.get('call_site') or {}
            return bool(span.get('from_expansion') and
                tuple(call.get(k) for k in ('file', 'start_line', 'end_line', 'start_column', 'end_column')) == region_anchor)
        for bid, block in by_id.items():
            term = block.get('terminator', {}); detail = term.get('detail', {})
            operand = detail.get('discriminant', {}); selector = operand.get('detail', {}).get('place', {})
            if (debug_local is None or block.get('is_cleanup') or term.get('kind') != 'SwitchInt'
                    or operand.get('kind') not in ('Copy', 'Move') or selector.get('projection')
                    or not in_instrument_scope((term.get('source_info') or {}).get('scope'))
                    or not in_instrument_scope(debug_scope)):
                continue
            control = selector.get('local'); false_assignments = []
            root_span = raw_span(term); root_key = span_key(root_span)
            root_ok = True
            for st in block.get('statements', []):
                kind = st.get('kind'); sd = st.get('detail', {}); local = sd.get('local')
                if kind == 'Assign':
                    dest = sd.get('destination', {}); rv = sd.get('rvalue', {}); op = rv.get('detail', {}).get('operand', {})
                    constant = op.get('detail', {}).get('constant', {})
                    is_false = (dest == {'local': control, 'projection': []} and rv.get('kind') == 'Use'
                                and op.get('kind') == 'Constant' and constant.get('type', {}).get('kind') == 'Bool'
                                and constant.get('value_debug') == 'Val(Scalar(0x00), bool)')
                    if is_false: false_assignments.append(st)
                    else: root_ok = False
                elif kind in ('StorageLive', 'StorageDead'):
                    local_span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
                    local_type = types.get(local, {})
                    root_ok &= bool(local == control or wrapper_local(local)
                                    or (local not in debug_bound and span_key(local_span) == root_key
                                        and local_type.get('kind') in ('Tuple', 'Bool', 'Never')))
                elif kind != 'Nop': root_ok = False
            targets = detail.get('targets', []); false_targets = [x.get('target') for x in targets if str(x.get('value')) == '0']
            fake_start = detail.get('otherwise')
            if (not root_ok or len(false_assignments) != 1 or len(false_targets) != 1
                    or fake_start is None or fake_start == false_targets[0]):
                continue
            # The wrapper must hand normal execution to business code, while
            # arriving at the selector only from the already-proven span.
            if not predecessors.get(bid) or not predecessors[bid] <= set(candidates):
                continue
            chain = []; current = fake_start; previous = bid; valid = True
            while current not in chain:
                candidate = by_id.get(current)
                if not candidate or candidate.get('is_cleanup') or predecessors.get(current, set()) - {previous, current}:
                    valid = False; break
                chain.append(current)
                for st in candidate.get('statements', []):
                    kind = st.get('kind'); sd = st.get('detail', {}); local = sd.get('local')
                    if kind in ('StorageLive', 'StorageDead'):
                        local_span = ((locals_by_id.get(local, {}).get('source_info') or {}).get('span') or {})
                        if not (local == debug_local or (local not in debug_bound and span_key(local_span) == root_key)):
                            valid = False; break
                    elif kind == 'Assign':
                        dest = sd.get('destination', {}); rv = sd.get('rvalue', {}); op = rv.get('detail', {}).get('operand', {})
                        typ = op.get('detail', {}).get('constant', {}).get('type', {})
                        if not (not dest.get('projection') and dest.get('local') not in debug_bound
                                and types.get(dest.get('local'), {}).get('kind') == 'Tuple'
                                and types.get(dest.get('local'), {}).get('detail', {}).get('elements') == []
                                and rv.get('kind') == 'Use' and op.get('kind') == 'Constant'
                                and typ.get('kind') == 'Tuple' and typ.get('detail', {}).get('elements') == []
                                and span_key(raw_span(st)) == root_key):
                            valid = False; break
                    elif kind != 'Nop': valid = False; break
                ct = candidate.get('terminator', {})
                if not valid or ct.get('kind') != 'Goto': valid = False; break
                target = ct.get('detail', {}).get('target')
                if target == current: break
                previous, current = current, target
            if (not valid or not chain or by_id[chain[-1]].get('terminator', {}).get('detail', {}).get('target') != chain[-1]
                    or not any(any(st.get('detail', {}).get('local') == debug_local
                                   for st in by_id[n].get('statements', [])) for n in chain)):
                continue
            candidates[bid] = block
            for number in chain: candidates[number] = by_id[number]
            fake_return_blocks = [bid, *chain]; fake_return_local = debug_local
            break
    if not candidates or (not asynchronous and not any(b['basic_block'] in candidates for b in enters)): return None
    return dict(kind='async_instrumentation' if asynchronous else 'sync_instrumentation', business_call_blocks=[b['basic_block'] for b in business],
                **{('span_new_blocks' if asynchronous else 'span_enter_blocks'): [b['basic_block'] for b in enters]},
                source_less_goto_blocks=sorted(connector_blocks), fake_return_blocks=fake_return_blocks,
                fake_return_debug_local=fake_return_local,
                technical_blocks={f'bb{bid}': fingerprint(b) for bid, b in candidates.items()},
                proof='generated span region; closed operation/call set; no business-value escape; reachable inner calls retained')


def prove_sync(body):
    try:
        return _prove_span(body)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def prove_async(body):
    """Per-BB async span proof; ordinary attribute-field calls remain owned.

    This does not remap identity or certify a whole forwarding coroutine.
    Uses the same operation and escape checks as the synchronous proof.
    """
    try:
        return _prove_span(body, asynchronous=True)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
