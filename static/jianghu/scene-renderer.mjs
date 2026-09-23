import { SCENES } from './scene-config.mjs';
import { WIDTH, HEIGHT, MAX_ACTORS, CHARACTER_SHEETS, characterArt, actorResting, mod, Camera, actorPose, spriteBox, hitActor } from './scene-model.mjs';

function imageAsset(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const timer=setTimeout(()=>{image.onload=null;image.onerror=null;reject(new Error('โหลดภาพหมดเวลา: '+url));},20000);
    image.onload = () => {clearTimeout(timer);resolve(image);};
    image.onerror = () => {clearTimeout(timer);reject(new Error('โหลดภาพไม่สำเร็จ: ' + url));}; image.src = url;
  });
}

export class SceneRenderer {
  constructor(canvas, onSelect) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.onSelect = onSelect;
    this.camera = new Camera(1, 1); this.actors = []; this.selected = null; this.following = false;
    this.time = 0; this.actorTime = 0; this.worldRunning = false; this.lastFrame = 0; this.visible = true; this.paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.scene = SCENES['river-inn']; this.sceneId = null; this.sceneRevision = 0; this.images = new Map(); this.atlases = new Map();
    this.night = false; this.frame = null; this.pointer = null; this.hover = null;
    this.resizeObserver = new ResizeObserver(() => this.resize()); this.resizeObserver.observe(canvas.parentElement);
    this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
    this.reducedMotion.addEventListener('change', e => { if (e.matches) this.pause(true); });
    document.addEventListener('visibilitychange', () => this.schedule());
    this.bindInput(); this.resize();
  }
  async load() {
    const atlases=await Promise.all(CHARACTER_SHEETS.map(async name=>[name,await this.asset(name)]));
    this.atlases=new Map(atlases);
    this.draw();
  }
  asset(name) {
    if (!this.images.has(name)) {
      const pending=imageAsset('/jianghu-assets/'+name).catch(error=>{this.images.delete(name);throw error;});
      this.images.set(name,pending);
    }
    return this.images.get(name);
  }
  async setScene(id) {
    if (id===this.sceneId && this.background) return true;
    const revision=++this.sceneRevision;
    this.sceneId=id; this.background=null; this.actors=[]; this.hover=null;
    this.selected=null; this.following=false; this.camera.reset(); this.draw(); this.schedule();
    if(!id) return true;
    const scene=SCENES[id];
    if(!scene) throw new Error('ไม่พบฉาก '+id);
    const background=await this.asset(scene.image);
    if(revision!==this.sceneRevision) return false;
    this.scene=scene; this.background=background; this.time=0; this.actorTime=0;
    this.draw(); this.schedule(); return true;
  }
  resize() {
    const { width, height } = this.canvas.parentElement.getBoundingClientRect();
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(width * this.dpr); this.canvas.height = Math.round(height * this.dpr);
    this.camera.resize(width, height); this.draw();
  }
  setActors(actors) {
    const clocks=new Map(this.actors.map(actor=>[actor.id,actor.motion_seconds]));
    this.actors = actors.slice(0, MAX_ACTORS).map(actor=>({...actor,motion_seconds:clocks.get(actor.id)??0}));
    if (!this.actors.some(a => a.id === this.selected)) { this.selected = null; this.following = false; }
    this.draw();
  }
  select(id) { this.selected = id; this.draw(); }
  follow(enabled) {
    this.following = enabled && this.actors.some(a => a.id === this.selected);
    if (this.following) { this.camera.zoom = Math.max(1.35, this.camera.zoom); this.centerSelected(); }
    this.draw();
  }
  centerSelected() {
    const actor = this.actors.find(a => a.id === this.selected); if (!actor) return;
    const pose = actorPose(actor, this.actorTime, this.scene.paths); this.camera.x = pose.x; this.camera.y = pose.y - 65; this.camera.constrain();
  }
  setVisible(value) { this.visible = value; this.lastFrame = 0; if (value) this.resize(); this.schedule(); }
  pause(value) { this.paused = value; this.lastFrame = 0; this.draw(); this.schedule(); }
  lighting(value) { this.night = value; this.draw(); }
  zoom(factor, point) { this.camera.zoomAt(factor, point); if (this.following) this.centerSelected(); this.draw(); }
  reset() { this.camera.reset(); this.following = false; this.draw(); }
  schedule() {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
    if (!this.visible || this.paused || document.hidden || !this.background) { this.lastFrame = 0; return; }
    this.frame = requestAnimationFrame(now => {
      this.frame = null;
      if (this.lastFrame && now - this.lastFrame < 1000 / 30) { this.schedule(); return; }
      const delta = this.lastFrame ? Math.min((now - this.lastFrame) / 1000, .1) : 0;
      this.lastFrame = now; this.time += delta;
      if(this.worldRunning) {
        this.actorTime += delta;
        for(const actor of this.actors)if(!actorResting(actor))actor.motion_seconds+=delta;
      }
      this.draw(); this.schedule();
    });
  }
  drawPortrait(canvas, actor) {
    const ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height);
    const {source,sheet}=characterArt(actor), atlas=this.atlases.get(sheet);
    if (!atlas) return;
    const height = canvas.height - 4, width = height * source[2] / source[3];
    ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(atlas, ...source, (canvas.width - width) / 2, 2, width, height);
  }
  draw() {
    if (!this.visible) return;
    const c = this.ctx, cam = this.camera;
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (!this.background) return;
    if (this.following) this.centerSelected();
    c.setTransform(this.dpr * cam.scale, 0, 0, this.dpr * cam.scale,
      this.dpr * (cam.width / 2 - cam.x * cam.scale), this.dpr * (cam.height / 2 - cam.y * cam.scale));
    c.imageSmoothingEnabled = true; c.imageSmoothingQuality = 'high';
    c.drawImage(this.background, 0, 0, WIDTH, HEIGHT);
    if (this.night) { c.fillStyle = '#10283d70'; c.fillRect(0, 0, WIDTH, HEIGHT); }
    this.water(); this.lanterns();
    const poses = this.actors.map(actor => ({ actor, pose: actorPose(actor, this.actorTime, this.scene.paths) })).sort((a, b) => a.pose.y - b.pose.y);
    for (const { actor, pose } of poses) this.drawActor(actor, pose);
    this.motes();
  }
  water() {
    const c = this.ctx, t = this.time, polygon=this.scene.water;
    if(!polygon.length) return;
    const xs=polygon.map(p=>p[0]),ys=polygon.map(p=>p[1]);
    const minX=Math.min(...xs),minY=Math.min(...ys),w=Math.max(...xs)-minX,h=Math.max(...ys)-minY;
    c.save(); c.beginPath();
    polygon.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y)); c.closePath(); c.clip();
    for (let i = 0; i < 34; i++) {
      const x = minX + mod(i * 127, w), y = minY + mod(i * 61, h);
      c.globalAlpha = Math.max(0, .12 + .14 * Math.sin(t * 1.8 + i)) * (this.night ? .45 : 1);
      c.strokeStyle = '#fff2bb'; c.lineWidth = 1.4; c.beginPath();
      c.moveTo(x + Math.sin(t + i) * 3, y); c.lineTo(x + 6 + mod(i, 13), y); c.stroke();
    }
    c.restore();
  }
  lanterns() {
    const c = this.ctx;
    const lamps = this.scene.lamps;
    c.save(); c.globalCompositeOperation = 'screen';
    lamps.forEach(([x,y,r], i) => {
      const pulse = .15 + .018 * Math.sin(this.time * 2.2 + i * 3);
      const glow = c.createRadialGradient(x,y,0,x,y,r * (this.night ? 1.7 : 1));
      glow.addColorStop(0, 'rgba(255,175,67,' + (pulse * (this.night ? 2.5 : 1)) + ')'); glow.addColorStop(1,'rgba(255,112,45,0)');
      c.fillStyle = glow; c.fillRect(x-r*2,y-r*2,r*4,r*4);
    }); c.restore();
  }
  drawActor(actor, pose) {
    const c = this.ctx, box = spriteBox(actor, pose), atlas=this.atlases.get(box.sheet);
    if (!atlas) return;
    const selected = actor.id === this.selected, hovered = actor.id === this.hover;
    c.save(); c.fillStyle = '#0b151e45'; c.beginPath(); c.ellipse(pose.x,pose.y-1,box.width*.40,4,0,0,Math.PI*2); c.fill();
    if (selected || hovered) { c.strokeStyle = '#f7d991'; c.lineWidth = 1.5; c.beginPath(); c.ellipse(pose.x,pose.y,box.width*.55,6,0,0,Math.PI*2); c.stroke(); }
    c.translate(pose.x,pose.y); if (pose.left) c.scale(-1,1);
    c.drawImage(atlas, ...box.source, -box.width/2, -box.height+pose.bob, box.width, box.height); c.restore();
    if (selected || hovered) {
      c.save(); c.font = '14px Tahoma, sans-serif'; c.textAlign = 'center';
      const width = c.measureText(actor.name).width + 18, y = pose.y - box.height - 24;
      c.fillStyle = '#102522e8'; c.fillRect(pose.x-width/2,y,width,23);
      c.fillStyle = '#ffdf9b'; c.fillText(actor.name,pose.x,y+16); c.restore();
    }
  }
  motes() {
    const c = this.ctx, t = this.time, {box:[bx,by,bw,bh],color}=this.scene.motes; c.save();
    for (let i=0;i<19;i++) {
      const x=bx+mod(i*83+t*(5+i%3),bw), y=by+mod(i*53+t*(8+i%4),bh);
      c.globalAlpha=.25+.20*Math.sin(t+i); c.fillStyle=color;
      c.fillRect(x+Math.sin(t*.6+i)*13,y,2+(i%2),2);
    } c.restore();
  }
  local(event) { const r=this.canvas.getBoundingClientRect(); return { x:event.clientX-r.left,y:event.clientY-r.top }; }
  bindInput() {
    this.canvas.addEventListener('pointerdown', e => {
      if (e.button !== 0) return; const point=this.local(e);
      this.pointer={id:e.pointerId,origin:point,last:point,moved:false}; this.canvas.setPointerCapture(e.pointerId);
    });
    this.canvas.addEventListener('pointermove', e => {
      const point=this.local(e);
      if (this.pointer?.id===e.pointerId) {
        const p=this.pointer; p.moved ||= Math.hypot(point.x-p.origin.x,point.y-p.origin.y)>5;
        if (p.moved) { this.following=false; this.camera.pan(point.x-p.last.x,point.y-p.last.y); }
        p.last=point; this.draw();
      } else { this.hover=hitActor(this.actors,this.camera.world(point),this.actorTime,this.scene.paths)?.id ?? null; this.canvas.style.cursor=this.hover===null?'grab':'pointer'; this.draw(); }
    });
    this.canvas.addEventListener('pointerup', e => {
      if (this.pointer?.id!==e.pointerId) return;
      if (!this.pointer.moved) { const actor=hitActor(this.actors,this.camera.world(this.local(e)),this.actorTime,this.scene.paths); if(actor) this.onSelect(actor); }
      this.pointer=null; if(this.canvas.hasPointerCapture(e.pointerId))this.canvas.releasePointerCapture(e.pointerId);
    });
    this.canvas.addEventListener('pointercancel',()=>{this.pointer=null;});
    this.canvas.addEventListener('lostpointercapture',()=>{this.pointer=null;});
    this.canvas.addEventListener('pointerleave',()=>{this.hover=null;this.draw();});
    this.canvas.addEventListener('wheel',e=>{e.preventDefault();this.zoom(e.deltaY<0?1.12:1/1.12,this.local(e));},{passive:false});
    this.canvas.addEventListener('keydown',e=>{
      const movement={ArrowLeft:[55,0],ArrowRight:[-55,0],ArrowUp:[0,55],ArrowDown:[0,-55]};
      if (movement[e.key]) {e.preventDefault();this.following=false;this.camera.pan(...movement[e.key]);this.draw();}
      if (e.key==='+'||e.key==='=') {e.preventDefault();this.zoom(1.12);}
      if (e.key==='-') {e.preventDefault();this.zoom(1/1.12);}
      if (e.key==='Home') {e.preventDefault();this.reset();}
    });
  }
}
