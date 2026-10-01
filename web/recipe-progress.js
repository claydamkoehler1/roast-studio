import {groupOf,isInitial,startingSettings} from './recipe-rules.js';

// Presentation follows acknowledged runner progress, never temperature guesses.
export const recipeColor = index => ['#97a552','#b1ad54','#cfb05c','#d5a058','#c68b55','#b88051'][index] || `hsl(${25+(index*13)%55} ${25+(index%4)*4}% ${52+(index%5)*3}%)`;
export function recipeMarkers(events){
 const found=new Map();
 for(const event of events||[]){
  if(event.kind!=='recipe_step')continue;
  try{const marker=JSON.parse(event.value);if(Number.isInteger(marker.step)&&marker.step>0&&Number.isFinite(marker.elapsed)&&Number.isFinite(marker.ibts)&&!found.has(marker.step))found.set(marker.step,marker);}catch{}
 }
 return [...found.values()];
}
export function recipeProgress(steps,runner,roastStatus,events=[]){
 const initial=steps.flatMap((s,i)=>isInitial(s)?[i]:[]);
 const nodes=[{indices:initial,charge:true,group:{conditions:[{sensor:'time',op:'>=',value:0}],actions:Object.entries(startingSettings(steps)).map(([control,value])=>({control,value}))}},...steps.flatMap((s,i)=>isInitial(s)?[]:[{indices:[i],group:groupOf(s)}])];
 const markers=recipeMarkers(events),settings=startingSettings(steps);
 nodes.forEach((node,i)=>{
  node.group.actions.forEach(a=>{if(a.control in settings)settings[a.control]=a.value;});
  node.settings={...settings,...(markers.find(m=>m.step===i+1)?.settings||{})};
  node.color=recipeColor(i);
 });
 const done=new Set(runner?.completed||[]),skipped=new Set(runner?.skipped||[]);
 for(const node of nodes){
  const resolved=node.indices.length?node.indices.every(i=>done.has(i)||skipped.has(i)):runner&&!runner.initializing;
  node.state=!resolved?'upcoming':node.indices.some(i=>skipped.has(i))?'skipped':'done';
 }
 const waiting=nodes.find(n=>n.state==='upcoming');
 let current=null;
 const roasting=roastStatus==='roasting';
 if(roasting&&runner){
  if(runner.state==='running'&&runner.initializing)current=nodes[0];
  else if(runner.state==='running'&&runner.applying_index!=null)current=nodes.find(n=>n.indices.includes(runner.applying_index));
  else if(runner.last_completed_index!=null)current=nodes.find(n=>n.indices.includes(runner.last_completed_index));
  else if(!runner.initializing&&nodes[0].state==='done')current=nodes[0];
 }
 if(current){current.current=true;current.caption=['paused','stopped'].includes(runner.state)?'Last applied':runner.initializing||runner.applying_index!=null?'Applying':'Current';}
 if(waiting&&!waiting.current&&(!roastStatus||(roasting&&runner?.state==='running')))waiting.next=true;
 const summary=!roastStatus?'Ready to roast':roastStatus==='cooling'?'Cooling':!runner?'Waiting for recipe':runner.state==='paused'?'Recipe paused':runner.state==='stopped'?'Recipe stopped':runner.state==='complete'?'Recipe finished · choose when to cool':current?.caption==='Applying'?'Applying settings':'Recipe running';
 return {nodes,summary};
}
