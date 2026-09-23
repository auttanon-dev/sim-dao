import { SCENES } from './scene-config.mjs';
// Scene coordinates are presentation only. Never write them back to the simulation.
export const WIDTH = 1672, HEIGHT = 941, MAX_ACTORS = 32;
export const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
export const mod = (x, n) => ((x % n) + n) % n;
export const ART_BOXES = [
  [0, 24, 314, 600], [320, 35, 302, 592], [630, 40, 302, 580], [946, 30, 308, 596],
  [0, 632, 313, 606], [320, 646, 302, 589], [634, 648, 304, 591], [943, 646, 303, 591],
];
// แผ่นตัวละครที่ "มีไฟล์จริงและวาดได้จริง" — ต้องตรงกับ sheet ทุกค่าใน character-art.json
// และกับรายการที่ jianghu_routes เสิร์ฟ ถ้าสามที่นี้ไม่ตรงกัน จะได้ appearance ที่ถูกทิ้งเงียบๆ
// (แผ่นไม่อยู่ในรายการ) หรือรูปที่โหลด 404 (ไม่มีไฟล์)
export const CHARACTER_SHEETS = ['characters.png', 'characters-martial.png', 'characters-civilian.png'];
export function characterArt(actor) {
  const appearance=actor.appearance;
  if(appearance && CHARACTER_SHEETS.includes(appearance.sheet))return appearance;
  return {sheet:'characters.png',source:ART_BOXES[mod(actor.art_index??actor.id,ART_BOXES.length)]};
}

export class Camera {
  constructor(width, height) { this.zoom = 1; this.x = WIDTH / 2; this.y = HEIGHT / 2; this.resize(width, height); }
  resize(width, height) { this.width = Math.max(1, width); this.height = Math.max(1, height); this.base = Math.max(this.width / WIDTH, this.height / HEIGHT); this.constrain(); }
  get scale() { return this.base * this.zoom; }
  screen(point) { return { x: (point.x - this.x) * this.scale + this.width / 2, y: (point.y - this.y) * this.scale + this.height / 2 }; }
  world(point) { return { x: (point.x - this.width / 2) / this.scale + this.x, y: (point.y - this.height / 2) / this.scale + this.y }; }
  constrain() {
    const halfW = this.width / this.scale / 2, halfH = this.height / this.scale / 2;
    this.x = clamp(this.x, Math.min(halfW, WIDTH / 2), Math.max(WIDTH - halfW, WIDTH / 2));
    this.y = clamp(this.y, Math.min(halfH, HEIGHT / 2), Math.max(HEIGHT - halfH, HEIGHT / 2));
  }
  zoomAt(factor, point = { x: this.width / 2, y: this.height / 2 }) {
    const anchor = this.world(point); this.zoom = clamp(this.zoom * factor, 1, 3.2);
    this.x = anchor.x - (point.x - this.width / 2) / this.scale;
    this.y = anchor.y - (point.y - this.height / 2) / this.scale; this.constrain();
  }
  pan(dx, dy) { this.x -= dx / this.scale; this.y -= dy / this.scale; this.constrain(); }
  reset() { this.zoom = 1; this.x = WIDTH / 2; this.y = HEIGHT / 2; this.constrain(); }
}

// Distance-based movement includes a short pause at every waypoint. These poses
// illustrate the recorded activity; the simulation does not store foot positions.
export const actorResting = actor => /sleep|meditat|cultivat|relax|idle|training|นอน|บำเพ็ญ|พัก|ฝึก/i.test(actor.state || '');
export function actorPose(actor, seconds, paths = SCENES['river-inn'].paths) {
  const path = paths[mod(actor.id, paths.length)];
  const seed = mod(actor.id * 31, 997) / 997;
  const resting = actorResting(actor);
  const speed = 8 + mod(actor.id, 5), pause = 2 + mod(actor.id, 3);
  const stops = [...path, ...path.slice(1,-1).reverse()];
  const legs = stops.map((a,i) => {
    const b=stops[(i+1)%stops.length];
    return {a,b,duration:Math.hypot((b[0]-a[0])*WIDTH,(b[1]-a[1])*HEIGHT)/speed};
  });
  const period=legs.reduce((sum,leg)=>sum+leg.duration+pause,0);
  let elapsed=mod(seed*period+(actor.motion_seconds??(resting?0:seconds)),period), leg=legs[0];
  for (const candidate of legs) {
    leg=candidate;
    if(elapsed<leg.duration+pause)break;
    elapsed-=leg.duration+pause;
  }
  const moving=!resting && elapsed>pause;
  const travel=clamp((elapsed-pause)/Math.max(.001,leg.duration),0,1);
  // Ease at both ends without stopping abruptly at the waypoint.
  const t=travel*travel*(3-2*travel), {a,b}=leg;
  return {x:(a[0]+(b[0]-a[0])*t)*WIDTH, y:(a[1]+(b[1]-a[1])*t)*HEIGHT,
    moving, left:b[0]<a[0],
    bob:Math.sin(seconds*(moving?7:1.6)+seed*6)*(moving?.7:.25)};
}

export function spriteBox(actor, pose) {
  const {source,sheet} = characterArt(actor);
  const height = 58 + pose.y / HEIGHT * 19;
  const width = height * source[2] / source[3];
  return { source, sheet, x: pose.x - width / 2, y: pose.y - height, width, height };
}

export function hitActor(actors, point, seconds, paths = SCENES['river-inn'].paths) {
  // Last drawn (nearest camera) actor wins overlaps.
  return actors.map(actor => ({ actor, pose: actorPose(actor, seconds, paths) }))
    .sort((a, b) => b.pose.y - a.pose.y)
    .find(({ actor, pose }) => { const b = spriteBox(actor, pose);
      return point.x >= b.x - 9 && point.x <= b.x + b.width + 9 && point.y >= b.y - 5 && point.y <= b.y + b.height + 9;
    })?.actor || null;
}

export class LatestRequest {
  constructor() { this.number = 0; this.controller = null; }
  start() { this.controller?.abort(); this.controller = new AbortController(); return { number: ++this.number, signal: this.controller.signal }; }
  current(number) { return number === this.number; }
}
