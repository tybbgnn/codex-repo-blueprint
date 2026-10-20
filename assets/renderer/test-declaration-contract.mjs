// Integration regression: pass any valid real-flow fixture with an external body actor.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {validateInput} from './contract.mjs';
const original=JSON.parse(fs.readFileSync(process.argv[2]));
assert((await validateInput(original)).valid,'baseline fixture must pass');
const flatten=xs=>xs.flatMap(a=>[a,...flatten(a.children??[])]);
const candidate=structuredClone(original);
const actor=flatten(candidate.actors).find(a=>a.kind==='body'&&a.actorId!==candidate.semanticRoot.actorRef);
assert(actor,'external body required');
const id=actor.actorId, hash='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
Object.assign(actor,{kind:'declaration',declarationRef:hash,sourceNodeRef:hash,implementationStatus:'unresolved'});delete actor.bodyRef;
candidate.fixture.actors=structuredClone(candidate.actors);
for(const n of candidate.execution.nodes)n.label='有源码依据的执行节点';
assert((await validateInput(candidate)).valid,'declaration with explicit unresolved implementation is a valid callable endpoint');
for(const [name,change] of [
 ['fabricated body',a=>a.bodyRef=hash+'|stage|main'],
 ['missing declaration',a=>delete a.declarationRef],
 ['missing status',a=>delete a.implementationStatus],
 ['mismatched source',a=>a.sourceNodeRef='aaaaaaaa'],
 ['non-callable endpoint',a=>{a.kind='module';delete a.declarationRef;delete a.implementationStatus;}],
]){
 const d=structuredClone(candidate);change(flatten(d.actors).find(a=>a.actorId===id));d.fixture.actors=structuredClone(d.actors);
 assert(!(await validateInput(d)).valid,name);
}
console.log(JSON.stringify({passed:true,positive:2,negative:5}));
