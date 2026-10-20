import {controlHeading} from '../display-labels.mjs';
import {showBasicBlocks} from './bb-details.js?v=sidebar-1';
import {sourceIdentity} from './render-config.js?v=source-fields-20261015';
import {projectLoopMarkers} from './loop-markers.mjs';
import {projectScopes} from '../projection.mjs';
import {computeLayout} from './seqdia-layout.js';
import {actors,messages,phases,segments,fixture,collectNodes,caseIndex,definitionNotes,initialState,display,dataKind,scopeAnnotations,purposeProjections,rootControls,rootAnchors,controls,data,readingSummaries} from './fixture.js?v=sidebar-1';
// The upstream layout algorithm is unchanged. Vertical fragments are a local extension.
const allActors=actors.flatMap(function flat(a){return [a,...(a.children??[]).flatMap(flat)]});
const actorById=new Map(allActors.map(a=>[a.actorId,a]));
const rawById=new Map(messages.map(m=>[m.messageId,m]));
const expandedActors=new Set(initialState.expandedActorIds);
const expandedPhases=new Set(initialState.expandedPhaseIds);
const expandedGoals=new Set(initialState.expandedGoalIds);
const expandedActions=new Set(initialState.expandedActionIds);
let selected=null,zoom=1,selectedLoop=null;
let detailNode=undefined;
document.addEventListener('source-node-selected',event=>{detailNode=event.detail.nodeId;});
// Execution views can select any mapped node through the same sidebar entrypoint.
document.addEventListener('click',event=>{const node=event.target.closest('[data-execution-node],[data-bb-group]');if(node){detailNode=node.dataset.executionNode??node.dataset.bbGroup;showBasicBlocks(detailNode);}});
const loopMarkers=projectLoopMarkers(data);
const actionDetails=new Map(phases.flatMap(p=>p.goals.flatMap(g=>g.actions.map(a=>[a.id,{p,g,a}]))));
const readingLabels=new Map(phases.flatMap(p=>[[p.id,p.label],...p.goals.flatMap(g=>[[g.id,g.label],...g.actions.map(a=>[a.id,a.label])])]));
const shortAction=id=>readingLabels.get(id)??'';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const color=id=>actorById.get(id)?.color??'#8593a3';
const toggle=(set,id)=>set.has(id)?set.delete(id):set.add(id);
const actionsOf=p=>p.goals.flatMap(g=>g.actions);
const count=p=>actionsOf(p).flatMap(a=>a.messages).length;
const actionByRender=new Map(phases.flatMap(p=>actionsOf(p)).map(a=>[a.renderId,a.id]));
const goalByRender=new Map(phases.flatMap(p=>p.goals).map(g=>[g.renderId,g.id]));
document.querySelector("#title").textContent=display.title;
const sourceHeader=document.querySelector('#root-source');
for(const element of sourceHeader.querySelectorAll('[data-source-field]')){
 const value=sourceIdentity[element.dataset.sourceField];
 element.textContent=typeof value==='string'&&value.trim()?value:'未提供';
}
sourceHeader.setAttribute('aria-label',`${sourceIdentity.symbol||'函数'} 源码位置`);
document.querySelector("#description").textContent=display.description;
document.querySelector("#case-summary").textContent=caseIndex.length?`案例索引 / ${caseIndex.length} 项覆盖`:`真实输入：无虚构案例索引`;
const diagram=document.querySelector('#diagram');
let lastLayout;
const viewport=document.querySelector('#viewport');
let pinnedEdges=[],pinnedActorLabels=[],frozenHeaderWidth=0;
function pinRunTurn(){
 const shift=viewport.scrollLeft/zoom;
 diagram.style.setProperty('--run-turn-shift',shift+'px');
 // Parent bars span descendants; their labels stay within the visible part of that span.
 for(const {label,left,right} of pinnedActorLabels){
  const visibleLeft=Math.max(left+8,shift+frozenHeaderWidth+8);
  const visibleRight=Math.min(right-8,shift+viewport.clientWidth/zoom-8);
  const available=Math.max(0,visibleRight-visibleLeft);
  label.style.visibility=available>0?'visible':'hidden';
  label.style.width=Math.min(260,available)+'px';
  label.style.left=((visibleLeft+visibleRight)/2-left)+'px';
 }
 // Only the root body endpoint follows its frozen rail; other actors keep their coordinates.
 for(const {path,tip,dot,from,to,yy,rootFrom,rootTo} of pinnedEdges){
  const start=from+(rootFrom?shift:0),end=to+(rootTo?shift:0),direction=end>start?1:-1;
  path.setAttribute('d',`M${start} ${yy}H${end}`);
  tip.setAttribute('d',`M${end} ${yy}l${-direction*10} -6v12z`);
  dot.setAttribute('cx',start);
 }
}
viewport.addEventListener('scroll',pinRunTurn,{passive:true});
let measuredViewportWidth;
new ResizeObserver(()=>{
 const width=viewport.clientWidth,changed=measuredViewportWidth!==undefined&&width!==measuredViewportWidth;
 measuredViewportWidth=width;
 if(changed)renderInPlace();
 pinRunTurn();
}).observe(viewport);
function render(){
 const layout=computeLayout(fixture,{expandedActorIds:expandedActors,headerRowHeight:64});
 lastLayout=layout;
 // Validate each independent fragment with the unchanged upstream linear check.
 const resolved=new Map(segments.flatMap(s=>computeLayout({actors,messages:s.messages.map(id=>rawById.get(id))},{expandedActorIds:expandedActors}).messages).map(r=>[r.message.messageId,r.message]));
 const baseWidth=Math.max(960,layout.leafCount*200+100),col=(baseWidth-100)/layout.leafCount;
 const rootActor=data.semanticRoot.actorRef;
 const baseX=id=>50+layout.anchors[id]*col;
 // Scale only the frozen root body region, including its leading gutter.
 // All other columns retain their widths and move right by the added space.
 const rootScale=1.5,rootBoundary=baseX(rootActor)+col/2,rootRegionWidth=rootBoundary*rootScale;
 const extraRootWidth=rootRegionWidth-rootBoundary;
 const expandRoot=px=>px<=rootBoundary?px*rootScale:px+extraRootWidth;
 const width=baseWidth+extraRootWidth,x=id=>expandRoot(baseX(id));
 const rootX=x(rootActor),edgePositions=[];
 const head=layout.headerHeight+18;
 let html='',headerHtml='',svg='',y=head+18;
 const placed=[],phaseBoxes=[],goalBoxes=[],actionBoxes=[];
 const markerPositions=[],drawnMarkers=new Set();
 const projection=projectScopes(data,{phases:expandedPhases,goals:expandedGoals});
 const activeRanges=new Map(),rangeEvidence=[];
 // One grid for cross-action scopes, reading rows and local controls.
 const STEP=24,BASE=65,GAP={inside:8,branch:16,block:24};
 const indent=()=>activeRanges.size*STEP;
 const rail=depth=>BASE+(activeRanges.size+depth)*STEP;
 const textLeft=depth=>rail(depth)+12;
 const textWidth=left=>Math.max(180,Math.min(760,viewport.clientWidth/zoom-left-32));
 const ruler=document.createElement('div');
 ruler.style.cssText='position:absolute;visibility:hidden;pointer-events:none;left:-10000px;top:0';
 document.body.append(ruler);
 function readingRow(cls,markup,left,attributes='',gap=GAP.inside){
  const available=textWidth(left);
  ruler.className=cls;ruler.style.width=available+'px';ruler.style.maxWidth='none';ruler.innerHTML=`<span class="run-turn-text">${markup}</span>`;
  const rowHeight=Math.ceil(ruler.getBoundingClientRect().height);
  html+=`<div class="${cls}" ${attributes} style="left:${left}px;top:${y}px;width:${available}px;max-width:none">${markup}</div>`;
  y+=rowHeight+gap;
 }
 function headingHeight(cls,label,left,minimum){
  ruler.className=cls;ruler.style.width=(textWidth(left)-24)+'px';ruler.style.height='auto';
  ruler.innerHTML=`<span style="max-width:${textWidth(left)-24}px">${esc(label)}</span>`;
  const height=Math.max(minimum,Math.ceil(ruler.getBoundingClientRect().height)+6);
  ruler.style.height='';return height;
 }
 function bracket(cls,left,top,bottom,attributes=''){
  html+=`<div class="${cls}" ${attributes} style="left:${left}px;top:${top}px;height:${Math.max(8,bottom-top)}px"></div>`;
 }
 // Markers annotate existing execution edges; no synthetic actions or connections.
 function markerRow(m,depth,showCondition=false){
  if(drawnMarkers.has(m))return;
  drawnMarkers.add(m);
  const target=actionDetails.get(m.targetActionRef)?.a;
  const scope=data.readingScopes.find(s=>s.id===m.scopeRef);
  const exitWord=scope?.repeat?.exit?.includes('break')?'break':'退出循环';
  const label=m.kind==='entry'?`循环入口 · ${shortAction(m.sourceActionRef)}`:
   m.kind==='goto'?`↪ ${target.label}`:
   m.kind==='continue'?`↶ continue → ${shortAction(m.targetActionRef)} · 下一次迭代`:
   m.kind==='exit'?`${exitWord} → ${target.label}`:
   `${m.kind} → 结束 ${actorById.get(data.semanticRoot.actorRef)?.label??'本次调用'}`;
  const markerCondition=m.condition;
  const left=textLeft(depth),top=y;
  const attributes=`data-loop-marker="${m.kind}" data-loop-scope="${m.scopeRef}" data-loop-source="${esc(m.sourceActionRef)}" data-loop-target="${esc(m.targetActionRef??'')}" data-execution-edges="${esc(m.edgeRefs.join(' '))}"`;
  readingRow('loop-marker-row',`<button class="loop-marker${selectedLoop===m.scopeRef?' active':''}" ${attributes} title="${esc(markerCondition)}">${esc(label)}${showCondition&&m.condition?`<small>${esc(markerCondition)}</small>`:''}</button>`,left);
  markerPositions.push({m,left,center:top+(y-top-GAP.inside)/2});
 }
 const shownNodes=new Set();
 const notes=(lines,depth=0,attributes='')=>{
  for(const line of lines??[])readingRow('flow-note',esc(line),textLeft(depth),attributes);
 };
 function scopeEvents(events){for(const e of events??[]){
  if(e.type==='open'){
   y+=GAP.branch;
   const left=rail(0),top=y;
   readingRow(`${e.kind==='branch'?'segment-condition':'control-semantic'} cross-label kind-${e.kind}`,`${e.kind==='branch'?'':`<span>${e.kind}</span>`}${esc(e.condition)}`,left+12,`data-reading-scope="${e.scopeRef}" data-range-label="${e.id}"`);
   activeRanges.set(e.id,{...e,top,left,lineTop:y-GAP.inside});
  }else if(e.type==='close'){
   const opened=activeRanges.get(e.id);if(!opened)continue;
   if(e.outcome)notes([e.outcome],0,`data-range-outcome="${e.id}"`);
   const bottom=y;
   bracket(`${e.kind==='loop'?'repeat-scope':'control-range'} kind-${e.kind}`,opened.left,opened.lineTop,bottom,`data-scope-range="${e.id}" data-scope-kind="${e.kind}" data-scope-members="${esc(e.memberActionRefs.join(' '))}"`);
   rangeEvidence.push({id:e.id,scopeRef:e.scopeRef,kind:e.kind,startRef:e.startRef,endRef:e.endRef,members:e.memberActionRefs,left:opened.left,top:opened.top,bottom});activeRanges.delete(e.id);y+=GAP.block;
  }else if(e.type==='summary'){
   if(readingSummaries[e.unitRef])continue; // Collapsed unit already owns its synopsis.
   notes([`${e.kind==='branch'?'分支':e.kind} · ${e.condition} → ${e.memberActionRefs.map(shortAction).join(' / ')}（收起在 ${shortAction(e.unitRef)}）`,...(e.outcome?[e.outcome]:[])],0,`data-scope-summary="${e.id}" data-summary-owner="${e.unitRef}" data-summary-members="${esc(e.memberActionRefs.join(' '))}"`);
  }else if(e.type==='successor'){
   if(!e.visible&&readingSummaries[e.unitRef])continue;
   notes([`${e.label}${e.visible?'':'（收起在 '+shortAction(e.unitRef)+'）'}`,...e.arrivals.map(a=>`${a.condition} → ${actionDetails.get(e.actionRef)?.a.label}`)],0,`data-shared-successor="${e.scopeRef}" data-successor-action="${e.actionRef}"`);
  }else if(e.type==='phaseGuard'){
   notes([`${e.kind} · ${e.condition}`,...e.outcomes],0,`data-phase-guard="${e.phaseRef}" data-guard-scope="${e.scopeRef}"`);
  }
 }}
 const beforeRead=id=>scopeEvents(projection.before.get(id));
 const afterRead=id=>scopeEvents(projection.after.get(id));
 // Every case uses this same consumer. Only the four shared node kinds differ.
 function renderBlock(node,owner,depth=0){
  // An origin binding and its readingScope are one control. The projection
  // owns the single visible range; a content-bearing origin is invalid input.
  const originScope=data.readingScopes.find(s=>s.originControlRef===node.id);
  if(originScope?.kind==='opt'){
   if(['messages','children','branches','notes','after'].some(k=>node[k]?.length))throw Error('Scope origin has a duplicate body: '+node.id);
   if(originScope.kind!==node.kind||originScope.condition!==node.condition||originScope.skip!==node.skip)throw Error('Scope origin differs from its range: '+node.id);
   shownNodes.add(node.id);return;
  }
  shownNodes.add(node.id);
  const controlled=node.kind!=='sequence',left=rail(depth);
  if(controlled){
   y+=GAP.branch;
   readingRow(`control-semantic kind-${node.kind}`,`<span>${node.kind}</span> ${esc(controlHeading(node,readingLabels.get(owner.action)??readingLabels.get(owner.goal)??readingLabels.get(owner.phase)??''))}`,left+12,`data-control="${node.kind}" data-node="${node.id}"`);
  }
  const scopeTop=y-GAP.inside,contentDepth=depth+(controlled?1:0);
  notes(node.notes,contentDepth);
  for(const id of node.messages??[]){
   if(!resolved.has(id))continue;
   const m=resolved.get(id),self=m.fromActorId===m.toActorId;
   placed.push({id,m,y:y+10,self,action:owner.action,phase:owner.phase,segment:node.id});y+=62;
  }
  const hidden=(node.messages??[]).filter(id=>!resolved.has(id)).length;
  if(hidden)notes((node.messages??[]).filter(id=>!resolved.has(id)).map(id=>rawById.get(id).label),contentDepth,`data-hidden-call="${node.id}"`);
  for(const child of node.children??[])renderBlock(child,owner,contentDepth);
  for(const [bi,branch] of (node.branches??[]).entries()){
   if(bi)y+=GAP.branch;
   const branchLeft=rail(contentDepth),branchTop=y;
   readingRow('segment-condition kind-branch',esc(branch.condition),branchLeft+12,`data-branch="${branch.id}" data-owner-node="${node.id}"`);
   for(const child of branch.children??[])renderBlock(child,owner,contentDepth+1);
   if(branch.outcome)notes([branch.outcome],contentDepth+1,`data-branch-outcome="${branch.id}"`);
   for(const m of loopMarkers.filter(m=>m.branchRef===branch.id))markerRow(m,contentDepth+1);
   bracket('control-range kind-branch',branchLeft,branchTop,y,`data-local-branch="${branch.id}"`);
  }
  if(node.kind==='loop'){
   const r=node.repeat;
   notes([r.limit,r.continue,r.exit].filter(Boolean),contentDepth,`data-repeat-note="${node.id}"`);
  }
  if(node.skip)notes([node.skip],contentDepth,`data-skip="${node.id}"`);
  if(controlled){
   bracket(`${node.kind==='loop'?'repeat-scope':'control-range'} kind-${node.kind}`,left,scopeTop,y,`data-local-range="${node.id}"${node.kind==='loop'?` data-repeat-scope="${node.id}" data-max-repeats="${node.repeat.maxRepeats??''}"`:''}`);
   y+=GAP.block;
  }
  notes(node.after,depth,`data-common-after="${node.id}"`);
 }
 // Source-backed parent-owned controls remain at their parent boundary, never reassigned to an action.
 
 // A synopsis belongs to its collapsed reading unit, never a list at the
 // end of an expanded ancestor. Protocol membership remains in the input.
 function collapsedSummary(unit,kind,depth){
  const summary=readingSummaries[unit.id];
  if(!summary||summary.kind!==kind)throw Error('Missing reading synopsis: '+unit.id);
  notes([summary.text],depth,`data-reading-summary="${esc(unit.id)}" data-summary-kind="${kind}"`);
 }

 if(data.prelude){
  readingRow('prelude-heading','入口（shell）',51,`data-prelude-shell="${esc(data.prelude.shellBodyId)}"`);
  for(const node of data.prelude.nodes){
   readingRow('prelude-node',`<button data-bb-group="${esc(node.id)}">${esc(node.label)}</button>`,77);
  }
  const relation=data.prelude.relation;
  notes([`构造 ${relation.constructionBbRef}；instrument ${relation.instrumentBbRefs.join(' / ')}；into_future ${relation.intoFutureBbRefs.join(' / ')}；poll ${relation.pollBbRefs.join(' / ')}`],1,`data-prelude-relation="${esc(relation.constructionBbRef)}"`);
  y+=GAP.block;
 }

 for(const p of phases){
  for(const anchor of rootAnchors.filter(a=>a.beforePhaseRef===p.id)){notes([`进入 ${p.label} 前的交接`]);renderBlock(rootControls.find(c=>c.id===anchor.controlRef),{phase:'ROOT',action:null});}
  beforeRead(p.id);
  const top=y,open=expandedPhases.has(p.id),heading=headingHeight('phase',p.label,51,34);y+=heading+2;
  if(!open)collapsedSummary(p,'phase',0);
  // Existing cross-phase note convention: preserve full conditions/outcomes even when reading containers collapse.
  for(const scope of scopeAnnotations.filter(s=>s.phaseRef===p.id)){
   notes([`${scope.kind} · ${scope.condition}`,...scope.outcomes,...(scope.commonAfter?[`共同后继：${scope.commonAfter.meaning}${scope.commonAfter.appliesTo?'；仅 '+scope.commonAfter.appliesTo.join(' / '):''}`]:[]),...(scope.repeat?[`继续：${scope.repeat.continue}`,`退出：${scope.repeat.exit}`]:[])],0,`data-scope-ref="${scope.id}"`);
  }
  if(open){
   if(p.boundaryControls.length){notes([`${p.label} 进入前按条件执行`]);for(const n of p.boundaryControls)renderBlock(n,{phase:p.id,action:null});}
   for(const [gi,g]of p.goals.entries()){
    beforeRead(g.id);const gIndent=indent();
    const gt=y,go=expandedGoals.has(g.id),gHeading=headingHeight('goal',g.label,77+gIndent,30);y+=gHeading+8;
    if(go){notes(g.notes,1);for(const [ai,a]of g.actions.entries()){
     beforeRead(a.id);const aIndent=indent();
     const at=y,ao=expandedActions.has(a.id),aHeading=headingHeight('action',a.label,101+aIndent,29);y+=aHeading+8;
     for(const m of loopMarkers.filter(m=>m.kind==='entry'&&m.sourceActionRef===a.id))markerRow(m,2);
     if(ao){notes(a.notes,2);for(const node of a.children)renderBlock(node,{phase:p.id,goal:g.id,action:a.id},2);}
     else collapsedSummary(a,'action',2);
     for(const m of loopMarkers.filter(m=>m.kind!=='entry'&&m.sourceActionRef===a.id&&!drawnMarkers.has(m)))markerRow(m,2,!!m.branchRef||m.kind==='exit'||m.kind==='continue');
     actionBoxes.push({p,g,a,top:at,open:ao,ai,indent:aIndent,heading:aHeading});afterRead(a.id);y+=GAP.branch;
    }}else collapsedSummary(g,'goal',1);
    goalBoxes.push({p,g,top:gt,open:go,gi,indent:gIndent,heading:gHeading});afterRead(g.id);y+=GAP.block;
   }
  }
  afterRead(p.id);phaseBoxes.push({p,top,bottom:y+5,open,heading});y+=20;
 }
 ruler.remove();
 const height=y+24;
 for(const a of layout.visibleActors.filter(a=>a.expanded)){
  html+=`<div class="region" style="left:${expandRoot(50+a.leafStart*col)}px;top:${head}px;width:${expandRoot(50+(a.leafStart+a.leafSpan)*col)-expandRoot(50+a.leafStart*col)}px;height:${height-head-20}px;background:${color(a.actorId)}08"></div>`;
 }
 for(const a of layout.visibleActors.filter(a=>a.isLeaf)){
  svg+=`<line class="${a.actorId===rootActor?'run-turn-rail':''}" data-rail="${a.actorId}" x1="${x(a.actorId)}" x2="${x(a.actorId)}" y1="${a.depth*64+63}" y2="${height-18}" stroke="${color(a.actorId)}" stroke-width="1.2" opacity=".72"/>`;
 }
 for(const a of layout.headerRows.flat()){
  const ax=expandRoot(50+(a.leafStart+a.leafSpan/2)*col);
  const kind=actorById.get(a.actorId).kind;
  const group=a.expanded&&(kind==='crate'||kind==='module');
  const left=group?expandRoot(50+a.leafStart*col)+9:ax-Math.min(172,a.leafSpan*col-18)/2;
  const aw=group?expandRoot(50+(a.leafStart+a.leafSpan)*col)-9-left:Math.min(172,a.leafSpan*col-18);
  headerHtml+=`<button class="actor ${group?'actor-group':''} ${a.actorId===rootActor?'run-turn-actor':''}" data-actor="${a.actorId}" ${a.hasChildren?`aria-expanded="${a.expanded}"`:''} aria-label="${esc(a.label)}" style="left:${left}px;top:${a.depth*64+10}px;width:${aw}px;height:46px;${a.actorId===data.semanticRoot.actorRef?`border-color:${color(a.actorId)};background:#eff5ff;`:''}" title="${esc(a.label)}">${group?'<span class="actor-group-label">':''}<small>${esc(kind)}</small><strong>${a.hasChildren?`<span class="chev">${a.expanded?'⌄':'›'}</span>`:''}${esc(a.label)}</strong>${group?'</span>':''}</button>`;
 }
 for(const {p,top,bottom,open,heading} of phaseBoxes){
  html+=`<div class="frame" style="left:28px;top:${top}px;width:${width-48}px;height:${bottom-top}px;--frame-color:${p.color}"></div><button class="frame-tag" data-phase="${p.id}" aria-label="${esc(p.label)} 阶段" aria-expanded="${open}" style="left:28px;top:${top}px;height:${bottom-top}px;--frame-color:${p.color}">阶段 ${phases.indexOf(p)+1}</button><button class="phase" data-phase="${p.id}" aria-expanded="${open}" style="top:${top+1}px;width:${width-73}px;height:${heading}px"><span data-semantic-label style="max-width:${textWidth(51)-24}px">${open?'⌄':'›'} ${esc(p.label)}</span><small>${p.goals.length} 子目标 / ${actionsOf(p).length} 个 action / ${count(p)} 消息</small></button>`;
 }
 for(const {p,g,top,open,indent,heading}of goalBoxes){html+=`<button class="goal" data-goal="${g.renderId}" data-source-goal="${esc(g.id)}" aria-expanded="${open}" style="left:${77+indent}px;top:${top}px;width:${width-101-indent}px;height:${heading}px"><span style="max-width:${textWidth(77+indent)-24}px">${open?'⌄':'›'} ${esc(g.label)}</span><small>${g.actions.length} 个 action</small></button>`;}
 for(const {p,a,top,open,ai,indent,heading} of actionBoxes){
  html+=`<button class="action" data-action="${a.renderId}" data-source-action="${esc(a.id)}" aria-expanded="${open}" style="left:${101+indent}px;top:${top}px;width:${width-125-indent}px;height:${heading}px"><span style="max-width:${textWidth(101+indent)-24}px"><span aria-hidden="true">${open?'⌄':'›'}&nbsp;</span><span data-semantic-label>${esc(a.label)}</span></span><small>${a.messages.length} 消息</small></button>`;
 }
 for(const row of placed){
  const {m,id,self}=row,from=x(m.fromActorId),to=x(m.toActorId),yy=row.y;
  const raw=rawById.get(id),active=selected&&(raw.pair?selected===raw.pair:selected===id);
  const stroke=color(m.fromActorId);
  svg+=`<circle data-message-dot="${id}" cx="${from}" cy="${yy}" r="3.5" fill="${stroke}"/>`;
  if(!self){edgePositions.push({id,from,to,yy,rootFrom:m.fromActorId===rootActor,rootTo:m.toActorId===rootActor});const direction=to>from?1:-1;svg+=`<path data-message-path="${id}" d="M${from} ${yy}H${to}" stroke="${stroke}" fill="none" stroke-width="2"/><path data-message-tip="${id}" d="M${to} ${yy}l${-direction*10} -6v12z" fill="${stroke}"/>`;}
  const labelWidth=Math.min(260,Math.max(190,Math.abs(baseX(m.toActorId)-baseX(m.fromActorId))-18));
  const left=rootX+6;
  const title=`${id} · ${raw.fromActorId} → ${raw.toActorId} · ${raw.pair??'self'}`;
  html+=`<button class="message ${active?'selected':''}" data-message="${id}" data-segment="${row.segment}" data-kind="${m.kind}" data-from="${m.fromActorId}" data-to="${m.toActorId}" data-original-from="${raw.fromActorId}" data-original-to="${raw.toActorId}" data-pair="${raw.pair??''}" title="${esc(title)}" aria-label="${esc(title+' '+m.label)}" style="left:${left}px;top:${yy+8}px;width:${labelWidth}px"><span>${esc(m.label)}</span><em>${esc(actorById.get(m.fromActorId).label)} → ${esc(actorById.get(m.toActorId).label)}</em></button>`;
 }
 html+=`<svg class="svg" width="${width}" height="${height}" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="#4c596a" stroke-width="1.2"/></marker></defs>${svg}</svg>`;
 // Opaque frozen column masks passing actor rails; its own rail/messages remain above it.
 html+=`<div class="run-turn-background" aria-hidden="true" style="top:${head}px;width:${rootRegionWidth}px;height:${height-head}px"></div><svg class="svg run-turn-foreground" width="${width}" height="${height}" aria-hidden="true"></svg>`;
 html+=`<div class="actor-head" style="height:${head}px"><div class="run-turn-background" aria-hidden="true" style="top:0;width:${rootRegionWidth}px;height:${head}px"></div>${headerHtml}</div>`;
 diagram.style.width=width+'px';diagram.style.height=height+'px';diagram.style.zoom=String(zoom);diagram.innerHTML=html;
 const foreground=diagram.querySelector('.run-turn-foreground');
 for(const element of diagram.querySelectorAll('.run-turn-rail,[data-message-dot],[data-message-path],[data-message-tip]'))foreground.append(element);
 document.querySelector('#scale').style.width=width*zoom+'px';document.querySelector('#scale').style.height=height*zoom+'px';
 // Move only reading text, not the full-width row backgrounds or their hit areas.
 for(const element of diagram.querySelectorAll('.flow-note,.control-semantic,.segment-condition')){
  const text=document.createElement('span');text.className='run-turn-text';
  while(element.firstChild)text.append(element.firstChild);
  element.append(text);
 }
 const paths=new Map([...diagram.querySelectorAll('[data-message-path]')].map(e=>[e.dataset.messagePath,e]));
 const tips=new Map([...diagram.querySelectorAll('[data-message-tip]')].map(e=>[e.dataset.messageTip,e]));
 const dots=new Map([...diagram.querySelectorAll('[data-message-dot]')].map(e=>[e.dataset.messageDot,e]));
 pinnedEdges=edgePositions.filter(e=>e.rootFrom||e.rootTo).map(e=>({...e,path:paths.get(e.id),tip:tips.get(e.id),dot:dots.get(e.id)}));
 frozenHeaderWidth=rootRegionWidth;
 pinnedActorLabels=[...diagram.querySelectorAll('.actor-group')].map(e=>({label:e.querySelector('.actor-group-label'),left:parseFloat(e.style.left),right:parseFloat(e.style.left)+parseFloat(e.style.width)}));
 pinRunTurn();
 const shown=new Set(placed.map(r=>r.id)),hiddenX=messages.filter(m=>!resolved.has(m.messageId)).map(m=>m.messageId),hiddenY=messages.filter(m=>resolved.has(m.messageId)&&!shown.has(m.messageId)).map(m=>m.messageId);
 document.querySelector('#status').textContent=`${layout.leafCount} 个可见参与者列 · ${placed.length} / ${messages.length} 条消息可见 · 横向收起隐藏 ${hiddenX.length} 条组内消息 · 纵向收起隐藏 ${hiddenY.length} 条消息`;
 document.querySelector('#state').textContent=JSON.stringify({fixture:dataKind+', static projection, not a runtime trace',scopeProjection:{ranges:rangeEvidence,summaries:projection.summaries,phaseGuards:projection.phaseGuards},expandedActors:[...expandedActors],expandedPhases:[...expandedPhases],expandedGoals:[...expandedGoals],expandedActions:[...expandedActions],visibleActors:layout.visibleActors.filter(a=>a.isLeaf).map(a=>a.actorId),visibleMessageIds:[...shown],hiddenByActorCollapse:hiddenX,hiddenByVerticalCollapse:hiddenY,selectedPairOrMessage:selected},null,2);
 showBasicBlocks(detailNode);
 if(selected){const rs=messages.filter(m=>(m.pair??m.messageId)===selected);document.querySelector('#message-selection').textContent=rs.map(m=>`${m.messageId} · ${m.fromActorId} → ${m.toActorId} · ${m.label}${m.taskId?' · 原任务 '+m.taskId:''}${m.handleId?' · 句柄 '+m.handleId:''}${m.wrapperId?' · 包装 '+m.wrapperId:''}${m.pairState==='open'?' · 返回未确认':''}${shown.has(m.messageId)?'':'（当前折叠隐藏）'}`).join('　 |　');}
 else document.querySelector('#message-selection').textContent='';
}
// Message endpoints already reflect each actor's current collapsed/expanded projection.
function locateMessageActor(actorId){
 if(!actorId||actorId===data.semanticRoot.actorRef)return;
 const actor=[...diagram.querySelectorAll('[data-actor]')].find(e=>e.dataset.actor===actorId);
 if(!actor)return;
 const bounds=actor.getBoundingClientRect(),view=viewport.getBoundingClientRect();
 const frozen=diagram.querySelector('.run-turn-background').getBoundingClientRect();
 const label=diagram.querySelector('.message.selected')?.getBoundingClientRect();
 const left=Math.min(Math.max(frozen.right,label?.right??frozen.right)+24,view.left+viewport.clientWidth/2);
 const right=view.left+viewport.clientWidth-24;
 if(bounds.left>=left&&bounds.right<=right)return;
 const delta=(bounds.left+bounds.right-left-right)/2;
 viewport.scrollTo({left:viewport.scrollLeft+delta,top:viewport.scrollTop,behavior:'instant'});
 pinRunTurn();
}
function locateLoopAction(actionRef,scopeRef){
 selectedLoop=scopeRef;
 const detail=actionDetails.get(actionRef);
 if(!detail){renderInPlace();return;}
 expandedPhases.add(detail.p.id);expandedGoals.add(detail.g.id);expandedActions.add(actionRef);
 render();
 const row=[...diagram.querySelectorAll('[data-source-action]')].find(e=>e.dataset.sourceAction===actionRef);
 if(row){const header=diagram.querySelector('.actor-head').getBoundingClientRect();viewport.scrollTop+=row.getBoundingClientRect().top-header.bottom-16;}
}
function renderInPlace(selector){const before=selector?diagram.querySelector(selector)?.getBoundingClientRect().top:null;const viewport=document.querySelector('#viewport');render();if(before!=null){const after=diagram.querySelector(selector)?.getBoundingClientRect().top;if(after!=null)viewport.scrollTop+=after-before;}}
diagram.addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;if(b.dataset.loopMarker){locateLoopAction(b.dataset.loopTarget||null,b.dataset.loopScope);return;}if(b.dataset.actor&&actorById.get(b.dataset.actor).children){toggle(expandedActors,b.dataset.actor);renderInPlace(`[data-actor="${b.dataset.actor}"]`);}else if(b.dataset.phase){detailNode=null;toggle(expandedPhases,b.dataset.phase);renderInPlace(`.phase[data-phase="${b.dataset.phase}"]`);}else if(b.dataset.goal){detailNode=goalByRender.get(b.dataset.goal);toggle(expandedGoals,goalByRender.get(b.dataset.goal));renderInPlace(`[data-goal="${b.dataset.goal}"]`);}else if(b.dataset.action){detailNode=actionByRender.get(b.dataset.action);const back=loopMarkers.find(m=>m.kind==='continue'&&m.sourceActionRef===actionByRender.get(b.dataset.action));if(back)selectedLoop=back.scopeRef;toggle(expandedActions,actionByRender.get(b.dataset.action));renderInPlace(`[data-action="${b.dataset.action}"]`);}else if(b.dataset.message){detailNode=null;const m=rawById.get(b.dataset.message),actorId=b.dataset.from===data.semanticRoot.actorRef?b.dataset.to:b.dataset.from;selected=m.pair??m.messageId;render();locateMessageActor(actorId);}});
document.querySelectorAll('[data-x]').forEach(b=>b.onclick=()=>{expandedActors.clear();if(+b.dataset.x>=1)actors.filter(a=>a.children).forEach(a=>expandedActors.add(a.actorId));if(+b.dataset.x===2)allActors.filter(a=>a.children).forEach(a=>expandedActors.add(a.actorId));render();});
document.querySelectorAll('[data-y]').forEach(b=>b.onclick=()=>{const level=+b.dataset.y;expandedPhases.clear();if(level>0){phases.forEach(p=>expandedPhases.add(p.id));expandedGoals.clear();expandedActions.clear();if(level>=2)phases.flatMap(p=>p.goals).forEach(g=>expandedGoals.add(g.id));if(level>=3)phases.flatMap(p=>actionsOf(p)).forEach(a=>expandedActions.add(a.id));}render();});
document.querySelector('#zoom').onchange=e=>{zoom=+e.target.value;render();};
document.querySelector('#reset').onclick=()=>{for(const [set,ids]of [[expandedActors,initialState.expandedActorIds],[expandedPhases,initialState.expandedPhaseIds],[expandedGoals,initialState.expandedGoalIds],[expandedActions,initialState.expandedActionIds]]){set.clear();ids.forEach(id=>set.add(id));}selected=null;selectedLoop=null;detailNode=undefined;zoom=1;document.querySelector('#zoom').value='1';render();document.querySelector('#viewport').scrollTop=0;};
render();

document.querySelector('#case-index').innerHTML=caseIndex.map(row=>'<tr>'+row.map(cell=>'<td>'+esc(cell)+'</td>').join('')+'</tr>').join('');
document.querySelector('#definition-info').textContent=definitionNotes.join('　');

// Resize only the shared column track; header, toolbar and diagram stay aligned.
const paneDivider=document.querySelector('#pane-divider');
const detailsPane=document.querySelector('#selection');
let paneDrag=null;
function paneWidthLimits(){
 const total=document.querySelector('.diagram-details-layout').clientWidth;
 return {min:Math.min(240,total/3),max:Math.max(total/3,total-384)};
}
function syncPaneDivider(){
 const {min,max}=paneWidthLimits();
 paneDivider.setAttribute('aria-valuemin',Math.round(min));
 paneDivider.setAttribute('aria-valuemax',Math.round(max));
 paneDivider.setAttribute('aria-valuenow',Math.round(detailsPane.getBoundingClientRect().width));
}
function setPaneWidth(width){
 const {min,max}=paneWidthLimits();
 document.body.style.setProperty('--details-width',`clamp(${min}px,${Math.max(min,Math.min(max,width))}px,calc(100% - 384px))`);
 syncPaneDivider();
}
paneDivider.addEventListener('pointerdown',event=>{
 if(event.button!==0)return;
 paneDrag={id:event.pointerId,x:event.clientX,width:detailsPane.getBoundingClientRect().width};
 paneDivider.setPointerCapture(event.pointerId);
 document.body.classList.add('resizing-panes');
 event.preventDefault();
});
paneDivider.addEventListener('pointermove',event=>{
 if(paneDrag?.id===event.pointerId)setPaneWidth(paneDrag.width+event.clientX-paneDrag.x);
});
function finishPaneDrag(event){
 if(paneDrag?.id!==event.pointerId)return;
 paneDrag=null;document.body.classList.remove('resizing-panes');
 if(paneDivider.hasPointerCapture(event.pointerId))paneDivider.releasePointerCapture(event.pointerId);
}
paneDivider.addEventListener('pointerup',finishPaneDrag);
paneDivider.addEventListener('pointercancel',finishPaneDrag);
paneDivider.addEventListener('lostpointercapture',finishPaneDrag);
paneDivider.addEventListener('keydown',event=>{
 const {min,max}=paneWidthLimits(),width=detailsPane.getBoundingClientRect().width;
 const next={ArrowLeft:width-16,ArrowRight:width+16,Home:min,End:max}[event.key];
 if(next===undefined)return;
 event.preventDefault();setPaneWidth(next);
});
new ResizeObserver(syncPaneDivider).observe(detailsPane);

// Shared entry for browser interaction regressions and embedded hosts.
globalThis.__BLUEPRINT_UI__={showBasicBlocks};
