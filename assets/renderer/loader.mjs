import {assertInput,collectNodes} from './contract.mjs';
export async function loadInput(candidate){const data=await assertInput(candidate),controls=new Map(data.controls.map(c=>[c.id,c]));
const phases=data.phases.map(p=>({...p,goals:p.goals.map(g=>({...g,actions:g.actions.map(a=>({...a,children:a.controlRefs.map(id=>controls.get(id)),messages:collectNodes(a.controlRefs.map(id=>controls.get(id))).flatMap(n=>n.messages??[])}))})),boundaryControls:p.boundaryControlRefs.map(id=>controls.get(id))}));
return {...data,data,phases,rootControls:data.rootControlRefs.map(id=>controls.get(id)),collectNodes};}
export async function loadInputUrl(url){const r=await fetch(url);if(!r.ok)throw Error('HTTP '+r.status);return loadInput(await r.json());}

// Published pages carry data locally. Never attempt a file:// fetch.
export async function loadJsonUrl(name,url){
 const embedded=globalThis.__BLUEPRINT_DATA__;
 if(embedded){if(!Object.hasOwn(embedded,name))throw Error('Missing embedded data: '+name);return embedded[name];}
 if(!['http:','https:'].includes(url.protocol))throw Error('Open a published deliverable (missing data.js)');
 const response=await fetch(url);if(!response.ok)throw Error('HTTP '+response.status);return response.json();
}
