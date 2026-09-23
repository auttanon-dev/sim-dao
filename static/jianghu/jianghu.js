import { SceneRenderer } from './scene-renderer.mjs';
import { LatestRequest, MAX_ACTORS } from './scene-model.mjs';

const $ = id => document.getElementById(id);
const state = {data:null, world:null, place:null, selected:null, query:'', tab:'town', refreshPaused:false, cinema:false, artReady:false, loading:false, signature:null};
const initialParams=new URLSearchParams(location.search);
for(const key of ['world','place']) {
  const value=initialParams.get(key);
  if(value!==null && /^\d+$/.test(value) && Number.isSafeInteger(Number(value))) state[key]=Number(value);
}
const requests = new LatestRequest();
const renderer = new SceneRenderer($('townCanvas'), actor => showCharacter(actor.id));
const number = new Intl.NumberFormat('th-TH');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stateName = name => ({Cultivating:'บำเพ็ญเพียร',Relaxing:'พักผ่อน',Socializing:'พบปะผู้คน',Sleeping:'พักผ่อน',Working:'ทำงาน',Training:'ฝึกฝน',Traveling:'เดินทาง',Meditating:'บำเพ็ญเพียร',Idle:'พักอยู่ในสถานที่'})[name] || name;
let worldBusy=false;
function syncWorld() {
  const live=state.data?.live;
  const running=live?.state==='running', stopping=live?.state==='stopping';
  renderer.worldRunning=running&&!state.refreshPaused;
  $('worldToggle').disabled=worldBusy||!live||stopping||state.data?.source==='preview';
  $('worldToggle').textContent=stopping?'กำลังบันทึกและพัก…':running?'พักเวลาโลก':'เดินโลกต่อ';
  $('worldToggle').setAttribute('aria-pressed',String(running));
  $('sourceLabel').textContent=live?.state==='error'?'โลกหยุด · เกิดข้อผิดพลาด':running?'เชื่อม SimDao · โลกกำลังเดิน':stopping?'SimDao · กำลังบันทึก':'SimDao · เวลาหยุดอยู่';
  if(state.data?.source==='preview')$('sourceLabel').textContent='โลกตัวอย่าง · ยังไม่ได้เชื่อมบันทึก';
  $('sourceLabel').title=live?.error||'';
}
const selectedActor = () => state.data?.residents.find(a => a.id === state.selected);

function panel(name, open) {
  $(name+'Panel').hidden = !open;
  $(name+'Toggle').setAttribute('aria-expanded', String(open));
  if (matchMedia('(max-width:760px)').matches && open) {
    const other = name==='places'?'people':'places'; $(other+'Panel').hidden=true;
    $(other+'Toggle').setAttribute('aria-expanded','false');
  }
  document.body.classList.toggle('has-people', !$('peoplePanel').hidden);
}
function notice(message, error=false) {
  $('notice').textContent=message; $('notice').hidden=false; $('notice').classList.toggle('error',error);
}
function ready() { if (state.data && (state.tab==='map' || (state.artReady && renderer.background))) $('notice').hidden=true; }
function setView(tab) {
  state.tab=tab;
  $('townCanvas').hidden=tab!=='town'; $('mapScene').hidden=tab!=='map';
  $('townTab').setAttribute('aria-pressed',String(tab==='town'));
  $('mapTab').setAttribute('aria-pressed',String(tab==='map'));
  for(const id of ['moodToggle','motionToggle','zoomIn','zoomOut','resetView']) $(id).disabled=tab!=='town';
  renderer.setVisible(tab==='town');
  $('townTab').textContent=state.data?.scene?'ชมสถานที่':'กลับโรงเตี๊ยม';
  $('townCanvas').setAttribute('aria-label','ฉาก'+(state.data?.place.name||'')+' ใช้ลูกศรเลื่อนกล้อง บวกหรือลบเพื่อซูม');
  $('followToggle').disabled=tab!=='town'||!renderer.actors.some(a=>a.id===state.selected);
  if(tab==='map'){ renderer.follow(false); syncFollow(); renderMap(); }
  $('sceneCredit').textContent=tab==='town'?'ท่าทางประกอบ · ผู้คนจากโลกจำลอง':'แผนที่และเส้นทางของโลกจำลอง';
}

function renderPlaces() {
  const places=(state.data?.places||[]).filter(p=>p.name.includes(state.query));
  $('placeList').innerHTML=places.map(p=>'<button class="place-button '+(p.id===state.place?'active':'')+'" data-place="'+p.id+'"><span>'+esc(p.name)+'<small>'+esc(p.type)+(p.scene_id?' · มีฉากให้ชม':'')+'</small></span><span class="count">'+p.population+' คน</span></button>').join('')||'<p class="empty">ไม่พบสถานที่</p>';
}
function renderResidents() {
  const residents=state.data.residents, scroll=$('residentList').scrollTop;
  $('residentCount').textContent=number.format(residents.length);
  $('populationDetail').textContent=residents.length>MAX_ACTORS?'มี '+residents.length+' คน · แสดงในฉาก '+MAX_ACTORS+' คน':'อยู่ในสถานที่ '+residents.length+' คน';
  $('residentList').innerHTML=residents.map(a=>'<button class="resident-button '+(a.id===state.selected?'active':'')+'" data-id="'+a.id+'"><canvas class="resident-sprite" width="80" height="112" aria-hidden="true"></canvas><span class="resident-name">'+esc(a.name)+'<small>'+esc(a.realm)+' · '+esc(stateName(a.state))+'</small></span></button>').join('')||'<p class="empty">ไม่มีผู้คนอยู่ที่นี่ในบันทึกปัจจุบัน</p>';
  $('residentList').querySelectorAll('[data-id]').forEach(button=>{
    const actor=residents.find(a=>a.id===Number(button.dataset.id));
    renderer.drawPortrait(button.querySelector('canvas'),actor);
  });
  $('residentList').scrollTop=scroll;
}
function renderEvents() {
  $('eventList').innerHTML=state.data.events.map(e=>'<article class="event"><small>วันที่ '+number.format(e.day)+' · '+esc(e.kind)+'</small><p>'+esc(e.text)+'</p></article>').join('')||'<p class="empty">ยังไม่มีบันทึกเหตุการณ์ในสถานที่นี้</p>';
}
function renderMap() {
  if(!state.data)return;
  const places=state.data.places, byId=new Map(places.map(p=>[p.id,p]));
  const xs=places.map(p=>p.x),ys=places.map(p=>p.y),minX=Math.min(...xs),minY=Math.min(...ys);
  const spanX=Math.max(...xs)-minX||1,spanY=Math.max(...ys)-minY||1;
  const px=x=>70+(x-minX)/spanX*800,py=y=>45+(y-minY)/spanY*470;
  $('worldMap').setAttribute('viewBox','0 0 1040 570');
  $('worldMap').innerHTML=state.data.roads.map(r=>{
    const a=byId.get(r.a),b=byId.get(r.b);
    return a&&b?'<line class="road '+(r.open?'':'closed')+'" x1="'+px(a.x)+'" y1="'+py(a.y)+'" x2="'+px(b.x)+'" y2="'+py(b.y)+'"/>':'';
  }).join('')+places.map(p=>'<g role="button" aria-label="'+esc(p.name)+' '+p.population+' คน" class="map-node '+(p.id===state.place?'active':'')+'" tabindex="0" data-place="'+p.id+'" transform="translate('+px(p.x)+','+py(p.y)+')"><title>'+esc(p.name)+'</title><circle r="'+(p.id===state.place?9:6)+'"/><text x="12" y="5">'+esc(p.name)+'</text></g>').join('');
}
function syncFollow() {
  $('followToggle').setAttribute('aria-pressed',String(renderer.following));
  $('followToggle').textContent=renderer.following?'เลิกติดตามกล้อง':'กล้องติดตาม';
}
function showCharacter(id) {
  const actor=state.data?.residents.find(a=>a.id===id);if(!actor)return;
  state.selected=id;renderer.select(id);
  $('characterCard').hidden=false; $('characterName').textContent=actor.name;
  $('characterOrg').textContent=actor.org;
  $('characterDao').textContent=actor.realm+' · '+actor.dao+' · '+stateName(actor.state);
  for(const [prefix,value,max] of [['hp',actor.hp,actor.max_hp],['mp',actor.mp,actor.max_mp]]) {
    $(prefix+'Meter').value=max>0?Math.max(0,Math.min(100,value/max*100)):0;
    $(prefix+'Value').textContent=Math.round(value)+'/'+Math.round(max);
  }
  $('characterSkills').innerHTML=actor.skills.slice(0,4).map(skill=>'<span>'+esc(skill)+'</span>').join('')||'<span>ยังไม่มีวิชาที่บันทึกไว้</span>';
  $('characterRelations').textContent=(actor.gender?actor.gender+' · อายุ '+actor.age+' ปี · ':'')+'สหาย '+actor.bonds+' · คู่แค้น '+actor.rivals;
  renderer.drawPortrait($('portraitCanvas'),actor);
  $('residentList').querySelectorAll('[data-id]').forEach(b=>b.classList.toggle('active',Number(b.dataset.id)===id));
  $('followToggle').disabled=state.tab!=='town'||!renderer.actors.some(a=>a.id===id);
  syncFollow();
}
function closeCharacter() {
  state.selected=null; renderer.select(null); renderer.follow(false);syncFollow();
  $('characterCard').hidden=true;
  $('residentList').querySelectorAll('.active').forEach(b=>b.classList.remove('active'));
}
function renderData() {
  const d=state.data,p=d.place;
  $('locationName').textContent=p.name;
  $('locationType').textContent=d.worlds.find(w=>w.id===d.world_id)?.name+' · '+p.type;
  $('locationPopulation').textContent=p.population+' คนอยู่ที่นี่ · '+d.season;
  $('worldClock').textContent='วันที่ '+number.format(d.day)+' · '+d.season;
  syncWorld();
  $('worldSelect').innerHTML=d.worlds.map(w=>'<option value="'+w.id+'">'+esc(w.name)+'</option>').join('');
  $('worldSelect').value=String(d.world_id);
  renderer.setActors(d.scene?d.residents:[]);
  renderPlaces();renderResidents();renderEvents();renderMap();
  if(state.selected!==null) {
    if(selectedActor())showCharacter(state.selected);
    else {closeCharacter();$('refreshStatus').textContent='ตัวละครที่เลือกไม่ได้อยู่ที่นี่แล้ว';}
  }
  ready();
}
async function loadData({silent=false,enter=false}={}) {
  if(silent&&state.loading)return;
  const request=requests.start();state.loading=true;
  let timeout=false;
  const timer=setTimeout(()=>{if(requests.current(request.number)){timeout=true;requests.controller?.abort();}},2000);
  if(!state.data)notice('กำลังเปิดฉากและอ่านบันทึกโลก…');
  if(!silent)$('refreshStatus').textContent='กำลังอ่าน…';
  try {
    const params=new URLSearchParams();
    if(state.world!==null)params.set('world',state.world);
    if(state.place!==null)params.set('place',state.place);
    const response=await fetch('/api/jianghu?'+params,{signal:request.signal,cache:'no-store'});
    if(!response.ok)throw new Error('อ่านข้อมูลไม่ได้ ('+response.status+')');
    const data=await response.json();
    if(!requests.current(request.number))return;
    clearTimeout(timer);
    const signature=JSON.stringify(data);
    if((data.scene?.id??null)!==renderer.sceneId || (data.scene && !renderer.background)) {
      notice('กำลังเปิด'+data.place.name+'…'); renderer.setVisible(false);
      await renderer.setScene(data.scene?.id??null);
      if(!requests.current(request.number))return;
    }
    state.world=data.world_id;state.place=data.place.id;
    if(signature!==state.signature) {state.data=data;state.signature=signature;renderData();}
    renderer.setActors(data.scene?data.residents:[]);
    renderer.setVisible(state.tab==='town');
    if(enter||!data.scene)setView(data.scene?'town':'map');
    ready();$('refreshStatus').textContent='อ่านล่าสุด '+new Date().toLocaleTimeString('th-TH',{hour:'2-digit',minute:'2-digit'});
  } catch(error) {
    if(!requests.current(request.number))return;
    if(error.name==='AbortError'&&!timeout)return;
    $('refreshStatus').textContent=state.data?'อ่านรอบใหม่ไม่สำเร็จ · กำลังแสดงข้อมูลเดิม':'อ่านข้อมูลไม่ได้';
    if(!state.data)notice('เปิดโลกจำลองไม่สำเร็จ กด “อ่านบันทึกล่าสุด” เพื่อลองอีกครั้ง',true);
    else if(!renderer.background) {
      setView('map');
      notice('เปิดฉากไม่สำเร็จ กด “อ่านบันทึกล่าสุด” เพื่อลองอีกครั้ง',true);
    }
    console.error(error);
  } finally {clearTimeout(timer);if(requests.current(request.number))state.loading=false;}
}
function choosePlace(id) {
  closeCharacter();state.place=id;renderer.reset();
  panel('places',false);loadData({enter:true});
}

$('placeList').addEventListener('click',e=>{const b=e.target.closest('[data-place]');if(b)choosePlace(Number(b.dataset.place));});
$('residentList').addEventListener('click',e=>{const b=e.target.closest('[data-id]');if(b)showCharacter(Number(b.dataset.id));});
$('worldMap').addEventListener('click',e=>{const b=e.target.closest('[data-place]');if(b)choosePlace(Number(b.dataset.place));});
$('worldMap').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){const b=e.target.closest('[data-place]');if(b){e.preventDefault();choosePlace(Number(b.dataset.place));}}});
$('placeSearch').addEventListener('input',e=>{state.query=e.target.value;renderPlaces();});
$('worldSelect').addEventListener('change',e=>{closeCharacter();state.world=Number(e.target.value);state.place=null;loadData({enter:true});});
$('townTab').onclick=()=>{if(state.data?.scene)setView('town');else{closeCharacter();state.world=0;state.place=null;loadData({enter:true});}};
$('mapTab').onclick=()=>setView('map');
for(const name of ['places','people']) {
  $(name+'Toggle').onclick=()=>panel(name,$(name+'Panel').hidden);
  $('close'+name[0].toUpperCase()+name.slice(1)).onclick=()=>panel(name,false);
}
$('closeCard').onclick=closeCharacter;
$('followToggle').onclick=()=>{renderer.follow(!renderer.following);syncFollow();};
$('townCanvas').addEventListener('pointermove',syncFollow);
$('townCanvas').addEventListener('keydown',syncFollow);
$('moodToggle').onclick=()=>{renderer.lighting(!renderer.night);$('moodToggle').setAttribute('aria-pressed',String(renderer.night));$('moodToggle').textContent=renderer.night?'กลับแสงยามเย็น':'แสงยามค่ำ';};
function syncMotion() {$('motionToggle').setAttribute('aria-pressed',String(renderer.paused));$('motionToggle').textContent=renderer.paused?'เปิดภาพเคลื่อนไหว':'พักภาพเคลื่อนไหว';}
$('motionToggle').onclick=()=>{renderer.pause(!renderer.paused);syncMotion();};
renderer.reducedMotion.addEventListener('change',syncMotion);
$('zoomIn').onclick=()=>renderer.zoom(1.2);$('zoomOut').onclick=()=>renderer.zoom(1/1.2);
$('resetView').onclick=()=>{renderer.reset();syncFollow();};
$('cinemaToggle').onclick=()=>{state.cinema=!state.cinema;document.body.classList.toggle('cinema',state.cinema);$('cinemaToggle').setAttribute('aria-pressed',String(state.cinema));$('cinemaToggle').textContent=state.cinema?'แสดงข้อมูล':'ชมเต็มฉาก';};
$('refreshToggle').onclick=()=>{state.refreshPaused=!state.refreshPaused;$('refreshToggle').textContent=state.refreshPaused?'เปิดการอัปเดต':'พักการอัปเดต';$('refreshToggle').setAttribute('aria-pressed',String(state.refreshPaused));syncWorld();if(!state.refreshPaused)loadData();};
$('refreshNow').onclick=()=>loadData();
$('worldToggle').onclick=async()=>{
  if(worldBusy)return;
  const action=state.data?.live?.state==='running'?'stop':'start';
  worldBusy=true;syncWorld();
  try {
    const response=await fetch('/api/jianghu/live/'+action,{method:'POST',signal:AbortSignal.timeout(15000)});
    if(!response.ok)throw new Error('เปลี่ยนเวลาโลกไม่สำเร็จ ('+response.status+')');
    await loadData();
  } catch(error) {
    notice('เปลี่ยนเวลาโลกไม่สำเร็จ กดอัปเดตเพื่อตรวจสถานะก่อนลองอีกครั้ง',true);console.error(error);
  } finally {worldBusy=false;syncWorld();}
};
document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(state.cinema)$('cinemaToggle').click();closeCharacter();panel('places',false);}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!state.refreshPaused)loadData({silent:true});});
setInterval(()=>{if(!state.refreshPaused&&!document.hidden)loadData({silent:true});},15000);

panel('people',!matchMedia('(max-width:760px)').matches);syncMotion();
renderer.load().then(()=>{state.artReady=true;if(state.data)renderResidents();if(selectedActor())showCharacter(state.selected);ready();}).catch(error=>{notice('โหลดภาพฉากไม่สำเร็จ กรุณารีเฟรชหน้าเพื่อลองอีกครั้ง',true);console.error(error);});
loadData({enter:true});
