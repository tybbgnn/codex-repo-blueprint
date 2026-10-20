import assert from 'node:assert/strict';
import fs from 'node:fs';
import shape from './schema-validator.mjs';
import {validateTerminalOnly} from './execution.mjs';

const cert={certificateKind:'terminal-loop',version:1,rawSha256:'a'.repeat(64),scopeId:'loop',
 memberBBs:['bb0'],exitEdges:[{from:'bb0',to:'bb1'}],terminalBBs:['bb9'],blocks:[]};
const scope={id:'loop',kind:'loop',members:[{kind:'action',ref:'a'}],terminalOnly:{proofRef:'proof',terminalNodeRefs:['done'],exitEdgeRefs:['exit']}};
const data={phases:[{id:'p',goals:[{id:'g',actions:[{id:'a',basicBlockRefs:['bb0']}]}]}],readingScopes:[scope],execution:{
 artifacts:[{id:'mir',format:'mir',sha256:'a'.repeat(64),content:'{}'},{id:'proof',format:'icfg',sha256:'b'.repeat(64),content:JSON.stringify(cert)}],evidence:[],
 nodes:[{id:'member',kind:'action',actionRef:'a'},{id:'done',kind:'terminal',outcome:'return',basicBlockRefs:['bb9']}],
 edges:[{id:'exit',from:'member',to:'done',kind:'loop-exit',readingScopeRef:'loop'}]}};
assert.deepEqual(validateTerminalOnly(data),[]);
const shellRef=structuredClone(data);shellRef.phases[0].goals[0].actions[0].basicBlockRefs=['shell:bb0'];
assert(validateTerminalOnly(shellRef).some(e=>e.code==='execution.terminalLoopNamespace'),'terminal loop rejects shell namespace');
const decisionData=structuredClone(data);
decisionData.execution.nodes.splice(1,0,{id:'choice',kind:'decision',decisionRef:'more',basicBlockRefs:['bb0']});
decisionData.execution.edges=[
 {id:'arrive',from:'member',to:'choice',kind:'flow',guards:[{decisionRef:'more',value:'none'}]},
 {id:'exit',from:'choice',to:'done',kind:'loop-exit',readingScopeRef:'loop',guards:[{decisionRef:'more',value:'none'}]},
];
assert.deepEqual(validateTerminalOnly(decisionData),[],'member-backed decision exit is valid');
for(const [name,change,code] of [
 ['wrong scope',d=>JSON.parse(d.execution.artifacts[1].content).scopeId='other','execution.terminalLoopProof'],
 ['pending terminal',d=>d.execution.nodes[1].outcome='suspend','execution.terminalLoopNode'],
 ['wrong loop',d=>d.execution.nodes[0].actionRef='other','execution.terminalLoopEdge'],
 ['unlisted exit',d=>d.execution.edges.push({id:'extra',from:'member',to:'done',kind:'loop-exit',readingScopeRef:'loop'}),'execution.terminalLoopCoverage'],
 ['both modes',d=>d.readingScopes[0].commonAfter={actionRef:'after',label:'after',arrivals:[]},'execution.terminalLoopExclusive'],
]){
 const d=structuredClone(data);if(name==='wrong scope'){const parsed=JSON.parse(d.execution.artifacts[1].content);parsed.scopeId='other';d.execution.artifacts[1].content=JSON.stringify(parsed);}else change(d);
 assert(validateTerminalOnly(d).some(e=>e.code===code),name);
}
for(const [name,change,code] of [
 ['decision outside scope',d=>d.execution.nodes.find(n=>n.id==='choice').basicBlockRefs=['bb7'],'execution.terminalLoopEdge'],
 ['decision exit unlisted',d=>d.readingScopes[0].terminalOnly.exitEdgeRefs=[],'execution.terminalLoopCoverage'],
 ['decision exit non-terminal',d=>{d.execution.nodes.find(n=>n.id==='done').kind='action';d.execution.nodes.find(n=>n.id==='done').actionRef='a';},'execution.terminalLoopNode'],
]){
 const d=structuredClone(decisionData);change(d);assert(validateTerminalOnly(d).some(e=>e.code===code),name);
}
const fixture=JSON.parse(fs.readFileSync(process.argv[2]));
const action=fixture.phases[0].goals[0].actions[0];
fixture.readingScopes.push({id:'schema-loop',kind:'loop',condition:'x',members:[{kind:'action',ref:action.id}],parentScopeRef:null,
 decision:{variable:'x',values:['continue','exit']},repeat:{entryActionRef:action.id,continueValues:['continue'],exitValues:['exit'],continue:'again',exit:'done',limit:'input'},
 commonAfter:{actionRef:action.id,label:'after',arrivals:[{path:'exit',condition:'done'}]},terminalOnly:{proofRef:'proof',terminalNodeRefs:['done'],exitEdgeRefs:['exit']}});
assert.equal(shape(fixture),false,'schema rejects commonAfter + terminalOnly');
console.log(JSON.stringify({passed:true,positive:2,negative:9}));
