// Exact existential projection of decision environments at each CFG node.
// Keep every value that a future guard or a scope observation can read before reset.
export function liveVariables(nodeIds, edges, observations = new Map()) {
 const live = new Map(nodeIds.map(id=>[id,new Set(observations.get(id)??[])]));
 let changed=true;
 while(changed){changed=false;for(const edge of edges){const here=live.get(edge.from),next=live.get(edge.to);const reset=new Set(edge.resetDecisionRefs??[]);for(const g of edge.guards??[])if(!here.has(g.decisionRef)){here.add(g.decisionRef);changed=true;}for(const value of next)if(!reset.has(value)&&!here.has(value)){here.add(value);changed=true;}}}
 return live;
}
export function projectEnvironment(env, live){return Object.fromEntries(Object.entries(env).filter(([key])=>live.has(key)));}
