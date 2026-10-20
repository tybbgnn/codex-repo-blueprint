// Run against a generated real-flow input; mutate each mapping independently.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import shape from './schema-validator.mjs';
import {validateSource} from './contract.mjs';
const data=JSON.parse(fs.readFileSync(process.argv[2]));
assert(shape(data),JSON.stringify(shape.errors));
assert.deepEqual(validateSource(data),[]);
const attributeCase=structuredClone(data),oldStart=attributeCase.functionSource.startLine;
attributeCase.functionSource.startLine=oldStart-1;
attributeCase.functionSource.lines.unshift('    #[tracing::instrument(fields(item_count = items.len()))]');
attributeCase.functionSource.attributeLines={startLine:oldStart-1,endLine:oldStart-1};
attributeCase.sourceGroups[0].lineRanges=[{startLine:oldStart-1,startColumn:52,endLine:oldStart-1,endColumn:63}];
assert(shape(attributeCase),JSON.stringify(shape.errors));
assert.deepEqual(validateSource(attributeCase),[]);
attributeCase.functionSource.startLine=oldStart;
assert(validateSource(attributeCase).some(e=>e.path==='functionSource.attributeLines'));
const nodes=[...(data.prelude?.nodes??[]),...data.phases.flatMap(p=>[p,...p.goals.flatMap(g=>[g,...g.actions])]),...data.execution.nodes,...data.sourceGroups];
let checks=0;
for(const n of nodes){
 const saved=n.lineRanges,reason=n.sourceRangeReason;delete n.sourceRangeReason;
 for(const ranges of [[],[{startLine:data.functionSource.startLine-1,endLine:data.functionSource.endLine}],(saved.length?saved:[{startLine:data.functionSource.startLine,endLine:data.functionSource.startLine}]).flatMap(r=>[r,r])]){
  n.lineRanges=ranges;assert(validateSource(data).some(e=>e.path===n.id),n.id);checks++;
 }
 n.lineRanges=saved;if(reason)n.sourceRangeReason=reason;
}
const probe=data.phases[0].goals[0],savedRanges=probe.lineRanges,savedBroadRangeReason=probe.broadRangeReason;delete probe.broadRangeReason;
probe.lineRanges=[{startLine:data.functionSource.startLine,endLine:data.functionSource.endLine}];
assert(validateSource(data).some(e=>e.path===probe.id&&e.message.includes('25%')));checks++;
probe.broadRangeReason='Explicit reviewed aggregate responsibility';assert(!validateSource(data).some(e=>e.path===probe.id));checks++;
if(savedBroadRangeReason)probe.broadRangeReason=savedBroadRangeReason;else delete probe.broadRangeReason;probe.lineRanges=savedRanges;
const lines=data.functionSource.lines;data.functionSource.lines=lines.slice(1);
assert(validateSource(data).some(e=>e.path==='functionSource'));
data.functionSource.lines=lines;
const source=data.functionSource;delete data.functionSource;
assert(validateSource(data).some(e=>e.path==='functionSource'));
data.functionSource=source;
const withPrelude=structuredClone(data),basis=withPrelude.phases[0].goals[0].actions[0];
const shared=structuredClone(data);shared.execution.nodes[0].id=basis.id;
assert.deepEqual(validateSource(shared),[],'no-prelude reading/execution shared ID remains valid');
withPrelude.prelude={shellBodyId:'shell|stage|main',nodes:[{id:'prelude:entry',label:'入口',basicBlockRefs:['shell:bb4'],lineRanges:structuredClone(basis.lineRanges),broadRangeReason:basis.broadRangeReason}],relation:{shellBodyId:'shell|stage|main',innerDefPathHash:'a'.repeat(32),constructionBbRef:'shell:bb1',innerMirSha256:'a'.repeat(64),shellMirSha256:'b'.repeat(64),instrumentBbRefs:['shell:bb2'],intoFutureBbRefs:['shell:bb3'],pollBbRefs:['shell:bb4'],technicalBlocks:[]}};
assert(shape(withPrelude),JSON.stringify(shape.errors));assert.deepEqual(validateSource(withPrelude),[]);
const bare=structuredClone(withPrelude);bare.prelude.nodes[0].basicBlockRefs=['bb4'];assert.equal(shape(bare),false,'prelude rejects bare bbN');
const collide=structuredClone(withPrelude);collide.prelude.nodes[0].id=basis.id;assert(validateSource(collide).some(e=>e.message.includes('collides')),'prelude ID collision');
const duplicatePrelude=structuredClone(withPrelude);duplicatePrelude.prelude.nodes.push({...structuredClone(duplicatePrelude.prelude.nodes[0]),basicBlockRefs:['shell:bb5']});assert(validateSource(duplicatePrelude).some(e=>e.message.includes('collides')),'duplicate prelude ID');
console.log(JSON.stringify({passed:true,nodes:nodes.length,negativeChecks:checks+3,lines:lines.length}));
