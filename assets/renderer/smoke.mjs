import {actionLabelFailures} from './display-labels.mjs';
// Standard-library DOM smoke; no browser/pixel-layout claim.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const site=path.resolve(process.argv[2]||'.'),reportPath=process.argv[3];
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
const camel=s=>s.replace(/-([a-z])/g,(_,x)=>x.toUpperCase());
class Element{
 constructor(tag='div',attrs={}){this.tagName=tag.toUpperCase();this.attrs={...attrs};this.children=[];this.parentElement=null;this._text='';this.style={setProperty(k,v){this[k]=v}};this.listeners={};this.scrollLeft=0;this.scrollTop=0;this.clientWidth=1200;this.clientHeight=900;this.value='1';this.dataset=new Proxy({}, {get:(_,k)=>this.attrs['data-'+String(k).replace(/[A-Z]/g,x=>'-'+x.toLowerCase())],set:(_,k,v)=>{this.attrs['data-'+String(k).replace(/[A-Z]/g,x=>'-'+x.toLowerCase())]=v;return true}});this.classList={toggle:(c,on)=>{const xs=this.className.split(' ').filter(x=>x!==c);if(on)xs.push(c);this.className=xs.join(' ')},add:(c)=>this.className+=' '+c,remove:(c)=>this.className=this.className.split(' ').filter(x=>x!==c).join(' ')};}
 set className(x){this.attrs.class=x}get className(){return this.attrs.class||''}
 set innerHTML(html){this.children=[];this._text='';parse(html,this)}get innerHTML(){return this._text+this.children.map(x=>x.outerHTML).join('')}
 get outerHTML(){if(this.tagName==='#TEXT')return this._text;return '<'+this.tagName.toLowerCase()+' '+Object.entries(this.attrs).map(([k,v])=>k+'="'+v+'"').join(' ')+'>'+this.innerHTML+'</'+this.tagName.toLowerCase()+'>'}
 set textContent(x){this.children=[];this._text=String(x)}get textContent(){return this._text+this.children.map(x=>x.textContent).join('')}
 get innerText(){return this.textContent}
 set open(v){this._open=v;for(const f of this.listeners.toggle||[])f({target:this})}get open(){return this._open}
 removeAttribute(k){delete this.attrs[k]}
 prepend(x){x.remove();x.parentElement=this;this.children.unshift(x)}
 setAttribute(k,v){this.attrs[k]=String(v)}getAttribute(k){return this.attrs[k]}
 append(x){x.remove();x.parentElement=this;this.children.push(x)}appendChild(x){this.append(x)}
 replaceChildren(...xs){this.children=[];this._text='';for(const x of xs)this.append(x)}
 get firstChild(){return this.children[0]}
 remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(x=>x!==this);this.parentElement=null}
 querySelectorAll(selector){let result=[];for(const x of this.children){if(matches(x,selector))result.push(x);result.push(...x.querySelectorAll(selector));}return [...new Set(result)]}
 querySelector(s){return this.querySelectorAll(s)[0]||null}
 closest(s){return matches(this,s)?this:this.parentElement?.closest(s)||null}
 addEventListener(name,f){(this.listeners[name]??=[]).push(f)}
 click(){this.onclick?.({target:this});let at=this;while(at){for(const fn of at.listeners.click||[])fn({target:this});at=at.parentElement}}
 getBoundingClientRect(){let width=parseFloat(this.style.width)||1200,left=parseFloat(this.style.left)||0,top=parseFloat(this.style.top)||0,height=this.tagName==='#TEXT'?0:Math.max(24,Math.ceil(this.textContent.length/Math.max(20,width/8))*20);return {left,right:left+width,top,bottom:top+height,width,height}}
 scrollTo(v){this.scrollLeft=v.left||0;this.scrollTop=v.top||0}setPointerCapture(){}hasPointerCapture(){return false}releasePointerCapture(){}
}
function matches(el,selector){return selector.split(',').some(sel=>{
 const parts=sel.trim().split(/\s+/);if(parts.length>1){if(!matches(el,parts.pop()))return false;let p=el.parentElement;while(p){if(matches(p,parts.join(' ')))return true;p=p.parentElement}return false;}
 sel=parts[0];if(el.tagName==='#TEXT')return false;const tag=sel.match(/^[A-Za-z][\w-]*/)?.[0];if(tag&&el.tagName!==tag.toUpperCase())return false;
 for(const m of sel.matchAll(/#([\w-]+)/g))if(el.attrs.id!==m[1])return false;
 for(const m of sel.matchAll(/\.([\w-]+)/g))if(!el.className.split(/\s+/).includes(m[1]))return false;
 for(const m of sel.matchAll(/\[([^\]=]+)(?:=["']?([^\]"']+)["']?)?\]/g))if(!Object.hasOwn(el.attrs,m[1])||m[2]!==undefined&&el.attrs[m[1]]!==m[2])return false;
 return true;
})}
function parse(html,root){const stack=[root];for(const token of html.match(/<!--[\s\S]*?-->|<[^>]+>|[^<]+/g)||[]){if(token.startsWith('<!--')||token.startsWith('<!'))continue;if(token.startsWith('</')){if(stack.length>1)stack.pop();continue;}if(token.startsWith('<')){const name=token.match(/^<([\w-]+)/)?.[1];if(!name)continue;const attrs={};for(const m of token.slice(name.length+1,-1).matchAll(/([^\s=]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g))attrs[m[1]]=decode(m[2]??m[3]??m[4]??'');let el=new Element(name,attrs);stack.at(-1).append(el);if(!['meta','link','input','br','hr','img'].includes(name)&&!token.endsWith('/>'))stack.push(el);}else{const e=new Element('#text');e._text=decode(token);stack.at(-1).append(e);}}}
const document=new Element('document');document.baseURI='http://localhost/roundtrip/index.html';document.body=new Element('body');document.append(document.body);parse(fs.readFileSync(path.join(site,'roundtrip/index.html'),'utf8'),document.body);document.createElement=tag=>new Element(tag);
let accesses=[];const context=vm.createContext({document,console,crypto:webcrypto,TextEncoder,URL,ResizeObserver:class{constructor(f){this.f=f}observe(){}},fetch:async url=>{const u=new URL(url);const rel=decodeURIComponent(u.pathname.replace(/^\//,''));const f=path.resolve(site,rel);if(!f.startsWith(site+path.sep))throw Error('escape');accesses.push(f);return{ok:fs.existsSync(f),status:fs.existsSync(f)?200:404,json:async()=>JSON.parse(fs.readFileSync(f,'utf8')),text:async()=>fs.readFileSync(f,'utf8')}}});
let modules=new Map();async function load(url){const u=new URL(url);u.search='';const key=u.href;if(modules.has(key))return modules.get(key);const f=path.resolve(site,u.pathname.slice(1));accesses.push(f);const m=new vm.SourceTextModule(fs.readFileSync(f,'utf8'),{context,identifier:key,initializeImportMeta(meta){meta.url=key}});modules.set(key,m);return m;}
const expected=JSON.parse(fs.readFileSync(path.join(site,'renderer-input.json'),'utf8'));
const expectedGoals=expected.phases.flatMap(p=>p.goals),expectedActions=expectedGoals.flatMap(g=>g.actions);
const report={environment:'Node VM with minimal DOM; executes bundled modules and real click handlers, not a browser or pixel-layout test',checks:{}};
try{
 if(fs.existsSync(path.join(site,'data.js'))){
  context.window=context;vm.runInContext(fs.readFileSync(path.join(site,'data.js'),'utf8'),context);
  await vm.runInContext(fs.readFileSync(path.join(site,'roundtrip/app.bundle.js'),'utf8'),context);
 }else{
  const m=await load('http://localhost/roundtrip/app.js');await m.link((spec,ref)=>load(new URL(spec,ref.identifier).href));await m.evaluate();
 }
 const count=s=>document.querySelectorAll(s).length,click=s=>{const el=document.querySelector(s);if(!el)throw Error('missing '+s);el.click()};
 report.checks.complete_function=count('#selection .bb-code-line')===expected.functionSource.lines.length;
 if(expected.prelude){
  report.checks.prelude_block=count('.prelude-heading')===1&&count('.prelude-node')===expected.prelude.nodes.length;
  const entry=expected.prelude.nodes[0];click(`[data-bb-group="${entry.id}"]`);
  report.checks.prelude_selectable=document.querySelector('#selection').dataset.sourceNode===entry.id;
  report.checks.prelude_namespaced=entry.basicBlockRefs.every(ref=>ref.startsWith('shell:bb'))&&document.querySelector('.bb-list').textContent.includes('shell:bb');
 }
 report.checks.initial_status=document.querySelector('#status').textContent;
 report.checks.phase_summaries=count('[data-summary-kind="phase"]')===expected.phases.length;
 click('[data-y="1"]');report.checks.goal_summaries=count('[data-summary-kind="goal"]')===expectedGoals.length;click('[data-goal]');report.checks.goal_details=count('#selection .bb-details')===1&&count('#selection .bb-source')>0;
 report.checks.bb_collapsed=!document.querySelector('.bb-blocks').open;report.checks.goal_highlight=count('.source-highlight')>0;
 click('.phase');report.checks.phase_clears_highlights=count('#selection .source-highlight')===0;report.checks.phase_keeps_full_source=count('#selection .bb-code-line')===expected.functionSource.lines.length;
 click('[data-y="2"]');report.checks.action_summaries=count('[data-summary-kind="action"]')===expectedActions.length;
 click('[data-action]');report.checks.action_details=count('#selection .bb-details')===1&&count('#selection .bb-code-line')>0;
 click('[data-x="2"]');click('[data-y="3"]');report.checks.all_messages=count('[data-message]')===expected.messages.length;report.checks.summary_replacement=count('[data-reading-summary]')===0;
 report.checks.scope_ranges=expected.readingScopes.every(s=>document.querySelectorAll('[data-scope-range]').some(e=>e.dataset.scopeRange===s.id||e.dataset.scopeRange.startsWith(s.id+'-part'))||document.querySelectorAll('[data-guard-scope]').some(e=>e.dataset.guardScope===s.id));
 report.checks.single_scope_origin=expected.readingScopes.filter(s=>s.kind==='opt'&&s.originControlRef).every(s=>!document.querySelector('[data-node="'+s.originControlRef+'"]'));
 const messageIds=document.querySelectorAll('[data-message]').map(e=>e.dataset.message);
 report.checks.unique_message_rows=new Set(messageIds).size===messageIds.length;
 const flowNotes=document.querySelectorAll('.flow-note');
 report.checks.no_fallback_filler=!flowNotes.some(e=>/未满足.{0,16}条件时进入对应的其他业务路径|的处理结果$|的分支范围$/.test(e.textContent.trim()));
 report.sequenceInventory={controls:document.querySelectorAll('[data-node]').map(e=>({id:e.dataset.node,title:e.textContent})),ranges:document.querySelectorAll('[data-range-label]').map(e=>({id:e.dataset.rangeLabel,title:e.textContent})),messageIds};
 report.markerRows=document.querySelectorAll('[data-loop-marker]').map(e=>({kind:e.dataset.loopMarker,label:e.textContent,source:e.dataset.loopSource,target:e.dataset.loopTarget,edgeRefs:e.dataset.executionEdges}));
 report.rendered_text=document.querySelector('#diagram').textContent;report.files=accesses;report.exceptions=[];
 report.labelFailures=actionLabelFailures(document.querySelectorAll('[data-action]').map(e=>({id:e.dataset.sourceAction,label:e.querySelector('[data-semantic-label]')?.textContent})),expectedActions);
 report.checks.no_generated_action_ids=report.labelFailures.length===0;
 report.observations={labelCheck:'Exact declared semantic label, complete unique action coverage; source terms may equal IDs.'};
 report.passed=Object.values(report.checks).every(x=>x!==false);
}catch(e){report.passed=false;report.exceptions=[e.stack]}
if(reportPath)fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({passed:report.passed,checks:report.checks,exceptions:report.exceptions,marker_count:report.markerRows?.length}));process.exit(report.passed?0:1);
