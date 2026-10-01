// Pure recipe presentation helpers. Recipe temperatures are stored in Celsius.
export function groupOf(step) {
  if (step.conditions) return step;
  const conditions = [{sensor:step.trigger || 'time',op:step.comparison || '>=',value:step.at || 0}];
  if (step.trigger && step.trigger !== 'time') conditions.push({sensor:'time',op:'>=',value:step.min_time ?? 5});
  return {conditions,actions:[{control:step.control,value:step.value}],reason:step.reason || '',after_turn:step.after_turn || false};
}
export const isInitial = step => {
  const g=groupOf(step);
  return g.conditions.length===1 && g.conditions[0].sensor==='time' && g.conditions[0].value===0;
};
export function startingSettings(steps) {
  const settings={power:7,fan:3,drum:9};
  steps.filter(isInitial).forEach(s=>groupOf(s).actions.forEach(a=>{if(a.control in settings)settings[a.control]=a.value;}));
  return settings;
}
export function actionText(action) {
  const labels={power:'P',fan:'F',drum:'D',yellow:'Mark yellowing',first_crack:'Mark first crack',popup:'Message',end_alert:'End alert'};
  return action.control in {power:1,fan:1,drum:1} ? labels[action.control]+action.value : labels[action.control] || action.control;
}
export function whenText(step, temperature, unit, clock) {
  const g=groupOf(step);
  return g.conditions.map(c=>c.sensor==='time' ? c.value===0?'At charge':clock(c.value)+' elapsed' : `${c.sensor==='bt'?'Bean probe':'IBTS'} ${c.op==='>='?'≥':'≤'} ${temperature(c.value)} ${unit}`).join(' + ') + (g.after_turn?' · after turning point':'');
}
