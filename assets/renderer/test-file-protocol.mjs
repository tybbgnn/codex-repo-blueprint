// Build a fresh published fixture, then exercise file:// and HTTP in Chrome.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const require=createRequire(import.meta.url);
const renderer=fileURLToPath(new URL('.',import.meta.url));
const fixture=path.resolve(process.argv[2]||process.env.BLUEPRINT_FIXTURE||'renderer-input.json');
const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'blueprint-file-test-'));
const candidate=path.join(scratch,'candidate');fs.cpSync(renderer,candidate,{recursive:true});
for(const name of ['renderer-input.json','reading-summaries.json','basic-block-details.json'])fs.copyFileSync(path.join(path.dirname(fixture),name),path.join(candidate,name));
for(const name of ['roundtrip/index.html','roundtrip/render-config.js']){
 const file=path.join(candidate,name);fs.writeFileSync(file,fs.readFileSync(file,'utf8').replaceAll('__SYMBOL__','fixture').replaceAll('__SOURCE_FILE__','fixture.rs').replaceAll('__MODULE__','fixture').replaceAll('__CRATE__','fixture'));
}
const delivery=path.join(scratch,'deliverable');
execFileSync(process.env.PYTHON||'python3',['-B','-c','import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from publish_site import assemble; assemble(Path(sys.argv[2]),Path(sys.argv[3]))',path.resolve(renderer,'../../scripts'),candidate,delivery]);
console.log(JSON.stringify(await require('../../tests/test_file_protocol.cjs').verify(delivery)));
// Keep generated fixtures for inspection; never remove user or test artifacts.
