import {recipeProgress,recipeMarkers,recipeColor} from './recipe-progress.js';
import {toF, toC, preheatC, fahrenheitText} from './temperature.js';
import {groupOf, isInitial, startingSettings, actionText, whenText} from './recipe-rules.js';
import { startAtmosphere } from './atmosphere.js';
const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths={bean:'M6 5C-1 13 6 23 15 19S25 2 15 2C10 2 8 3 6 5m10-2c-6 3-1 13-10 16',spark:'m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2',plus:'M12 5v14M5 12h14',arrow:'M4 12h15m-5-5 5 5-5 5',close:'m6 6 12 12M6 18 18 6',check:'m5 12 4 4L19 6',link:'m9 15 6-6m-6 9-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2-4 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0',flame:'M13 2c2 8 8 8 6 15-1 5-12 7-14 0-1-5 3-7 4-11 0 5 3 5 4-4Z',fan:'M12 12C4-1 22-1 16 8m-4 4c15 0 6 16 1 7m-1-7C4 25-4 8 7 9',drum:'M4 6c0-4 16-4 16 0v12c0 4-16 4-16 0zm0 0c0 4 16 4 16 0',history:'M3 12a9 9 0 1 0 2-6M3 3v5h5m4-1v5l3 2',download:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',book:'M4 3h15v18H4zM8 7h7M8 11h7M8 15h4',cup:'M4 5h12v8a6 6 0 0 1-12 0zm12 2h2a3 3 0 0 1 0 6h-2M3 22h15'};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.bean}"/></svg>`;
const btn = (text, action, cls='', attrs='') => `<button type="button" class="${cls}" data-action="${action}" ${attrs}>${text}</button>`;
const fmt = (v,n=1) => v==null || !Number.isFinite(Number(v)) ? '—' : Number(v).toFixed(n);
const clock = n => {n=Math.max(0,Math.floor(n||0));return `${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;};
const date = v => v ? new Date(v.length===10?v+'T12:00:00':v).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'}) : '—';
const money = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n||0);
const kg = n => `${fmt(n/1000,2)} kg`;
const label = s => ({recipe_step:'Recipe step',popup:'Recipe message',end_alert:'End alert',yellow:'Yellowing',first_crack:'First crack',first_crack_end:'Crack end',second_crack:'Second crack',charge:'Charge',drop:'Drop',control:'Control',note:'Note',connection:'Connection'}[s]||s);
let boot,data,live={active:null,hardware:{},samples:[],events:[],telemetry:{}},aiStatus=null,jobs=[],selectedJob=null;
let page=['roast','recipes','beans','history'].includes(location.hash.slice(1))?location.hash.slice(1):'roast';
let selectedBean='',selectedRecipe='',reference=null,search='',historyFilter='all',compareIds=[],saveModal=null,modalKind='';
const dismissedAlerts=new Set();
let packagingRoast=null,reviewChart=null,resizeTimer;
let conversations=[],conversation=null,chatBusy=false,chatError='',chatRenderSignature='';
let beanImportJob=null,beanImportSignature="";
let renderedPage=null;
let pollBusy=false,pollCount=0,toastTimer,jobSignature='',draftParent=null;
const temp = n => n==null?'—':fmt(toF(n));
const prose = value => esc(fahrenheitText(value));
const rate = n => n==null?'—':fmt(n*1.8);
const unit = () => '°F';
async function api(path, body){const res=await fetch('/api/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Roast-Token':boot.token},body:JSON.stringify(body)});const val=await res.json();if(!res.ok)throw Error(val.error||'Request failed');return val;}
function toast(message,error=false){$('#toast').textContent=fahrenheitText(message);$('#toast').className='show'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').className='',6000);}
async function loadData(){data=await api('data');}
function empty(title,description,action='',symbol='bean'){return `<div class="empty-state"><div class="symbol">${icon(symbol)}</div><h2>${title}</h2>${description?`<p>${description}</p>`:''}${action}</div>`;}
function heading(title,actions=''){return `<div class="page-head"><h1>${title}</h1><div class="page-intro"><div class="actions">${actions}</div></div></div>`;}
function render(){
 const pages=['roast','recipes','beans','history'];
 // Keep the header and scrolling viewport mounted when changing pages.
 if(!$('#main'))$('#app').innerHTML=`<header class="top">${btn('Menu','menu','menu-toggle','aria-haspopup="dialog" aria-controls="site-menu" aria-expanded="false"')}<div id="return-roast"></div></header><div class="atmosphere" aria-hidden="true"><div class="light-field light-one"></div><div class="light-field light-two"></div><div class="ambient-bloom bloom-one"></div><div class="ambient-bloom bloom-two"></div><div class="ambient-bloom bloom-three"></div></div><main class="main" id="main"></main><dialog id="site-menu" aria-label="Menu"><button type="button" class="menu-toggle" data-action="close-menu" autofocus>Close</button><nav class="menu-links" aria-label="Main navigation">${pages.map(p=>`<button type="button" data-page="${p}">${p==='roast'?'Home':p[0].toUpperCase()+p.slice(1)}</button>`).join('')}</nav><div class="menu-settings">${btn('Settings','settings','quiet small')}</div></dialog>`;
 workspaceAtmosphere();
 startAtmosphere($('.atmosphere'));
 const changed=renderedPage!==page,main=$('#main');
 if(changed)main.style.setProperty('--page-offset',pages.indexOf(page)<pages.indexOf(renderedPage)?'-28px':'28px');
 $$('.menu-links button').forEach(button=>{const active=button.dataset.page===page;if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');});
 main.className=`main page-${page}`;
 main.innerHTML=`<div class="page-content${changed?' page-enter':''}">${({roast:roastPage,recipes:recipesPage,beans:beansPage,history:historyPage})[page]()}</div>`;
 if(changed)main.scrollTop=0;
 renderedPage=page;
 if(page==='roast')updateRoast();
 if(page==='recipes')updateDraft();
}
function put(selector,html){const el=$(selector);if(!el)return;const template=document.createElement('template');template.innerHTML=html;if(el.innerHTML!==template.innerHTML)el.replaceChildren(template.content.cloneNode(true));}
function go(p){closeMenu();page=p;search='';location.hash=p;render();}
function closeMenu(){const menu=$('#site-menu');if(menu?.open)menu.close();$('[data-action="menu"]')?.setAttribute('aria-expanded','false');}
function openMenu(){const menu=$('#site-menu');menu.showModal();$('[data-action="menu"]').setAttribute('aria-expanded','true');menu.onclose=()=>{$('[data-action="menu"]').setAttribute('aria-expanded',String(menu.open));};}
function homeClock(now=new Date()){
 const day=now.toLocaleDateString(undefined,{month:'long',day:'numeric',year:'numeric'});
 const time=now.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit',hour12:true});
 return `<span class="home-date">${esc(day)}</span><br><em>${esc(time)}</em>`;
}
function updateHomeClock(){if($('#home-clock'))put('#home-clock',homeClock());}
function roastPage(){
 if(!live.active&&!live.workspace)return `<section class="roast-landing"><div class="hero-copy"><h1 id="home-clock">${homeClock()}</h1>${btn('Begin roast '+icon('arrow'),'new-roast','begin-button primary with-icon')}</div></section>`;
 return `<section class="roast-console" aria-label="Roast controls and graph"><div class="console-toolbar"><div class="console-heading"><div id="workspace-title"></div><div id="phase-controls" class="actions"></div></div><div class="actions"><button type="button" class="quiet small connection-control" data-action="machine"><span id="machine-dot" class="dot"></span><span id="machine-label">Bullet R2</span></button>${!live.active?btn(icon('close'),'close-workspace','quiet icon-btn','aria-label="Close workspace" title="Close workspace"'):''}</div></div><div id="roast-error" class="alert-space"></div><div id="recipe-alerts" aria-live="polite"></div><div class="console-readings">${[['elapsed','Time',''],['ibts','Bean surface · IBTS','hot'],['bt','Bean probe','probe-reading'],['ror','Heating rate · RoR','ror-reading']].map(([id,name,cls])=>`<div class="metric ${cls}"><label>${name}</label><div class="value"><span id="metric-${id}">—</span><span class="suffix" id="suffix-${id}"></span></div></div>`).join('')}</div><div id="chart-key" class="chart-key"></div><div class="chart-wrap" id="live-chart"></div><div class="control-mode-row"><div id="control-mode-switch"></div><span id="recipe-run-status" role="status"></span></div><div id="recipe-timeline" class="recipe-timeline"></div><div id="controls" class="control-bar"></div><div class="console-tools"><div id="events" class="event-bar"></div><div id="recipe-controls" class="actions"></div></div></section>`;
}
function chart(samples,events=[],overlay=null,compact=false){
 if(!compact)reviewChart={samples,events,overlay};
 const w=compact?Math.max(270,($('#live-chart')?.clientWidth||window.innerWidth)):Math.max(270,Math.min(1500,window.innerWidth-100)),h=compact?Math.max(260,$('#live-chart')?.clientHeight||window.innerHeight-350):480,l=62,r=58,t=32,b=42,iw=w-l-r,ih=h-t-b;
 const maxT=Math.max(840,Math.ceil(Math.max(samples.at(-1)?.elapsed||0,overlay?.samples?.at(-1)?.elapsed||0)/120)*120);
 const peak=[samples,overlay?.samples||[]].reduce((max,series)=>series.reduce((m,s)=>Math.max(m,Number.isFinite(s.ibts)?s.ibts:0,Number.isFinite(s.bt)?s.bt:0),max),0);
 const maxY=Math.max(250,Math.ceil((Math.max(peak,compact&&!live.active?(live.workspace?.preheat||0):0)+15)/50)*50);
 const x=n=>l+n/maxT*iw,y=n=>h-b-n/maxY*ih,yr=n=>h-b-(Math.max(-10,Math.min(40,n))+10)/50*ih;
 const line=(arr,key,fn)=>{let d='',started=false;for(const s of arr){if(!Number.isFinite(s[key])){started=false;continue;}if(s.gap_before)started=false;d+=(started?'L':'M')+x(s.elapsed).toFixed(1)+','+fn(s[key]).toFixed(1);started=true;}return d;};
 const grid=Array.from({length:maxY/50+1},(_,i)=>i*50).map(n=>`<line class="grid" x1="${l}" x2="${w-r}" y1="${y(n)}" y2="${y(n)}"/><text x="${l-10}" y="${y(n)+3}" text-anchor="end">${Math.round(toF(n))}</text>`).join('');
 const axis=Array.from({length:w<500?5:8},(_,i)=>i*maxT/(w<500?4:7)).map(n=>`<text x="${x(n)}" y="${h-10}" text-anchor="middle">${clock(n)}</text>`).join('');
 const rorAxis=[0,10,20,30,40].map(n=>`<text x="${w-r+10}" y="${yr(n)+3}">${Math.round(n*1.8)}</text>`).join('');
 return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Roast curve: IBTS and bean temperature in ${unit()}, rate of rise in degrees per minute"><defs><clipPath id="chart-clip"><rect x="${l}" y="${t}" width="${iw}" height="${ih}"/></clipPath></defs>${grid}${axis}${rorAxis}<g clip-path="url(#chart-clip)">${overlay?`<path d="${line(overlay.samples,'ibts',y)}" fill="none" stroke="#d3d9ce" stroke-width="3" stroke-dasharray="8 6"/>`:''}${[['ibts',y,'#efd18d',4],['bt',y,'#9ce3c6',3.5],['ror',yr,'#b4c7ff',3]].map(([key,fn,c,width])=>`<path d="${line(samples,key,fn)}" fill="none" stroke="${c}" stroke-width="${width}" stroke-linejoin="round"/>`).join('')}${events.filter(e=>['yellow','first_crack','drop'].includes(e.kind)).map(e=>`<line x1="${x(e.elapsed)}" x2="${x(e.elapsed)}" y1="${t}" y2="${h-b}" stroke="#353b36" stroke-dasharray="3 4"/><text x="${x(e.elapsed)+5}" y="${t+9}">${esc(label(e.kind))}</text>`).join('')}</g>${recipeMarkers(events).map(m=>`<circle class="recipe-start-dot" cx="${x(m.elapsed)}" cy="${y(m.ibts)}" r="6" fill="${recipeColor(m.step-1)}" stroke="#11180f" stroke-width="2"><title>Step ${m.step} started · ${clock(m.elapsed)} · ${temp(m.ibts)} ${unit()}</title></circle>`).join('')}</svg>`;
}
function recipeEventText(event){const m=recipeMarkers([event])[0];return m?`Step ${m.step} started at ${temp(m.ibts)} ${unit()} · Power ${m.settings.power} Air ${m.settings.fan} Drum ${m.settings.drum}`:'Step started';}
function chartKeys(overlay){
 const preheat=!live.active&&live.workspace?`<span>Preheat <b>${temp(live.workspace.preheat)} ${unit()}</b></span>`:'';
 const curve=overlay?`<span class="curve-key"><i aria-hidden="true"></i>Recorded overlay · ${esc(overlay.name)}</span>`:'';
 put('#chart-key',preheat+curve);
}
function updateRecipeTimeline(recipe){
 if(!recipe){put('#recipe-timeline','');put('#recipe-run-status','Manual control');return;}
 const {nodes,summary}=recipeProgress(recipe.steps,live.automation,live.active?.status,live.events);
 put('#recipe-run-status',summary);
 const condition=c=>c.sensor==='time'?`T ≥ ${c.value}s`:`${c.sensor==='bt'?'Probe ':''}${c.op==='>='?'≥':'≤'}${Number(toF(c.value).toFixed(1))}°F`;
 const previous=$('#recipe-timeline .recipe-rail'),scroll=previous?.scrollLeft||0,oldCurrent=$('#recipe-timeline').dataset.current;
 const activeIndex=nodes.findIndex(n=>n.current),selected=activeIndex>=0?activeIndex:nodes.findIndex(n=>n.next),key=String(selected);
 put('#recipe-timeline',`<ol class="recipe-rail" aria-label="Recipe progress">${nodes.map((node,i)=>{
  const detail=node.charge?'Start':node.group.conditions.map(condition).join(' and ')+(node.group.after_turn?' · after turning point':'');
  const state=node.current?node.caption:node.state==='done'?'Applied':node.state==='skipped'?'Skipped':node.next?'Next':'Upcoming';
  return `<li class="recipe-stop ${node.state}${node.current?' current':''}${node.next?' next':''}" style="--step-color:${node.color}" ${node.current?'aria-current="step"':''}><div class="recipe-stop-heading"><b>${i+1}. ${esc(detail)}</b><span class="recipe-stop-state">${esc(state)}</span></div><span class="recipe-stop-settings">${[['P','power','Power'],['F','fan','Air'],['D','drum','Drum']].map(([letter,key,name])=>`<span class="recipe-setting" aria-label="${name} ${node.settings[key]}" title="${name}"><span>${letter}</span><b>${node.settings[key]}</b></span>`).join('')}</span></li>`;
 }).join('')}</ol>`);
 const rail=$('#recipe-timeline .recipe-rail');
 rail.scrollLeft=scroll;
 if(oldCurrent!==key&&selected>=0){const node=rail.children[selected];rail.scrollLeft=Math.max(0,node.offsetLeft-rail.offsetLeft-20);}
 $('#recipe-timeline').dataset.current=key;
}
function manualControl(){
 const session=live.active||live.workspace;
 if(!session?.profile_id)return true;
 if(live.active&&live.automation)return !['running','complete'].includes(live.automation.state);
 return session.control_mode==='manual';
}
function workspaceRecipe(){const session=live.active||live.workspace,p=data.profiles.find(p=>p.id===session?.profile_id);return p?{...p,steps:session.steps||p.steps,preheat:live.workspace?.preheat??p.preheat,batch_g:session.green_g??p.batch_g}:null;}
function workspaceAtmosphere(){
 const host=$('.atmosphere'),mode=page==='roast'&&(live.active||live.workspace)?'workspace':'ambient';
 if(host&&host.dataset.mode!==mode)host.dataset.mode=mode;
 if(host&&host.dataset.page!==page)host.dataset.page=page;
 put('#return-roast',page!=='roast'&&(live.active||live.workspace)?btn('Return to roast','return-roast','quiet small'):'');
}
function phaseControls(){
 const a=live.active,w=live.workspace,h=live.hardware,practice=(a?.mode||w?.mode)==='practice';
 const state=practice?w?.stage:h.fresh?h.telemetry?.machine_state:null;
 const can=practice||(h.fresh&&h.armed&&!h.pending);
 const transition=(text,action,allowed=can)=>btn(h.pending?'Confirming…':text,'transition','console-phase',`data-transition="${action}" data-state="${state}" ${allowed?'':'disabled'}`);
 if(a?.status==='cooling')return (can&&['cooldown','cooling'].includes(state)?transition('Shut down','shutdown'):'')+btn('Save roast','finish','console-phase')+(state==='shutdown'?'<span class="console-status">Cooling roaster</span>':'');
 if(!practice&&!h.fresh)return btn(h.connected?'Waiting for R2…':'Connect R2','workspace-connect','console-phase',h.connected?'disabled':'');
 if(!practice&&!h.armed)return btn('Enable controls','workspace-arm','console-phase');
 if(a?.status==='roasting')return transition('Start cooling','cool',practice||(h.fresh&&h.armed&&state==='roasting'&&(!h.pending||h.pending_control)));
 if(state==='ready')return transition('Preheat','preheat');
 if(['preheating','stabilizing'].includes(state))return transition('Advance to charge','charge')+`<span class="console-status">${state==='stabilizing'?'Stabilizing':'Preheating'} · ${temp(w.preheat)} ${unit()}</span>`;
 if(state==='charge')return (!practice&&!w.auto_record?transition('Watch for charge','watch-charge'):'')+transition(practice?'Start roast':'Start roast manually',practice?'record':'roast')+(w.auto_record?'<span class="console-status">Ready for beans</span>':'');
 if(state==='roasting')return transition('Record roast','record');
 return '<span class="console-status">'+(state==='shutdown'?'Cooling roaster':'Complete the current cycle on the R2')+'</span>';
}
function updateRoast(){
 workspaceAtmosphere();
 if(page!=='roast')return;
 if((live.active||live.workspace)&&!$('#live-chart')){render();return;}
 if(!(live.active||live.workspace)&&$('#live-chart')){render();return;}
 if(!$('#live-chart'))return;
 const a=live.active,w=live.workspace,t=live.telemetry||{},h=live.hardware||{},recording=a?.status==='roasting',p=workspaceRecipe(),practice=(a?.mode||w?.mode)==='practice';
 const closeButton=$('[data-action="close-workspace"]');if(closeButton)closeButton.hidden=!!a;
 $('#machine-label').textContent=practice?'Practice':h.fresh?'R2 connected':h.connected?'Waiting for R2':'R2 disconnected';
 $('#machine-dot').className='dot'+(h.fresh?' good':'');
 put('#phase-controls',phaseControls());
 for(const [key,value] of Object.entries({elapsed:clock(a?.elapsed),ibts:temp(t.ibts),bt:temp(t.bt),ror:rate(t.ror)})){$('#metric-'+key).textContent=value;$('#suffix-'+key).textContent=key==='elapsed'?'':key==='ror'?unit()+'/m':unit();}
 const manual=manualControl();
 put('#workspace-title',p?`<button class="workspace-recipe-title" data-action="session-recipe" title="View full recipe">${esc(p.name)}</button>`:`<h1 class="workspace-recipe-title">${esc((a||w)?.name||'Manual roast')}</h1>`);
 const modeUnavailable=!!a&&!recording;
 const autoUnavailable=!p||modeUnavailable||(!manual?false:recording&&!practice&&(!h.fresh||!h.armed||h.pending||h.error));
 put('#control-mode-switch',p?btn(manual?'Exit manual':'Manual override','control-mode','manual-override',`data-mode="${manual?'auto':'manual'}" ${(manual?autoUnavailable:modeUnavailable)?'disabled':''} title="${manual?'Resume future recipe steps':'Pause recipe and adjust settings yourself'}"`):'');
 updateRecipeTimeline(p);
 $('#recipe-timeline').hidden=manual;
 $('#controls').hidden=!manual;
 if(manual)put('#recipe-run-status',live.automation?.reason&&live.automation.reason!=='Manual control.'?'Recipe paused':'Manual control');
 const overlay=reference;
 chartKeys(overlay);
 $('#live-chart').innerHTML=chart(live.samples,live.events,overlay,true);
 put('#roast-error',live.error||h.error?`<div class="notice error">${esc(live.error||h.error)}</div>`:'');
 put('#recipe-alerts',live.events.filter(e=>['popup','end_alert'].includes(e.kind)&&!dismissedAlerts.has(e.id)).map(e=>`<div class="notice recipe-notice"><div><b>${e.kind==='end_alert'?'Recipe end target':'Recipe message'}</b><p>${prose(e.value)}</p></div>${btn('Dismiss','dismiss-recipe-alert','quiet small',`data-id="${e.id}"`)}</div>`).join(''));
 const enabled=recording&&(practice||h.fresh&&h.armed&&!h.pending);
 put('#controls',['power','fan','drum'].map((name,i)=>`<div class="control">${icon(['flame','fan','drum'][i])}<span class="control-label" data-short="${['P','F','D'][i]}">${['Power','Air','Drum'][i]}</span><div class="stepper">${btn('−','control','',`data-control="${name}" data-value="${(t[name]||0)-1}" aria-label="Decrease ${name}" ${!enabled||t[name]<=(name==='power'?0:1)?'disabled':''}`)}<b>${t[name]??'—'}</b>${btn('+','control','',`data-control="${name}" data-value="${(t[name]||0)+1}" aria-label="Increase ${name}" ${!enabled||t[name]>=(name==='fan'?12:name==='power'?10:9)?'disabled':''}`)}</div></div>`).join(''));
 put('#events',recording?['yellow','first_crack'].map(kind=>btn(label(kind),'event','quiet small',`data-kind="${kind}" ${live.events.some(e=>e.kind===kind)||kind==='yellow'&&live.events.some(e=>e.kind==='first_crack')?'disabled':''}`)).join('')+btn('Note','note','quiet small')+(!h.fresh&&!practice?btn('End recording','drop','quiet small'):''):'');
 const runner=live.automation,status=runner?.state;
 put('#recipe-controls',(data.roasts.some(r=>r.status==='complete')?btn(reference?'Change overlay':'Overlay','reference','quiet small'):'')+(practice&&recording?`<select id="speed" class="draft-select" aria-label="Simulation speed">${[1,5,15,30].map(n=>`<option value="${n}" ${live.speed===n?'selected':''}>${n}×</option>`).join('')}</select>`:''));
 if(status==='paused'&&runner.reason!=='Manual control.'&&!live.error&&!h.error)put('#roast-error',`<div class="notice error">${esc(runner.reason)}</div>`);
}
function recipesPage(){return heading('Recipes',btn('Write recipe','edit-recipe','quiet small')+btn('Import RoasTime','import-recipe','quiet small')+btn('Add recipe '+icon('plus'),'add-recipe','primary with-icon'))+
 `<div class="recipe-stack" id="recipe-library">${recipeLibrary()}</div><section class="conversation-list" ${conversations.length?'':'hidden'}><div class="section-heading"><h2>Conversations</h2></div><div id="conversation-list">${conversationList()}</div></section>`;}
function recipeLibrary(){return data.profiles.map((p,i)=>`<button class="recipe-row" data-action="view-recipe" data-id="${p.id}"><span class="recipe-art" aria-hidden="true"><span>${String(i+1).padStart(2,'0')}</span>${icon('bean')}</span><div class="recipe-info"><span class="eyebrow">${p.guidance.model?'ASTRA RECIPE · FIRST TRIAL':'PERSONAL RECIPE'}</span><h2>${esc(p.name)}</h2><p>${esc(p.style)}</p></div><div class="recipe-summary"><b>${fmt(p.batch_g,0)} <small>g</small></b><span>${temp(p.preheat)} ${unit()} preheat</span></div><span class="row-arrow">${icon('arrow')}</span></button>`).join('')||empty('No recipes yet','');}
function conversationList(){return conversations.map(c=>`<button class="conversation-row" data-action="continue-chat" data-id="${c.id}"><span>${icon('spark')} ${esc(c.title)}</span><span>${date(c.updated)} ${icon('arrow')}</span></button>`).join('')||'<p class="hint">No conversations yet.</p>';}
function currentJob(){return conversation?.jobs?.find(j=>j.id===selectedJob)||jobs.find(j=>j.id===selectedJob)||jobs.find(j=>!['chat','bean'].includes(j.context.task));}
function recipePane(existing=null){
 conversation=existing;chatError='';chatRenderSignature='';
 const c=existing?.context,bean=c?.bean||{},d=bean.details||{};
 const parameters=`<div class="field-grid">${selectField('chat-lot','Beans from inventory',data.lots.map(l=>[l.id,l.name]),c?.bean.id||selectedBean,'Describe new beans')}${field('chat-batch','Batch · g',c?.batch_g||500,'number','min="200" max="1000" required')}${selectField('chat-brew','Brew method',[['Filter','Filter'],['Espresso','Espresso'],['Both','Both']],c?.brew||'Filter')}${field('chat-goal','Cup goal',c?.goal||'Sweet, balanced, chocolate and caramel')}</div><div id="custom-beans" ${c?.bean.id||selectedBean?'hidden':''}>${field('chat-name','Coffee name',bean.name||'')}${textarea('chat-notes','Bean details',bean.notes||'','Paste bean details, your observations, or the seller description…')}</div>${disclosure('Roast.World reference · optional',`<p class="hint">Public community guidance is included. Paste a recipe’s steps or exported JSON and its link to discuss that specific recipe. The signed-in library is not automatically synced.</p>${textarea('chat-reference','Recipe or community notes',c?.community_reference||'','Paste recipe/export and source link…')}<a href="https://roast.world" target="_blank" rel="noreferrer">Open Roast.World ↗</a>`)}`;
 const body=`<div class="recipe-workshop"><div class="chat-preferences">${selectField('chat-expertise','Experience',[['beginner','Beginner'],['intermediate','Intermediate'],['advanced','Advanced']],boot.settings.astra_expertise||'beginner')}</div><details class="bean-parameters" ${existing||window.innerWidth<=760?'':'open'}><summary>${existing?esc(bean.name)+' · '+fmt(c.batch_g,0)+' g · '+esc(c.brew):'Your beans & roast'}</summary><fieldset ${existing?'disabled':''}>${parameters}</fieldset>${existing?btn('Edit bean parameters','edit-chat-parameters','quiet small'):''}</details><div class="conversation-body"><div id="chat-stream" class="chat-stream" role="log" aria-label="Recipe conversation"></div><div id="chat-result"></div></div><div class="chat-compose"><label class="composer-label" for="chat-message">Message Astra</label><textarea id="chat-message" rows="2" placeholder="Message Astra…" aria-describedby="chat-hint"></textarea><div class="composer-meta"><span id="chat-hint">Enter to send</span><span id="chat-status" role="status"></span></div><p class="privacy">Chat, bean details and relevant roast history are sent to OpenAI via your ChatGPT account.</p></div></div>`;
 openModal('Astra',body,null,'',true,'conversation');
 $('#dialog').classList.add('workshop-pane');updateDraft();$('#chat-message').focus();
}
function chatSources(ids=[]){return `<div class="chat-sources">${ids.map(id=>{const source=aiStatus?.sources?.find(s=>s.id===id);return source?`<a href="${esc(source.url)}" target="_blank" rel="noreferrer">${esc(source.title)} ↗</a>`:'';}).join('')}</div>`;}
function chatRecipe(job){return job?.context.task==='chat'?job.result?.recipe:job?.context.task==='recipe'?job.result:null;}
function updateDraft(){
 if(!$('#chat-stream')||modalKind!=='conversation')return;
 const entries=conversation?.messages||[],cj=conversation?.jobs||[],running=cj.find(j=>j.status==='running'),latest=cj[0];
 const signature=JSON.stringify([entries,cj.map(j=>[j.id,j.status,j.profile_id,j.result,j.error]),chatBusy,chatError]);
 if(signature!==chatRenderSignature){
  const scroller=$('.conversation-body'),follow=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<100;
  const expanded=new Set($$('.chat-attachment[open]').map(d=>d.dataset.jobId));
  const messages=entries.map(m=>{const job=cj.find(j=>j.id===m.job_id),recipe=m.role==='assistant'?chatRecipe(job):null;
   return `<article class="chat-message ${m.role}"><span class="eyebrow">${m.role==='user'?'YOU':'ASTRA'}</span><div class="chat-text">${prose(m.content)}</div>${m.role==='assistant'?chatSources(job?.result?.source_ids):''}${recipe?`<details class="chat-attachment" data-job-id="${job.id}"><summary>${esc(recipe.name)} <span>${fmt(recipe.batch_g,0)} g</span></summary>${recipeBody(recipe)}<div class="actions">${btn(job.profile_id?'Saved':'Save recipe','save-ai','primary small',`data-job-id="${job.id}" ${job.profile_id?'disabled':''}`)}</div></details>`:''}</article>`;
  }).join('');
  const status=running||chatBusy?`<div class="chat-thinking"><i class="spinner"></i>Astra is thinking… ${running?btn('Stop','cancel-ai','quiet small'):''}</div>`:latest&&['failed','cancelled'].includes(latest.status)?`<div class="notice error" role="alert">${esc(latest.error)} ${btn('Retry','retry-chat','quiet small')}</div>`:'';
  put('#chat-stream',(entries.length?messages:'<div class="chat-welcome"><h2>What would you like to roast?</h2></div>')+status+(chatError?`<div class="notice error" role="alert">${esc(chatError)}</div>`:''));
  put('#chat-result','');$$('.chat-attachment').forEach(d=>{d.open=expanded.has(d.dataset.jobId);});chatRenderSignature=signature;
  if(follow)scroller.scrollTop=scroller.scrollHeight;
 }
 const expertise=$('#chat-expertise');if(expertise)expertise.disabled=!!running||chatBusy;
 const input=$('#chat-message');input.setAttribute('aria-busy',String(!!running||chatBusy));
 $('#chat-status').textContent=running?'Working · '+clock((Date.now()-new Date(running.created))/1000):chatBusy?'Sending…':'';
}
function showChatError(error){chatError=error.message||String(error);updateDraft();}

async function ensureConversation(){
 if(conversation&&$('.bean-parameters fieldset').disabled)return;
 const context={lot_id:num('chat-lot')||null,batch_g:num('chat-batch'),brew:val('chat-brew'),goal:val('chat-goal'),community_reference:val('chat-reference'),bean:{name:val('chat-name'),origin:val('chat-origin'),process:val('chat-process'),notes:val('chat-notes'),details:{variety:val('chat-variety'),density:val('chat-density'),moisture:val('chat-moisture')}}};
 conversation=await api(conversation?'ai/conversations/update':'ai/conversations',conversation?{...context,id:conversation.id}:context);conversations=await api('ai/conversations');
 $('.bean-parameters fieldset').disabled=true;$('.bean-parameters').open=false;$('.bean-parameters summary').textContent=conversation.title+' · '+conversation.context.batch_g+' g';
 put('#conversation-list',conversationList());if($('.conversation-list'))$('.conversation-list').hidden=!conversations.length;
}
async function sendConversation(retry=false){
 if(chatBusy||conversation?.jobs?.some(j=>j.status==='running'))return;
 const input=$('#chat-message'),message=input?.value.trim();
 if(!retry&&!message){input?.focus();return;}
 if(!retry&&!$('#modal-form').reportValidity())return;
 chatBusy=true;chatError='';updateDraft();
 try{
  if(!retry)await ensureConversation();
  const cid=conversation.id,body=retry?{conversation_id:cid,retry_job_id:conversation.jobs[0].id}:{conversation_id:cid,message};
  const job=await api('ai/chat',body);jobs=[job,...jobs.filter(j=>j.id!==job.id)];jobSignature='';
  if(!retry&&input?.isConnected&&input.value.trim()===message)input.value='';
  const updated=await api('ai/conversations/'+cid);
  if(conversation?.id===cid){conversation=updated;updateDraft();const scroll=$('.conversation-body');if(scroll)scroll.scrollTop=scroll.scrollHeight;}
 }catch(error){showChatError(error);}finally{chatBusy=false;updateDraft();}
}

function recipeBody(r,compact=false){
 const g=r.guidance||r,steps=r.steps||[];
 return `<div class="recipe-sheet"><div class="eyebrow">${esc(r.style)}</div><h2>${esc(r.name)}</h2>${r.summary||r.notes?(compact?disclosure('Notes',`<p>${prose(r.summary||r.notes)}</p>`):`<p class="summary">${prose(r.summary||r.notes)}</p>`):''}<div class="recipe-metrics"><div><label>Batch</label><b>${fmt(r.batch_g,0)} <small>g</small></b></div><div><label>Preheat</label><b>${temp(r.preheat)} <small>${unit()}</small></b></div><div><label>Starting settings</label><b style="font-size:28px">${Object.entries(startingSettings(steps)).map(([k,v])=>k[0].toUpperCase()+v).join(' / ')}</b></div></div><div class="recipe-steps">${steps.filter(s=>!isInitial(s)).map(s=>`<div class="recipe-step"><span class="when">${esc(whenText(s,temp,unit(),clock))}</span><b>${esc(groupOf(s).actions.map(actionText).join(' / '))}</b><p>${prose(s.reason||groupOf(s).actions.filter(a=>['popup','end_alert'].includes(a.control)).map(a=>a.value).join(' '))}</p></div>`).join('')}</div>${g.edited?'<div class="notice">Settings edited after generation. The rationale below describes the original Astra draft.</div>':''}${g.drop?`<div class="recipe-drop"><h3>Drop guide · ${temp(g.drop.min_c)}–${temp(g.drop.max_c)} ${unit()} IBTS</h3><p>${prose(g.drop.guidance)}</p></div>`:''}${g.phases?.length?disclosure('Watch, listen, adjust',g.phases.map(p=>`<div class="recipe-phase"><b>${esc(p.name)} · ${prose(p.cue)}</b><p>${prose(p.action)}</p></div>`).join('')):''}${g.rationale?disclosure('Why this recipe',`<p>${prose(g.rationale)}</p>`):''}${g.assumptions?disclosure('Assumptions & preparation',`<p style="margin-bottom:12px">${prose(g.preparation)}</p><ul>${g.assumptions.map(s=>`<li>${prose(s)}</li>`).join('')}</ul>`):''}${g.adjustments?disclosure('After you taste it',`<ul>${g.adjustments.map(s=>`<li>${prose(s)}</li>`).join('')}</ul>`):''}${g.source_ids?disclosure('References',g.source_ids.map(id=>{const s=aiStatus?.sources?.find(s=>s.id===id);return s?`<a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.title)} ↗</a>`:esc(id);}).join('')):''}</div>`;
}
function disclosure(title,body,open=false){return `<details class="disclosure" ${open?'open':''}><summary>${title}</summary><div class="inside">${body}</div></details>`;}
function beansPage(){return heading('Beans',btn(icon('plus')+' Add beans','bean','primary with-icon'))+`<div class="list-toolbar"><input class="search" id="bean-search" type="search" value="${esc(search)}" placeholder="Find a coffee…" aria-label="Search beans"><span class="small-text muted">${data.lots.length} ${data.lots.length===1?'coffee':'coffees'}</span></div><div id="bean-list">${beanList()}</div><div class="totals"><span><strong>${kg(data.lots.reduce((s,l)=>s+l.stock_g,0))}</strong>green coffee</span><span><strong>${money(data.lots.reduce((s,l)=>s+l.stock_g/1000*l.cost_per_kg,0))}</strong>inventory value</span><span class="spacer"></span>${btn('Stock ledger','ledger','quiet small')}</div>`;}
function beanList(){const lots=data.lots.filter(l=>(l.name+' '+l.origin+' '+l.process).toLowerCase().includes(search.toLowerCase()));return lots.length?`<div class="table-wrap"><table><thead><tr><th>Coffee</th><th>Process</th><th>In stock</th><th>Cost / kg</th><th></th></tr></thead><tbody>${lots.map(l=>`<tr><td><div class="row"><span class="bean-dot">${icon('bean')}</span><button class="name-button" data-action="bean-profile" data-id="${l.id}"><strong>${esc(l.name)}</strong><small>${esc(l.origin)}</small></button></div></td><td>${esc(l.process)}</td><td><button type="button" class="inventory-value" data-action="stock" data-id="${l.id}" aria-label="Edit stock for ${esc(l.name)}"><span class="mono">${kg(l.stock_g)}</span><span class="stock-bar"><i style="width:${Math.min(100,l.stock_g/5000*100)}%"></i></span></button></td><td><button type="button" class="inventory-value mono" data-action="bean-cost" data-id="${l.id}" aria-label="Edit cost for ${esc(l.name)}">${money(l.cost_per_kg)}</button></td><td class="end">${btn('Make a recipe '+icon('arrow'),'bean-recipe','quiet small with-icon',`data-id="${l.id}"`)}</td></tr>`).join('')}</tbody></table></div>`:empty(search?'No matching coffees':'No beans yet','',search?'':btn('Add beans','bean','primary'));}
function historyPage(){return heading('History',btn('Batches','batches','quiet small')+btn('Compare selected','compare','quiet small',compareIds.length<2?'hidden':''))+`<div class="list-toolbar"><input class="search" id="history-search" type="search" value="${esc(search)}" placeholder="Find a roast…" aria-label="Search history"><div class="filters">${['all','hardware','practice'].map(m=>btn({all:'All roasts',hardware:'Real',practice:'Practice'}[m],'filter',historyFilter===m?'active':'',`data-mode="${m}"`)).join('')}</div></div><div id="history-list">${historyList()}</div>`;}
function historyList(){const list=data.roasts.filter(r=>(historyFilter==='all'||r.mode===historyFilter)&&(r.name+' '+r.lot_name).toLowerCase().includes(search.toLowerCase()));return list.length?`<div class="table-wrap"><table><thead><tr><th></th><th>Roast</th><th>Date</th><th>Batch</th><th>Time</th><th>Loss</th><th>Cup</th><th>Status</th></tr></thead><tbody>${list.map(r=>`<tr><td style="width:20px;padding-right:0"><input type="checkbox" data-compare="${r.id}" aria-label="Compare ${esc(r.name)}" ${compareIds.includes(r.id)?'checked':''}></td><td><button class="name-button" data-action="roast-detail" data-id="${r.id}"><strong>${esc(r.name)}</strong><small>${esc(r.lot_name||'Practice coffee')}</small></button></td><td class="muted">${date(r.started)}</td><td class="mono">${fmt(r.green_g,0)} g<small>${r.roasted_g?fmt(r.roasted_g,0)+' g out':'Not weighed'}</small></td><td class="mono">${clock(r.elapsed)}</td><td class="mono">${r.roasted_g?fmt((r.green_g-r.roasted_g)/r.green_g*100)+'%':'—'}</td><td>${r.score==null?'—':fmt(r.score,0)}</td><td><span class="tag ${r.mode==='practice'?'':'tint'}">${r.mode==='practice'?'Practice':r.seasoning?'Seasoning':r.status}</span>${r.mode==='practice'&&r.status!=='complete'?`<small>${esc(r.status)}</small>`:''}</td></tr>`).join('')}</tbody></table></div>`:empty(search?'No matching roasts':'No roasts yet','',search?'':btn('Start a roast','new-roast','primary'),'history');}

// Forms and sheets keep advanced functions one level below the main workspace.
function field(id,name,value='',type='text',attrs=''){return `<div class="field"><label for="${id}">${name}</label><input id="${id}" name="${id}" type="${type}" value="${esc(value)}" ${attrs}></div>`;}
function selectField(id,name,options,value='',placeholder=''){return `<div class="field"><label for="${id}">${name}</label><select id="${id}" name="${id}">${placeholder?`<option value="">${placeholder}</option>`:''}${options.map(([v,text])=>`<option value="${esc(v)}" ${String(v)===String(value)?'selected':''}>${esc(text)}</option>`).join('')}</select></div>`;}
function textarea(id,name,value='',placeholder=''){return `<div class="field"><label for="${id}">${name}</label><textarea id="${id}" name="${id}" placeholder="${esc(placeholder)}">${esc(value)}</textarea></div>`;}
function val(id){return $('#'+id)?.value||'';}
function num(id){return Number(val(id));}
function openModal(title,body,save=null,button='Save',wide=false,kind=''){
 closeMenu();
 saveModal=save;modalKind=kind;const d=$('#dialog');d.className=wide?'wide':'';
 d.innerHTML=`<form id="modal-form"><header class="modal-head"><h2 id="modal-title">${title}</h2>${btn(icon('close'),'close','quiet icon-btn','aria-label="Close"')}</header><div class="modal-body">${body}<div class="form-error" id="modal-error" role="alert"></div></div>${save?`<footer class="modal-foot">${btn('Cancel','close','quiet')}<button type="submit" class="primary">${button}</button></footer>`:''}</form>`;
 if(!d.open)d.showModal();document.body.classList.add('modal-open');
}
function closeModal(){ $('#dialog').close(); }
function batchesModal(){
 const plans=data.plans.filter(p=>p.status==='planned');
 openModal('Batches',`<div class="section-heading"><h3>Upcoming roasts</h3>${btn('Plan a batch','plan','small')}</div>${plans.length?plans.map(p=>`<div class="connection-row"><div><h3>${esc(p.name)}</h3><p>${esc(p.lot_name)} · ${p.batch_g} g · ${esc(p.scheduled)}</p></div><div class="actions">${live.active||live.workspace?'':btn('Roast','planned-roast','small',`data-id="${p.id}"`)}${btn('Cancel','cancel-plan','quiet small',`data-id="${p.id}"`)}</div></div>`).join(''):'<p class="hint">No planned batches.</p>'}<div class="divider"></div><h3>Packaged coffee</h3><p class="hint" style="margin:8px 0 16px">Open a completed real roast in History to record bags.</p>${data.packages.length?`<div class="table-wrap"><table><thead><tr><th>Roast</th><th>Bags</th><th>Price each</th><th></th></tr></thead><tbody>${data.packages.map(p=>`<tr><td>${esc(data.roasts.find(r=>r.id===p.roast_id)?.name||'Roast '+p.roast_id)}</td><td>${p.count} × ${fmt(p.grams_each,0)} g</td><td>${money(p.price_each)}</td><td>${btn('Labels','labels','small',`data-id="${p.id}"`)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="hint">No bags recorded yet.</p>'}`,null,'',true);
}
function planModal(){openModal('Plan a batch',`${field('plan-name','Batch name','','text','required')}<div class="field-grid">${selectField('plan-lot','Beans',data.lots.map(l=>[l.id,l.name]),selectedBean,'Choose coffee')}${selectField('plan-recipe','Recipe',data.profiles.map(p=>[p.id,p.name]),selectedRecipe,'Manual roast')}${field('plan-weight','Batch weight · g',500,'number','min="200" max="1000" required')}${field('plan-date','Roast date',new Date().toLocaleDateString('en-CA'),'date','required')}</div><p class="hint">A plan reserves no stock. Inventory is deducted when the real roast starts.</p>`,async()=>{await api('plans',{name:val('plan-name'),lot_id:num('plan-lot'),profile_id:num('plan-recipe')||null,batch_g:num('plan-weight'),scheduled:val('plan-date')});await loadData();batchesModal();},'Save plan');}
$('#dialog').addEventListener('close',()=>{if(!$('#dialog').open){document.body.classList.remove('modal-open');saveModal=null;modalKind='';}});
$('#dialog').addEventListener('click',e=>{if(e.target===$('#dialog'))closeModal();});
function newRoast(preset={}){
 if(live.active||live.workspace){closeModal();go('roast');return;}
 setupRoast(preset.profile_id||null,preset);
}
function setRoastKind(kind){
 const recipe=kind==='recipe';
 $('#dialog').dataset.roastKind=kind;
 $$('[data-action="roast-kind"]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.kind===kind)));
 $('#start-recipe-panel').hidden=!recipe;
 $('#start-recipe').disabled=!recipe;
 $('#start-manual-settings').hidden=recipe;
 $('#start-manual-settings').disabled=recipe;
 $('#modal-error').textContent='';
}
function updateSetupRecipe(apply=false){
 const p=data.profiles.find(p=>p.id===num('start-recipe'));
 const summary=$('#start-recipe-summary');
 summary.hidden=!p;
 if(!p){summary.innerHTML='';return;}
 const initial=startingSettings(p.steps);
 summary.innerHTML=`<span><small>Preheat</small>${temp(p.preheat)} ${unit()}</span><span><small>Power</small>P${initial.power}</span><span><small>Air</small>F${initial.fan}</span><span><small>Drum</small>D${initial.drum}</span>`;
 if(apply){$('#start-weight').value=p.batch_g;$('#start-name').value=p.name;if(p.guidance?.lot_id)$('#start-lot').value=p.guidance.lot_id;}
}
function setupRoast(pid=null,preset={}){
 const p=data.profiles.find(p=>p.id===pid);
 openModal('Begin Roast',`<div class="roast-kind-picker" role="group" aria-label="Roast method">${btn(`${icon('drum')}<span>Manual</span>`,'roast-kind','roast-kind',`data-kind="manual" aria-pressed="${!p}" aria-controls="start-manual-settings"`)}${btn(`${icon('book')}<span>Recipe</span>`,'roast-kind','roast-kind',`data-kind="recipe" aria-pressed="${!!p}" aria-controls="start-recipe-panel"`)}</div>
 <div id="start-recipe-panel" ${p?'':'hidden'}>${selectField('start-recipe','Recipe',data.profiles.map(r=>[r.id,r.name]),p?.id||'','Select a recipe')}${data.profiles.length?'':'<p class="hint">No saved recipes yet. Add one in Recipes.</p>'}<div id="start-recipe-summary" class="setup-recipe-summary" hidden></div></div>
 <div class="field-grid roast-batch-fields">${selectField('start-lot','Beans',data.lots.map(l=>[l.id,l.name]),preset.lot_id||p?.guidance?.lot_id||selectedBean,'Choose your coffee')}${field('start-name','Batch name',preset.name||p?.name||'New roast','text','required maxlength="300"')}${field('start-weight','Batch · g',preset.batch_g||p?.batch_g||500,'number','required min="200" max="1000"')}</div>
 <fieldset id="start-manual-settings" class="manual-setpoints" ${p?'hidden disabled':''}><legend>Starting setpoints</legend><div class="field-grid">${field('start-preheat','Preheat · °F',446,'number','min="212" max="590" step="0.1" required')}${field('start-power','Power · P0–P10',7,'number','min="0" max="10" step="1" required')}${field('start-fan','Air · F1–F12',3,'number','min="1" max="12" step="1" required')}${field('start-drum','Drum · D1–D9',9,'number','min="1" max="9" step="1" required')}</div></fieldset>
 `,async()=>{
 const recipeMode=$('[data-kind="recipe"]').getAttribute('aria-pressed')==='true';
 const recipe=recipeMode?data.profiles.find(r=>r.id===num('start-recipe')):null;
 if(recipeMode&&!recipe)throw Error('Select a recipe.');
 const body={mode:'hardware',name:val('start-name'),lot_id:num('start-lot')||null,profile_id:recipe?.id||null,green_g:num('start-weight'),seasoning:false,plan_id:preset.plan_id||null,preheat:recipe?.preheat??preheatC(num('start-preheat'))};
 if(!recipe)Object.assign(body,{power:num('start-power'),fan:num('start-fan'),drum:num('start-drum')});
 live=await api('prepare',body);reference=recipe?.reference_roast_id?await api('roasts/'+recipe.reference_roast_id):null;selectedBean=body.lot_id;selectedRecipe=body.profile_id;closeModal();go('roast');
 },'Open roast workspace',true,'roast-setup');
 $('#dialog').classList.add('roast-setup');
 $('#start-recipe').required=true;
 setRoastKind(p?'recipe':'manual');
 updateSetupRecipe();
}

async function beanModal(id){
 if(id)return editBeanInventory(id);
 const pending=jobs.find(j=>j.context.task==='bean'&&!j.lot_id&&['running','complete'].includes(j.status));
 if(pending){beanImportJob=await api('ai/jobs/'+pending.id);openBeanImport();return;}
 newBeanImport();
}
function newBeanImport(){
 beanImportJob=null;beanImportSignature='';
 openModal('Add beans',`${field('bean-url','Product-page link','','url','placeholder="https://www.sweetmarias.com/…" maxlength="3000"')}${disclosure('Or paste the page text',`${textarea('bean-page-text','Product-page text','','Paste the seller’s description…')}<p class="hint">Use this if the link cannot be read.</p>`)}<p class="privacy">Page text is sent to OpenAI through your ChatGPT account.</p>`,async()=>{
  beanImportJob=await api('beans/import',{url:val('bean-url'),text:val('bean-page-text')});jobs=[beanImportJob,...jobs.filter(j=>j.id!==beanImportJob.id)];openBeanImport();
 },'Build bean profile',false,'bean-source');
}
function safeLink(url){try{const parsed=new URL(url);return ['http:','https:'].includes(parsed.protocol)?esc(parsed.href):'';}catch{return '';}}
function beanDocument(doc,source={},inventory=null){
 const sourceLink=safeLink(source.url),flavors=Array.isArray(doc.flavors)?doc.flavors:[];
 return `<article class="bean-dossier"><header class="bean-hero"><div class="bean-art" aria-hidden="true">${icon('bean')}</div><div class="bean-hero-copy"><span class="eyebrow">${esc(doc.origin||'COFFEE PROFILE')}${doc.process?' · '+esc(doc.process):''}</span><h1>${esc(doc.name)}</h1><p>${prose(doc.summary)}</p><div class="flavor-notes">${flavors.map(note=>`<span>${esc(note)}</span>`).join('')}</div></div></header><div class="dossier-body">${inventory?`<div class="bean-inventory-strip"><span><strong>${kg(inventory.stock_g)}</strong>in your collection</span><span><strong>${money(inventory.cost_per_kg)}</strong>per kg</span>${btn('Make a recipe '+icon('arrow'),'bean-recipe','accent with-icon',`data-id="${inventory.id}"`)}</div>`:''}${doc.facts?.length?`<div class="bean-facts">${doc.facts.map(f=>`<div><span>${esc(f.label)}</span><p>${prose(f.value)}</p></div>`).join('')}</div>`:''}<div class="bean-story">${(doc.sections||[]).map((section,i)=>`<section><span class="story-index">${String(i+1).padStart(2,'0')}</span><div><h2>${prose(section.title)}</h2><p>${prose(section.body)}</p></div></section>`).join('')}</div>${doc.roasting_context?`<section class="bean-roasting"><h2>At the roaster</h2><p>${prose(doc.roasting_context)}</p></section>`:''}${doc.unknowns?.length?disclosure('What the page doesn’t tell us',`<ul>${doc.unknowns.map(item=>`<li>${prose(item)}</li>`).join('')}</ul>`):''}${inventory?.notes?`<section class="bean-personal"><h3>Your notes</h3><p>${prose(inventory.notes)}</p></section>`:''}<div class="bean-provenance"><span>${doc.supplier?esc(doc.supplier)+' · ':''}${source.method?esc(source.method):'Your coffee notes'}${source.captured?' · captured '+date(source.captured):''}</span>${sourceLink?`<a href="${sourceLink}" target="_blank" rel="noreferrer">View seller page ↗</a>`:''}</div>${source.truncated?'<p class="notice">This page exceeded the capture limit. The first 100,000 characters were retained.</p>':''}${source.text?disclosure('Original captured context',`<pre class="source-context">${prose(source.text)}</pre>`):''}</div></article>`;
}
function openBeanImport(){
 const job=beanImportJob;if(!job)return;
 beanImportSignature=job.id+':'+job.status;
 if(job.status==='running'){
  openModal('Reading your coffee',`<div class="bean-reading"><i class="spinner"></i><h2>Reading the page…</h2><p class="hint">You can return from Add beans.</p>${btn('Cancel import','cancel-ai','quiet small')}</div>`,null,'',false,'bean-import');
 }else if(job.status==='complete'){
  openModal('Your bean profile',beanDocument(job.result,job.context.source||{})+`<section class="bean-save">${textarea('import-notes','Your notes · optional','','Corrections, purchase notes, or anything you want Astra to consider.')}</section>`,async()=>{
   const saved=await api('beans/save',{id:job.id,stock_g:0,cost_per_kg:0,notes:val('import-notes')});await loadData();jobs=await api('ai/jobs');beanImportJob=null;closeModal();go('beans');beanProfile(saved.id);toast('Coffee saved with its full context.');
  },'Save coffee',true,'bean-preview');$('#dialog').classList.add('bean-popup');
 }else{
  openModal('Couldn’t read that page',`<div class="bean-import-intro"><h2>Try pasting the page text.</h2><p>${esc(job.error)}</p></div>${btn('Try another link or paste text','new-bean-import','primary')}`,null,'',false,'bean-import');
 }
}
async function updateBeanImport(){
 if(!beanImportJob||!['bean-import','bean-preview'].includes(modalKind))return;
 const job=jobs.find(j=>j.id===beanImportJob.id);if(!job||job.id+':'+job.status===beanImportSignature)return;
 beanImportJob=await api('ai/jobs/'+job.id);openBeanImport();
}
function beanProfile(id){
 const lot=data.lots.find(l=>l.id===id);if(!lot)return;
 const details=lot.details||{},doc=details.document||{name:lot.name,origin:lot.origin,process:lot.process,supplier:lot.supplier,summary:lot.notes||'Your green coffee, ready for the next roast.',flavors:[],facts:Object.entries(details).map(([label,value])=>({label,value:typeof value==='string'?value:JSON.stringify(value)})),sections:[]};
 openModal('Your coffee',beanDocument(doc,details.source||{},lot)+`<div class="dossier-actions">${btn('Edit notes','edit-bean','quiet',`data-id="${id}"`)}</div>`,null,'',true,'bean-profile');$('#dialog').classList.add('bean-popup');
}
function editBeanInventory(id){
 const lot=data.lots.find(l=>l.id===id);if(!lot)return;
 openModal('Your coffee notes',`${field('bean-name','Coffee name',lot.name,'text','required')}${textarea('bean-notes','Your notes & corrections',lot.notes,'Add anything you know about this coffee. Astra will consider it alongside the seller page.')}`,async()=>{
  const name=val('bean-name'),notes=val('bean-notes');await loadData();
  await api('lots',{...data.lots.find(l=>l.id===id),name,notes});await loadData();closeModal();render();beanProfile(id);
 },'Save notes');
}
const gramsFor = (amount,unit) => amount*(unit==='lb'?453.59237:1);
function stockModal(id){
 const lot=data.lots.find(l=>l.id===id);if(!lot)return;
 openModal('Edit stock',`<p class="inventory-coffee">${esc(lot.name)}</p><p class="hint inventory-current">Currently ${fmt(lot.stock_g,1)} g · ${fmt(lot.stock_g/453.59237,2)} lbs</p>${selectField('stock-direction','Adjustment',[['add','Add'],['subtract','Subtract']],'add')}<div class="field-grid">${field('stock-amount','Amount','','number','required min="0.000001" step="any" inputmode="decimal"')}${selectField('stock-unit','Unit',[['g','Grams (g)'],['lb','Pounds (lbs)']],'g')}</div>`,async()=>{
  const amount=gramsFor(num('stock-amount'),val('stock-unit'));
  if(!Number.isFinite(amount)||amount<=0)throw Error('Enter an amount greater than zero.');
  const subtract=val('stock-direction')==='subtract';
  await api('stock',{id,amount_g:amount*(subtract?-1:1),reason:subtract?'Stock subtracted':'Stock added'});await loadData();closeModal();render();toast('Stock updated.');
 },'Finish');
}
function costModal(id){
 const lot=data.lots.find(l=>l.id===id);if(!lot)return;
 openModal('Edit cost',`<p class="inventory-coffee">${esc(lot.name)}</p>${field('bean-price','Cost · $',lot.cost_per_kg,'number','required min="0" step="any" inputmode="decimal"')}<div class="field-grid">${field('bean-price-weight','For this amount',1000,'number','required min="0.000001" step="any" inputmode="decimal"')}${selectField('bean-price-unit','Unit',[['g','Grams (g)'],['lb','Pounds (lbs)']],'g')}</div>`,async()=>{
  const weight=gramsFor(num('bean-price-weight'),val('bean-price-unit')),price=num('bean-price');
  if(!Number.isFinite(weight)||weight<=0||!Number.isFinite(price)||price<0)throw Error('Enter a valid price and a weight greater than zero.');
  const cost=price/weight*1000;
  if(cost>10000)throw Error('Cost must be no more than $10,000 per kg.');
  await loadData();await api('lots',{...data.lots.find(l=>l.id===id),cost_per_kg:cost});await loadData();closeModal();render();toast('Cost updated.');
 },'Finish');
}
function importRecipe(){
 openModal('Import RoasTime',`${textarea('import-json','Recipe JSON','','Paste an exported standard R2 recipe…')}<p class="hint">Preview the conditions and actions before saving. R1 and R2 Pro recipes are rejected.</p>`,async()=>{
  let raw;try{raw=JSON.parse(val('import-json'));}catch{throw Error('Paste valid recipe JSON.');}
  const recipe=await api('profiles/import',{recipe:raw});
  openModal('Review import',recipeBody(recipe),async()=>{await api('profiles',recipe);await loadData();closeModal();render();toast('Recipe imported.');},'Save recipe',true);
 },'Preview',true);
}
function editRecipe(id){const p=data.profiles.find(p=>p.id===id)||{steps:[{trigger:'time',at:0,control:'power',value:7},{trigger:'time',at:0,control:'fan',value:3},{trigger:'time',at:0,control:'drum',value:9}]};
 openModal(p.id?'Edit recipe':'Write a recipe',`<div class="field-grid">${field('recipe-name','Name',p.name||'','text','required')}${field('recipe-style','Cup / style',p.style||'Balanced','text','required')}${field('recipe-preheat','Preheat · °F',toF(p.preheat||230),'number','min="212" max="590" step="0.1" required')}${field('recipe-batch','Batch · g',p.batch_g||500,'number','min="200" max="1000" required')}</div>${textarea('recipe-notes','Notes',fahrenheitText(p.notes||''))}<div class="section-heading"><h3>Rules</h3>${btn('Add rule','add-step','quiet small')}</div><p class="hint">All conditions in a rule must match. Each rule runs once. Time starts at charge.</p><div id="step-rows">${p.steps.map(stepRow).join('')}</div>`,async()=>{
 const steps=$$('.step-editor').map(el=>({conditions:$$('.condition-row',el).map(row=>({sensor:$('[data-rule="sensor"]',row).value,op:$('[data-rule="op"]',row).value,value:$('[data-rule="sensor"]',row).value==='time'?Number($('[data-rule="threshold"]',row).value):toC($('[data-rule="threshold"]',row).value)})),actions:$$('.action-row',el).map(row=>{const control=$('[data-rule="control"]',row).value,raw=$('[data-rule="value"]',row).value;return {control,value:['popup','end_alert'].includes(control)?raw:['yellow','first_crack'].includes(control)?1:Number(raw)};}),reason:$('[data-rule="reason"]',el).value,after_turn:el.dataset.afterTurn==='true'}));
 await api('profiles',{id:p.id,name:val('recipe-name'),style:val('recipe-style'),preheat:preheatC(num('recipe-preheat')),batch_g:num('recipe-batch'),notes:val('recipe-notes'),steps,reference_roast_id:p.reference_roast_id});await loadData();closeModal();render();toast('Recipe saved.');},'Save recipe',true);
}
function conditionRow(c={sensor:'time',op:'>=',value:5}){return `<div class="rule-row condition-row"><select data-rule="sensor" aria-label="Condition sensor">${[['ibts','IBTS · °F'],['bt','Bean probe · °F'],['time','Elapsed · sec']].map(([v,n])=>`<option value="${v}" ${c.sensor===v?'selected':''}>${n}</option>`).join('')}</select><select data-rule="op" aria-label="Comparison"><option value=">=" ${c.op==='>='?'selected':''}>≥</option><option value="<=" ${c.op==='<='?'selected':''}>≤</option></select><input data-rule="threshold" aria-label="Condition value" type="number" step="any" min="0" max="3600" value="${esc(c.sensor==='time'?c.value:toF(c.value))}" required>${btn('×','remove-rule-row','quiet small','aria-label="Remove condition"')}</div>`;}
function actionRow(a={control:'power',value:6}){return `<div class="rule-row action-row"><select data-rule="control" aria-label="Recipe action">${[['power','Power · P0–P10'],['fan','Air · F1–F12'],['drum','Drum · D1–D9'],['yellow','Mark yellowing'],['first_crack','Mark first crack'],['popup','Message'],['end_alert','End alert']].map(([v,n])=>`<option value="${v}" ${a.control===v?'selected':''}>${n}</option>`).join('')}</select><input data-rule="value" aria-label="Setting or message" value="${esc(a.value??1)}" required>${btn('×','remove-rule-row','quiet small','aria-label="Remove action"')}</div>`;}
function stepRow(step={trigger:'ibts',at:170,control:'power',value:6,min_time:90}){const g=groupOf(step);return `<div class="step-editor recipe-rule" data-after-turn="${!!g.after_turn}"><div class="row spread"><span class="eyebrow">WHEN</span>${btn('Remove rule','remove-step','quiet small')}</div><div class="rule-conditions">${g.conditions.map(conditionRow).join('')}</div>${btn('+ Condition','add-condition','quiet small')}<div class="eyebrow rule-then">THEN</div><div class="rule-actions">${g.actions.map(actionRow).join('')}</div>${btn('+ Action','add-rule-action','quiet small')}<input data-rule="reason" aria-label="Rule note" placeholder="Note · optional" value="${esc(g.reason||'')}">${g.after_turn?'<span class="hint">Wait for turning point (preserved legacy guard)</span>':''}</div>`;}
function viewRecipe(id,sessionView=false){
 const p=sessionView?workspaceRecipe():data.profiles.find(p=>p.id===id);if(!p)return;
 const busy=!!(live.active||live.workspace),current=p.id===(live.active?.profile_id||live.workspace?.profile_id);
 const actions=sessionView?'':`<div class="actions">${busy?btn('Return to roast','return-roast','quiet'):btn('Use for a roast '+icon('arrow'),'use-recipe','primary with-icon',`data-id="${p.id}"`)}${busy&&current?'':btn('Edit recipe','edit-recipe','quiet',`data-id="${p.id}"`)}</div>`;
 openModal(sessionView?'Roast recipe':'Recipe',recipeBody(p,sessionView)+actions,null,'',true,'recipe');
}
async function roastDetail(id){const r=await api('roasts/'+id);openModal('Roast details',`<div class="history-detail"><div class="row spread"><div><div class="eyebrow">${date(r.started)} · ${r.mode==='practice'?'SIMULATED':'BULLET R2'}</div><h2 style="margin-top:9px">${esc(r.name)}</h2></div><span class="tag">${esc(r.status)}</span></div><div class="chart-wrap" style="padding:20px 0 0">${chart(r.samples,r.events)}</div><div class="legend"><span><i></i>IBTS</span><span><i class="bt"></i>Bean</span><span><i class="ror"></i>RoR</span></div><div class="history-stats"><div>Charge<b>${fmt(r.green_g,0)} g</b></div><div>Roasted<b>${r.roasted_g?fmt(r.roasted_g,0)+' g':'—'}</b></div><div>Duration<b>${clock(r.elapsed)}</b></div><div>Loss<b>${r.roasted_g?fmt((1-r.roasted_g/r.green_g)*100)+'%':'—'}</b></div><div>Development<b>${r.events.some(e=>e.kind==='first_crack')?clock(r.elapsed-r.events.find(e=>e.kind==='first_crack').elapsed):'—'}</b></div></div><div class="event-list">${r.events.filter(e=>!['control','connection','note','recipe_step'].includes(e.kind)).map(e=>`<span><b>${label(e.kind)}</b>${clock(e.elapsed)}</span>`).join('')}</div>${textarea('roast-tasting','How did it taste?',r.tasting,'Sweetness, acidity, body, finish. What would you change?')}<div class="field-grid">${field('roast-score','Cup score · optional',r.score??'','number','min="0" max="100" step="0.1"')}${field('roast-rest','Rest before tasting · days',r.rest_days,'number','min="0" max="90"')}${field('roast-output','Cooled weight · g',r.roasted_g??'','number',`min="1" max="${r.green_g}" step="0.1"`)}</div>${textarea('roast-notes','Roast notes',r.notes)}${disclosure('Event log',r.events.map(e=>`<p><b>${clock(e.elapsed)} · ${esc(label(e.kind))}</b> ${prose(e.kind==='recipe_step'?recipeEventText(e):e.value)}</p>`).join(''))}<div class="actions"><a class="small-text" href="/api/export/${r.id}?format=json" download>Export JSON</a><a class="small-text" href="/api/export/${r.id}?format=csv" download>Export CSV</a>${r.mode==='hardware'&&!r.seasoning&&r.status==='complete'?btn('Package coffee','package','quiet small',`data-id="${r.id}"`):''}${r.mode==='hardware'&&r.status==='complete'?btn('Replay settings','replay-settings','quiet small',`data-id="${r.id}"`):''}${r.lot_id?btn('Recipe from these beans','bean-recipe','quiet small',`data-id="${r.lot_id}"`):''}</div></div>`,async()=>{await api('roast/update',{id:r.id,tasting:val('roast-tasting'),notes:val('roast-notes'),score:val('roast-score'),rest_days:num('roast-rest'),roasted_g:val('roast-output')});await loadData();closeModal();render();toast('Roast and tasting notes saved.');},'Save notes',true);}
function replaySettings(id){openModal('Replay settings',`${field('replay-preheat','Preheat · °F',446,'number','min="212" max="590" step="0.1" required')}<p class="hint">Replays recorded power, air and drum settings by time. Review preheat for this batch.</p>`,async()=>{const recipe=await api('profiles/from-roast',{id,preheat:preheatC(num('replay-preheat'))});openModal('Review replay',recipeBody(recipe),async()=>{const saved=await api('profiles',recipe);await loadData();closeModal();go('recipes');viewRecipe(saved.id);},'Save recipe',true);},'Preview');}
function machineModal(){const h=live.hardware;openModal('Bullet R2',`<div class="connection-row"><div><h3>${h.fresh?'Receiving live telemetry':h.connected?'Connected · waiting for telemetry':'USB disconnected'}</h3><p>${esc(h.error||'Standard R2 · 1700 W · 200–1000 g')}</p></div>${btn(h.connected?'Disconnect':'Connect USB',h.connected?'disconnect':'connect','primary')}</div><p class="hint" style="margin:18px 0">Connect the R2 by USB and close other roasting software that may hold the connection.</p><div class="connection-row"><div><h3>Machine controls</h3><p>${h.armed?'Enabled for this connection':'Enable to send power, fan, drum and machine commands'}</p></div>${btn(h.armed?'Disable':'Enable','arm','',`data-enabled="${!h.armed}" ${!h.fresh?'disabled':''}`)}</div>${!live.active&&!live.workspace?disclosure('Manual machine commands',`<div class="field-grid" style="margin-top:22px">${field('machine-preheat','Preheat target · °F',446,'number','min="212" max="590" step="0.1"')}<div style="align-self:center">${btn('Set preheat target','preheat','',!h.armed?'disabled':'')}</div></div><div class="actions">${btn('Press PRS','prs','',!h.armed?'disabled':'')}</div>`):''}<p class="hint" style="margin-top:16px">USB controls await physical R2 validation. Cooling fan, back-to-back and on-machine crack markers still use the panel.</p><a class="small-text" href="/api/hardware/diagnostics" download="r2-diagnostics.json">Export connection diagnostics</a>`,null,'',false,'machine');}
function settingsModal(){openModal('Your studio',`<div class="field-grid">${field('studio-name','Studio name',boot.settings.studio,'text','required')}${selectField('studio-expertise','Astra experience level',[['beginner','Beginner'],['intermediate','Intermediate'],['advanced','Advanced']],boot.settings.astra_expertise||'beginner')}</div><label class="checkbox"><input id="seasoned" type="checkbox" ${boot.settings.machine_seasoned?'checked':''}>I have completed the R2’s manufacturer seasoning process.</label><div class="divider"></div><div class="connection-row"><div><h3>Astra with ChatGPT</h3><p id="settings-auth">${esc(aiStatus?.message||'Checking sign-in…')}</p></div>${btn('Check sign-in','check-ai','small')}</div><p class="hint" style="margin-top:14px">Uses the official Codex CLI and your ChatGPT account. No API key is needed. On Mac, double-click Connect ChatGPT.command in the app folder. On Windows, sign in to Codex with ChatGPT. Then check again.</p><div class="actions" style="margin-top:17px">${btn('Recipe knowledge','knowledge','quiet small')}<a class="small-text" href="https://learn.chatgpt.com/docs/auth" target="_blank" rel="noreferrer">About account sign-in ↗</a></div>${disclosure('Storage & backup',`<p>All beans, recipes, roast samples, tasting notes and Astra drafts are saved in your local SQLite database.</p><p style="overflow-wrap:anywhere;margin:10px 0">${esc(boot.database)}</p><a href="/api/backup" download>Download a database backup</a>`)}${disclosure('Roaster care',`<p>Clean and maintain the R2 according to the manufacturer’s instructions.</p>${btn('Log maintenance','maintenance','small')}<div style="margin-top:14px">${data.maintenance.slice(0,6).map(m=>`<p>${date(m.created)} · ${esc(m.task)}</p>`).join('')||'No maintenance recorded.'}</div>`)}${disclosure('Bag costs & pricing',`<div class="field-grid">${[['bag_g','Bag weight · g'],['sale_price','Sale price · $'],['packaging','Packaging / bag · $'],['energy','Energy / bag · $'],['fee_percent','Selling fee · %'],['labor_per_bag','Labor / bag · $'],['fixed_per_bag','Other costs / bag · $']].map(([k,label])=>field('cost-'+k,label,boot.settings[k],'number','min="0" step="0.01"')).join('')}</div>`)}<p class="hint" style="margin-top:16px">Version ${boot.version}</p>`,async()=>{const body={studio:val('studio-name'),units:'F',astra_expertise:val('studio-expertise'),machine_seasoned:$('#seasoned').checked};for(const k of ['bag_g','sale_price','packaging','energy','fee_percent','labor_per_bag','fixed_per_bag'])body[k]=num('cost-'+k);await api('settings',body);boot=await api('bootstrap');closeModal();render();toast('Settings saved.');},'Save settings');}
async function knowledgeModal(){if(!aiStatus)aiStatus=await api('ai/status');openModal('What Astra knows',`<div class="stack"><div><div class="eyebrow">MACHINE FIRST</div><h2 style="margin:10px 0">Your standard Bullet R2.</h2><p class="hint">1700 W, 200–1000 g batches, P0–P10. The recipe context covers IBTS versus bean temperature, thermal stabilization, airflow response, machine states and manufacturer preparation.</p></div><div><h3>Roasting, then tasting</h3><p class="hint" style="margin-top:7px">Sensory milestones, heat adjustments, first crack and drop guidance. Numeric targets are provisional until you roast and taste. Astra sees up to six completed, non-seasoning real roasts of the selected coffee, with your notes and a sampled curve.</p></div><div><h3>Knowns and unknowns</h3><p class="hint" style="margin-top:7px">Your bean details and cup goal shape each draft. Missing density or moisture stays unknown. Practice sessions are excluded. Machine preparation status comes from Settings.</p></div><div><h3>References</h3><div class="inside">${aiStatus.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noreferrer">${esc(s.title)} ↗</a>`).join('')}</div></div><p class="hint">Reference pack ${esc(aiStatus.knowledge_version)} · Astra proposes recipes; you review and save them before recipe mode applies their settings.</p></div>`);}

async function generateRecipe(body){const job=await api('ai/generate',body);jobs=[job,...jobs.filter(j=>j.id!==job.id)];selectedJob=job.id;jobSignature='';updateDraft();}
document.addEventListener('submit',async e=>{
 if(!['modal-form','recipe-form'].includes(e.target.id))return;e.preventDefault();
 if(modalKind==='conversation'){sendConversation();return;}
 const form=e.target,error=$('#'+(form.id==='modal-form'?'modal-error':'ai-error')),submit=$('button[type="submit"]',form);error.textContent='';submit.disabled=true;
 try{if(form.id==='modal-form'){if(saveModal)await saveModal();}else{await generateRecipe({lot_id:num('ai-lot'),goal:val('goal'),batch_g:num('ai-batch'),brew:val('brew'),parent_id:draftParent});}}
 catch(err){if(error.isConnected)error.textContent=err.message;else toast(err.message,true);}
 finally{if(submit.isConnected)submit.disabled=form.id==='recipe-form'&&jobs.some(j=>j.status==='running');}
});
document.addEventListener('click',async e=>{
 const el=e.target.closest('[data-page],[data-action]');if(!el||el.disabled)return;
 if(el.dataset.page){if(el.dataset.page===page)closeMenu();else go(el.dataset.page);return;}
 const action=el.dataset.action,id=Number(el.dataset.id);
 try{
  if(action==='menu')return openMenu();
  if(action==='close-menu')return closeMenu();
  if(action==='return-roast'){closeModal();go('roast');return;}
  if(action==='session-recipe')return viewRecipe(null,true);
  if(action==='close')return closeModal();
  if(action==='roast-kind')return setRoastKind(el.dataset.kind);
  if(action==='close-workspace'){live=await api('workspace/cancel',{});reference=null;render();return;}
  if(action==='workspace-connect'||action==='workspace-arm'){el.disabled=true;await api(action==='workspace-connect'?'connect':'arm',action==='workspace-arm'?{enabled:true}:{});live=await api('state');updateRoast();return;}
  if(action==='transition'){el.disabled=true;live=await api('transition',{action:el.dataset.transition,expected_state:el.dataset.state});await loadData();updateRoast();return;}
  if(action==='control-mode'){el.disabled=true;try{live=await api('control-mode',{mode:el.dataset.mode});}finally{updateRoast();}return;}
  if(action==='automation'){el.disabled=true;live=await api('automation',{enabled:el.dataset.enabled==='true'});updateRoast();return;}
  if(action==='dismiss-recipe-alert'){dismissedAlerts.add(id);updateRoast();return;}
  if(action==='import-recipe')return importRecipe();
  if(action==='add-condition')return el.closest('.step-editor').querySelector('.rule-conditions').insertAdjacentHTML('beforeend',conditionRow());
  if(action==='add-rule-action')return el.closest('.step-editor').querySelector('.rule-actions').insertAdjacentHTML('beforeend',actionRow());
  if(action==='remove-rule-row')return el.closest('.rule-row').remove();
  if(action==='add-recipe')return recipePane();
  if(action==='continue-chat'){conversation=await api('ai/conversations/'+id);return recipePane(conversation);}
  if(action==='edit-chat-parameters'){$('.bean-parameters fieldset').disabled=false;$('.bean-parameters').open=true;return;}
  if(action==='retry-chat')return await sendConversation(true);
  if(action==='batches')return batchesModal();
  if(action==='plan')return planModal();
  if(action==='planned-roast'){const p=data.plans.find(p=>p.id===id);return newRoast({...p,plan_id:p.id});}
  if(action==='cancel-plan'){await api('plan/cancel',{id});await loadData();return batchesModal();}
  if(action==='labels'){const p=data.packages.find(p=>p.id===id),r=data.roasts.find(r=>r.id===p.roast_id);return openModal('Batch labels',`<div class="print-label"><div class="eyebrow">${esc(boot.settings.studio)}</div><h2>${esc(r.lot_name||r.name)}</h2><p>${esc(r.name)}</p><div class="divider"></div><p>Roasted ${date(r.started)} · Batch ${r.id}</p><p>Net weight ${fmt(p.grams_each,0)} g / ${fmt(p.grams_each/28.3495,1)} oz</p></div><div class="actions">${btn('Print label','print','primary')}</div><p class="hint">One traceability label. Select the number of copies in your print dialog.</p>`,null,'',false);}
  if(action==='print'){window.print();return;}
  if(action==='go-recipes')return go('recipes');
  if(action==='settings')return settingsModal();
  if(action==='knowledge')return await knowledgeModal();
  if(action==='new-roast')return newRoast();
  if(action==='bean')return await beanModal(id);
  if(action==='bean-profile')return beanProfile(id);
  if(action==='edit-bean')return editBeanInventory(id);
  if(action==='new-bean-import')return newBeanImport();
  if(action==='view-recipe')return viewRecipe(id);
  if(action==='edit-recipe')return editRecipe(id);
  if(action==='add-step')return $('#step-rows').insertAdjacentHTML('beforeend',stepRow());
  if(action==='remove-step')return el.closest('.step-editor').remove();
  if(action==='use-recipe'){selectedRecipe=id;selectedBean=data.profiles.find(p=>p.id===id)?.guidance.lot_id||selectedBean;return newRoast({profile_id:id,lot_id:selectedBean});}
  if(action==='bean-recipe'){selectedBean=id;closeModal();go('recipes');recipePane();return;}
  if(action==='stock')return stockModal(id);
  if(action==='bean-cost')return costModal(id);
  if(action==='ledger'){const movements=await api('movements');return openModal('Stock ledger',movements.length?`<div class="table-wrap"><table><thead><tr><th>Coffee</th><th>Change</th><th>Reason</th><th>Date</th></tr></thead><tbody>${movements.map(m=>`<tr><td>${esc(m.lot_name)}</td><td>${m.amount_g>0?'+':''}${fmt(m.amount_g,0)} g</td><td>${esc(m.reason)}</td><td>${date(m.created)}</td></tr>`).join('')}</tbody></table></div>`:'No stock movements yet.',null,'',true);}
  if(action==='filter'){historyFilter=el.dataset.mode;render();return;}
  if(action==='replay-settings')return replaySettings(id);
  if(action==='roast-detail')return await roastDetail(id);
  if(action==='machine')return machineModal();
  if(['connect','disconnect','arm'].includes(action)){el.disabled=true;await api(action,action==='arm'?{enabled:el.dataset.enabled==='true'}:{});live=await api('state');machineModal();updateRoast();return;}
  if(action==='preheat'){await api('machine',{name:'preheat',value:preheatC(num('machine-preheat'))});toast('Preheat target sent. Verify the machine display.');return;}
  if(action==='prs'){await api('machine',{name:'prs'});toast('PRS requested. Check the machine.');return;}
  if(action==='control'){el.disabled=true;await api('control',{name:el.dataset.control,value:Number(el.dataset.value)});live=await api('state');updateRoast();return;}
  if(action==='event'){await api('event',{kind:el.dataset.kind});live=await api('state');updateRoast();return;}
  if(action==='note')return openModal('Roast note',`${selectField('note-kind','Event',[['note','Note'],['first_crack_end','First crack ends'],['second_crack','Second crack']],'note')}${textarea('note-text','Observation','','Color, aroma, a change you made…')}`,async()=>{await api('event',{kind:val('note-kind'),value:val('note-text')});closeModal();live=await api('state');updateRoast();},'Record event');
  if(action==='drop'){return openModal('Drop the batch',`<p>End the roast recording and move on to cooling and weighing.</p>${live.active.mode==='hardware'?`<label class="checkbox" style="margin-top:18px"><input id="send-cooling" type="checkbox" ${live.hardware.armed?'':'disabled'}>Send PRS to start machine cooling</label><p class="hint" style="margin-top:13px">Open the discharge door at the machine. If manual controls are disabled, start cooling on its panel.</p>`:''}`,async()=>{await api('drop',{send_cooling:$('#send-cooling')?.checked||false});live=await api('state');closeModal();updateRoast();},'Mark drop');}
  if(action==='finish')return openModal('Save your roast',`${field('finished-weight','Cooled weight · g','','number',`required min="1" max="${live.active.green_g}" step="0.1" placeholder="Weigh after cooling"`)}${textarea('finished-notes','First impressions','','How did the roast go?')}`,async()=>{await api('finish',{roasted_g:num('finished-weight'),notes:val('finished-notes')});await loadData();live=await api('state');closeModal();go('history');toast('Roast saved. Add tasting notes when it’s ready.');},'Save roast');
  if(action==='reference'){return openModal('Overlay',`${selectField('reference-id','Saved roast',data.roasts.filter(r=>r.status==='complete').map(r=>[r.id,r.name+' · '+(r.mode==='practice'?'practice':date(r.started))]),reference?.id,'No overlay')}<p class="hint">Reference IBTS appears as a dashed curve. Compare similar charge weights and conditions.</p>`,async()=>{reference=val('reference-id')?await api('roasts/'+num('reference-id')):null;closeModal();updateRoast();},'Apply overlay');}
  if(action==='compare'){const records=await Promise.all(compareIds.slice(0,2).map(id=>api('roasts/'+id)));return openModal('Compare roasts',`<div class="chart-wrap">${chart(records[0].samples,records[0].events,records[1])}</div><div class="split">${records.map((r,i)=>`<div><span class="eyebrow">${i?'DASHED':'SOLID'} · ${r.mode==='practice'?'PRACTICE':'REAL'}</span><h3 style="margin-top:8px">${esc(r.name)}</h3><p class="hint">${fmt(r.green_g,0)} g · ${clock(r.elapsed)} · ${r.roasted_g?fmt((1-r.roasted_g/r.green_g)*100)+'% loss':'No cooled weight'}</p><p class="hint">${esc(r.tasting||'No tasting notes yet.')}</p></div>`).join('')}</div>`,null,'',true);}
  if(action==='check-ai'){el.disabled=true;aiStatus=await api('ai/status?refresh=1');if($('#settings-auth'))$('#settings-auth').textContent=aiStatus.message;toast(aiStatus.message,!aiStatus.ready);return;}
  if(action==='cancel-ai'){await api('ai/cancel',{});toast('Cancelling generation…');return;}
  if(action==='retry-ai'){const j=currentJob();return await generateRecipe({lot_id:j.context.bean.id,batch_g:j.context.batch_g,goal:j.context.goal,brew:j.context.brew,parent_id:j.context.parent_id||null});}
  if(action==='save-ai'||action==='roast-ai'){const j=el.dataset.jobId?conversation.jobs.find(j=>j.id===Number(el.dataset.jobId)):currentJob(),result=await api('ai/save',{id:j.id});await loadData();jobs=await api('ai/jobs');selectedRecipe=result.id;selectedBean=j.context.bean.id;if(conversation)conversation=await api('ai/conversations/'+conversation.id);updateDraft();put('#recipe-library',recipeLibrary());toast('Recipe saved.');return;}
  if(action==='refine-ai'){const j=currentJob();draftParent=j.id;$('#ai-lot').value=j.context.bean.id;$('#ai-batch').value=j.context.batch_g;$('#brew').value=j.context.brew;$('#goal').value='';$('#goal').placeholder='What would you like to change about this draft?';updateDraft();$('#goal').focus();return;}
  if(action==='clear-refine'){draftParent=null;updateDraft();return;}
  if(action==='maintenance')return openModal('Log maintenance',`${selectField('care-task','Task',[['Chaff collector cleaned','Chaff collector cleaned'],['IBTS cleaned','IBTS cleaned'],['Exhaust filter cleaned','Exhaust filter cleaned'],['Deep clean','Deep clean'],['Inspection','Inspection']])}${textarea('care-notes','Notes')}`,async()=>{await api('maintenance',{task:val('care-task'),notes:val('care-notes')});await loadData();closeModal();toast('Maintenance recorded.');});
  if(action==='package'){const r=data.roasts.find(r=>r.id===id),available=r.roasted_g-r.packaged_g;packagingRoast=r;openModal('Package coffee',`<p style="margin-bottom:18px">${esc(r.name)} · ${fmt(available,0)} g available</p><div class="field-grid">${field('bag-count','Bags',1,'number','min="1" max="10000" required')}${field('bag-weight','Weight per bag · g',boot.settings.bag_g,'number','min="1" step="0.001" required')}${field('bag-price','Price per bag · $',boot.settings.sale_price,'number','min="0" step="0.01" required')}</div><div id="bag-estimate" class="notice" style="margin-bottom:15px"></div><p class="hint">Green coffee cost for this roast: ${money(r.cost_per_kg*r.green_g/1000)}. Packaging and operating costs are adjustable in Settings.</p>`,async()=>{await api('packages',{roast_id:id,count:num('bag-count'),grams_each:num('bag-weight'),price_each:num('bag-price')});await loadData();closeModal();render();toast('Bags recorded.');},'Record bags');updateBagEstimate();return;}
 }catch(error){const target=$('#dialog').open?$('#modal-error'):null;if(target)target.textContent=error.message;else toast(error.message,true);}
 finally{if(el.isConnected&&el.disabled&&!['event','control'].includes(action))el.disabled=false;if(modalKind==='conversation')updateDraft();}
});
function updateBagEstimate(){if(!$('#bag-estimate')||!packagingRoast)return;const s=boot.settings,price=num('bag-price'),green=packagingRoast.cost_per_kg*packagingRoast.green_g/1000/packagingRoast.roasted_g*num('bag-weight'),other=s.packaging+s.energy+s.labor_per_bag+s.fixed_per_bag+price*s.fee_percent/100;$('#bag-estimate').textContent='Per bag: '+money(green)+' green coffee + '+money(other)+' allocated costs. Estimated contribution: '+money(price-green-other)+'.';}
document.addEventListener('input',e=>{if(['bag-weight','bag-price','bag-count'].includes(e.target.id))updateBagEstimate();if(e.target.id==='bean-search'){search=e.target.value;$('#bean-list').innerHTML=beanList();}if(e.target.id==='history-search'){search=e.target.value;$('#history-list').innerHTML=historyList();}});
document.addEventListener('change',async e=>{const el=e.target;try{
 if(el.id==='chat-expertise'){el.disabled=true;try{await api('settings',{astra_expertise:el.value});boot=await api('bootstrap');}catch(error){el.value=boot.settings.astra_expertise||'beginner';throw error;}finally{el.disabled=false;}return;}
 if(el.dataset.rule==='sensor'){const input=$('[data-rule="threshold"]',el.closest('.condition-row'));input.value=el.value==='time'?5:338;}
 if(el.id==='chat-lot'){$('#custom-beans').hidden=!!el.value;}
 if(el.id==='speed')await api('practice',{speed:Number(el.value)});
 if(el.id==='draft-choice'){selectedJob=Number(el.value);updateDraft();}
 if(el.id==='ai-lot'){selectedBean=el.value;if(draftParent){draftParent=null;updateDraft();}}
 if(el.id==='start-recipe')updateSetupRecipe(true);
 if(el.id==='start-lot'&&val('start-name')==='New roast')$('#start-name').value=data.lots.find(l=>l.id==el.value)?.name||'New roast';
 if(el.dataset.compare){const id=Number(el.dataset.compare);if(el.checked){if(compareIds.length>=2){el.checked=false;toast('Choose two roasts to compare.');return;}compareIds.push(id);}else compareIds=compareIds.filter(n=>n!==id);const b=$('[data-action="compare"]');if(b)b.hidden=compareIds.length!==2;}
}catch(error){toast(error.message,true);}});
document.addEventListener('keydown',e=>{
 if(e.target.id!=='chat-message'||e.key!=='Enter'||e.isComposing)return;
 e.preventDefault();sendConversation();
});
document.addEventListener('keydown',async e=>{if(page!=='roast'||($('#dialog').open||$('#site-menu')?.open)||e.target.matches('input,textarea,select,button')||e.ctrlKey||e.metaKey||e.altKey||live.active?.status!=='roasting')return;const kind={y:'yellow',f:'first_crack'}[e.key.toLowerCase()];if(kind){e.preventDefault();try{await api('event',{kind});live=await api('state');updateRoast();}catch(error){toast(error.message,true);}}});
window.addEventListener('hashchange',()=>{const p=location.hash.slice(1);if(p!==page&&['roast','recipes','beans','history'].includes(p)){closeMenu();page=p;search='';render();}});
async function poll(){if(pollBusy)return;pollBusy=true;try{
 const old=live.active?.status;live=await api('state');if(old!==live.active?.status)await loadData();updateRoast();
 if(++pollCount%3===0&&(page==='recipes'||modalKind==='conversation'||jobs.some(j=>j.status==='running'))){
  if(conversation&&modalKind==='conversation'){
   const cid=conversation.id,updated=await api('ai/conversations/'+cid);
   if(conversation?.id===cid){conversation=updated;updateDraft();}
  }
  jobs=await api('ai/jobs');const sig=jobs.map(j=>[j.id,j.status,j.profile_id].join(':')).join('|');
  if(sig!==jobSignature){await updateBeanImport();conversations=await api('ai/conversations');put('#conversation-list',conversationList());if($('.conversation-list'))$('.conversation-list').hidden=!conversations.length;jobSignature=sig;}
 }
 if(modalKind==='conversation')updateDraft();
 if($('#job-time'))$('#job-time').textContent=clock((Date.now()-new Date(currentJob().created))/1000)+' elapsed';
 if(old==='roasting'&&live.active?.status==='cooling')toast('Roast ended. Cool and weigh your batch.');
 }catch(error){if(modalKind==='conversation')showChatError(new Error('Could not refresh the conversation. Your messages are saved; reconnect to the local app.'));if($('#roast-error'))$('#roast-error').innerHTML='<div class="notice error">The local app is unreachable. Use the R2 panel. Saved samples remain in your database.</div>';$$('#controls button,#events button').forEach(b=>b.disabled=true);}finally{pollBusy=false;}}
try{boot=await api('bootstrap');[data,live,jobs,conversations]=await Promise.all([api('data'),api('state'),api('ai/jobs'),api('ai/conversations')]);selectedJob=jobs[0]?.id;selectedBean=data.lots[0]?.id||'';render();setInterval(poll,1000);setInterval(updateHomeClock,1000);api('ai/status').then(status=>{aiStatus=status;updateDraft();}).catch(()=>{});}catch(error){$('#app').innerHTML=`<div class="loading"><h2>Couldn’t open your studio.</h2><p>${esc(error.message)}</p><p>Run Start Roasting.cmd, then reload.</p></div>`;}

window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{updateRoast();const wrap=$('#dialog .chart-wrap');if($('#dialog').open&&wrap&&reviewChart)wrap.innerHTML=chart(reviewChart.samples,reviewChart.events,reviewChart.overlay);},80);});
