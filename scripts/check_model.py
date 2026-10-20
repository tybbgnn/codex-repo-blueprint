#!/usr/bin/env python3
"""Check the unified element/decision/ownership/message model at S2, S5 and S7."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from ledger_lib import read
from canonical_stages import canonical_selection, derive_group_order


def check(elements, ledger, hierarchy, external=None, endpoints=None, blocks=None, edges=None, raw=None, definitions=None):
    rows=elements['items']; ids=[row['id'] for row in rows]
    if len(ids)!=len(set(ids)):
        raise ValueError('model-duplicate-id: facts/elements')
    by_id={row['id']:row for row in rows}
    for row in rows:
        if row.get('kind') not in ('bb','call','body','switch'):
            raise ValueError('model-unknown-kind: '+row['id'])
        if row['kind'] in ('call','switch') and row.get('bb') not in by_id:
            raise ValueError('model-unknown-bb: '+row['id'])
    selection=canonical_selection(ledger,elements,hierarchy)
    decisions={row['id']:row for row in selection['items']}
    nodes=hierarchy['nodes']
    technical={ref for ref,node in nodes.items() if node['kind']=='bb' and node.get('technical')}
    records={row['bbRef']:row for row in ledger.get('granularity',{}).get('technicalBlocks',[])}
    if len(records)!=len(ledger.get('granularity',{}).get('technicalBlocks',[])):
        raise ValueError('model-duplicate-id: technical BB decision')
    if raw is not None and blocks!={f"bb{b['basic_block']}":b for b in raw['basic_blocks']}:
        raise ValueError('model-bb-coverage: facts differ from raw MIR')
    if blocks is not None:
        from classify import fingerprint
        factual={row['id']:row for row in rows if row['kind']=='bb'}
        if set(factual)!=set(blocks):raise ValueError('model-bb-coverage: elements differ from MIR BBs')
        for ref,block in blocks.items():
            operations=[dict(statementIndex=op.get('statement_index',index),kind=op['kind']) for index,op in enumerate(block.get('statements',[])) if op['kind'] not in ('StorageLive','StorageDead')]
            expected=dict(factSha256=fingerprint(block),operations=operations,terminator=dict(kind=block['terminator']['kind'],successors=block['terminator']['successors']))
            if factual[ref].get('proofs',{}).get('mirWitness')!=expected:
                raise ValueError('model-mir-witness: '+ref)
            if raw is not None:
                optional={}
                if block.get('is_cleanup'):optional['cleanup']=dict(isCleanup=True)
                if block['terminator']['kind'] in ('UnwindResume','UnwindTerminate'):
                    optional['unwind']=dict(terminatorKind=block['terminator']['kind'])
                if ref=='bb0' and raw.get('is_coroutine') and block['terminator']['kind']=='SwitchInt':
                    optional['stateDispatch']=dict(terminatorKind='SwitchInt',isCoroutine=True)
                if block['terminator']['kind'] in ('Drop','Goto','SwitchInt'):
                    from technical_boundary import apply_review
                    witness=dict(bbRef=ref,category='drop',reason='Validate structural drop candidate',evidenceRefs=[ref],
                        factSha256=expected['factSha256'],operationProofs=[dict(op,reason='Validate actual operation') for op in operations],
                        terminatorProof=expected['terminator'])
                    try:apply_review({ref:block},{},{},[witness],raw)
                    except ValueError:pass
                    else:optional['drop']=dict(operations=operations,terminatorKind=block['terminator']['kind'])
                for key in ('cleanup','unwind','stateDispatch','drop'):
                    if factual[ref].get('proofs',{}).get(key)!=optional.get(key):
                        raise ValueError('model-structural-proof: '+ref+' '+key)

    # Instrumentation is carried by S1 proofs; other explicit proof records are independently checked by ownership/P14.
    proven={row['id'] for row in rows if row['kind']=='bb' and row.get('proofs',{}).get('instrumentation')}
    if proven-technical:
        raise ValueError('model-log-business: '+','.join(sorted(proven-technical)))
    for key,decision in decisions.items():
        row=by_id[key];refs={row['bb']} if row['kind']=='call' else set(row['bbRefs'])
        disposition=decision['disposition']
        interval=by_id.get(row.get('bb'),{}).get('proofs',{}).get('technicalIntervals',{})
        interval_call=bool(row['kind']=='call' and interval.get('terminator'))
        if interval_call and disposition!='technical':
            raise ValueError('model-call-interval: '+key)
        if disposition=='technical' and not interval_call and (not refs or not refs<=technical):
            raise ValueError('model-technical-proof: '+key)
        if disposition=='technical' and not interval_call and any(ref not in proven and ref not in records for ref in refs):
            raise ValueError('model-technical-proof: '+key)
        if row['kind']=='call' and row['bb'] in technical and disposition!='technical':
            raise ValueError('model-bb-destination: '+key)
        if row['kind']=='body' and refs and refs<=technical and disposition!='technical':
            raise ValueError('model-body-destination: '+key)
        if row['kind']=='body' and decision.get('semanticRole')=='business' and disposition!='shown':
            raise ValueError('model-local-business: '+key)
    if blocks is not None and edges is not None:
        expected=deepcopy(nodes);derive_group_order(expected,edges,blocks)
        for key,node in nodes.items():
            if node['kind']=='action' and node.get('group_order_basis')!=expected[key]['group_order_basis']:
                raise ValueError('model-group-order: '+key)
    switches={row['bb'] for row in rows if row['kind']=='switch'}
    inventory=ledger.get('granularity',{}).get('decisions',[])
    inventory_ids=[row['id'] for row in inventory]
    if len(inventory_ids)!=len(set(inventory_ids)):raise ValueError('model-duplicate-id: decision inventory')
    counts=Counter(ref for row in inventory for ref in set(row.get('evidenceRefs',[])) if ref in switches)
    if any(count>1 for count in counts.values()):raise ValueError('model-duplicate-id: SwitchInt decision')
    covered=set(counts)
    if covered!=switches:
        raise ValueError('model-switch-inventory: '+','.join(sorted(switches-covered)))
    if external is not None:
        if 'innerBodies' in external:
            raise ValueError('model-redundant-field: innerBodies')
        actor_ids=set()
        def actors(rows):
            for actor in rows:
                actor_ids.add(actor['actorId']);actors(actor.get('children',[]))
        actors(external.get('actors',[]))
        for key,decision in decisions.items():
            if decision['disposition']=='folded' and decision.get('actorRef') in actor_ids:
                raise ValueError('model-folded-actor: '+key)
        messages=defaultdict(list)
        annotations={member['invocationRef']:member for member in external.get('business_members',[])}
        for message in external['messages']:
            key=message.get('bindingRef')
            if key not in decisions or by_id[key]['kind']!='call':
                raise ValueError('model-unknown-id: message '+str(key))
            body_ref=annotations.get(message.get('invocationRef'),{}).get('bodyElementRef')
            body=by_id.get(body_ref,{})
            body_invocation=(body.get('kind')=='body' and decisions.get(body_ref,{}).get('disposition')=='shown' and key in body.get('callRefs',[]))
            if decisions[key]['disposition']!='shown' and not body_invocation:
                raise ValueError('model-message-destination: '+key)
            if body_ref and not body_invocation:
                raise ValueError('model-body-message: '+str(body_ref))
            messages[key].append(message)
        for key,row in by_id.items():
            if row['kind']!='call' or (decisions[key]['disposition']!='shown' and not messages[key]):continue
            pair=messages[key]
            annotation=annotations.get(pair[0].get('invocationRef'),{}) if pair else {}
            if annotation.get('internalOperation'):
                if (len(pair)!=1 or pair[0]['kind']!='self' or pair[0].get('pair') is not None
                    or pair[0]['fromActorId']!=pair[0]['toActorId']):
                    raise ValueError('model-internal-message: '+key)
                continue
            if len(pair)!=2 or Counter(m['kind'] for m in pair)!=Counter(request=1,**{'return':1}):
                raise ValueError('model-shown-message: '+key)
            a,b=pair
            if not a.get('pair') or a['pair']!=b.get('pair') or a.get('invocationRef')!=b.get('invocationRef') or a.get('internalOperation')!=b.get('internalOperation') or a.get('bodyElementRef')!=b.get('bodyElementRef') or (a['fromActorId'],a['toActorId'])!=(b['toActorId'],b['fromActorId']):
                raise ValueError('model-message-pair: '+key)
        endpoint_rows=(endpoints or {}).get('endpoints',[])
        endpoint_actors={row['canonical_path']:row['actorRef'] for row in endpoint_rows}
        if 'business_members' in external:
            endpoints_by_actor={row['actorRef']:row for row in endpoint_rows}
            bodies_by_path={row.get('canonical_path'):row for row in rows if row['kind']=='body' and row.get('canonical_path')}
            members=external['business_members']; member_ids=[member['id'] for member in members]
            if len(member_ids)!=len(set(member_ids)):raise ValueError('model-duplicate-id: business member')
            covered=Counter(); owner_by_invocation={}
            for member in members:
                if 'lifecycle' in member or 'canonical_key' in member:
                    raise ValueError('model-redundant-field: copied lifecycle/member key')
                key=member.get('bindingRef');invocation=member.get('invocationRef')
                if key not in decisions or not messages[key]:
                    raise ValueError('model-member-binding: '+str(key))
                covered[key]+=1; pair=messages[key]
                request=pair[0] if member.get('internalOperation') else next(m for m in pair if m['kind']=='request')
                if request.get('invocationRef')!=invocation or request['toActorId']!=member.get('targetActorRef'):
                    raise ValueError('model-member-invocation: '+key)
                owner=decisions[key].get('ownerActionRef')
                if 'ownerActionRef' in member and member['ownerActionRef']!=owner:
                    raise ValueError('model-owner-mismatch: member '+key)
                owner_by_invocation[invocation]=owner
                endpoint=endpoints_by_actor.get(member['targetActorRef'])
                if not endpoint:raise ValueError('model-member-endpoint: '+key)
                if member.get('internalOperation'):
                    owner=(definitions or {}).get(elements.get('ownerDefPathHash'),{})
                    if (by_id[key].get('targetCategory') not in ('std','third_party') or request['fromActorId']!=request['toActorId']
                        or by_id[key]['callee'].get('def_path_hash') in (definitions or {})
                        or endpoint['canonical_path']!=owner.get('identity',{}).get('canonical_path')):
                        raise ValueError('model-internal-operation: '+key)
                    continue
                body=bodies_by_path.get(endpoint['canonical_path'])
                if body is not None:
                    if decisions[body['id']]['disposition']!='shown' or key not in body['callRefs']:
                        raise ValueError('model-member-endpoint: '+key)
                else:
                    callee=by_id[key].get('resolvedCallee',by_id[key]['callee'])
                    definition=(definitions or {}).get(callee.get('def_path_hash'),{})
                    canonical=definition.get('identity',{}).get('canonical_path') or callee.get('canonical_path')
                    if canonical!=endpoint['canonical_path']:raise ValueError('model-member-endpoint: '+key)
            expected_members={key for key,row in by_id.items() if row['kind']=='call' and (decisions[key]['disposition']=='shown' or messages[key])}
            if set(covered)!=expected_members or any(count!=1 for count in covered.values()):
                raise ValueError('model-member-coverage: shown calls require one business member each')
            for clause in external.get('clauses',[]):
                owner=owner_by_invocation.get(clause.get('invocationRef'))
                if 'ownerActionRef' in clause and clause['ownerActionRef']!=owner:
                    raise ValueError('model-owner-mismatch: clause '+clause['id'])

        for key,row in by_id.items():
            if row['kind']!='body' or decisions[key]['disposition']!='shown':continue
            actor=endpoint_actors.get(row.get('canonical_path'))
            linked=[message for ref in row['callRefs'] for message in messages[ref]]
            if not actor or not any(actor in (message['fromActorId'],message['toActorId']) for message in linked):
                raise ValueError('model-body-endpoint: '+key)
    return {'passed':True,'calls':sum(row['kind']=='call' for row in rows),'bodies':sum(row['kind']=='body' for row in rows),
            'unaccountedCalls':0,'ownerContradictions':0,'destinations':dict(Counter(row['disposition'] for row in decisions.values()))}


def check_context(c,stage,ledger=None,hierarchy=None):
    ledger=ledger or c.ledger(2)
    hierarchy=hierarchy or c.load('stage2/hierarchy.json')
    external=c.ledger(5) if stage==5 else c.load('stage5/external.json') if stage>=7 else None
    endpoints=read(c.inputs/'ledgers/endpoint-ledger.json') if external is not None else None
    elements=c.load('facts/elements.json')
    raw=c.load('raw-body.json')
    from stage_engine import read_callee_slice,prove_returned_coroutine,prove_caller_future_flow
    pins=c.load('input-pins.json');by_id={row['id']:row for row in elements['items']}
    for row in elements['items']:
        binding=row.get('proofs',{}).get('erasedFuture') if row['kind']=='call' else None
        if binding is None:continue
        pin=binding['constructorMirPin']
        if pin['def_path_hash']!=row['callee'].get('def_path_hash'):raise ValueError('model-callee-pin: caller identity mismatch')
        constructor=read_callee_slice(pin,pins)
        if prove_returned_coroutine(constructor)!=binding['returned'] or prove_caller_future_flow(raw,row)!=binding['callerFlow']:
            raise ValueError('model-erased-future: returned value/consumer proof mismatch')
        body=by_id.get('body:'+binding['returned']['coroutineDefPathHash'],{})
        if (row['id'] not in body.get('erasedFutureBindings',[]) or not set(binding['callerFlow']['callRefs'])<=set(body.get('callRefs',[]))
                or not set(binding['callerFlow']['bbRefs'])<=set(body.get('bbRefs',[]))):
            raise ValueError('model-erased-future: body element missing exact caller links')
    rule=InformationRule(pins)
    effects=rule.decisions(raw,elements)
    for row in elements['items']:
        if row['kind']!='call':continue
        original=row['callee'].get('def_path_hash');actual=rule.access.resolve(original,fname(row['func'])) if original else original
        expected=None
        if actual!=original and effects[row['id']]['new']=='shown':
            definition=rule.access.definition(actual)
            expected=dict(def_path_hash=actual,canonical_path=definition['identity']['canonical_path'])
        if row.get('resolvedCallee')!=expected:raise ValueError('model-trait-target: '+row['id'])
    for row in elements['items']:
        if row['id'] in effects and row.get('proofs',{}).get('informationEffect')!={key:value for key,value in effects[row['id']].items() if key!='new'}:
            raise ValueError('model-information-proof: '+row['id'])
    proof=c.load('facts/instrumentation-candidates.json') or {}
    expected=set(proof.get('technical_blocks',{}))-set(proof.get('conflicts',[]))
    for row in elements['items']:
        if row['kind']!='bb':continue
        ref=row['id']
        witness=dict(factSha256=proof['technical_blocks'][ref],blockRole=proof.get('block_roles',{}).get(ref),
                     eventMacroProof=proof.get('block_proofs',{}).get(ref)) if ref in expected else None
        if row.get('proofs',{}).get('instrumentation')!=witness:
            raise ValueError('model-instrumentation-proof: '+ref)
    if stage>=5:
        from canonical_stages import prepare_instrumentation_ledger
        ledger,_=prepare_instrumentation_ledger(ledger,c.load('facts/instrumentation-candidates.json'),elements)
        if ledger['granularity']['technicalBlocks']!=c.load('stage2/granularity.json')['technicalBlocks']:
            raise ValueError('model-technical-witnesses: S2 differs from derived MIR/proof records')
    if stage>=5:
        if c.load('stage2/selection.json')!=canonical_selection(ledger,elements,hierarchy):
            raise ValueError('model-selection-drift: S2 selection differs from decisions/hierarchy')
        expected=[row['proofs']['technicalIntervals'] for row in elements['items'] if row['kind']=='bb' and row.get('proofs',{}).get('technicalIntervals')]
        if c.load('stage2/granularity.json').get('technicalIntervals')!=expected:
            raise ValueError('model-technical-intervals: S2 differs from elements')
    result=check(elements,ledger,hierarchy,external,endpoints,c.load('facts/blocks.json'),c.load('facts/edges.json'),raw,c.load('facts/definitions-index.json'))
    c.save(f'stage{stage}/model-check.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--stage',type=int,choices=(2,5,7),required=True)
    args=parser.parse_args()
    from ledger_lib import Context
    print(check_context(Context(args.inputs,args.out),args.stage))


# Information-preservation rule: semantic table and MIR data-flow machinery.
import re, collections
def fname(func):
    try: d=func['detail']['constant']['type']['display']
    except Exception: return '?'
    if not d.endswith('}'): return d
    depth=0
    for i in range(len(d)-1,-1,-1):
        if d[i]=='}': depth+=1
        elif d[i]=='{':
            depth-=1
            if depth==0: return d[i+1:-1]
    return d
def fhash(func):
    try: return func['detail']['constant']['type']['def_path_hash']
    except Exception: return None
TRANSPARENT=re.compile(r'(as [\w:]*Clone>::clone$|as [\w:]*Deref>::deref$|as [\w:]*DerefMut>::deref_mut$|as [\w:]*Into<.*>>::into$|as [\w:]*From<.*>>::from$|as [\w:]*AsRef<.*>>::as_ref$|as [\w:]*AsMut<.*>>::as_mut$|as [\w:]*Borrow<.*>>::borrow$|as [\w:]*ToOwned>::to_owned$|^std::option::Option::<.*>::(as_ref|as_mut|as_deref|as_deref_mut)$|^std::result::Result::<.*>::(as_ref|as_mut|as_deref)$|as [\w:]*IntoFuture>::into_future$|^std::pin::Pin::<.*>::new_unchecked$|as [\w:]*Future>::poll$|as [\w:]*Try>::branch$|as [\w:]*FromResidual<.*>>::from_residual$|get_context$|as [\w:]*ToString>::to_string$|^std::sync::Arc::<.*>::clone$|as [\w:]*IntoIterator>::into_iter$|as tracing::Instrument>::instrument$|as tracing::instrument::Instrument>::instrument$)')
MACHINERY=re.compile(r'(Future>::poll$|Try>::branch$)')
STDPFX=('std::','core::','alloc::')
def is_project_type(t,owner_suffix):
    """t: type json. Project = workspace ADT (codex_* path, or same crate as owner), not coroutine/closure."""
    if not isinstance(t,dict): return False
    if t.get('kind') in ('Coroutine','Closure','CoroutineClosure','CoroutineWitness'): return False
    disp=t.get('display') or ''; h=t.get('def_path_hash') or ''
    if t.get('kind')=='Adt':
        if disp.startswith('codex_') or (h.endswith(owner_suffix)): return True
    return False
def type_mentions_project(t,owner_suffix,depth=0):
    if not isinstance(t,dict) or depth>6: return False
    if is_project_type(t,owner_suffix): return True
    if t.get('kind') in ('Coroutine','Closure','CoroutineClosure'): return False
    det=t.get('detail') or {}
    for k in ('pointee',):
        if isinstance(det.get(k),dict) and type_mentions_project(det[k],owner_suffix,depth+1): return True
    for g in t.get('generic_args') or []:
        if g.get('kind')=='Type' and type_mentions_project(g.get('type'),owner_suffix,depth+1): return True
    return False
GUARD=re.compile(r'(MutexGuard|RwLockWriteGuard|RefMut|OwnedMutexGuard|MappedMutexGuard|OwnedRwLockWriteGuard)<')
INTERIOR_W=re.compile(r'(Atomic\w+::(store|swap|fetch_\w+|compare_exchange\w*)$|RefCell::<.*>::borrow_mut$|::send_replace$|::send_modify$|::send_if_modified$)')

class InformationBody:
    def __init__(s,raw,owner_suffix,rule):
        s.rule=rule
        s.r=raw; s.sfx=owner_suffix; s.bbs=raw['basic_blocks']; s.loc=raw['locals']
        s.argc=raw.get('arg_count',0)
        s.defs=collections.defaultdict(list)   # key -> list of (loc, kind, info)
        s.uses=collections.defaultdict(list)   # key -> list of (loc, kind, dest_key, info)
        s.calls={}  # bbidx -> terminator
        s.switches=[]  # (bb, discr key, span)
        s.discr_of={}  # key(temp) -> key of place discriminated
        s.machinery_dest=set()
        for b in s.bbs:
            i=b['basic_block']
            for j,st in enumerate(b['statements']):
                if st['kind']!='Assign': continue
                dst=st['detail']['destination']; rv=st['detail']['rvalue']; dk=s.key(dst)
                srcs=s.rv_places(rv)
                s.defs[dk].append(((i,j),rv['kind'],rv))
                if rv['kind']=='Discriminant': s.discr_of[dk]=s.key(rv['detail']['place'])
                if rv['kind']=='Aggregate': continue
                if any(p.get('kind')=='Deref' for p in dst.get('projection',[])) and dk[0]=='l': continue
                for sp in srcs: s.uses[s.key(sp)].append(((i,j),rv['kind'],dk,rv))
            t=b['terminator']
            if t['kind']=='Call':
                s.calls[i]=t
                dk=s.key(t['detail']['destination']); nm=fname(t['detail']['func'])
                s.defs[dk].append(((i,'T'),'Call',t))
                if MACHINERY.search(nm): s.machinery_dest.add(dk)
                for ai,a in enumerate(t['detail'].get('args',[])):
                    p=s.op_place(a)
                    if p is not None: s.uses[s.key(p)].append(((i,'T'),'CallArg' if ai==0 else 'CallArgN',dk,t))
            elif t['kind']=='SwitchInt':
                p=s.op_place(t['detail']['discriminant'])
                if p is not None: s.switches.append((i,s.key(p),t['source_info']['span']))
            elif t['kind']=='Assert':
                msg=t['detail']['message']['kind']
                if msg not in ('Overflow','OverflowNeg','BoundsCheck','DivisionByZero','RemainderByZero','ResumedAfterReturn','ResumedAfterPanic','MisalignedPointerDereference','NullPointerDereference','ResumedAfterDrop'):
                    p=s.op_place(t['detail']['condition'])
                    if p is not None: s.switches.append((i,s.key(p),t['source_info']['span']))
        s.flags=s.drop_flags()
    def key(s,place):
        proj=place.get('projection',[])
        for idx,p in enumerate(proj):
            if p.get('kind')=='Field' and (p['detail'].get('owner_type') or {}).get('kind')=='Coroutine':
                v=None
                if idx>0 and proj[idx-1].get('kind')=='Downcast': v=proj[idx-1]['detail'].get('variant_index')
                return ('co',v,p['detail']['field_index'])
        return ('l',place['local'])
    def op_place(s,op):
        if op.get('kind') in ('Copy','Move'): return op['detail']['place']
        return None
    def rv_places(s,rv):
        k=rv['kind']; d=rv['detail']; out=[]
        if k in ('Use','Cast','UnaryOp','ShallowInitBox','Repeat'):
            p=s.op_place(d['operand']); out+= [p] if p else []
        elif k in ('Ref','RawPtr','AddressOf','Discriminant','Len','CopyForDeref'):
            out.append(d['place'])
        elif k in ('BinaryOp','CheckedBinaryOp'):
            for o in (d['left'],d['right']):
                p=s.op_place(o); out+= [p] if p else []
        elif k=='Aggregate':
            for o in d.get('operands',[]):
                p=s.op_place(o); out+= [p] if p else []
        return out
    def drop_flags(s):
        fl=set()
        for k,ds in s.defs.items():
            if ds and all(kind=='Use' and rv['detail']['operand'].get('kind')=='Constant' for _,kind,rv in ds): fl.add(k)
        return fl
    def switch_is_machinery(s,dk):
        src=s.discr_of.get(dk,dk)
        if src in s.machinery_dest: return 'await/?'
        if src[0]=='l':
            t=s.ltype(src)
            if t and (t.get('kind')=='Coroutine' or (t.get('kind')=='Ref' and ((t.get('detail') or {}).get('pointee') or {}).get('kind')=='Coroutine') or '{async' in (t.get('display') or '')[:40]): return 'coroutine-state'
        # coroutine state: discriminant of (*_k) where _k = copy (_1.0)
        for _,kind,rv in s.defs.get(src,[]):
            pass
        if dk in s.flags or src in s.flags: return 'drop-flag'
        return None
    def ltype(s,k):
        if k[0]=='l' and k[1]<len(s.loc): return s.loc[k[1]]['type']
        return None
    # ----- criterion 1: forward data flow from key to a branch -----
    def reaches_branch(s,start,limit=4000):
        prev={start:None}; work=[start]; n=0
        sw=collections.defaultdict(list)
        for bb,k,span in s.switches: sw[k].append((bb,span))
        exp_hit=None
        while work and n<limit:
            k=work.pop(); n+=1
            for bb,span in sw.get(k,[]):
                mach=s.switch_is_machinery(k)
                if mach: continue
                ev=s.chain(prev,k)+[f'SwitchInt@bb{bb} L{span.get("start_line")}']
                if thirdparty_macro(span):
                    exp_hit=exp_hit or ev; continue
                return ('fire',ev)
            for loc,kind,dk,info in s.uses.get(k,[]):
                if kind in ('CallArg','CallArgN'):
                    nm=fname(info['detail']['func'])
                    if TRANSPARENT.search(nm):
                        if kind=='CallArgN': continue
                    elif s.rule.is_project_fn(nm,fhash(info['detail']['func'])): continue
                    step=(dk,f'bb{loc[0]} {short(nm)}->{fmt(dk)}')
                else:
                    if kind=='Discriminant':
                        # discriminant of machinery dest: only the switch is machinery; payload flows via field reads (Use)
                        pass
                    step=(dk,f'bb{loc[0]}[{loc[1]}] {kind}->{fmt(dk)}')
                if dk not in prev:
                    prev[dk]=(k,step[1]); work.append(dk)
        if exp_hit: return ('expansion-only',exp_hit)
        return (None,None)
    def chain(s,prev,k):
        out=[]
        while prev.get(k):
            pk,desc=prev[k]; out.append(desc); k=pk
        out.append(f'src {fmt(k)}')
        return list(reversed(out))[-8:]
    # ----- criterion 2: &mut into project state -----
    def place_is_state(s,place,depth=0):
        proj=place.get('projection',[]); seen_deref=False
        for p in proj:
            if p['kind']=='Deref': seen_deref=True
            if p['kind']=='Field' and seen_deref and is_project_type(p['detail'].get('owner_type'),s.sfx):
                return f"&mut field .{p['detail']['field_index']} of {p['detail']['owner_type']['display'][:60]}"
        if seen_deref and proj and proj[0]['kind']=='Deref':
            k=s.key(place); t=s.ltype(k)
            if t and t.get('kind')=='Ref' and (t.get('detail') or {}).get('mutability')=='Mut' and is_project_type(t['detail'].get('pointee'),s.sfx):
                if s.ptr_from_state(k,depth): return f"&mut *{fmt(k)}: {t['display'][:60]}"
        if proj and proj[0]['kind']=='Deref' and depth<4 and place.get('local') is not None:
            r=s.mut_arg_state({'local':place['local'],'projection':[]},depth+1)
            if r and 'guard' in r: return 'through '+r
        if not proj or all(p['kind']!='Deref' for p in proj):
            t=s.ltype(s.key(place)) if not proj else None
            if t and GUARD.search(t.get('display','')):  # v2: any lock guard = shared state
                return f"&mut guard {t['display'][:70]}"
        return None
    def ptr_from_state(s,k,depth=0):
        """k holds &mut Project: true if it points into shared state (param, deref of state, guard deref_mut)."""
        if depth>6: return False
        if k[0]=='l' and 1<=k[1]<=s.argc: return True
        if k[0]=='co': return True
        for loc,kind,info in s.defs.get(k,[]):
            if kind=='Ref' and info['detail'].get('borrow_kind') not in ('Shared',):
                pl=info['detail']['place']
                if any(p['kind']=='Deref' for p in pl.get('projection',[])): return True
                t=s.ltype(s.key(pl))
                if t and GUARD.search(t.get('display','')): return True
            elif kind=='Use':
                p=s.op_place(info['detail']['operand'])
                if p and s.ptr_from_state(s.key(p),depth+1): return True
            elif kind=='Call':
                nm=fname(info['detail']['func'])
                if TRANSPARENT.search(nm):
                    for a in info['detail'].get('args',[]):
                        p=s.op_place(a)
                        if p and (s.ptr_from_state(s.key(p),depth+1) or s.mut_arg_state(p,depth+1)): return True
                else: return True   # returned &mut Project from a call: points into callee-owned state
        return False
    def mut_arg_state(s,place,depth=0):
        k=s.key(place)
        for loc,kind,info in s.defs.get(k,[]):
            if kind=='Ref' and info['detail'].get('borrow_kind') not in ('Shared','Fake','Shallow'):
                r=s.place_is_state(info['detail']['place'],depth)
                if r: return f'bb{loc[0]} {r}'
            elif kind=='Use' and depth<4:
                p=s.op_place(info['detail']['operand'])
                if p:
                    r=s.mut_arg_state(p,depth+1)
                    if r: return r
            elif kind=='Call' and depth<4 and TRANSPARENT.search(fname(info['detail']['func'])):
                for a in info['detail'].get('args',[]):
                    p=s.op_place(a)
                    if p:
                        r=s.mut_arg_state(p,depth+1)
                        if r: return f'via {short(fname(info["detail"]["func"]))}: '+r
        t=s.ltype(k)
        if t and t.get('kind')=='Ref' and (t.get('detail') or {}).get('mutability')=='Mut' and is_project_type(t['detail'].get('pointee'),s.sfx) and s.ptr_from_state(k,depth):
            return f'arg {fmt(k)}: {t["display"][:60]}'
        return None
    def call_writes(s,t):
        nm=fname(t['detail']['func'])
        if TRANSPARENT.search(nm) or 'drop_in_place' in nm: return None
        if INTERIOR_W.search(nm): return f'interior write {short(nm)}'
        for a in t['detail'].get('args',[]):
            p=s.op_place(a)
            if p:
                r=s.mut_arg_state(p)
                if r: return r
        return None
    def body_writes(s):
        for i,t in s.calls.items():
            r=s.call_writes(t)
            if r: return f'bb{i} {short(fname(t["detail"]["func"]))}: {r}'
        for b in s.bbs:
            for j,st in enumerate(b['statements']):
                if st['kind']=='Assign':
                    r=s.place_is_state(st['detail']['destination'])
                    if r and 'guard' not in r: return f'bb{b["basic_block"]}[{j}] assign {r}'
        return None
    def struct_field_read(s,place):
        proj=place.get('projection',[])
        for i,p in enumerate(proj):
            if p['kind']=='Field' and not (i>0 and proj[i-1]['kind']=='Downcast') and is_project_type(p['detail'].get('owner_type'),s.sfx):
                return True
        return False
    def origin(s,k,depth=0,seen=None):
        """classify where a value comes from: 'input' (fn args / captured upvars, via projections),
        'selector' (type-id/downcast/eq library check on inputs), 'const', or 'domain'."""
        seen=seen if seen is not None else set()
        if k in seen or depth>40: return 'input'
        seen.add(k)
        if k[0]=='l' and 1<=k[1]<=s.argc: return 'input'
        if k[0]=='co' and k[1] is None: return 'input'
        ds=s.defs.get(k,[])
        if not ds: return 'input'
        res='const'
        for loc,kind,info in ds:
            if kind=='Call':
                nm=fname(info['detail']['func'])
                if s.rule.is_project_fn(nm,fhash(info['detail']['func'])) and not TRANSPARENT.search(nm): return 'domain'
                if TRANSPARENT.search(nm) or SELECTOR_LIB.search(nm):
                    for a in info['detail'].get('args',[]):
                        p=s.op_place(a)
                        if p:
                            o=s.origin(s.key(p),depth+1,seen)
                            if o=='domain': return 'domain'
                    res='input'
                else: return 'domain'
            elif kind=='Aggregate': res='input' if res=='const' else res
            else:
                if kind=='Use' and info['detail']['operand'].get('kind')=='Constant': continue
                for p in s.rv_places(info):
                    o=s.origin(s.key(p),depth+1,seen)
                    if o=='domain': return 'domain'
                res='input'
        return res
    def domain_switch(s):
        exp=None
        for bb,k,span in s.switches:
            if s.switch_is_machinery(k): continue
            src=s.discr_of.get(k,k)
            if s.origin(src)!='domain': s.selector_only=getattr(s,'selector_only',0)+1; continue
            if thirdparty_macro(span):
                exp=exp or f'bb{bb} L{span.get("start_line")} (macro)'; continue
            return f'SwitchInt@bb{bb} {span.get("file","")}:{span.get("start_line")}',exp
        return None,exp

SELECTOR_LIB=re.compile(r'(type_id|TypeId|downcast|::is::<|Any>::|::eq$|PartialEq)')
def thirdparty_macro(span):
    f=span.get('file') or ''
    return bool(span.get('from_expansion')) and (f.startswith('../') or '.cargo/' in f or '/rustlib/' in f or f.startswith('/rustc/'))
def fmt(k): return f'_{k[1]}' if k[0]=='l' else f'co[v{k[1]}].{k[2]}'
def short(n): return re.sub(r'<[^<>]*(?:<[^<>]*(?:<[^<>]*>[^<>]*)*>[^<>]*)*>','<…>',n)[-90:]



# ---- library operation table (semantics of std/third-party ops; applies to every caller alike) ----
INFRA=re.compile(r'(^tracing::|^<tracing|tracing::|::log::|^log::|metrics|otel|Instrument|::poll$|into_future|Pin::<.*>::new_unchecked|get_context|maybe_done|or_cancel|drop_in_place|::drop$|Drop>::drop|^std::mem::drop|CancellationToken::(child_token|clone)|::lock$|PoisonError|into_inner|Mutex::<.*>::(lock|new)|RwLock::<.*>::(read|write|new)|::enter$|Span::|Waker|Context::)')
TRANSP=re.compile(r'(Clone>::clone$|Deref>::deref$|DerefMut>::deref_mut$|Into<.*>>::into$|From<.*>>::from$|AsRef<.*>>::as_ref$|AsMut<.*>>::as_mut$|Borrow<.*>>::borrow|ToOwned>::to_owned$|::as_(ref|mut|deref|deref_mut|str|slice|bytes|path)$|ToString>::to_string$|^std::fmt::|^core::fmt::|::fmt$|Arguments|format|Display|Try>::branch$|FromResidual<.*>>::from_residual$|IntoIterator>::into_iter$|::(iter|iter_mut|into_iter|map|map_err|cloned|copied|flatten|chain|enumerate|zip|rev|collect|extend|push|push_str|append|insert|sort|sort_by|sort_by_key|sort_unstable\w*|join|concat|new|with_capacity|default|downgrade|upgrade|unwrap|expect|ok_or|ok_or_else|unwrap_or_else|unwrap_or_default|unwrap_or|to_vec|into_boxed\w*|pin|spawn|into_values|into_keys|keys|values|entry|or_insert\w*|and_modify|then|then_some)(::<.*>)?$|Default>::default$|Arc::<.*>::(new|clone)|Box::<.*>::(new|pin)|Iterator>::(map|cloned|copied|chain|zip|enumerate|collect|flatten|rev)(::<.*>)?$|Extend<.*>>::extend|FromIterator|serde_json::(to_string|to_value|json)|Value)')
DROPS=re.compile(r'::(filter|filter_map|find|find_map|retain|dedup|dedup_by\w*|take|skip|first|last|get|get_mut|nth|position|truncate|pop|remove|split_off|min|max|min_by\w*|max_by\w*|ok|err|and_then|take_while|skip_while|split_first|split_last|strip_prefix|strip_suffix|trim\w*|swap_remove|drain)(::<.*>)?$')
COMPUTES=re.compile(r'::(len|count|sum|product|checked_\w+|saturating_\w+|wrapping_\w+|abs|pow|hash|now|elapsed|duration_since|as_secs\w*|as_millis|from_str|parse|from_slice|from_value|encode|decode|round|ceil|floor|to_lowercase|to_uppercase|split|lines|chars|bytes|replace|div_ceil)(::<.*>)?$|serde_json::from_str|Iterator>::(count|sum|fold|max|min)')
PRED=re.compile(r'(::is_\w+|::eq$|::ne$|::lt$|::le$|::gt$|::ge$|::cmp$|::partial_cmp$|::contains\w*|::starts_with|::ends_with|::any|::all|::matches|::has_\w+|PartialEq|PartialOrd)(::<.*>)?$')
FMT=re.compile(r'(^std::fmt::|^core::fmt::|fmt::Arguments|fmt::rt::|::fmt$|Display>::|Debug>::|^std::hint::must_use|Iterator>::next$|::next$|^std::slice::from_ref|poll_fn|ArcSwap\w*::<.*>::load\w*$|Guard<.*>::|watch::Ref)')
def lib_kind(nm):
    if INFRA.search(nm): return 'infrastructure'
    if FMT.search(nm): return 'transparent'
    if PRED.search(nm): return 'predicate'
    if DROPS.search(nm): return 'DROPS'
    if COMPUTES.search(nm): return 'COMPUTES'
    if TRANSP.search(nm): return 'transparent'
    return 'UNCLASSIFIED'

OPTION_H="a0b8cae325ff330d2bac9d628bdc1eb8"
POLL_H='28aabbb50e2876b92bac9d628bdc1eb8'
def ret_keys(B):
    ks={('l',0)}
    for b in B.bbs:
        for st in b['statements']:
            if st['kind']=='Assign' and st['detail']['rvalue']['kind']=='Aggregate' and B.key(st['detail']['destination'])==('l',0):
                ak=st['detail']['rvalue']['detail']['aggregate_kind']; d=ak.get('detail') or {}
                if (d.get('definition') or {}).get('def_path_hash')==POLL_H:
                    for p in B.rv_places(st['detail']['rvalue']): ks.add(B.key(p))
    return ks
def flows_to_return(B,k,rk):
    seen={k}; work=[k]
    while work:
        x=work.pop()
        if x in rk: return True
        for loc,kind,dk,info in B.uses.get(x,[]):
            if kind=='Use' and dk not in seen: seen.add(dk); work.append(dk)
    return False
def returns_none(B):
    """DROPS: Option::None (or a scalar/str literal, i.e. an output not constructed from the input) is itself the return value."""
    rk=ret_keys(B)
    for b in B.bbs:
        for j,st in enumerate(b['statements']):
            if st['kind']!='Assign': continue
            rv=st['detail']['rvalue']; dk=B.key(st['detail']['destination'])
            if rv['kind']=='Aggregate':
                ak=rv['detail']['aggregate_kind']; d=ak.get('detail') or {}
                if ak['kind']=='Adt' and (d.get('definition') or {}).get('def_path_hash')==OPTION_H and d.get('variant_index')==0 and flows_to_return(B,dk,rk):
                    return f'returns Option::None at bb{b["basic_block"]}'
            elif rv['kind']=='Use' and rv['detail']['operand'].get('kind')=='Constant' and flows_to_return(B,dk,rk):
                c=rv['detail']['operand']['detail'].get('constant',{}).get('type',{}).get('kind')
                if c in ('Bool','Int','Uint','Str','Ref','Float','Char'):
                    return f'returns literal ({c}) at bb{b["basic_block"]} - output not constructed from input'
    return None

def information_destination(effect):
    return 'shown' if effect['kind'] in ('DECIDES','WRITES','DROPS','COMPUTES') else 'folded'


class InformationRule:
    """Approved MIR v3 rule, using only exact pinned slices; no case-specific decisions."""
    def __init__(self,pins,generate=False):
        from mir_access import MirAccess
        self.access=MirAccess(pins,generate)
        self.pins=pins; self.memo={}; self.cache={}
        self.locators={p['def_path_hash']:p for p in pins.get('information_mir_slices',[])}
    def has_mir(self,h,display="",line=None):
        if not h:return False
        return self.access.body(h,display,line) is not None
    def is_project_fn(self,nm,h):
        return bool(h and self.access.definition(h)) or nm.startswith('codex_') or nm.startswith('<codex_')
    def mir(self,h):
        return self.access.body(h)

    def inner_body(self,h):
        """async fn outer wrapper -> its coroutine body."""
        b=self.mir(h)
        if b is None: return None,None
        calls=[x for x in b['basic_blocks'] if x['terminator']['kind']=='Call']
        if not calls:
            for x in b['basic_blocks']:
                for st in x['statements']:
                    if st['kind']=='Assign' and st['detail']['rvalue']['kind']=='Aggregate':
                        ak=st['detail']['rvalue']['detail']['aggregate_kind']
                        if ak.get('kind')=='Coroutine':
                            ch=(ak.get('detail') or {}).get('def_path_hash') or ((ak.get('detail') or {}).get('definition') or {}).get('def_path_hash')
                            if ch and self.has_mir(ch):
                                ib=self.mir(ch)
                                if ib: return ib,ch
        return b,h
    def children(self,b):
        out=[]
        for x in b['basic_blocks']:
            for st in x['statements']:
                if st['kind']=='Assign' and st['detail']['rvalue']['kind']=='Aggregate':
                    ak=st['detail']['rvalue']['detail']['aggregate_kind']
                    if ak.get('kind') in ('Coroutine','Closure','CoroutineClosure'):
                        d=ak.get('detail') or {}
                        ch=d.get('def_path_hash') or (d.get('definition') or {}).get('def_path_hash')
                        if ch and ch not in out: out.append(ch)
        return out

    def analyse(self,h,depth=0,stack=()):
        if h in stack: return dict(kind=None,why='recursion cycle',unknown=True)
        memo_key=(h,stack)
        if memo_key in self.memo: return self.memo[memo_key]
        b,bh=self.inner_body(h)
        if b is None: return dict(kind=None,why='no MIR',unknown=True)
        B=InformationBody(b,h[16:],self); path=(b.get('canonical_path') or '')[-70:]
        res=None
        w=B.body_writes()
        if w: res=dict(kind='WRITES',why=f'{path}: {w}'[:220])
        if not res:
            for bb,k,span in B.switches:
                if B.switch_is_machinery(k) or thirdparty_macro(span): continue
                if B.origin(B.discr_of.get(k,k))=='domain':
                    res=dict(kind='DECIDES',why=f'{path}: branch bb{bb} {span.get("file")}:{span.get("start_line")} on a computed/project value'); break
        if not res:
            r=returns_none(B)
            if r: res=dict(kind='DROPS',why=f'{path}: {r}')
        if not res:
            for b2 in B.bbs:
                for st in b2['statements']:
                    rv=st['detail'].get('rvalue') if st['kind']=='Assign' else None
                    if rv and rv['kind'] in ('BinaryOp','CheckedBinaryOp') and rv['detail'].get('operator') in ('Add','Sub','Mul','Div','Rem','AddWithOverflow','SubWithOverflow','MulWithOverflow','Shl','Shr','AddUnchecked','SubUnchecked','MulUnchecked'):
                        res=dict(kind='COMPUTES',why=f'{path}: arithmetic {rv["detail"]["operator"]} at bb{b2["basic_block"]}'); break
                if res: break
        unknown=[]
        if not res:
            for i,t in B.calls.items():
                nm=fname(t['detail']['func']); ch=fhash(t['detail']['func'])
                if ch: ch=self.access.resolve(ch,nm)
                if ch and self.has_mir(ch,nm, str((t.get('source_info') or {}).get('span',{}).get('file'))+':'+str((t.get('source_info') or {}).get('span',{}).get('start_line'))) and ch!=h:
                    sub=self.analyse(ch,depth+1,stack+(h,))
                    if sub.get('kind'): res=dict(kind=sub['kind'],why=f'{path}: calls {short(nm)} -> {sub["why"]}'[:260]); break
                    if sub.get('unknown'): unknown.append(short(nm))
                elif ch and self.is_project_fn(nm,ch):
                    unknown.append('no-MIR '+short(nm))
                else:
                    lk=lib_kind(nm)
                    if lk in ('DROPS','COMPUTES'): res=dict(kind=lk,why=f'{path}: library {short(nm)} at bb{i}'); break
                    if lk=='UNCLASSIFIED': unknown.append('unclassified lib '+short(nm))
        if not res:
            for ch in self.children(b):
                if ch not in stack and ch!=h and ch!=bh:
                    sub=self.analyse(ch,depth+1,stack+(h,))
                    if sub.get('kind'): res=dict(kind=sub['kind'],why=f'{path}: inner closure -> {sub["why"]}'[:260]); break
        if not res: res=dict(kind=None,why=f'{path}: information-preserving body',unknown=bool(unknown),unknowns=unknown[:6])
        self.memo[memo_key]=res; return res

    def decisions(self,raw,elements):
        B=InformationBody(raw,raw['owner_def_path_hash'][16:],self); rows=[]
        for x in elements['items']:
            if x['kind'] not in ('call','body'): continue
            row=dict(id=x['id'])
            if x['kind']=='call':
                t=B.calls[int(x['bb'][2:])]; nm=fname(t['detail']['func']); sp=x['source_info']['span']
                ch=(x.get('callee') or {}).get('def_path_hash') or fhash(t['detail']['func'])
                if ch: ch=self.access.resolve(ch,nm)
                proj=x.get('targetCategory') in ('local_mir','local_no_mir') or self.is_project_fn(nm,ch) or ((x.get('callee') or {}).get('canonical_path') or '').startswith('codex_')
                row.update(callee=(x.get('callee') or {}).get('canonical_path') or nm,display=short(nm),line=f"{sp.get('file')}:{sp.get('start_line')}"+(' (macro)' if sp.get('from_expansion') else ''))
                kind=None; why=''
                w=B.call_writes(t)
                if w: kind,why='WRITES',f'bb{x["bb"][2:]} {w}'
                if not kind and proj:
                    available=bool(ch and self.has_mir(ch,nm,row['line']))
                    st,ev=B.reaches_branch(B.key(t['detail']['destination']))
                    debug=t['detail']['func'].get('detail',{}).get('constant',{}).get('value_debug','')
                    library_predicate=lib_kind(nm)=='predicate' and bool(re.search(r'~\s*(?:core|std|alloc)\[',debug))
                    if st=='fire' and (available or ch in self.access.owner_index()):
                        if library_predicate:why='condition of branch (predicate library op feeding '+ev[-1]+')'
                        else:kind,why='DECIDES','result decides branch: '+' > '.join(ev)
                    elif available:
                        a=self.analyse(ch)
                        if a.get('kind'): kind,why=a['kind'],a['why']
                        else:
                            why=a['why']+(' ; unresolved: '+', '.join(a.get('unknowns',[])) if a.get('unknowns') else '')
                            row['partial']=bool(a.get('unknowns'))
                    if not available:
                        row['noMir']=True
                        if not why:why='declaration/out-of-scope: no executable MIR in extraction container; see missing_mir report'
                elif not kind:
                    if ch and not self.access.definition(ch):self.access.note(ch,nm,row['line'],'declaration','std/third-party declaration absent from definitions')
                    lk=lib_kind(nm); row['libKind']=lk
                    if lk in ('DROPS','COMPUTES','predicate','UNCLASSIFIED'):
                        st,ev=B.reaches_branch(B.key(t['detail']['destination']))
                        if st=='fire' and lk!='UNCLASSIFIED': why=f'condition of branch ({lk} library op feeding {ev[-1]})'
                        elif lk=='predicate': kind,why='COMPUTES','predicate value stored, not a branch condition'
                        elif lk=='UNCLASSIFIED': why='UNCLASSIFIED library op (not in table) - folded, listed'; row['unclassified']=True
                        else: kind,why=lk,f'library {lk} op'
                    else: why=lk
            else:
                h=x['def_path_hash']
                row.update(callee=x.get('canonical_path'),line=((x.get('source') or {}).get('file') or '?')+':'+str(((x.get('source') or {}).get('span') or {}).get('start_line')),bodyKind='owned-closure' if x.get('owned') else 'callee-async-body')
                f=((x.get('source') or {}).get('file') or '')
                if f.startswith('../') or '.cargo/' in f:
                    kind,why=None,'infrastructure: body defined in third-party crate/macro ('+f[-40:]+')'
                elif self.has_mir(h,line=row['line']):
                    a=self.analyse(h); kind,why=a.get('kind'),a['why']; row['partial']=bool(a.get('unknowns'))
                else: kind,why=None,'declaration/out-of-scope body; see missing_mir report'; row['noMir']=True
            # A selected project endpoint needs its own exact body pin even when
            # caller-side evidence already settles the effect; do not inspect descendants.
            if x['kind']=='call' and kind and proj and ch:self.has_mir(ch,nm,row['line'])
            row['kind']=kind or 'transparent/infrastructure'; row['why']=why[:400]
            row['new']=information_destination(row); rows.append(row)
        return {row['id']:row for row in rows}

if __name__=='__main__':main()
