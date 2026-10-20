// Real Chrome, default file security; temporary HTTP listener always closed.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {pathToFileURL,fileURLToPath}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
async function verify(deliverable){
 const root=path.resolve(deliverable),entry=path.join(root,'roundtrip/index.html');
 const expected=JSON.parse(fs.readFileSync(path.join(root,'renderer-input.json')));
 const server=http.createServer((req,res)=>{
  try{
   const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
   const target=path.resolve(root,'.'+name);
   assert(target.startsWith(root+path.sep));
   const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.md':'text/plain'};
   res.writeHead(200,{'Content-Type':types[path.extname(target)]||'application/octet-stream'});res.end(fs.readFileSync(target));
  }catch(e){res.writeHead(404);res.end('Not found');}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 let browser;const results=[];
 try{
  browser=await chromium.launch({headless:true,...(process.env.BROWSER_PATH?{executablePath:process.env.BROWSER_PATH}:{})});
  for(const url of [pathToFileURL(entry).href,`http://127.0.0.1:${server.address().port}/roundtrip/index.html`]){
   const page=await browser.newPage();const errors=[];const requests=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
   page.on('requestfailed',r=>errors.push(r.url()+': '+r.failure()?.errorText));
   page.on('request',r=>requests.push(r.url()));
   page.on('response',r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);});
   await page.goto(url,{waitUntil:'load'});
   await page.waitForSelector('#selection .bb-code-line',{timeout:120000});
   assert(await page.locator('#diagram .phase').count()>0,'page renders phase nodes');
   assert.equal(await page.locator('.bb-code-line').count(),expected.functionSource.lines.length);
   for(const name of ['renderer-input.json','reading-summaries.json','basic-block-details.json']){
    assert.deepEqual(await page.evaluate(name=>window.__BLUEPRINT_DATA__[name],name),JSON.parse(fs.readFileSync(path.join(root,name))));
   }
   const goal=expected.phases.flatMap(p=>p.goals).find(g=>g.lineRanges.length);
   assert(goal,'fixture has a selectable goal');
   await page.locator('[data-y="1"]').click();
   await page.locator(`[data-source-goal="${goal.id}"]`).click();
   assert.equal(await page.locator('#selection').getAttribute('data-source-node'),goal.id);
   assert(await page.locator('.source-highlight').count()>0,'sidebar highlights source');
   await page.locator('.bb-blocks summary').click();
   assert(await page.locator('.bb-blocks').evaluate(e=>e.open),'sidebar BB list opens');
   await page.locator('.phase').first().click();
   assert.equal(await page.locator('.source-highlight').count(),0);
   const links=await page.locator('a[href],script[src],link[href]').evaluateAll(es=>es.map(e=>e.href||e.src));
   for(const link of links){
    if(link.startsWith('data:'))continue;
    const parsed=new URL(link);assert.equal(parsed.protocol,new URL(url).protocol);
    if(parsed.protocol==='file:')assert(fs.statSync(fileURLToPath(parsed)).isFile(),link);
    else{assert.equal(parsed.origin,new URL(url).origin);assert.equal((await page.request.get(link)).status(),200,link);}
   }
   assert(!requests.some(u=>/\.json(?:$|\?)/.test(u)),'embedded data avoids fetch on both protocols');
   assert.deepEqual(errors,[],'no console, page, resource or request errors');
   results.push({protocol:new URL(url).protocol,passed:true,nodes:await page.locator('#diagram .phase').count(),links:links.length,errors});
   await page.close();
  }
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
 return {deliverable:root,passed:true,results};
}
module.exports={verify};
if(require.main===module)verify(process.argv[2]).then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e);process.exitCode=1});
