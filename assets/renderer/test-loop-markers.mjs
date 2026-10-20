import assert from 'node:assert/strict';
import fs from 'node:fs';
import {projectLoopMarkers} from './roundtrip/loop-markers.mjs';
const action=id=>({id,kind:'action',actionRef:id});
const edge=(id,from,to,kind='flow',extra={})=>({id,from,to,kind,...extra});
const scope={id:'loop',kind:'loop',condition:'处理剩余输入',members:['check','render','advance'].map(ref=>({kind:'action',ref})),repeat:{entryActionRef:'check'}};
function fixture(edges,extra=[]){return {readingScopes:[scope],execution:{nodes:['check','render','advance','done'].map(action).concat(extra),edges}};}
const back=edge('back','advance','check','loop-continue',{readingScopeRef:'loop'});
// The consumed-prefix update is the actual back-edge source; incoming work is not.
let data=fixture([edge('rendered','render','advance'),back]);
let markers=projectLoopMarkers(data);
assert.deepEqual(markers.filter(m=>m.kind==='continue').map(m=>[m.sourceActionRef,m.edgeRefs]),[['advance',['back']]]);
assert.equal(markers.filter(m=>m.kind==='goto').length,0);
// A direct back edge remains visible without a predecessor; action exit also stays put.
data=fixture([back,edge('exit','advance','done','loop-exit',{readingScopeRef:'loop'})]);
markers=projectLoopMarkers(data);
assert.deepEqual(markers.filter(m=>m.kind==='continue'||m.kind==='exit').map(m=>[m.kind,m.sourceActionRef,m.edgeRefs]),[['continue','advance',['back']],['exit','advance',['exit']]]);
// A certified terminal-only exit reuses the existing return marker and keeps its edge.
data=fixture([back,edge('return','advance','terminal','loop-exit',{readingScopeRef:'loop'})],[{id:'terminal',kind:'terminal',outcome:'return'}]);
markers=projectLoopMarkers(data);
assert.deepEqual(markers.filter(m=>m.kind==='return').map(m=>[m.sourceActionRef,m.edgeRefs]),[['advance',['return']]]);
// A decision-sourced terminal exit is anchored at its same-guard member action.
data=fixture([
 back,
 edge('checked-none','advance','more','flow',{guards:[{decisionRef:'choice',value:'no'}]}),
 edge('return-none','more','terminal','loop-exit',{readingScopeRef:'loop',guards:[{decisionRef:'choice',value:'no'}]})
],[{id:'more',kind:'decision',decisionRef:'choice'},{id:'terminal',kind:'terminal',outcome:'return'}]);
markers=projectLoopMarkers(data);
assert.deepEqual(markers.filter(m=>m.kind==='return').map(m=>[m.sourceActionRef,m.edgeRefs]),[['advance',['checked-none','return-none']]]);
// A genuine boundary decision may still collapse, keeping guard-incompatible paths apart.
const guard=value=>[{decisionRef:'choice',value}];
data=fixture([
 edge('take','advance','boundary','flow',{guards:guard('yes')}),
 edge('skip','render','boundary','flow',{guards:guard('no')}),
 edge('back','boundary','check','loop-continue',{readingScopeRef:'loop',guards:guard('yes')}),
 edge('exit','boundary','done','loop-exit',{readingScopeRef:'loop',guards:guard('no')})
],[{id:'boundary',kind:'decision',decisionRef:'choice'}]);
markers=projectLoopMarkers(data);
assert.deepEqual(markers.filter(m=>m.kind==='continue'||m.kind==='exit').map(m=>[m.kind,m.sourceActionRef,m.edgeRefs]),[['continue','advance',['take','back']],['exit','render',['skip','exit']]]);
// Without a graph-backed entry, invent no loop route.
assert.deepEqual(projectLoopMarkers(fixture([edge('next','render','advance')])),[]);
// Optional real pilot regression: every action-owned loop edge retains its source.
if(process.argv[2]){
 const d=JSON.parse(fs.readFileSync(process.argv[2]));const ms=projectLoopMarkers(d);const nodes=new Map(d.execution.nodes.map(n=>[n.id,n]));let checked=0;
 for(const e of d.execution.edges){if(!['loop-continue','loop-exit'].includes(e.kind)||nodes.get(e.from)?.kind!=='action')continue;const kind=e.kind==='loop-continue'?'continue':'exit';const m=ms.find(m=>m.kind===kind&&m.scopeRef===e.readingScopeRef&&m.edgeRefs.includes(e.id));assert.ok(m,e.id);assert.equal(m.sourceActionRef,nodes.get(e.from).actionRef);assert.deepEqual(m.edgeRefs,[e.id]);checked++;}
 assert.ok(checked>0);console.log(JSON.stringify({realPilotEdges:checked}));
}
console.log(JSON.stringify({passed:true,regressionCases:6}));
