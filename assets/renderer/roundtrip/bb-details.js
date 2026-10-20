import {rangeMarker} from '../display-labels.mjs';
import {columnIntervals,isAttributeLine} from '../attribute-source.mjs';
import {data,basicBlockDetails} from './fixture.js?v=sidebar-1';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const reading=new Map(data.phases.flatMap(p=>[[p.id,{...p,kind:'phase'}],...p.goals.flatMap(g=>[[g.id,{...g,kind:'goal'}],...g.actions.map(a=>[a.id,{...a,kind:'action'}])])]));
const execution=new Map((data.execution?.nodes??[]).map(n=>[n.id,n]));
const prelude=new Map((data.prelude?.nodes??[]).map(n=>[n.id,{...n,kind:'prelude'}]));
const groups=new Map((data.sourceGroups??[]).map(n=>[n.id,{...n,kind:'bb_group'}]));
function label(n){return n.label??reading.get(n.actionRef)?.label??n.decisionRef??n.outcome??n.id;}
function highlightedText(text,line,ranges){
 const intervals=columnIntervals(text,line,ranges);
 if(!intervals.length)return esc(text);
 let html='',cursor=0;
 for(const [start,end] of intervals){html+=esc(text.slice(cursor,start))+`<mark class="source-column-highlight source-highlight">${esc(text.slice(start,end))}</mark>`;cursor=end;}
 return html+esc(text.slice(cursor));
}
const panel=document.querySelector('#selection');
const source=data.functionSource;
let current,initialized=false;
function initialize(){
 if(initialized)return;initialized=true;
 if(!source){panel.innerHTML='<div id="message-selection"></div>';return;}
 panel.innerHTML=`<section class="bb-details"><div id="message-selection"></div><h3 class="bb-selection-title" aria-live="polite"></h3><details class="bb-blocks"><summary></summary><p class="bb-list"></p></details><label class="bb-node-picker">定位执行节点 / BB 组<select aria-label="定位执行节点 / BB 组"><option value="">选择节点…</option>${prelude.size?`<optgroup label="入口（shell）">${[...prelude.values()].map(n=>`<option value="${esc(n.id)}">${esc(label(n))} · ${esc(n.id)}</option>`).join('')}</optgroup>`:''}<optgroup label="执行图节点">${[...execution.values()].map(n=>`<option value="${esc(n.id)}">${esc(label(n))} · ${esc(n.id)}</option>`).join('')}</optgroup><optgroup label="BB 组">${[...groups.values()].map(n=>`<option value="${esc(n.id)}">${esc(label(n))} · ${esc(n.id)}</option>`).join('')}</optgroup></select></label><section class="bb-source"><div class="bb-source-heading"><strong>完整 Rust 函数 · ${source.lines.length} 行</strong><span>${esc(source.file)} · 第 ${source.startLine}–${source.endLine} 行</span></div><pre class="bb-source-scroll" tabindex="0" aria-label="完整函数源码"><code>${source.lines.map((line,i)=>{const number=source.startLine+i,attribute=isAttributeLine(source,number);return `<span class="bb-code-line${attribute?' source-attribute':''}" data-line="${number}"><span class="bb-line-number">${number}</span><span class="bb-line-text">${esc(line)}</span></span>`;}).join('')}</code></pre></section></section>`;
 // Keep wheel movement in the same event turn as source selection. Chromium's
 // native smooth wheel animation can commit old deltas after showBasicBlocks
 // scrolls to a new node, even if the wheel began at the bottom of the pane.
 // Owning this bounded scrollport avoids that stale compositor animation; trackpad
 // deltas, horizontal/shift scrolling and keyboard scrolling remain available.
 const scroll=panel.querySelector('.bb-source-scroll');
 scroll.addEventListener('wheel',event=>{
  if(event.ctrlKey||!event.cancelable)return; // Preserve browser pinch/zoom.
  event.preventDefault();
  const unit=event.deltaMode===1?parseFloat(getComputedStyle(scroll).lineHeight):event.deltaMode===2?scroll.clientHeight:1;
  const horizontal=event.shiftKey&&event.deltaX===0;
  scroll.scrollBy({left:(horizontal?event.deltaY:event.deltaX)*unit,top:(horizontal?0:event.deltaY)*unit,behavior:'instant'});
 },{passive:false});
 panel.querySelector('select').addEventListener('change',event=>{
  const id=event.target.value||null;
  document.dispatchEvent(new CustomEvent('source-node-selected',{detail:{nodeId:id}}));
  showBasicBlocks(id);
 });
}
export function showBasicBlocks(nodeId){
 initialize();if(!source)return;
 // Phase selection resets the highlight but keeps the complete function visible.
 const node=prelude.get(nodeId)??reading.get(nodeId)??execution.get(nodeId)??groups.get(nodeId);
 const active=node?.kind==='phase'?null:node;
 const key=active?.id??null;
 if(current===key)return;current=key;
 const title=panel.querySelector('.bb-selection-title');
 title.textContent=active?label(active):data.semanticRoot.symbol;title.title=active?`${label(active)} · ${active.id}`:data.semanticRoot.symbol;
 panel.dataset.sourceNode=key??'';
 const blocks=panel.querySelector('.bb-blocks');blocks.open=false;
 const refs=active?.basicBlockRefs??[];
 blocks.hidden=!active;
 blocks.querySelector('summary').textContent=`包含的 basic blocks（${refs.length} 个）`;
 blocks.querySelector('.bb-list').textContent=refs.map(ref=>{
  const fact=basicBlockDetails?.blocks?.[ref];
  const kind=fact?.terminator?.kind??fact?.terminator_kind;
  return kind?`${ref} (${kind})`:ref;
 }).join(' · ');
 panel.querySelector('select').value=prelude.has(key)||execution.has(key)||groups.has(key)?key:'';
 const ranges=active?.lineRanges??[];
 for(const row of panel.querySelectorAll('.bb-code-line')){
  const line=Number(row.dataset.line),highlighted=ranges.some(r=>line>=r.startLine&&line<=r.endLine);
  const lineRanges=ranges.filter(r=>r.startColumn===undefined&&line>=r.startLine&&line<=r.endLine);
  row.classList.toggle('source-highlight',lineRanges.length>0);
  row.querySelector('.bb-line-text').innerHTML=highlightedText(source.lines[line-source.startLine],line,ranges);
  row.querySelector('.bb-range-label')?.remove();
  row.removeAttribute('aria-label');
  if(highlighted){
   row.setAttribute('aria-label',`${label(active)} · 第 ${line} 行`);
   if(ranges.some(r=>r.startLine===line)){
    const marker=document.createElement('span');marker.className='bb-range-label';marker.textContent=rangeMarker(active.lineRanges.find(r=>r.startLine===line),active.lineRanges.findIndex(r=>r.startLine===line));marker.title=active.id;row.prepend(marker);
   }
  }
 }
 const scroll=panel.querySelector('.bb-source-scroll');
 panel.scrollTop=0;
 // Scroll only the code pane; scrollIntoView would move the diagram/body too.
 const first=panel.querySelector('.source-highlight');
 scroll.scrollTop=first?scroll.scrollTop+first.getBoundingClientRect().top-scroll.getBoundingClientRect().top-16:0;
}
