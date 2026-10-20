import assert from 'node:assert/strict';
import {loadJsonUrl} from './loader.mjs';
const originalFetch=globalThis.fetch;
try{
 let calls=0;
 globalThis.fetch=async()=>{calls++;return {ok:true,json:async()=>({http:true})};};
 globalThis.__BLUEPRINT_DATA__={'renderer-input.json':{source:'embedded'}};
 assert.deepEqual(await loadJsonUrl('renderer-input.json',new URL('file:///page/renderer-input.json')),{source:'embedded'});
 assert.deepEqual(await loadJsonUrl('renderer-input.json',new URL('http://127.0.0.1/renderer-input.json')),{source:'embedded'});
 await assert.rejects(loadJsonUrl('missing.json',new URL('http://127.0.0.1/missing.json')),/Missing embedded/);
 assert.equal(calls,0);
 delete globalThis.__BLUEPRINT_DATA__;
 await assert.rejects(loadJsonUrl('renderer-input.json',new URL('file:///page/renderer-input.json')),/missing data.js/);
 assert.equal(calls,0,'file protocol must never reach fetch');
 assert.deepEqual(await loadJsonUrl('renderer-input.json',new URL('http://127.0.0.1/renderer-input.json')),{http:true});
 assert.equal(calls,1);
 globalThis.fetch=async()=>({ok:false,status:404});
 await assert.rejects(loadJsonUrl('renderer-input.json',new URL('http://127.0.0.1/renderer-input.json')),/HTTP 404/);
 console.log('Embedded data and HTTP-only fallback passed');
}finally{globalThis.fetch=originalFetch;delete globalThis.__BLUEPRINT_DATA__;}
