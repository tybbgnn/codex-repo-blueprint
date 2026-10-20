import classificationRegistry from './classification-registry.mjs';
import shape from './schema-validator.mjs';
import {walkControls} from './control-tree.mjs';
export {collectNodes} from './control-tree.mjs';
import {validateExecution} from './execution.mjs';
export const equal=(a,b)=>a===b||!!a&&!!b&&typeof a==='object'&&typeof b==='object'&&Array.isArray(a)===Array.isArray(b)&&Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>Object.hasOwn(b,k)&&equal(a[k],b[k]));
function validateCommon(d,entries){
 const errors=[],fail=(code,path,message)=>errors.push({code,path,message});
 for(const s of d.readingScopes??[])for(const b of s.branches??[])if(!b.outcome&&(b.members?.length!==1||b.members[0]?.kind!=='action'||b.effect))fail('scope.outcome',b.id,'omitted outcome requires one action member and no effect');
 const map=(xs,key,namespace)=>{const out=new Map();for(const x of xs){if(out.has(x[key]))fail('id.duplicate',namespace,x[key]);out.set(x[key],x);}return out;};
 const actors=d.actors.flatMap(function f(a){return [a,...(a.children??[]).flatMap(f)]});
 const aa=map(actors,'actorId','actors'),mm=map(d.messages,'messageId','messages'),roots=map(d.controls,'id','controls'),nodes=map(entries.map(e=>e.node),'id','control nodes');
 const pp=map(d.phases,'id','phases'),gg=map(d.phases.flatMap(p=>p.goals),'id','goals'),acts=map(d.phases.flatMap(p=>p.goals.flatMap(g=>g.actions)),'id','actions');
 map([...gg.values(),...acts.values()],'renderId','render IDs');
 const ownership=new Map(),msgOwner=new Map(),branches=new Set();let ordinal=0;
 function own(ref,scope){if(!roots.has(ref))fail('reference.control',scope,ref);if(ownership.has(ref))fail('control.multipleOwners',scope,ref);ownership.set(ref,scope);}
 for(const r of d.rootControlRefs)own(r,'ROOT');
 for(const p of d.phases){for(const r of p.boundaryControlRefs)own(r,p.id);for(const g of p.goals)for(const a of g.actions)for(const r of a.controlRefs)own(r,a.id);}
 for(const r of roots.keys())if(!ownership.has(r))fail('control.unowned','controls',r);
 for(const {node:n,rootControlRef:root,branchPath,guardPath,invocationControlRef} of entries){
  for(const id of n.messages??[]){if(!mm.has(id))fail('reference.message',n.id,id);if(msgOwner.has(id))fail('message.multipleOwners',n.id,id);msgOwner.set(id,{root,node:n.id,ordinal:ordinal++,branchPath,guardPath,invocationControlRef});}
  if(n.kind==='alt'&&n.branches.length<2)fail('control.alt',n.id,'alt needs explicit alternatives');if(n.kind==='opt'&&!n.skip)fail('control.opt',n.id,'opt needs bypass');if(n.kind==='loop'&&(!n.repeat?.continue||!n.repeat?.exit))fail('control.loop',n.id,'loop needs continue/exit');
  for(const b of n.branches??[]){if(branches.has(b.id))fail('id.duplicate','branches',b.id);branches.add(b.id);}
 }
 for(const m of d.messages)if(!msgOwner.has(m.messageId))fail('message.unowned','messages',m.messageId);
 function tree(list,parent=null){for(const a of list){if(Object.hasOwn(a,'parentActorId')&&a.parentActorId!==(parent?.actorId??null))fail('actor.parent',a.actorId,'wrong parent');if(parent&&!(parent.kind==='crate'?a.kind==='module':parent.kind==='module'?['body','declaration'].includes(a.kind):false))fail('actor.hierarchy',a.actorId,'crate→module→body/declaration');if(['body','declaration'].includes(a.kind)&&a.children?.length)fail('actor.bodyChildren',a.actorId,'callable leaf required');if(a.kind==='declaration'&&(a.bodyRef!==undefined||a.sourceNodeRef!==a.declarationRef||a.implementationStatus!=='unresolved'))fail('actor.declaration',a.actorId,'exact declaration identity without a fabricated implementation body required');tree(a.children??[],a);}}tree(d.actors);
 const pairs=new Map(),handles=new Map();for(const m of d.messages){for(const k of ['fromActorId','toActorId'])if(!['body','declaration'].includes(aa.get(m[k])?.kind))fail('message.endpoint',m.messageId,m[k]);if(m.kind==='self'&&(m.fromActorId!==m.toActorId||m.pair!==null))fail('message.self',m.messageId,'invalid self');if(m.kind!=='self'&&(m.pair===null||m.fromActorId===m.toActorId))fail('pair.required',m.messageId,'pair and two distinct callable endpoints required');if(m.pair){const a=pairs.get(m.pair)??[];a.push(m);pairs.set(m.pair,a);}for(const k of ['handleId','wrapperId'])if(m[k]){if(!m.taskId)fail('identity.task',m.messageId,k);const t=handles.get(m[k]);if(t&&t!==m.taskId)fail('identity.conflict',m.messageId,k);handles.set(m[k],m.taskId);}if(m.wrapperId===m.taskId&&m.wrapperId)fail('identity.wrapper',m.messageId,'wrapper distinct');}
 for(const [pair,ms]of pairs){if(ms.length===1){if(ms[0].kind!=='request'||ms[0].pairState!=='open'||ms[0].completion!=='unknown')fail('pair.incomplete',pair,'open unknown request required');continue;}if(ms.length!==2){fail('pair.cardinality',pair,'one request + one conditional return');continue;}const q=ms.find(m=>m.kind==='request'),r=ms.find(m=>m.kind==='return');if(!q||!r){fail('pair.kinds',pair,'request/return required');continue;}if(q.fromActorId!==r.toActorId||q.toActorId!==r.fromActorId)fail('pair.endpoints',pair,'reverse endpoints');for(const k of ['taskId','handleId','wrapperId','attemptId','taskEvent','invocationRef'])if(q[k]!==r[k])fail('pair.identity',pair,k);if(msgOwner.get(q.messageId)?.root!==msgOwner.get(r.messageId)?.root||msgOwner.get(q.messageId)?.invocationControlRef!==msgOwner.get(r.messageId)?.invocationControlRef)fail('pair.invocationScope',pair,'pair must remain in one logical root invocation/control');const qo=msgOwner.get(q.messageId),ro=msgOwner.get(r.messageId);if(qo&&ro&&(qo.ordinal>=ro.ordinal||!qo.guardPath.every((b,i)=>b.kind===ro.guardPath[i]?.kind&&b.ref===ro.guardPath[i]?.ref)))fail('pair.orderAndGuard',pair,'request must precede return under same or outer branch conditions');if(q.pairState||r.pairState)fail('pair.closedState',pair,'closed pair marked open');}
 const segmentUse=new Map();for(const s of d.segments){let previous;for(const id of s.messages??[]){const m=mm.get(id);if(!m){fail('segment.unknown',s.id,id);continue;}segmentUse.set(id,(segmentUse.get(id)??0)+1);if(previous&&previous.toActorId!==m.fromActorId)fail('segment.nonlinear',s.id,id);previous=m;}}
 for(const m of d.messages)if(segmentUse.get(m.messageId)!==1)fail('segment.coverage','segments',m.messageId);
 if(!equal(d.fixture,{actors:d.actors,messages:[]}))fail('derived.fixture','fixture','identity mismatch');
 for(const [k,m]of [['expandedActorIds',aa],['expandedPhaseIds',pp],['expandedGoalIds',gg],['expandedActionIds',acts]]){if(new Set(d.initialState[k]).size!==d.initialState[k].length)fail('initial.duplicate',k,'duplicate');for(const id of d.initialState[k])if(!m.has(id))fail('initial.reference',k,id);}
 const anchored=new Set();for(const a of d.rootAnchors){if(!d.rootControlRefs.includes(a.controlRef)||!pp.has(a.beforePhaseRef)||anchored.has(a.controlRef))fail('root.anchor','rootAnchors',a.controlRef);anchored.add(a.controlRef);}if(!equal([...anchored].sort(),[...d.rootControlRefs].sort()))fail('root.anchorCoverage','rootAnchors','every root control requires exactly one reading boundary anchor');
 for(const scope of d.scopeAnnotations){if(!pp.has(scope.phaseRef))fail('scope.phase','scopeAnnotations',scope.id);for(const id of scope.actionRefs??[])if(!acts.has(id))fail('scope.action','scopeAnnotations',id);}
 return errors;
}
export function readingIndex(d){const nodes=new Map(),actions=[];for(const p of d.phases){const pa=[];for(const g of p.goals){const ga=[];for(const a of g.actions){nodes.set(a.id,{...a,kind:'action',phase:p.id,goal:g.id,actionIds:[a.id],index:actions.length});actions.push(a.id);ga.push(a.id);pa.push(a.id);}nodes.set(g.id,{...g,kind:'goal',phase:p.id,actionIds:ga});}nodes.set(p.id,{...p,kind:'phase',phase:p.id,actionIds:pa});}return {nodes,actions};}
export function expandRefs(refs,index){return refs.flatMap(r=>index.nodes.get(r.ref)?.actionIds??[]);}
function validateScopes(d,entries){const errors=[],fail=(code,path,message)=>errors.push({code,path,message});
 const ix=readingIndex(d),scopes=new Map(),controls=new Map(entries.map(({node:n})=>[n.id,n])),members=new Map();
 function unique(xs,path){if(new Set(xs).size!==xs.length)fail('scope.duplicate',path,'duplicate reference/value');}
 function expand(refs,path){for(const r of refs)if(ix.nodes.get(r.ref)?.kind!==r.kind)fail('scope.reference',path,r.ref);const ids=expandRefs(refs,ix);unique(ids,path);return ids;}
 function partition(parts,domain,path){const flat=parts.flat();unique(flat,path);if(!equal([...flat].sort(),[...domain].sort()))fail('scope.partition',path,'decision values must be complete, disjoint and exact');}
 for(const s of d.readingScopes){if(scopes.has(s.id))fail('scope.duplicate',s.id,'scope id');scopes.set(s.id,s);members.set(s.id,expand(s.members,s.id));unique(s.decision.values,s.id);if(s.decision.values.length<2)fail('scope.decision',s.id,'explicit alternatives required');}
 unique(d.readingScopes.flatMap(s=>[s.id,...(s.branches??[]).map(b=>b.id)]),'readingScopes/range ids');
 for(const s of d.readingScopes){const ids=members.get(s.id),set=new Set(ids);if(!ids.length)fail('scope.empty',s.id,'nonempty controlled range required');const positions=ids.map(id=>ix.actions.indexOf(id));if(positions.some((v,i)=>i&&v<=positions[i-1]))fail('scope.memberOrder',s.id,'references must preserve reading-tree order');
  // Existing range brackets cannot cover an unrelated step between two members.
  if(positions.length&&positions.at(-1)-positions[0]+1!==positions.length)fail('scope.noncontiguous',s.id,'range would enclose unrelated reading members; provide separate precise ranges');
  if(s.parentScopeRef){const parent=members.get(s.parentScopeRef);if(!parent||!ids.every(id=>parent.includes(id)))fail('scope.parent',s.id,'parent must contain exact child members');let p=s.parentScopeRef,seen=new Set([s.id]);while(p){if(seen.has(p)){fail('scope.cycle',s.id,'parent cycle');break;}seen.add(p);p=scopes.get(p)?.parentScopeRef;}}
  if(s.kind==='alt'){if(!s.branches||s.branches.length<2){fail('scope.alt',s.id,'explicit alternative branches required');continue;}unique(s.branches.map(b=>b.id),s.id);partition(s.branches.map(b=>b.when),s.decision.values,s.id);const all=[];for(const b of s.branches){const bi=expand(b.members,b.id);all.push(...bi);if(b.effect?.kind==='terminate-turn'&&(bi.length||b.effect.scopeRef!==d.semanticRoot.symbol))fail('scope.termination',b.id,'whole-turn termination has no subsequent members');if(!bi.length&&b.effect?.kind!=='terminate-turn')fail('scope.emptyBranch',b.id,'empty branch needs explicit whole-turn termination');if(s.originControlRef){const origin=controls.get(s.originControlRef),ob=origin?.branches?.find(x=>x.id===b.sourceBranchRef);if(!ob||ob.condition!==b.condition)fail('scope.origin',b.id,'condition must match original control branch');}}unique(all,s.id);if(!equal([...all].sort(),[...ids].sort()))fail('scope.branchMembers',s.id,'branch union must exactly cover range');}
  if(s.kind==='opt'&&s.originControlRef){
   const c=controls.get(s.originControlRef);
   if(!c||c.kind!=='opt'||c.condition!==s.condition||c.skip!==s.skip)fail('scope.origin',s.id,'opt origin must match its single projected range');
   if(c&&['messages','children','branches','notes','after'].some(k=>c[k]?.length))fail('scope.originBody',s.id,'range origin is a body-free binding, not a second visible control');
  }
  if(s.kind==='opt'){if(!s.skip||!s.takeValues||!s.skipValues)fail('scope.opt',s.id,'take and bypass required');else partition([s.takeValues,s.skipValues],s.decision.values,s.id);}
  if(s.kind==='loop'){if(!s.repeat)fail('scope.loop',s.id,'repeat semantics required');else {partition([s.repeat.continueValues,s.repeat.exitValues],s.decision.values,s.id);if(s.repeat.entryActionRef!==ids[0])fail('scope.loopEntry',s.id,'continue returns to range entry');if(s.repeat.continue===s.repeat.exit)fail('scope.loopExit',s.id,'continue and exit differ');}if(Boolean(s.commonAfter)===Boolean(s.terminalOnly))fail('scope.loopSuccessor',s.id,'exactly one of outside successor or certified terminal-only exits required');}
  if(s.commonAfter){const a=s.commonAfter;if(ix.nodes.get(a.actionRef)?.kind!=='action'||set.has(a.actionRef)||ix.actions.indexOf(a.actionRef)<=Math.max(...positions))fail('scope.successor',s.id,'shared successor must be one later action outside scope');const expected=s.kind==='alt'?s.branches.filter(b=>b.effect?.kind!=='terminate-turn').map(b=>b.id):s.kind==='opt'?['taken','skipped']:['exit'];if(!equal(a.arrivals.map(x=>x.path).sort(),expected.sort()))fail('scope.arrivals',s.id,'exact branch/take-bypass/exit arrivals required');}
 }
 // Crossed intervals cannot be honestly drawn as nested ranges in this visual grammar.
 const ss=[...scopes.values()];for(let i=0;i<ss.length;i++)for(let j=i+1;j<ss.length;j++){const a=members.get(ss[i].id),b=members.get(ss[j].id),overlap=a.some(x=>b.includes(x));if(overlap&&!a.every(x=>b.includes(x))&&!b.every(x=>a.includes(x)))fail('scope.crossing',ss[i].id,'partially crossing ranges need a different expression; do not move or duplicate reading nodes');if(overlap&&(a.every(x=>b.includes(x))||b.every(x=>a.includes(x)))){const small=a.length<b.length?ss[i]:ss[j],large=a.length<b.length?ss[j]:ss[i];let p=small.parentScopeRef,seen=new Set();while(p&&p!==large.id&&!seen.has(p)){seen.add(p);p=scopes.get(p)?.parentScopeRef;}if(p!==large.id)fail('scope.nesting',small.id,'overlapping contained scopes require explicit parent relation');}}
 return errors;}
function validateDeclarations(d,entries){
 const errors=[],fail=(code,path,message)=>errors.push({code,path,message}),index=readingIndex(d),all=entries.map(e=>e.node),nodes=new Map(all.map(c=>[c.id,c])),roots=new Map(d.controls.map(c=>[c.id,c]));
 const unique=(xs,path)=>{if(new Set(xs).size!==xs.length)fail('id.duplicate',path,'IDs must be unique');};
 unique(d.phases.flatMap(p=>[p.id,...p.goals.flatMap(g=>[g.id,...g.actions.map(a=>a.id)])]),'reading');unique(d.segments.map(s=>s.id),'segments');
 const actors=d.actors.flatMap(function f(a){return [a,...(a.children??[]).flatMap(f)]}),am=new Map(actors.map(a=>[a.actorId,a]));
 if(am.get(d.semanticRoot.actorRef)?.kind!=='body'||!d.actors.some(a=>a.actorId===d.semanticRoot.actorRef))fail('semanticRoot.actor','semanticRoot','primary body must be an explicit root actor');
 for(const a of d.actors)if(['module','declaration'].includes(a.kind))fail('actor.root',a.actorId,'root actor is body or crate');
 for(const id of d.initialState.expandedActorIds)if(!am.get(id)?.children?.length)fail('initial.actorContainer',id,'expanded actors must have children');
 const owners=[];for(const controlRef of d.rootControlRefs)owners.push({controlRef,owner:{kind:'root',ref:'ROOT'}});
 for(const p of d.phases){for(const controlRef of p.boundaryControlRefs)owners.push({controlRef,owner:{kind:'phase',ref:p.id}});for(const g of p.goals)for(const a of g.actions)for(const controlRef of a.controlRefs)owners.push({controlRef,owner:{kind:'action',ref:a.id}});}
 const sort=(xs,key)=>[...xs].sort((a,b)=>a[key].localeCompare(b[key]));
 if(!equal(sort(owners,'controlRef'),sort(d.controlOwners,'controlRef')))fail('derived.controlOwners','controlOwners','declaration must exactly match unique reading/parent ownership');
 const placements=[],branches=[];
 for(const {node:c,rootControlRef,branchPath} of entries){for(const messageRef of c.messages??[])placements.push({messageRef,controlRef:c.id,rootControlRef,branchPath});for(const b of c.branches??[])branches.push({branchRef:b.id,controlRef:c.id});}
 if(!equal(sort(placements,'messageRef'),sort(d.messagePlacements,'messageRef')))fail('derived.messagePlacements','messagePlacements','exact node/root/branch path declaration differs');
 if(!equal(sort(branches,'branchRef'),sort(d.branchRoles.map(({role,...b})=>b),'branchRef')))fail('derived.branchRoles','branchRoles','exact branch roles required');
 const role=new Map(d.branchRoles.map(b=>[b.branchRef,b.role])),mm=new Map(d.messages.map(m=>[m.messageId,m]));
 const rc=new Map(d.returnContracts.map(r=>[r.messageRef,r]));if(rc.size!==d.returnContracts.length||!equal([...rc.keys()].sort(),d.messages.filter(m=>m.kind==='return').map(m=>m.messageId).sort()))fail('return.coverage','returnContracts','every return requires one explicit completion meaning');
 for(const p of placements)if(mm.get(p.messageRef)?.kind==='return'){const r=rc.get(p.messageRef),m=mm.get(p.messageRef),last=p.branchPath.at(-1)??null;if(!r||r.branchRef!==last)fail('return.branch',p.messageRef,'return must remain in its declared result branch');const roles=p.branchPath.map(b=>role.get(b));if(roles.some(b=>['unwind','terminate-turn','cancelled'].includes(b)))fail('pair.completionBranch',p.messageRef,'normal/poll return cannot belong to unwind/termination/cancellation');if(roles.includes('pending')&&r?.meaning!=='poll-pending'||r?.meaning==='poll-pending'&&(!m.taskId||!roles.includes('pending')))fail('return.pending',p.messageRef,'Pending poll response differs from task completion');if(r?.meaning==='task-ready'&&(!m.taskId||!roles.includes('ready')))fail('return.ready',p.messageRef,'Ready result belongs to the task Ready branch');if(r?.meaning==='future-handle'&&!m.taskId)fail('return.handle',p.messageRef,'handle return requires original task identity');}
 const invocation=new Map();for(const entry of entries){const c=entry.node;if(c.invocationRef){if(invocation.has(c.invocationRef))fail('invocation.duplicate',c.id,c.invocationRef);invocation.set(c.invocationRef,entry);}}
 unique(d.purposeProjections.map(p=>p.id),'purposes');for(const p of d.purposeProjections){if(p.goalRef&&index.nodes.get(p.goalRef)?.kind!=='goal'||p.relatedGoalRefs.some(g=>index.nodes.get(g)?.kind!=='goal')||!p.goalRef&&!p.relatedGoalRefs.length)fail('purpose.owner',p.id,'visible goal anchor required');const refs=[...p.invocationRefs,...p.waitRefs];unique(refs,p.id);if(!refs.length||refs.some(r=>!invocation.has(r)))fail('purpose.members',p.id,'exact control invocation refs required');}
 unique(d.scopeAnnotations.map(s=>s.id),'scopeAnnotations');for(const s of d.scopeAnnotations){unique(s.actionRefs,s.id);if((s.phaseRefs??[]).some(p=>index.nodes.get(p)?.kind!=='phase'))fail('scope.phaseRefs',s.id,'unknown phase reference');}unique(d.caseIndex.map(c=>c[0]),'caseIndex');
 if(d.deliveryMode==='test-suite'){unique(d.testBoundaries.map(b=>b.id),'testBoundaries');const actions=d.testBoundaries.flatMap(b=>b.actionRefs),cases=d.caseIndex.map(c=>c[0]);unique(actions,'testBoundaries/actions');if(!equal([...actions].sort(),[...index.actions].sort()))fail('test.boundaryCoverage','testBoundaries','every action must belong to one declared independent test boundary');for(const b of d.testBoundaries)if(!b.caseRefs.length||b.caseRefs.some(r=>!cases.includes(r)))fail('test.caseReference',b.id,'exact case references required');if(cases.some(id=>!d.testBoundaries.some(b=>b.caseRefs.includes(id))))fail('test.caseCoverage','caseIndex','every case belongs to explicit test boundary');}
 return errors;
}
export function validateSource(d){
 if(d.deliveryMode!=='real-flow')return [];
 const errors=[],fail=(path,message)=>errors.push({code:'source.range',path,message});
 const s=d.functionSource;
 if(!s){fail('functionSource','complete owning function source required');return errors;}
 if(s.endLine<s.startLine||s.lines.length!==s.endLine-s.startLine+1||!s.lines.some(x=>x.trim()))fail('functionSource','line count must equal inclusive function span');
 const signatureOffset=s.lines.findIndex(line=>/\bfn\s+\w+/.test(line));
 const signatureLine=signatureOffset<0?null:s.startLine+signatureOffset;
 if(s.attributeLines){
  if(s.startLine!==s.attributeLines.startLine||s.attributeLines.endLine<s.attributeLines.startLine||s.attributeLines.endLine>=signatureLine)fail('functionSource.attributeLines','source starts at attributeLines.startLine and the attribute ends before the signature');
 }else if(signatureLine!==null&&s.startLine!==signatureLine)fail('functionSource.startLine','source without attributeLines starts at the signature');
 if(!d.sourceGroups)fail('sourceGroups','BB group source mappings required');
 const innerNodes=[...readingIndex(d).nodes.values(),...(d.execution?.nodes??[]),...(d.sourceGroups??[])];
 const preludeNodes=d.prelude?.nodes??[],nodes=[...preludeNodes,...innerNodes];
 const innerIds=new Set(innerNodes.map(n=>n.id)),preludeIds=new Set();for(const n of preludeNodes){if(preludeIds.has(n.id)||innerIds.has(n.id))fail(n.id,'source node ID collides across prelude/reading/execution/source groups');preludeIds.add(n.id);}
 if(d.prelude&&d.prelude.shellBodyId!==d.prelude.relation.shellBodyId)fail('prelude.shellBodyId','must equal relation.shellBodyId');
 if(d.prelude){const r=d.prelude.relation,refs=[r.constructionBbRef,...r.instrumentBbRefs,...r.intoFutureBbRefs,...r.pollBbRefs,...r.technicalBlocks.flatMap(b=>[b.bbRef,...b.evidenceRefs])];for(const ref of refs)if(!/^shell:bb[0-9]+$/.test(ref))fail('prelude.relation',`shell BB namespace required: ${ref}`);}
 const groupIds=new Set();for(const g of d.sourceGroups??[]){if(groupIds.has(g.id))fail(g.id,'duplicate source group');groupIds.add(g.id);}
 for(const n of nodes){
  const shell=preludeNodes.includes(n),pattern=shell?/^shell:bb[0-9]+$/:/^bb[0-9]+$/;
  for(const ref of n.basicBlockRefs??[])if(!pattern.test(ref))fail(n.id,shell?'prelude requires shell:bbN refs':'primary nodes require bbN refs');
  const sourceLess=classificationRegistry.exceptions.source_less.required.every(k=>typeof n[k]==='string'?n[k].trim():Array.isArray(n[k])&&n[k].length);
  if((!n.lineRanges?.length&&!sourceLess)||!n.basicBlockRefs?.length){fail(n.id,'BB refs plus ranges or documented source-less context required');continue;}
  const exempt=d.phases.some(p=>p.id===n.id)||(d.sourceGroups??[]).some(g=>g.id===n.id);
  const covered=(n.lineRanges??[]).reduce((sum,r)=>sum+r.endLine-r.startLine+1,0);
  if(!exempt&&covered>(s.endLine-s.startLine+1)*.25&&!n.broadRangeReason?.trim())fail(n.id,'source coverage exceeds 25% without broadRangeReason');
  let previous=null;
  for(const r of n.lineRanges){
   const columns=(r.startColumn===undefined)===(r.endColumn===undefined);
   const validColumns=columns&&(r.startColumn===undefined||r.startColumn>=1&&r.endColumn>=1&&(r.startLine<r.endLine||r.startColumn<r.endColumn));
   const starts=[r.startLine,r.startColumn??0],ends=[r.endLine,r.endColumn??Number.MAX_SAFE_INTEGER];
   const overlaps=previous&&(starts[0]<previous.ends[0]||starts[0]===previous.ends[0]&&starts[1]<previous.ends[1]);
   const adjacent=previous&&r.startColumn===undefined&&previous.range.startColumn===undefined&&r.startLine<=previous.range.endLine+1;
   if(r.startLine<s.startLine||r.endLine>s.endLine||r.endLine<r.startLine||!validColumns||overlaps||adjacent)fail(n.id,'ranges must be sorted, merged, and within function span');
   previous={range:r,ends};
  }
 }
 return errors;
}
export async function validateInput(d){
 if(!shape(d))return {valid:false,profile:'v6.1/1',errors:shape.errors.map(e=>({code:'shape.'+e.keyword,path:e.instancePath,message:e.message}))};
 const entries=walkControls(d.controls);
 const errors=[...validateSource(d),...validateCommon(d,entries),...validateScopes(d,entries),...validateDeclarations(d,entries)];
 if(d.deliveryMode==='real-flow'&&!errors.length)errors.push(...await validateExecution(d));
 return {valid:!errors.length,profile:'v6.1/1',errors,proof:d.deliveryMode==='real-flow'?'Evidence-consistent guarded reachability, not independent authentication of source claims.':'Explicit independent synthetic boundaries; no real-flow connectivity claim.'};
}
export async function assertInput(d){const r=await validateInput(d);if(!r.valid){const e=new Error(r.errors.map(e=>`${e.code} ${e.path} ${e.message}`).join('\n'));e.errors=r.errors;throw e;}return d;}
