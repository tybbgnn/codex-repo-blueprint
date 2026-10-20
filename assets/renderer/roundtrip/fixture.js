import {loadInput,loadJsonUrl} from '../loader.mjs';
let model;try{model=await loadInput(await loadJsonUrl('renderer-input.json',new URL('../renderer-input.json',document.baseURI)));}catch(e){document.querySelector('#status').textContent='输入校验失败：'+e.message;throw e;}
export const {actors,messages,phases,segments,fixture,collectNodes,caseIndex,definitionNotes,initialState,display,dataKind,scopeAnnotations,purposeProjections,rootControls,rootAnchors,controls,data}=model;

// Local presentation sidecar; the validated v6.1 business input stays unchanged.
export const readingSummaries=(await loadJsonUrl('reading-summaries.json',new URL('../reading-summaries.json',document.baseURI))).units;
export const basicBlockDetails=await loadJsonUrl('basic-block-details.json',new URL('../basic-block-details.json',document.baseURI));

// An omitted branch outcome is carried by its single action's canonical summary.
for(const scope of data.readingScopes??[])for(const branch of scope.branches??[]){
 if(!branch.outcome&&!readingSummaries[branch.members[0]?.ref]?.text?.trim())throw Error('Missing branch/action outcome: '+branch.id);
}
