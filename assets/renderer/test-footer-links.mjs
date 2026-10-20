// Check the layout shipped as deliverable/, including its nested roundtrip entrypoint.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const root=path.resolve(process.argv[2]||fileURLToPath(new URL('.',import.meta.url)));
const entry=path.join(root,'roundtrip/index.html');
const footer=fs.readFileSync(entry,'utf8').match(/<footer\b[^>]*>([\s\S]*?)<\/footer>/i)?.[1];
assert(footer,'entrypoint has a footer');
const links=[...footer.matchAll(/<a\b[^>]*href=["']([^"']+)["']/gi)].map(m=>m[1]);
assert(links.length,'footer contains documentation links');
for(const href of links){
 const url=new URL(href,pathToFileURL(entry));
 assert.equal(url.protocol,'file:','footer documentation is shipped locally');
 const target=fileURLToPath(url);
 assert(target.startsWith(root+path.sep),'footer target stays within the published site');
 assert(fs.statSync(target).isFile(),`missing footer target: ${href}`);
 assert(fs.readFileSync(target,'utf8').trim(),`empty footer target: ${href}`);
}
console.log(`Footer links passed (${links.length})`);
