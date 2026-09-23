import test from 'node:test';
import assert from 'node:assert/strict';
import { Camera, WIDTH, HEIGHT, actorPose, hitActor, LatestRequest, characterArt } from '../static/jianghu/scene-model.mjs';
import { SCENES } from '../static/jianghu/scene-config.mjs';
import { SceneRenderer } from '../static/jianghu/scene-renderer.mjs';

test('NPC hit selection agrees with rendering after panning and zooming', () => {
  const camera=new Camera(1280,720), actors=[{id:24,art_index:0,state:'Sleeping'}];
  camera.zoomAt(2);camera.pan(-200,75);
  const pose=actorPose(actors[0],3), screen=camera.screen({x:pose.x,y:pose.y-25});
  assert.equal(hitActor(actors,camera.world(screen),3).id,24);
  assert.equal(hitActor(actors,{x:0,y:0},3),null);
});
test('camera never exposes outside the backdrop even on portrait screens', () => {
  for(const [w,h] of [[1280,720],[390,844],[2560,1080]]) {
    const cam=new Camera(w,h);cam.zoomAt(9);cam.pan(100000,-100000);
    const a=cam.world({x:0,y:0}),b=cam.world({x:w,y:h});
    assert.ok(a.x>=-1e-8&&a.y>=-1e-8&&b.x<=WIDTH+1e-8&&b.y<=HEIGHT+1e-8);
    cam.reset();assert.equal(cam.zoom,1);
  }
});
test('resting characters do not walk; presentation motion does not mutate the snapshot', () => {
  const rest=Object.freeze({id:10,state:'Sleeping'}),walk=Object.freeze({id:10,state:'Working'});
  assert.equal(actorPose(rest,0).x,actorPose(rest,20).x);
  assert.notEqual(actorPose(walk,0).x,actorPose(walk,20).x);
});
test('a delayed earlier response cannot replace the latest chosen place', () => {
  const requests=new LatestRequest(),old=requests.start(),latest=requests.start();
  assert.equal(old.signal.aborted,true);assert.equal(requests.current(old.number),false);
  assert.equal(requests.current(latest.number),true);
});

test('selection follows each scene route; paced movement pauses without teleporting', () => {
  const actor=Object.freeze({id:17,state:'Working'});
  for(const scene of Object.values(SCENES)) {
    let stopped=0,moved=0,last=actorPose(actor,0,scene.paths);
    for(let time=.1;time<120;time+=.1) {
      const pose=actorPose(actor,time,scene.paths);
      assert.ok(Math.hypot(pose.x-last.x,pose.y-last.y)<3,'continuous positions');
      if(pose.moving)moved++;else stopped++;
      assert.equal(hitActor([actor],{x:pose.x,y:pose.y-20},time,scene.paths)?.id,actor.id);
      last=pose;
    }
    assert.ok(stopped>0 && moved>0);
  }
});

function sceneHarness() {
  const renderer=Object.create(SceneRenderer.prototype),pending=new Map();
  Object.assign(renderer,{sceneRevision:0,sceneId:null,background:null,camera:new Camera(1280,720),
    draw(){},schedule(){},asset(name){return new Promise((resolve,reject)=>pending.set(name,{resolve,reject}));}});
  return {renderer,pending};
}
test('slow artwork cannot overwrite a newer scene or restore actors from another place', async () => {
  const {renderer,pending}=sceneHarness();
  const old=renderer.setScene('sword-sect'), latest=renderer.setScene('bamboo-forest');
  pending.get('bamboo-forest.png').resolve('forest image');
  assert.equal(await latest,true);
  pending.get('sword-sect.png').resolve('old image');
  assert.equal(await old,false);
  assert.equal(renderer.background,'forest image');assert.deepEqual(renderer.actors,[]);
  const stale=renderer.setScene('river-inn');
  await renderer.setScene(null);pending.get('river-inn.png').resolve('inn image');
  assert.equal(await stale,false);assert.equal(renderer.background,null);
});
test('failed art loads can be retried for the same selected place', async () => {
  const {renderer,pending}=sceneHarness();
  const first=renderer.setScene('sword-sect');
  pending.get('sword-sect.png').reject(new Error('offline'));
  await assert.rejects(first,/offline/);
  const retry=renderer.setScene('sword-sect');
  pending.get('sword-sect.png').resolve('sect image');
  assert.equal(await retry,true);assert.equal(renderer.background,'sect image');
});

test('changing activity preserves the foot position and does not mutate API data', () => {
  const renderer=Object.create(SceneRenderer.prototype);
  Object.assign(renderer,{actors:[],draw(){}});
  const source=Object.freeze({id:45,state:'Working'});
  renderer.setActors([source]); renderer.actors[0].motion_seconds=17;
  const moving=actorPose(renderer.actors[0],20);
  renderer.setActors([{...source,state:'Sleeping'}]);
  const sleeping=actorPose(renderer.actors[0],21);
  assert.equal(sleeping.x,moving.x);assert.equal(sleeping.y,moving.y);
  assert.equal(source.motion_seconds,undefined);
});

test('portrait and scene use the same atlas crop and old snapshots remain supported', () => {
  const appearance={sheet:'characters-martial.png',source:[10,20,100,200]};
  assert.equal(characterArt({id:1,appearance}),appearance);
  assert.equal(characterArt({id:1}).sheet,'characters.png');
  // แผ่นที่ยังไม่มีไฟล์จริงต้องถอยไปใช้แผ่นหลัก ไม่ใช่ขอรูปที่ตอบ 404
  const missing={sheet:'characters-elders.png',source:[10,20,100,200]};
  assert.equal(characterArt({id:1,appearance:missing}).sheet,'characters.png');
});
