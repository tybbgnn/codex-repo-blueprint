// Real-browser regression for source reachability and selection; no npm install required.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {fileURLToPath}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const url=process.argv[2]||'http://127.0.0.1:8765/roundtrip/';
const shots=process.argv[3];
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_PATH?{executablePath:process.env.BROWSER_PATH}:{})});
 const report={checks:[],errors:[]};
 const check=(name,ok)=>{assert(ok,name);report.checks.push(name)};
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
  await page.goto(url,{waitUntil:'networkidle'});
  // Async input validation can continue after the network is idle. Wait for
  // initialization, then assert exact line content/count (including truncation).
  await page.waitForSelector('#selection .bb-code-line');
  const d=await page.evaluate(()=>window.__BLUEPRINT_DATA__?.['renderer-input.json'])||await (await page.request.get(new URL('../renderer-input.json',url).href)).json();
  const source=d.functionSource;
  if(shots)fs.mkdirSync(shots,{recursive:true});
  const shot=async name=>{if(shots)await page.screenshot({path:path.join(shots,name+'.png')});};
  const lines=()=>page.locator('.bb-code-line');
  async function full(){
   check('full function rows',await lines().count()===source.endLine-source.startLine+1);
   assert.deepEqual(await page.locator('.bb-line-text').allTextContents(),source.lines);
  }
  async function selectedPrelude(node){
   await full();
   check('prelude selection persists',await page.locator('#selection').getAttribute('data-source-node')===node.id);
   check('prelude BB refs stay namespaced',(await page.locator('.bb-list').textContent()).includes('shell:bb'));
   if(node.lineRanges.length)check('prelude source highlight',await page.locator('.source-highlight,.source-column-highlight').count()>0);
  }
  await full();
  check('default has no highlight',await page.locator('.source-highlight').count()===0);
  check('default begins at signature',await page.locator('.bb-source-scroll').evaluate(e=>e.scrollTop)===0);
  if(d.prelude){const prelude=d.prelude.nodes[0];await page.locator('.bb-node-picker select').selectOption(prelude.id);await selectedPrelude(prelude);}
  await shot('default');
  // Prefer a disjoint goal near the end of the function: catches the original overflow.
  const goals=d.phases.flatMap(p=>p.goals);
  const goal=goals.filter(g=>g.lineRanges.length>1).sort((a,b)=>b.lineRanges[0].startLine-a.lineRanges[0].startLine)[0]||goals[0];
  await page.locator('[data-y="1"]').click();
  await page.locator(`[data-source-goal="${goal.id}"]`).click();
  async function selected(node){
   await full();
   const expected=node.lineRanges.flatMap(r=>Array.from({length:r.endLine-r.startLine+1},(_,i)=>r.startLine+i));
   // Column-precise attribute highlights are <mark> inside an unhighlighted row: map each to its code line.
   const actual=await page.locator('.source-highlight').evaluateAll(es=>[...new Set(es.map(e=>Number(e.closest('.bb-code-line').dataset.line)))]);
   assert.deepEqual(actual,expected,node.id+' all disjoint ranges highlighted');
   check('one named marker per range',await page.locator('.bb-range-label').count()===node.lineRanges.length);
   if(node.lineRanges.length)check('marker identifies selected node',await page.locator('.bb-range-label').first().getAttribute('title')===node.id);
   check('BB list collapsed',!await page.locator('.bb-blocks').evaluate(e=>e.open));
   check('BB total', (await page.locator('.bb-blocks summary').textContent()).includes(String(node.basicBlockRefs.length)));
   if(!node.lineRanges.length)return;
   const geometry=await page.evaluate(()=>{
    const pre=document.querySelector('.bb-source-scroll'),r=pre.getBoundingClientRect(),first=document.querySelector('.source-highlight').getBoundingClientRect();
    return {height:pre.clientHeight,top:first.top,bottom:r.bottom,scrollTop:pre.scrollTop,viewTop:r.top};
   });
   check('code scrollport stays readable',geometry.height>=140);
   check('first highlighted line auto-scrolled into view',geometry.top>=geometry.viewTop&&geometry.top<geometry.bottom);
   report.lastGeometry=geometry;
  }
  await selected(goal);await shot('goal-selected');
  const action=goal.actions.find(a=>a.lineRanges.length>1)||goal.actions[0];
  await page.locator(`[data-source-action="${action.id}"]`).click();
  await selected(action);await shot('action-selected');
  const exec=d.execution.nodes.find(n=>n.actionRef===action.id)||d.execution.nodes.find(n=>n.lineRanges.length>1);
  await page.locator('.bb-node-picker select').selectOption(exec.id);
  await selected(exec);await shot('exec-node-selected');
  // Every mapping stays rendered; expanding a long BB list cannot consume the code pane.
  await page.locator('.bb-blocks summary').click();
  check('expanded BB list',await page.locator('.bb-blocks').evaluate(e=>e.open));
  check('expanded list preserves readable code',await page.locator('.bb-source-scroll').evaluate(e=>e.clientHeight>=140));
  await page.locator('.bb-blocks summary').click();
  const pre=page.locator('.bb-source-scroll');
  // Playwright mouse.wheel returns before dispatch/compositor scrolling ends.
  // Start away from the bottom so scrollend is guaranteed for scrollable source.
  await pre.evaluate(e=>{e.scrollTop=0});
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  await pre.evaluate(e=>{
   window.sourceWheelDone=e.scrollHeight<=e.clientHeight;let received=false;
   e.addEventListener('wheel',()=>{received=true},{once:true});
   const ended=()=>{if(received){window.sourceWheelDone=true;e.removeEventListener('scrollend',ended)}};
   e.addEventListener('scrollend',ended);
  });
  await pre.hover();await page.mouse.wheel(0,100000);
  await page.waitForFunction(()=>window.sourceWheelDone);
  await page.waitForFunction(()=>{const e=document.querySelector('.bb-source-scroll');return e.scrollTop+e.clientHeight>=e.scrollHeight-2});
  const last=await lines().last().boundingBox(),box=await pre.boundingBox();
  check('wheel reaches final source line',last.y>=box.y&&last.y+last.height<=box.y+box.height);
  await shot('scrolled-bottom');
  const hasSourceGroups=d.sourceGroups.length>0;
  let group;
  if(hasSourceGroups){
   group=d.sourceGroups.find(g=>g.lineRanges.length>1)||d.sourceGroups[0]||goal;
   await page.locator('.bb-node-picker select').selectOption(group.id);await selected(group);
  }else{
   group=exec;
   const goalNode=page.locator(`[data-source-goal="${goal.id}"]`);
   if(!await goalNode.isVisible())await page.locator('[data-y="1"]').click();
   await goalNode.click();await selected(goal);
   await page.locator('[data-x="0"]').click();
   check(`zero-sourceGroups ${goal.id} redraw preserves selection`,await page.locator('#selection').getAttribute('data-source-node')===goal.id);
   const actionNode=page.locator(`[data-source-action="${action.id}"]`);
   if(!await actionNode.isVisible())await page.locator('[data-y="2"]').click();
   await actionNode.click();await selected(action);
   await page.locator('[data-x="0"]').click();
   check(`zero-sourceGroups ${action.id} redraw preserves selection`,await page.locator('#selection').getAttribute('data-source-node')===action.id);
   await page.locator('.bb-node-picker select').selectOption(exec.id);await selected(exec);
   await page.locator('[data-x="0"]').click();
   check(`zero-sourceGroups ${exec.id} redraw preserves selection`,await page.locator('#selection').getAttribute('data-source-node')===exec.id);
   await page.locator('.bb-node-picker select').selectOption(exec.id);await selected(group);
  }
  // Re-rendering unrelated diagram controls must preserve the selected source and scroll.
  // Move away from the selection target: a redraw must not reset user scrolling.
  await pre.evaluate(e=>{e.scrollTop=Math.min(e.scrollHeight-e.clientHeight, e.scrollTop+137)});
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  const before=await pre.evaluate(e=>e.scrollTop);await page.locator('[data-x="0"]').click();
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
  check('diagram redraw preserves source selection',await page.locator('#selection').getAttribute('data-source-node')===group.id);
  check('diagram redraw preserves source scroll',Math.abs(await pre.evaluate(e=>e.scrollTop)-before)<2);
  // A wheel default action can still be animating when selection changes. Start
  // at the bottom (so a bottom predicate cannot accidentally wait for it), then
  // change selection and redraw on the very next animation frame. No sleeps.
  await page.evaluate(async ({execId,groupId})=>{
   const {showBasicBlocks}=window.__BLUEPRINT_UI__||await import('./bb-details.js?v=sidebar-1');
   const pre=document.querySelector('.bb-source-scroll');
   const select=id=>{
    const picker=document.querySelector('.bb-node-picker select');
    picker.value=id;picker.dispatchEvent(new Event('change',{bubbles:true}));
   };
   select(execId);pre.scrollTop=pre.scrollHeight;
   window.sourceRedrawRace=null;
   pre.addEventListener('wheel',()=>requestAnimationFrame(()=>{
    select(groupId);
    pre.scrollTop=Math.min(pre.scrollHeight-pre.clientHeight,pre.scrollTop+137);
    const before=pre.scrollTop,code=pre.querySelector('code'),samples=[];
    let frames=0;
    const sample=()=>{
     // Exercise actor depth, reading depth and zoom through real UI handlers.
     if(frames===0)document.querySelector('[data-x="0"]').click();
     if(frames===4)document.querySelector('[data-y="3"]').click();
     if(frames===8){const zoom=document.querySelector('#zoom');zoom.value='.85';zoom.dispatchEvent(new Event('change'));}
     showBasicBlocks(groupId); // Repeated selection must not re-center the pane.
     samples.push(pre.scrollTop);
     if(++frames<12)return requestAnimationFrame(sample);
     window.sourceRedrawRace={before,samples,sameCode:code===pre.querySelector('code'),node:document.querySelector('#selection').dataset.sourceNode};
    };
    sample();
   }),{once:true});
  },{execId:exec.id,groupId:group.id});
  await pre.hover();await page.mouse.wheel(0,100000);
  await page.waitForFunction(()=>window.sourceRedrawRace);
  report.scrollRedrawRace=await page.evaluate(()=>window.sourceRedrawRace);
  check('wheel/selection/redraw preserves source DOM',report.scrollRedrawRace.sameCode);
  check('wheel/selection/redraw preserves selection',report.scrollRedrawRace.node===group.id);
  check('wheel/selection/redraw preserves every frame of user scroll',report.scrollRedrawRace.samples.every(top=>Math.abs(top-report.scrollRedrawRace.before)<2));
  await page.locator('#zoom').selectOption('1');
  // Footer links must resolve inside a disposable site, including when mounted
  // below a URL prefix or visited through roundtrip/index.html.
  const footerLinks=await page.locator('footer a[href]').evaluateAll(es=>es.map(e=>e.href));
  check('footer has documentation link',footerLinks.length>0);
  for(const href of footerLinks){
   check('footer link stays local',new URL(href).origin===new URL(url).origin);
   if(new URL(href).protocol==='file:'){check('footer file is nonempty',fs.readFileSync(fileURLToPath(href),'utf8').trim().length>0);continue;}
   const response=await page.request.get(href);
   check('footer documentation returns HTTP 200',response.status()===200);
   check('footer documentation is nonempty',(await response.text()).trim().length>0);
  }
  await page.locator('.phase').first().click();
  await full();check('phase clears highlight',await page.locator('.source-highlight').count()===0);
  // Check the original tall-list goal at a smaller viewport too.
  await page.setViewportSize({width:1100,height:720});
  await page.locator('[data-y="1"]').click();await page.locator(`[data-source-goal="${goal.id}"]`).click();await selected(goal);
  await page.locator('.bb-blocks summary').click();
  check('smaller viewport expanded list keeps scrollport',await pre.evaluate(e=>e.clientHeight>=120));
  check('no browser exceptions',report.errors.length===0);
  report.passed=true;report.selected={goal:goal.id,action:action.id,execution:exec.id,group:hasSourceGroups?group.id:null};
 }catch(e){report.passed=false;report.failure=e.stack;throw e;}
 finally{
  if(shots)fs.writeFileSync(path.join(shots,'browser-check.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));await browser.close();
 }
})().catch(e=>{console.error(e);process.exitCode=1});
