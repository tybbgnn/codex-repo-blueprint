// Read-only presentation projection. Every route retains its actual execution edges.
export function projectLoopMarkers(data) {
 const execution=data.execution??{}, edges=execution.edges??[];
 const nodes=new Map((execution.nodes??[]).map(n=>[n.id,n]));
 const decisions=new Map((execution.decisions??[]).map(d=>[d.id,d]));
 const owners=new Map((data.controlOwners??[]).map(c=>[c.controlRef,c.owner]));
 const readingMembers=new Map();
 for(const phase of data.phases??[]){const phaseActions=[];for(const goal of phase.goals){const ids=goal.actions.map(a=>a.id);readingMembers.set(goal.id,ids);for(const id of ids)readingMembers.set(id,[id]);phaseActions.push(...ids);}readingMembers.set(phase.id,phaseActions);}
 const controlById=new Map();
 function inherit(control,owner){owner=owners.get(control.id)??owner;controlById.set(control.id,control);if(owner)owners.set(control.id,owner);for(const child of control.children??[])inherit(child,owner);for(const branch of control.branches??[])for(const child of branch.children??[])inherit(child,owner);}
 for(const control of data.controls??[])inherit(control,owners.get(control.id));
 // Preserve already authored Chinese business domains; resolve enum keys through their display binding.
 function guardLabel(guard){if(/[\u3400-\u9fff]/.test(guard.value))return guard.value;const decision=decisions.get(guard.decisionRef);const binding=decision?.branchBindings?.find(b=>b.values.includes(guard.value));const control=controlById.get(decision?.controlRef);const branch=control?.branches?.find(b=>b.id===binding?.branchRef);if(branch)return branch.condition;const scope=(data.readingScopes??[]).find(s=>s.id===decision?.readingScopeRef);if(scope?.kind==='loop')return scope.repeat.continueValues.includes(guard.value)?scope.repeat.continue:scope.repeat.exit;if(scope?.kind==='opt')return scope.takeValues.includes(guard.value)?scope.condition:scope.skip;if(scope?.kind==='alt')return scope.branches.find(b=>b.when.includes(guard.value))?.condition??scope.condition;return control?.condition??'';}
 const markers=[];
 const compatible=(a,b)=>!a.some(g=>b.some(h=>g.decisionRef===h.decisionRef&&g.value!==h.value));
 function anchor(edge) {
  const node=nodes.get(edge.from), decision=decisions.get(node?.decisionRef);
  const owner=owners.get(decision?.controlRef);
  const sourceActionRef=node?.actionRef??(owner?.kind==='action'?owner.ref:null);
  const guard=(edge.guards??[]).find(g=>g.decisionRef===node?.decisionRef);
  const branchRef=decision?.branchBindings?.find(b=>b.values.includes(guard?.value))?.branchRef;
  return {sourceNodeRef:edge.from,sourceActionRef,branchRef};
 }
 for(const scope of data.readingScopes??[]) {
  if(scope.kind!=='loop')continue;
  const members=new Set(scope.members.flatMap(m=>readingMembers.get(m.ref)??(m.kind==='action'?[m.ref]:[])));
  const loopEdges=edges.filter(e=>e.readingScopeRef===scope.id&&['loop-continue','loop-exit'].includes(e.kind));
  const back=loopEdges.find(e=>e.kind==='loop-continue'&&nodes.get(e.to)?.actionRef===scope.repeat?.entryActionRef);
  if(!back)continue; // No graph-backed entry/return: do not infer one from ordering.
  markers.push({kind:'entry',scopeRef:scope.id,sourceActionRef:nodes.get(back.to).actionRef,edgeRefs:[back.id],condition:scope.condition});
  function add(kind,path,targetActionRef) {
   const at=anchor(path[0]);
   if(!members.has(at.sourceActionRef))return;
   const guards=[...new Map(path.flatMap(e=>e.guards??[]).map(g=>[g.decisionRef,g])).values()];
   markers.push({kind,scopeRef:scope.id,...at,targetActionRef,edgeRefs:path.map(e=>e.id),condition:guards.map(guardLabel).join('；')});
  }
  function decisionPaths(nodeRef,guards,seen=new Set()) {
   if(seen.has(nodeRef))return [];
   const node=nodes.get(nodeRef);if(node?.kind!=='decision')return [];
   const next=new Set(seen).add(nodeRef),paths=[];
   for(const first of edges.filter(e=>e.to===nodeRef&&e.kind!=='loop-continue'&&compatible(e.guards??[],guards))){
    if(nodes.get(first.from)?.kind==='action')paths.push([first]);
    else for(const path of decisionPaths(first.from,guards,next))paths.push([...path,first]);
   }
   return paths;
  }
  for(const end of loopEdges) {
   const target=nodes.get(end.to)?.actionRef;
   if(!target)continue;
   const kind=end.kind==='loop-continue'?'continue':'exit';
   // An action may itself own the back/exit edge. Never move that route to an
   // incoming action: its state updates must complete before the marker.
   if(nodes.get(end.from)?.kind!=='decision') {
    add(kind,[end],target);
    continue;
   }
   // Collapse only an explicit boundary decision. Guard conflicts prevent break
   // paths from being presented as continue paths (and vice versa).
   const predecessors=edges.filter(e=>e.to===end.from&&e.kind!=='loop-continue'&&compatible(e.guards??[],end.guards??[]));
   for(const first of predecessors) {
    add(kind,[first,end],target);
    if(kind==='continue'&&nodes.get(first.from)?.kind==='action') {
     for(const arrival of edges.filter(e=>e.to===first.from&&e.kind!=='loop-continue'))add('goto',[arrival],nodes.get(first.from).actionRef);
    }
   }
  }
  for(const edge of edges) {
   const terminal=nodes.get(edge.to);
   if(terminal?.kind!=='terminal')continue;
   const kind=terminal.outcome==='error'?'error':'return';
   if(nodes.get(edge.from)?.kind==='decision')for(const path of decisionPaths(edge.from,edge.guards??[]))add(kind,[...path,edge],null);
   else add(kind,[edge],null);
  }
 }
 return markers;
}
