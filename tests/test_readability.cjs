// Real-browser regression for semantic labels, wrapping and compact source markers.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
(async()=>{
 const url=process.argv[2],dir=process.argv[3];if(dir)fs.mkdirSync(dir,{recursive:true});
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_PATH?{executablePath:process.env.BROWSER_PATH}:{})});
 const report={checks:[],errors:[]};const check=(name,ok)=>{assert(ok,name);report.checks.push(name)};
 try{
  for(const width of [1440,1000])for(const mutate of [false,true]){
   const page=await browser.newPage({viewport:{width,height:900}});page.on('pageerror',e=>report.errors.push(e.message));
   if(mutate)await page.route('**/renderer-input.json',async route=>{
    const response=await route.fetch(),d=await response.json();
    const long='保留配置并等待上下文准备完成，然后交付当前请求的业务结果和下一步处理所需信息'.repeat(5);
    d.phases[0].label=long;d.phases[0].goals[0].label=long;d.phases[0].goals[0].actions[0].label=long;
    await route.fulfill({response,json:d});
   });
   await page.goto(url,{waitUntil:'networkidle'});
   await page.waitForSelector('#selection .bb-code-line');
   const d=await (await page.request.get(new URL('../renderer-input.json',url).href)).json();
   await page.locator('[data-y="3"]').click();await page.locator('[data-x="2"]').click();
   check('no bare local alt headings',!(await page.locator('.control-semantic.kind-alt').allTextContents()).some(s=>s.trim()==='alt'));
   const labels=await page.locator('[data-action]').evaluateAll(es=>es.map(e=>({id:e.dataset.sourceAction,label:e.querySelector('[data-semantic-label]')?.textContent})));
   check('action labels have semantic slots',labels.every(r=>r.label?.trim()));
   if(!mutate)assert.deepEqual(labels.map(r=>[r.id,r.label]),d.phases.flatMap(p=>p.goals.flatMap(g=>g.actions.map(a=>[a.id,a.label]))));
   check('phase rails use ordinals',(await page.locator('.frame-tag').allTextContents()).every(s=>/^阶段 \d+$/.test(s)));
   check('message rows preserved',await page.locator('[data-message]').count()===d.messages.length);
   const failures=await page.locator('.phase,.goal,.action').evaluateAll(es=>es.flatMap(e=>{
    const label=e.querySelector(':scope > span'),r=e.getBoundingClientRect(),l=label.getBoundingClientRect();
    return l.top<r.top-1||l.bottom>r.bottom+1||label.scrollWidth>label.clientWidth+2?[{text:label.textContent,rect:r.toJSON(),label:l.toJSON()}]:[];
   }));
   assert.deepEqual(failures,[],'heading wraps within measured row');report.checks.push('heading wraps within measured row');
   const overlap=await page.evaluate(()=>{
    const rows=[...document.querySelectorAll('.phase,.goal,.action,.flow-note,.control-semantic,.segment-condition,.loop-marker-row,.message')].map(e=>({e,r:e.getBoundingClientRect()})).sort((a,b)=>a.r.top-b.r.top);
    return rows.slice(1).filter((x,i)=>x.r.top<rows[i].r.bottom-1).map(x=>x.e.textContent);
   });
   assert.deepEqual(overlap,[],'reading rows do not overlap');report.checks.push('reading rows do not overlap');
   await page.locator('[data-source-action]').first().click();
   check('compact range markers',(await page.locator('.bb-range-label').allTextContents()).every(s=>/^片段 \d+ · L\d+(–\d+)?$/.test(s)));
   check('full function preserved',await page.locator('.bb-code-line').count()===d.functionSource.lines.length);
   const title=await page.locator('h1').evaluate(e=>e.scrollWidth<=e.clientWidth+1);
   check('title fits viewport width',title);
   if(dir)await page.screenshot({path:path.join(dir,`${width}-${mutate?'long':'original'}.png`)});
   const beforeWidth=await page.locator('.action > span').first().evaluate(e=>parseFloat(e.style.maxWidth));
   await page.setViewportSize({width:width===1440?1000:1440,height:900});
   await page.waitForFunction(previous=>parseFloat(document.querySelector('.action > span').style.maxWidth)!==previous,beforeWidth);
   const afterWidth=await page.locator('.action > span').first().evaluate(e=>parseFloat(e.style.maxWidth));
   check('resize recomputes reading width',width===1440?afterWidth<beforeWidth:afterWidth>beforeWidth);
   const contained=await page.locator('.phase,.goal,.action').evaluateAll(es=>es.every(e=>e.querySelector(':scope > span').getBoundingClientRect().bottom<=e.getBoundingClientRect().bottom+1));
   check('resize preserves measured row heights',contained);

   await page.close();
  }
  check('no browser exceptions',report.errors.length===0);report.passed=true;
 }catch(e){report.passed=false;report.failure=e.stack;throw e;}
 finally{if(dir)fs.writeFileSync(path.join(dir,'readability.json'),JSON.stringify(report,null,2));await browser.close();}
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1});
