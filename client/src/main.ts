import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { createFlamingoModel, type ModelPart } from './model';
import './style.css';

type Project = { name: string; address: string; confidence: number; floors: number; heightFt: number; source: string; caveat: string; takeoff: { id: string; label: string; quantity: string; color: string; sheets: string }[] };
const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
  <div class="shell">
    <header><div class="brand"><span class="mark">F</span><span>FORMWORK</span><b>beta</b></div><div class="project-title"><small>ACTIVE PROJECT</small><strong id="title">Loading model…</strong></div><div class="header-actions"><button class="ghost" id="uploadBtn">Import PDF</button><button class="accent" id="shareBtn">Share selection</button><div class="avatar" id="avatar">AX</div></div></header>
    <aside class="left-panel">
      <div class="panel-head"><span>MODEL SYSTEMS</span><button id="allBtn">ALL</button></div>
      <div id="systems" class="systems"></div>
      <div class="source-card"><span>SOURCE SET</span><strong>34 sheets · IFC</strong><small>Revision 13 · 2026.01.16</small><div class="meter"><i></i></div><p><b id="confidence">82%</b> model confidence</p></div>
    </aside>
    <main id="viewport"><canvas id="scene"></canvas><div class="view-label"><span class="live-dot"></span> LIVE MODEL <b id="visibleCount">—</b></div><div class="north">N<div></div></div><div class="floor-controls"><span id="floorModeLabel">SECTION HEIGHT</span><input id="floorSlider" type="range" min="1" max="12" value="12"><b id="floorValue">ROOF</b></div><div class="toolbar"><button data-view="iso" class="active" title="Perspective">◇</button><button data-view="front" title="South elevation">▤</button><button data-view="top" title="Plan">⊞</button><button id="isolateBtn" title="Isolate selected floor">L</button><button id="explodeBtn" title="Explode floors">↕</button><button id="resetBtn" title="Reset view">↺</button></div></main>
    <aside class="right-panel"><div class="panel-head"><span>SELECTION</span><button id="closeInfo">×</button></div><div id="selectionEmpty" class="empty"><div class="select-icon">⌁</div><strong>Select a building element</strong><p>Click a panel, trim, floor, window, or balcony to inspect it.</p></div><div id="selectionInfo" class="selection hidden"><div class="selection-color"></div><small id="selectionSystem">ELEMENT</small><h2 id="selectionName">—</h2><dl><div><dt>LEVEL</dt><dd id="selectionFloor">—</dd></div><div><dt>QUANTITY</dt><dd id="selectionQty">Drawing set</dd></div><div><dt>STATUS</dt><dd><span class="verified">VISUAL MATCH</span></dd></div></dl><button id="addSelection" class="accent wide">Add to share set</button></div><div class="takeoff-note"><span>FIELD NOTE</span><p>Yellow, purple, blue and pink surfaces reproduce the estimator highlights—not final material colors.</p></div></aside>
    <footer><span><i class="ok"></i> Model ready</span><span>2061 BEACH AVE / REV 13</span><span id="accountLabel">EDITOR · ARDIT</span></footer>
  </div>
  <dialog id="uploadDialog"><form id="uploadForm"><button type="button" class="dialog-close">×</button><span class="eyebrow">NEW SOURCE</span><h2>Import architectural PDF</h2><p>Upload the drawing set, then calibrate one known dimension. This demo stores the PDF locally; automatic geometry still requires review.</p><label class="drop"><input name="pdf" type="file" accept="application/pdf" required><b>Choose PDF drawing set</b><small>Up to 80 MB</small></label><button class="accent wide" type="submit">Import for calibration</button><div class="dialog-status"></div></form></dialog>
  <dialog id="shareDialog"><form id="shareForm"><button type="button" class="dialog-close">×</button><span class="eyebrow">CLIENT ROOM</span><h2>Share selected scope</h2><p><b id="shareCount">0</b> elements will be isolated in a read-only 3D room.</p><label>Client account<input name="account" value="Alban · Site Team" required></label><label>Expires<select name="hours"><option value="24">24 hours</option><option value="168" selected>7 days</option><option value="720">30 days</option></select></label><button class="accent wide" type="submit">Create secure room</button><div class="dialog-status"></div></form></dialog>`;

const canvas = document.querySelector<HTMLCanvasElement>('#scene')!;
const viewport = document.querySelector<HTMLElement>('#viewport')!;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.1;
const scene = new THREE.Scene(); scene.background = new THREE.Color(0xd6d4cd); scene.fog = new THREE.Fog(0xd6d4cd, 80, 190);
const camera = new THREE.PerspectiveCamera(34, 1, .1, 400); camera.position.set(54, 38, 66);
const controls = new OrbitControls(camera, canvas); controls.target.set(0, 16, 0); controls.enableDamping = true; controls.dampingFactor = .06; controls.minDistance = 25; controls.maxDistance = 145; controls.maxPolarAngle = Math.PI * .49;
scene.add(new THREE.HemisphereLight(0xf7f4e9, 0x646b70, 2.3));
const sun = new THREE.DirectionalLight(0xfff4dc, 3.1); sun.position.set(35, 65, 48); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.camera.left = -55; sun.shadow.camera.right = 55; sun.shadow.camera.top = 60; sun.shadow.camera.bottom = -30; scene.add(sun);
const { root, parts } = createFlamingoModel(); scene.add(root);
const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2(); let selected: ModelPart | null = null; const shareSet = new Set<string>(); let roomAllowed: Set<string> | null = null; let exploded = false; let isolateFloor = false; let selectedFloor = 12; let project: Project;

function resize() { const w = viewport.clientWidth, h = viewport.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
new ResizeObserver(resize).observe(viewport); resize();
function animate() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(animate); } animate();

fetch('/api/project').then(r => r.json()).then((data: Project) => { project = data; renderProject(); loadRoom(); }).catch(() => document.querySelector('#title')!.textContent = 'API offline — run the .NET server');

function renderProject() {
  const reviewLink=document.createElement('a');reviewLink.href='/floors.html';reviewLink.textContent='Review first four floors →';reviewLink.style.cssText='display:block;padding:16px;background:#d7ff48;color:#182014;font-weight:bold;text-decoration:none';document.querySelector('.left-panel')!.prepend(reviewLink);
  document.querySelector('#title')!.textContent = `${project.name} / ${project.address}`;
  document.querySelector('#confidence')!.textContent = 'Unverified';
  const systems = document.querySelector('#systems')!;
  systems.innerHTML = project.takeoff.map(s => `<button class="system-row active" data-system="${s.id}"><i style="--c:${s.color}"></i><span><b>${s.label}</b><small>${s.sheets}</small></span><strong>${s.quantity}</strong></button>`).join('');
  systems.querySelectorAll<HTMLButtonElement>('.system-row').forEach(btn => btn.onclick = () => { btn.classList.toggle('active'); applyVisibility(); });
  updateCount();
}

function allowedByFilters(p:ModelPart){const active=new Set([...document.querySelectorAll<HTMLButtonElement>('.system-row.active')].map(x=>x.dataset.system));const f=p.userData.floor as number|undefined;const floorAllowed=!f||(isolateFloor?f===selectedFloor:f<=selectedFloor);return floorAllowed&&(!roomAllowed||(!!p.userData.partId&&roomAllowed.has(p.userData.partId)))&&(!p.userData.system||active.has(p.userData.system))}
function applyVisibility() {
  const active = new Set([...document.querySelectorAll<HTMLButtonElement>('.system-row.active')].map(x => x.dataset.system));
  root.traverse(obj=>{const p=obj as ModelPart;if(p.userData.floor)p.visible=allowedByFilters(p);else if(p.userData.system)p.visible=active.has(p.userData.system)}); updateCount();
}
function updateCount() { let count = 0; root.traverse(obj => { let shown=obj.visible,p=obj.parent;while(shown&&p&&p!==root){shown=p.visible;p=p.parent}if(obj.type==='Mesh'&&shown)count++; }); document.querySelector('#visibleCount')!.textContent = `${count} ELEMENTS`; }
document.querySelector<HTMLButtonElement>('#allBtn')!.onclick = () => { document.querySelectorAll('.system-row').forEach(x => x.classList.add('active')); applyVisibility(); };

canvas.addEventListener('pointerdown', e => { const rect = canvas.getBoundingClientRect(); pointer.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1); raycaster.setFromCamera(pointer, camera); const hit = raycaster.intersectObject(root, true).find(x => x.object.type === 'Mesh'); if (hit) showSelection(hit.object as ModelPart); });
function showSelection(part: ModelPart) {
  selected = part; document.querySelector('#selectionEmpty')!.classList.add('hidden'); document.querySelector('#selectionInfo')!.classList.remove('hidden');
  document.querySelector('#selectionSystem')!.textContent = (part.userData.system || 'building element').toUpperCase();
  document.querySelector('#selectionName')!.textContent = part.userData.label || part.name;
  document.querySelector('#selectionFloor')!.textContent = part.userData.floor ? (part.userData.floor === 12 ? 'ROOF' : `LEVEL ${part.userData.floor}`) : 'MULTI-LEVEL';
  document.querySelector('#selectionQty')!.textContent = part.userData.quantity || 'From drawing set';
}
document.querySelector<HTMLButtonElement>('#closeInfo')!.onclick = () => { selected = null; document.querySelector('#selectionEmpty')!.classList.remove('hidden'); document.querySelector('#selectionInfo')!.classList.add('hidden'); };
document.querySelector<HTMLButtonElement>('#addSelection')!.onclick = () => { if (!selected) return; shareSet.add(selected.userData.partId || selected.uuid); const btn = document.querySelector<HTMLButtonElement>('#addSelection')!; btn.textContent = `Added · ${shareSet.size} in share set`; setTimeout(() => btn.textContent = 'Add to share set', 1300); };

function applyFloorView(){root.traverse(obj=>{const p=obj as ModelPart;if(p.userData.floor)p.visible=allowedByFilters(p)});document.querySelector('#floorValue')!.textContent=selectedFloor===12?'ROOF':`L${selectedFloor}`;updateCount()}
document.querySelector<HTMLInputElement>('#floorSlider')!.oninput = e => { selectedFloor=+(e.target as HTMLInputElement).value; applyFloorView(); };
document.querySelector<HTMLButtonElement>('#isolateBtn')!.onclick=()=>{isolateFloor=!isolateFloor;document.querySelector('#floorModeLabel')!.textContent=isolateFloor?'ISOLATED FLOOR':'SECTION HEIGHT';document.querySelector('#isolateBtn')!.classList.toggle('active',isolateFloor);applyFloorView()};
document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(btn => btn.onclick = () => { document.querySelectorAll('[data-view]').forEach(x => x.classList.remove('active')); btn.classList.add('active'); const v = btn.dataset.view; camera.position.set(v === 'front' ? 0 : v === 'top' ? .01 : 54, v === 'top' ? 105 : v === 'front' ? 18 : 38, v === 'front' ? 90 : v === 'top' ? .01 : 66); controls.target.set(0, 16, 0); controls.update(); });
document.querySelector<HTMLButtonElement>('#resetBtn')!.onclick = () => { camera.position.set(54, 38, 66); controls.target.set(0, 16, 0); };
document.querySelector<HTMLButtonElement>('#explodeBtn')!.onclick = () => { exploded = !exploded; root.children.forEach(obj => { const floor = obj.userData.floor as number | undefined; if (floor) obj.position.y += exploded ? (floor - 1) * .22 : -(floor - 1) * .22; }); };

const uploadDialog = document.querySelector<HTMLDialogElement>('#uploadDialog')!; const shareDialog = document.querySelector<HTMLDialogElement>('#shareDialog')!;
document.querySelector<HTMLButtonElement>('#uploadBtn')!.onclick = () => uploadDialog.showModal();
document.querySelector<HTMLButtonElement>('#shareBtn')!.onclick = () => { if (!shareSet.size) parts.filter(p => p.userData.system === 'shaft').forEach(p => shareSet.add(p.userData.partId!)); document.querySelector('#shareCount')!.textContent = String(shareSet.size); shareDialog.showModal(); };
document.querySelectorAll<HTMLButtonElement>('.dialog-close').forEach(b => b.onclick = () => (b.closest('dialog') as HTMLDialogElement).close());
document.querySelector<HTMLFormElement>('#uploadForm')!.onsubmit = async e => { e.preventDefault(); const form = e.currentTarget as HTMLFormElement; const status = form.querySelector('.dialog-status')!; status.textContent = 'Reading drawing set…'; const res = await fetch('/api/import', { method: 'POST', body: new FormData(form) }); const data = await res.json(); status.textContent = res.ok ? `✓ ${data.fileName} imported. ${data.message}` : data.message; };
document.querySelector<HTMLFormElement>('#shareForm')!.onsubmit = async e => { e.preventDefault(); const form = e.currentTarget as HTMLFormElement; const fd = new FormData(form); const status = form.querySelector('.dialog-status')!; status.textContent = 'Creating client room…'; const res = await fetch('/api/shares', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account: fd.get('account'), partIds: [...shareSet], expiresInHours: Number(fd.get('hours')) }) }); const data = await res.json(); if (!res.ok) return void (status.textContent = data.message); const url = new URL(data.url, location.href).href; await navigator.clipboard?.writeText(url); status.innerHTML = `✓ Room created and link copied.<br><a href="${url}">${url}</a>`; };

async function loadRoom() { const token = new URLSearchParams(location.search).get('room'); if (!token) return; const res = await fetch(`/api/shares/${token}`); if (!res.ok) return; const room = await res.json(); roomAllowed = new Set(room.partIds); root.traverse(obj => { const p = obj as ModelPart; if (p.userData.partId) p.visible = roomAllowed!.has(p.userData.partId); else if (p.type === 'Mesh') p.visible = false; }); document.querySelector('#accountLabel')!.textContent = `CLIENT ROOM · ${room.account.toUpperCase()}`; document.querySelector('.left-panel')!.classList.add('room-mode'); document.querySelector<HTMLButtonElement>('#shareBtn')!.style.display = 'none'; document.querySelector<HTMLButtonElement>('#uploadBtn')!.style.display = 'none'; document.querySelector<HTMLButtonElement>('#allBtn')!.style.display = 'none'; }
