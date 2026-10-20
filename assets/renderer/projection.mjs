import {readingIndex,expandRefs} from './contract.mjs';
/** Pure projection: reading ownership is never rewritten. Events only annotate/brace existing rows. */
export function projectScopes(d,state){
 const ix=readingIndex(d),before=new Map(),after=new Map(),units=[],ranges=[],summaries=[],phaseGuards=[];
 const push=(m,id,e)=>m.set(id,[...(m.get(id)??[]),e]);
 for(const p of d.phases){if(!state.phases.has(p.id)){units.push(ix.nodes.get(p.id));continue;}for(const g of p.goals){if(!state.goals.has(g.id)){units.push(ix.nodes.get(g.id));continue;}for(const a of g.actions)units.push(ix.nodes.get(a.id));}}
 const sm=new Map(d.readingScopes.map(s=>[s.id,s]));
 const depth=s=>s.parentScopeRef?1+depth(sm.get(s.parentScopeRef)):0;
 function anchor(unit,ids){const set=new Set(ids);let n=unit;if(n.kind==='action'){const g=ix.nodes.get(n.goal);if(g.actionIds.every(a=>set.has(a)))n=g;}return n;}
 function addRange(id,scope,ids,kind,condition,level,outcome){
  const whole=units.filter(u=>u.actionIds.some(a=>ids.includes(a))&&u.actionIds.every(a=>ids.includes(a))),partial=units.filter(u=>u.actionIds.some(a=>ids.includes(a))&&!u.actionIds.every(a=>ids.includes(a)));
  // A collapsed group can contain several mutually exclusive branches. Never wrap the whole group as one branch.
  for(const u of partial){const specific=ids.filter(a=>u.actionIds.includes(a));const e={type:'summary',id,scopeRef:scope.id,kind,condition,memberActionRefs:specific,unitRef:u.id,outcome,level};summaries.push(e);push(after,u.id,e);}
  if(whole.length){let chunks=[];for(const u of whole){const i=units.indexOf(u),prev=chunks.at(-1);if(prev&&units.indexOf(prev.at(-1))+1===i)prev.push(u);else chunks.push([u]);}
   for(const [i,chunk]of chunks.entries()){const start=anchor(chunk[0],ids),end=anchor(chunk.at(-1),ids),e={type:'open',id:id+(chunks.length>1?'-part'+i:''),scopeRef:scope.id,kind,condition,level,startRef:start.id,endRef:end.id,memberActionRefs:chunk.flatMap(u=>u.actionIds),outcome};ranges.push(e);push(before,start.id,e);push(after,end.id,{...e,type:'close'});}
  }
 }
 for(const s of d.readingScopes){const ids=expandRefs(s.members,ix),ps=[...new Set(ids.map(a=>ix.nodes.get(a).phase))],level=depth(s)*2;
  if(ps.length>1&&s.kind==='alt'&&ps.every(p=>ix.nodes.get(p).actionIds.every(a=>ids.includes(a))&&s.branches.filter(b=>expandRefs(b.members,ix).some(a=>ix.nodes.get(a).phase===p)).length===1)){for(const p of ps){const b=s.branches.find(b=>expandRefs(b.members,ix).some(a=>ix.nodes.get(a).phase===p));const terms=s.branches.filter(b=>b.effect?.kind==='terminate-turn');const e={type:'phaseGuard',scopeRef:s.id,phaseRef:p,kind:s.kind,condition:b.condition+' → 本阶段适用',outcomes:[...(b.outcome?[b.outcome]:[]),...terms.map(b=>b.condition+' → '+b.outcome)],memberActionRefs:ids.filter(a=>ix.nodes.get(a).phase===p)};phaseGuards.push(e);push(before,p,e);}}else{
  addRange(s.id,s,ids,s.kind,s.condition,level,s.kind==='opt'?s.skip:s.kind==='loop'?[s.repeat.continue,s.repeat.exit,s.repeat.limit].join('；'):s.branches.filter(b=>b.effect?.kind==='terminate-turn').map(b=>b.condition+' → '+b.outcome).join('；')||null);
  if(s.kind==='alt')for(const b of s.branches)addRange(b.id,s,expandRefs(b.members,ix),'branch',b.condition,level+1,b.outcome);
  }
  if(s.commonAfter){const a=s.commonAfter,target=ix.nodes.get(a.actionRef),u=units.find(u=>u.actionIds.includes(a.actionRef)),visible=u.kind==='action';push(visible?before:after,visible?target.id:u.id,{type:'successor',scopeRef:s.id,actionRef:a.actionRef,unitRef:u.id,visible,label:a.label,arrivals:a.arrivals,level});}
 }
 for(const es of before.values())es.sort((a,b)=>(a.type==='phaseGuard'?-100:a.type==='successor'?-1:a.level)-(b.type==='phaseGuard'?-100:b.type==='successor'?-1:b.level));
 for(const es of after.values())es.sort((a,b)=>(b.level??0)-(a.level??0));
 return {before,after,units,ranges,summaries,phaseGuards};
}
