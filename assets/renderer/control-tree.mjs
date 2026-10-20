/** Shape-validated Control union traversal. References remain rooted in the original
 * tree; this index never hoists branch members or registers a node twice. */
export function walkControls(controls){
 const entries=[];
 function visit(node,rootControlRef,branchPath,guardPath,invocationControlRef){
  // opt/loop messages and children belong to their taken/body scope, not the
  // surrounding sequence. alt.messages/children precede its alternatives.
  const guards=['opt','loop'].includes(node.kind)?[...guardPath,{kind:node.kind,ref:node.id}]:guardPath;
  const invocation=node.invocationRef?node.id:invocationControlRef;
  entries.push({node,rootControlRef,branchPath,guardPath:guards,invocationControlRef:invocation});
  for(const child of node.children??[])visit(child,rootControlRef,branchPath,guards,invocation);
  if(node.kind==='alt')for(const branch of node.branches)for(const child of branch.children)visit(child,rootControlRef,[...branchPath,branch.id],[...guards,{kind:'branch',ref:branch.id}],invocation);
 }
 for(const root of controls)visit(root,root.id,[],[],root.id);
 return entries;
}
export const collectNodes=controls=>walkControls(controls).map(e=>e.node);
