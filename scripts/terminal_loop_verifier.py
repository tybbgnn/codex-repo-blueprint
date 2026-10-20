"""Independent terminal-only loop verifier. Never imports generator classifiers."""
import hashlib
import json
import re


def _places(value):
    if isinstance(value, dict):
        if 'local' in value and 'projection' in value:
            yield value
        else:
            for child in value.values(): yield from _places(child)
    elif isinstance(value, list):
        for child in value: yield from _places(child)


def _place_key(place):
    if not place.get('projection'): return place.get('local')
    steps=place['projection']
    if [x.get('kind') for x in steps] == ['Deref','Downcast','Field']:
        field=steps[-1].get('detail', {}); owner=field.get('owner_type', {}).get('def_path_hash')
        if owner: return ('frame-field', owner, steps[1].get('detail', {}).get('variant_index'), field.get('field_index'))
    return (place.get('local'), json.dumps(steps, sort_keys=True))


def _drop_flags(raw):
    if not isinstance(raw.get('debug_variables'), list): return set()
    types={x['local']:x.get('type', {}) for x in raw.get('locals', [])}; roots=_frame_roots(raw); owner=raw.get('owner_def_path_hash')
    def frame_bool(place):
        steps=place.get('projection', []); typ=types.get(place.get('local'), {}); field=steps[-1].get('detail', {}) if steps else {}
        return bool(place.get('local') in roots and [x.get('kind') for x in steps] == ['Deref','Downcast','Field']
                    and owner and typ.get('kind') == 'Ref' and typ.get('detail', {}).get('pointee', {}).get('def_path_hash') == owner
                    and field.get('owner_type', {}).get('def_path_hash') == owner and field.get('field_type', {}).get('kind') == 'Bool')
    named={_place_key(p) for v in raw['debug_variables'] for p in _places(v)}
    candidates={x['local'] for x in raw.get('locals', []) if x.get('type', {}).get('kind') == 'Bool' and x['local'] > raw.get('arg_count',0) and x['local'] not in named}
    candidates.update(_place_key(p) for b in raw.get('basic_blocks', []) for p in _places(b) if frame_bool(p) and _place_key(p) not in named)
    blocks={b.get('basic_block'):b for b in raw.get('basic_blocks', [])}; bad=set(); writes=set(); reads=set(); values={}
    for block in blocks.values():
        for op in block.get('statements', []):
            if op.get('kind') in ('StorageLive','StorageDead','Nop'): continue
            d=op.get('detail', {}); dest=d.get('destination', {}) if op.get('kind') == 'Assign' else {}; key=_place_key(dest)
            if key in candidates:
                rv=d.get('rvalue', {}); operand=rv.get('detail', {}).get('operand', {}); const=operand.get('detail', {}).get('constant', {}); literal=const.get('value', {}); bits=literal.get('detail', {}).get('bits')
                if dest.get('projection') and not frame_bool(dest) or rv.get('kind') != 'Use' or operand.get('kind') != 'Constant' or const.get('type', {}).get('kind') != 'Bool' or literal.get('kind') != 'ScalarInt' or bits not in ('0','1'): bad.add(key)
                else: writes.add(key); values.setdefault(key,set()).add(bits)
                value={k:v for k,v in d.items() if k != 'destination'}
            else: value=d
            bad.update(_place_key(p) for p in _places(value) if _place_key(p) in candidates)
        term=block.get('terminator', {}); d=term.get('detail', {}); used=[p for p in _places(d) if _place_key(p) in candidates or p.get('local') in candidates]
        if not used: continue
        discr=d.get('discriminant', {}); place=discr.get('detail', {}).get('place', {}); targets=[x.get('target') for x in d.get('targets', [])]+[d.get('otherwise')]; targets=list(dict.fromkeys(targets)); guarded=False
        if len(targets) == 2 and all(x in blocks for x in targets):
            for drop_id,bypass in (targets,targets[::-1]):
                arm=blocks[drop_id]; end=arm.get('terminator', {})
                if end.get('kind') == 'Drop' and end.get('detail', {}).get('target') == bypass and all(x.get('kind') in ('StorageLive','StorageDead','Nop') for x in arm.get('statements', [])): guarded=True
        if term.get('kind') == 'SwitchInt' and discr.get('kind') in ('Copy','Move') and _place_key(place) in candidates and len(used) == 1 and guarded: reads.add(_place_key(place))
        else: bad.update(_place_key(p) for p in used)
    return {x for x in (candidates & writes & reads)-bad if values.get(x) == {'0','1'}}


def _dead_locals(raw):
    reads={p['local'] for v in raw.get('debug_variables', []) for p in _places(v)}; writes=set()
    for block in raw.get('basic_blocks', []):
        for op in [*block.get('statements', []), block.get('terminator', {})]:
            d=op.get('detail', {}); dest=d.get('destination', {})
            if dest and not dest.get('projection') and op.get('kind') in ('Assign','Call'):
                writes.add(dest.get('local'))
                for k,v in d.items():
                    if k != 'destination': reads.update(p['local'] for p in _places(v))
            elif op.get('kind') not in ('StorageLive','StorageDead','Nop'):
                reads.update(p['local'] for p in _places(d))
    return {x for x in writes if x is not None and x > raw.get('arg_count', 0) and x not in reads}


def _frame_roots(raw):
    owner=raw.get('owner_def_path_hash'); types={x['local']:x.get('type', {}) for x in raw.get('locals', [])}
    def own_ref(t): return bool(owner and t.get('kind') == 'Ref' and t.get('detail', {}).get('pointee', {}).get('def_path_hash') == owner)
    first=types.get(1, {}); direct=own_ref(first)
    pinned=first.get('display','').startswith(('std::pin::Pin<','core::pin::Pin<')) and any(own_ref(x.get('type', {})) for x in first.get('generic_args', []))
    if not raw.get('is_coroutine') or raw.get('arg_count',0) < 1 or not (direct or pinned): return set()
    roots={1} if direct else set(); writes={}
    for block in raw.get('basic_blocks', []):
        for op in [*block.get('statements', []),block.get('terminator', {})]:
            dest=op.get('detail', {}).get('destination', {})
            if dest and not dest.get('projection'): writes.setdefault(dest['local'], []).append(op)
    for _ in range(len(writes)+1):
        old=set(roots)
        for local,ops in writes.items():
            if not own_ref(types.get(local, {})): continue
            valid=True
            for op in ops:
                rv=op.get('detail', {}).get('rvalue', {}); operand=rv.get('detail', {}).get('operand', {}); place=operand.get('detail', {}).get('place', {}); steps=place.get('projection', [])
                self_field=pinned and place.get('local') == 1 and len(steps) == 1 and steps[0].get('kind') == 'Field' and steps[0].get('detail', {}).get('field_index') == 0
                if op.get('kind') != 'Assign' or rv.get('kind') != 'Use' or operand.get('kind') not in ('Copy','Move') or not (self_field or not steps and place.get('local') in roots): valid=False;break
            if valid: roots.add(local)
        if roots == old: break
    return roots


def _scope_members(scope, data):
    phases=data.get('phases', []); actions={a['id']:a for p in phases for g in p.get('goals', []) for a in g.get('actions', [])}
    goals={g['id']:g for p in phases for g in p.get('goals', [])}; selected=[]
    for m in scope.get('members', []):
        if m.get('kind') == 'action' and m.get('ref') in actions: selected.append(actions[m['ref']])
        elif m.get('kind') == 'goal' and m.get('ref') in goals: selected += goals[m['ref']].get('actions', [])
        elif m.get('kind') == 'phase':
            selected += [a for p in phases if p['id'] == m.get('ref') for g in p.get('goals', []) for a in g.get('actions', [])]
    return {int(r[2:]) for a in selected for r in a.get('basicBlockRefs', []) if re.fullmatch(r'bb\d+', r)}


def _place_type(raw, place):
    typ={x['local']:x.get('type', {}) for x in raw.get('locals', [])}.get(place.get('local'), {})
    for step in place.get('projection', []):
        if step.get('kind') == 'Field': typ=step.get('detail', {}).get('field_type', {})
    return typ.get('display', '')


def _safe_drop(display):
    value=(display or '').replace(' ', '')
    if value in {'alloc::string::String','std::string::String','codex_protocol::models::PermissionProfile'}: return True
    if value.startswith(('std::vec::Vec<','alloc::vec::Vec<','std::vec::IntoIter<','alloc::vec::IntoIter<',
                         'std::sync::Arc<','alloc::sync::Arc<','std::rc::Rc<','alloc::rc::Rc<')): return True
    for wrapper in ('std::option::Option<','core::option::Option<','std::result::Result<','core::result::Result<'):
        if value.startswith(wrapper) and value.endswith('>'):
            inner=value[len(wrapper):-1]; parts=[]; depth=start=0
            for i,ch in enumerate(inner):
                depth += ch == '<'; depth -= ch == '>'
                if ch == ',' and depth == 0: parts.append(inner[start:i]); start=i+1
            parts.append(inner[start:])
            return all(_safe_drop(x) or re.fullmatch(r'(?:u|i)(?:8|16|32|64|128|size)|bool|char|\(\)',x) for x in parts)
    return False


def _certificate(data, ref):
    execution=data.get('execution') or {}; artifacts={a['id']:a for a in execution.get('artifacts', [])}
    evidence={e['id']:e for e in execution.get('evidence', [])}; artifact=artifacts.get(ref)
    if artifact is None and ref in evidence: artifact=artifacts.get(evidence[ref].get('artifactRef'))
    if not artifact: return None, None
    content=artifact.get('content', '')
    if hashlib.sha256(content.encode()).hexdigest() != artifact.get('sha256'): return None, None
    try: return json.loads(content), artifact
    except (TypeError, ValueError): return None, None


def _execution_exit_failures(data, scope, cert):
    """Independently validate the displayed terminal-only boundary."""
    execution=data.get('execution') or {}; nodes={n.get('id'):n for n in execution.get('nodes', [])}
    edges=execution.get('edges', []); terminal=scope.get('terminalOnly') or {}
    member_actions={m.get('ref') for m in scope.get('members', []) if m.get('kind') == 'action'}
    phases=data.get('phases', [])
    for m in scope.get('members', []):
        if m.get('kind') == 'goal':
            member_actions.update(a['id'] for p in phases for g in p.get('goals', []) if g.get('id') == m.get('ref') for a in g.get('actions', []))
        elif m.get('kind') == 'phase':
            member_actions.update(a['id'] for p in phases if p.get('id') == m.get('ref') for g in p.get('goals', []) for a in g.get('actions', []))
    member_bbs=set(cert.get('memberBBs', [])); incoming={n:[] for n in nodes}
    for edge in edges: incoming.setdefault(edge.get('to'), []).append(edge)
    def member_node(node): return node.get('kind') == 'action' and node.get('actionRef') in member_actions
    def scope_decision(node, seen=frozenset()):
        refs=node.get('basicBlockRefs', [])
        if node.get('kind') != 'decision' or node.get('id') in seen or not refs or not set(refs) <= member_bbs: return False
        parents=incoming.get(node.get('id'), [])
        return bool(parents) and all(member_node(nodes.get(e.get('from'), {})) or scope_decision(nodes.get(e.get('from'), {}), seen | {node.get('id')}) for e in parents)
    declared=set(terminal.get('exitEdgeRefs', [])); terminals=set(terminal.get('terminalNodeRefs', []))
    exits=[e for e in edges if e.get('readingScopeRef') == scope.get('id') and e.get('kind') == 'loop-exit']
    fail=[]
    terminal_bbs=set(cert.get('terminalBBs', []))
    for ref in terminals:
        node=nodes.get(ref, {})
        if node.get('kind') != 'terminal' or node.get('outcome') not in ('return','error') or not set(node.get('basicBlockRefs', [])) & terminal_bbs:
            fail.append({'code':'terminal-loop-terminal-node','scope':scope.get('id'),'node':ref})
    if declared != {e.get('id') for e in exits}: fail.append({'code':'terminal-loop-exit-coverage','scope':scope.get('id')})
    for edge in exits:
        source=nodes.get(edge.get('from'), {}); target=nodes.get(edge.get('to'), {})
        guard=source.get('kind') == 'decision' and any(g.get('decisionRef') == source.get('decisionRef') for g in edge.get('guards', []))
        source_ok=member_node(source) or scope_decision(source) and guard
        target_ok=edge.get('to') in terminals and target.get('kind') == 'terminal' and target.get('outcome') in ('return','error')
        if not source_ok or not target_ok: fail.append({'code':'terminal-loop-execution-edge','scope':scope.get('id'),'edge':edge.get('id')})
    return fail


def verify_terminal_loop(data, raw, scope):
    """Return failure records; an empty result is a complete independent proof."""
    terminal=scope.get('terminalOnly') or {}; cert,_=_certificate(data, terminal.get('proofRef'))
    fail=[]
    if not cert: return [{'code':'terminal-loop-certificate','scope':scope.get('id'),'reason':'missing or invalid proof artifact'}]
    cited = list(cert.get('memberBBs', [])) + list(cert.get('terminalBBs', []))
    cited += [ref for phase in data.get('phases', []) for goal in phase.get('goals', [])
              for action in goal.get('actions', []) for ref in action.get('basicBlockRefs', [])]
    cited += [ref for node in (data.get('execution') or {}).get('nodes', [])
              for ref in node.get('basicBlockRefs', [])]
    if any(not re.fullmatch(r'bb[0-9]+', ref) for ref in cited):
        return [{'code':'terminal-loop-bb-namespace','scope':scope.get('id')}]
    fail.extend(_execution_exit_failures(data, scope, cert))
    blocks={b['basic_block']:b for b in raw.get('basic_blocks', [])}; members=_scope_members(scope,data)
    def succ(block):
        unwind=block.get('terminator', {}).get('detail', {}).get('unwind', {}); target=unwind.get('detail', {}).get('target') if isinstance(unwind,dict) else None
        return [x for x in block.get('terminator', {}).get('successors', []) if x != target and x in blocks and not blocks[x].get('is_cleanup')]
    def suspension_tail(start):
        seen=set(); todo=[start]; pending=False; leaves=[]
        while todo:
            n=todo.pop()
            if n in seen or n in members: return False
            seen.add(n); block=blocks[n]; term=block.get('terminator', {}); pending |= term.get('kind') == 'Yield'
            for statement in block.get('statements', []):
                d=statement.get('detail', {}); rd=d.get('rvalue', {}).get('detail', {})
                pending |= (d.get('destination') == {'local':0,'projection':[]} and d.get('rvalue', {}).get('kind') == 'Aggregate'
                            and rd.get('aggregate_kind', {}).get('detail', {}).get('variant_index') == 1)
            children=succ(block)
            if children: todo.extend(children)
            else: leaves.append(term.get('kind'))
        return pending and bool(leaves) and all(k in ('Return','Yield') for k in leaves)
    exits=[]; excluded=[]
    for n in sorted(members):
        for target in succ(blocks.get(n, {})):
            if target in members: continue
            if blocks[target].get('terminator', {}).get('kind') == 'Unreachable' and not blocks[target].get('statements'):
                excluded.append({'from':'bb'+str(n),'to':'bb'+str(target),'reason':'unreachable-sink'})
            elif suspension_tail(target): excluded.append({'from':'bb'+str(n),'to':'bb'+str(target),'reason':'suspension'})
            else: exits.append((n,target))
    tail=set(); active=set(); cyclic=False
    def walk(n):
        nonlocal cyclic
        if n in members or n in active: cyclic=True; return
        if n in tail: return
        active.add(n); tail.add(n)
        for child in succ(blocks[n]): walk(child)
        active.remove(n)
    for _,target in exits: walk(target)
    flags=_drop_flags(raw); dead=_dead_locals(raw); roots=_frame_roots(raw); records=[]; terminals=[]
    for n in sorted(tail):
        operations=[]; block=blocks[n]
        for index,statement in enumerate(block.get('statements', [])):
            kind=statement.get('kind'); d=statement.get('detail', {}); reason=None
            if kind in ('StorageLive','StorageDead','Nop'): reason='storage-or-nop'
            elif kind == 'Assign':
                dest=d.get('destination', {}); rv=d.get('rvalue', {}); rd=rv.get('detail', {})
                if _place_key(dest) in flags: reason='proven-drop-flag'
                elif not dest.get('projection') and dest.get('local') in dead:
                    op=rd.get('operand', {}); place=rd.get('place', {})
                    own_place=(not place.get('projection') or place.get('local') in roots and [x.get('kind') for x in place.get('projection', [])] == ['Deref','Downcast','Field'])
                    if rv.get('kind') == 'Use' and op.get('kind') == 'Constant' or rv.get('kind') == 'Discriminant' and own_place:
                        reason='dead-temporary'
                elif dest == {'local':0,'projection':[]}:
                    op=rd.get('operand', {}); place=op.get('detail', {}).get('place', {}); agg=rd.get('aggregate_kind', {}).get('detail', {})
                    if rv.get('kind') == 'Use' and op.get('kind') == 'Constant': reason='constant-return-slot'
                    elif rv.get('kind') == 'Use' and op.get('kind') in ('Copy','Move') and not place.get('projection'): reason='selected-result-return-slot'
                    elif rv.get('kind') == 'Aggregate' and agg.get('variant_index') == 0 and len(rd.get('operands', [])) == 1:
                        selected=rd['operands'][0]; selected_place=selected.get('detail', {}).get('place', {})
                        if selected.get('kind') in ('Copy','Move') and not selected_place.get('projection'): reason='poll-ready-return-slot'
            elif kind == 'SetDiscriminant' and raw.get('is_coroutine') and d.get('place', {}).get('local') in roots and d.get('variant_index') == 1:
                reason='own-coroutine-completed-state'
            operations.append({'index':index,'kind':kind,'reason':reason})
            if reason is None: fail.append({'code':'terminal-loop-operation','scope':scope['id'],'bb':'bb'+str(n),'operation':index,'kind':kind})
        term=block.get('terminator', {}); kind=term.get('kind'); reason=None
        if kind == 'Goto': reason='transport'
        elif kind == 'Return': reason='terminal-return'; terminals.append(n)
        elif kind == 'Drop' and _safe_drop(_place_type(raw,term.get('detail', {}).get('place', {}))): reason='side-effect-free-drop:'+_place_type(raw,term['detail']['place'])
        elif kind == 'SwitchInt':
            place=term.get('detail', {}).get('discriminant', {}).get('detail', {}).get('place', {})
            if _place_key(place) in flags: reason='drop-flag-routing'
        if reason is None: fail.append({'code':'terminal-loop-terminator','scope':scope['id'],'bb':'bb'+str(n),'kind':kind})
        records.append({'bb':n,'operations':operations,'terminator':{'kind':kind,'reason':reason},'normalSuccessors':succ(block)})
    mir=None
    for artifact in (data.get('execution') or {}).get('artifacts', []):
        if artifact.get('format') == 'mir':
            try:
                if json.loads(artifact.get('content','')) == raw and hashlib.sha256(artifact['content'].encode()).hexdigest() == artifact.get('sha256'): mir=artifact
            except (TypeError,ValueError): pass
    expected={'certificateKind':'terminal-loop','version':1,'rawSha256':mir.get('sha256') if mir else None,
              'scopeId':scope.get('id'),'memberBBs':['bb'+str(n) for n in sorted(members)],
              'exitEdges':[{'from':'bb'+str(a),'to':'bb'+str(b)} for a,b in exits],
              'excludedEdges':excluded,'terminalBBs':['bb'+str(n) for n in sorted(terminals)],'blocks':records}
    leaves={n for n in tail if not succ(blocks[n])}
    if cyclic or not terminals or leaves != set(terminals): fail.append({'code':'terminal-loop-tail','scope':scope['id'],'reason':'tail must be acyclic and end only in Return'})
    for key,value in expected.items():
        if cert.get(key) != value: fail.append({'code':'terminal-loop-mismatch','scope':scope['id'],'field':key})
    if scope.get('commonAfter'): fail.append({'code':'terminal-loop-exclusive','scope':scope['id']})
    return fail
