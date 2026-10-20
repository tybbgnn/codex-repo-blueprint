// Semantic content is checked at its own DOM slot; IDs stay in data attributes.
export function actionLabelFailures(rows, actions) {
 const expected=new Map(actions.map(a=>[a.id,a.label])),seen=new Set(),failures=[];
 for(const row of rows){
  if(seen.has(row.id)||!expected.has(row.id)||row.label!==expected.get(row.id))failures.push(row.id);
  seen.add(row.id);
 }
 for(const id of expected.keys())if(!seen.has(id))failures.push(id);
 return failures;
}
export function controlHeading(node, ownerLabel='') {
 if(node.condition?.trim())return node.condition;
 if(node.kind==='alt')return ownerLabel?`${ownerLabel} · 结果分支`:'结果分支';
 return '';
}
export function rangeMarker(range,index) {
 return `片段 ${index+1} · L${range.startLine}${range.endLine===range.startLine?'':`–${range.endLine}`}`;
}
