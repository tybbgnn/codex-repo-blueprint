"""Callable endpoints are constrained by MIR entity identities, never name ordering."""
def select(request,rows,targets=None):
    callable_rows=[r for r in rows if r.get('rustc',{}).get('def_kind') in ('Fn','AssocFn','Closure')]
    wanted=set((targets or {}).get(request['id'],[]))
    if wanted:callable_rows=[r for r in callable_rows if r.get('def_path_hash') in wanted]
    if len(callable_rows)!=1:
        raise ValueError('endpoint '+request['id']+' resolved to '+str(len(callable_rows))+' callable definitions constrained by MIR '+str(sorted(wanted)))
    return callable_rows[0]

def targets_from(c,ledger):
    external=c.ledger(5);calls={r['id']:r for r in c.load('facts/call-bindings.json')}
    pins=c.load('input-pins.json');owner=pins['definition_row']
    elements={r['id']:r for r in c.load('facts/elements.json')['items']}
    result={}
    for request in ledger['endpoints']:
        wanted=set();actor=request['actorRef']
        if request['canonical_path']==owner['identity']['canonical_path']:wanted.add(owner['def_path_hash'])
        for member in external.get('business_members',[]):
            if member.get('targetActorRef')!=actor or member.get('internalOperation'):continue
            body=elements.get(member.get('bodyElementRef'),{})
            if body.get('def_path_hash'):wanted.add(body['def_path_hash']);continue
            call=calls.get(member.get('bindingRef'),{})
            callee=elements.get(member.get('bindingRef'),{}).get('resolvedCallee',call.get('callee',{}))
            h=callee.get('def_path_hash')
            if h:wanted.add(h)
        # Exact constructed body identities (including async coroutine consumers).
        for body in elements.values():
            if body['kind']=='body' and body.get('canonical_path')==request['canonical_path']:wanted.add(body['def_path_hash'])
        result[request['id']]=sorted(wanted)
    return result
