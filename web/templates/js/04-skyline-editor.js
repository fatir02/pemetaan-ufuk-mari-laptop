function skySvgEl(tag, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs || {}).forEach(([k, v]) => el.setAttribute(k, String(v)));
  return el;
}

function buildSkyAnchors(horizon) {
  if (!horizon || horizon.length < 2) return [];
  const candidates = [0];
  for (let x = 2; x < horizon.length - 2; x++) {
    const a = horizon[x] - horizon[x - 2], b = horizon[x + 2] - horizon[x];
    if (Math.abs(b - a) > 1.4 || Math.abs(b) > 4.0) candidates.push(x);
  }
  candidates.push(horizon.length - 1);
  const stride = Math.max(1, Math.ceil(candidates.length / 120));
  const out = candidates.filter((_, i) => i % stride === 0);
  if (out[out.length - 1] !== horizon.length - 1) out.push(horizon.length - 1);
  return out.map(x => ({ x, y: Number(horizon[x]) }));
}

function skyPointFromEvent(e, worldSpace) {
  const svg = document.getElementById('skylineEditorSvg');
  const target = worldSpace ? document.getElementById('skyWorld') : svg;
  if (!svg || !target) return null;
  const p = new DOMPoint(e.clientX, e.clientY);
  const matrix = target.getScreenCTM();
  return matrix ? p.matrixTransform(matrix.inverse()) : null;
}

function openSkylineEditor(objectIndex) {
  if (!currentProfileData || !currentProfileData.horizon_y) return alert('Proses citra terlebih dahulu.');
  const modal = document.getElementById('skylineEditorModal');
  modal.style.display = 'flex';
  skyEditor.mode = 'navigate';
  skyEditor.selected = Number.isInteger(objectIndex) ? objectIndex : -1;
  skyEditor.anchors = buildSkyAnchors(currentProfileData.horizon_y);
  skyEditor.dirty = false;
  renderSkylineEditor();
  setSkyEditorMode('navigate');
  resetSkyEditorView();
  if (skyEditor.selected >= 0) focusSkyObject(skyEditor.selected);
}

function closeSkylineEditor() {
  document.getElementById('skylineEditorModal').style.display = 'none';
  document.getElementById('skylineTooltip').style.display = 'none';
}

function setSkyEditorMode(mode) {
  skyEditor.mode = mode;
  ['navigate', 'edit', 'add'].forEach(name => {
    const id = name === 'navigate' ? 'skyModeNavigate' : name === 'edit' ? 'skyModeEdit' : 'skyModeAdd';
    document.getElementById(id)?.classList.toggle('active', name === mode);
  });
  document.getElementById('skyObjectType').style.display = mode === 'add' ? 'block' : 'none';
  document.getElementById('skylineEditorViewport').style.cursor = mode === 'navigate' ? 'grab' : 'crosshair';
  renderSkylineVectors();
}

function renderSkylineEditor() {
  const svg = document.getElementById('skylineEditorSvg');
  const w = Number(currentProfileData.image_width), h = Number(currentProfileData.image_height);
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.innerHTML = '';
  const world = skySvgEl('g', { id: 'skyWorld' });
  const image = skySvgEl('image', { x: 0, y: 0, width: w, height: h, preserveAspectRatio: 'none', href: currentProfileData.raw_base64 || selectedImageBase64 });
  world.appendChild(image);
  world.appendChild(skySvgEl('g', { id: 'skyVectors' }));
  svg.appendChild(world);
  installSkyEditorEvents();
  renderSkylineVectors();
}

function horizonPathData() {
  const horizon = currentProfileData.horizon_y || [];
  if (!horizon.length) return '';
  const step = Math.max(1, Math.floor(horizon.length / 1800));
  let d = `M 0 ${horizon[0]}`;
  for (let x = step; x < horizon.length; x += step) d += ` L ${x} ${horizon[x]}`;
  if ((horizon.length - 1) % step) d += ` L ${horizon.length - 1} ${horizon[horizon.length - 1]}`;
  return d;
}

function renderSkylineVectors() {
  const layer = document.getElementById('skyVectors');
  if (!layer || !currentProfileData) return;
  layer.innerHTML = '';
  const horizon = currentProfileData.horizon_y || [];
  const objects = window.__prominentObjectsData || [];
  const z = skyEditor.zoom || 1;
  const lineWidth = Math.max(.35, 2.0 / Math.sqrt(z));
  layer.appendChild(skySvgEl('path', { d: horizonPathData(), class: 'horizon-path', 'stroke-width': lineWidth, 'data-role': 'horizon' }));

  const targetAz = Number(document.getElementById('sliderAz')?.value);
  if (Number.isFinite(targetAz) && currentProfileData.az_min !== currentProfileData.az_max) {
    const tx = (targetAz - currentProfileData.az_min) / (currentProfileData.az_max - currentProfileData.az_min) * (horizon.length - 1);
    layer.appendChild(skySvgEl('line', { x1: tx, y1: 0, x2: tx, y2: currentProfileData.image_height, class: 'target-line', 'stroke-width': Math.max(.3, 1.2 / Math.sqrt(z)) }));
  }

  objects.forEach((obj, idx) => {
    const xs = Math.max(0, Number(obj.x_start ?? obj.x ?? 0));
    const xe = Math.min(horizon.length - 1, Number(obj.x_end ?? obj.x ?? xs));
    const cx = Number(obj.x ?? Math.round((xs + xe) / 2));
    const y = Math.max(8, Math.min(...horizon.slice(Math.floor(xs), Math.floor(xe) + 1)) - 13);
    const cls = idx === skyEditor.selected ? 'object-span selected' : (skyEditor.selected >= 0 ? 'object-span muted' : 'object-span');
    const path = skySvgEl('path', { d: `M ${xs} ${y-6} L ${xs} ${y+6} M ${xs} ${y} L ${xe} ${y} M ${xe} ${y-6} L ${xe} ${y+6}`, class: cls, 'stroke-width': lineWidth, 'data-object': idx });
    layer.appendChild(path);
    const marker = skySvgEl('circle', { cx, cy: horizon[Math.max(0, Math.min(horizon.length - 1, Math.round(cx)))], r: Math.max(2.4, 5/z), class: 'object-marker', 'stroke-width': Math.max(.4, 1/z), 'data-object': idx });
    layer.appendChild(marker);
    if (skyEditor.mode === 'edit') {
      [['left', xs], ['right', xe]].forEach(([side, x]) => layer.appendChild(skySvgEl('circle', { cx: x, cy: y, r: Math.max(3, 5/z), class: 'span-handle', 'data-object': idx, 'data-side': side })));
    }
  });

  if (skyEditor.mode === 'edit') {
    skyEditor.anchors.forEach((p, idx) => layer.appendChild(skySvgEl('circle', { cx: p.x, cy: p.y, r: Math.max(3, 5/z), class: 'pen-anchor', 'data-anchor': idx })));
  }
}

function applySkyTransform() {
  const world = document.getElementById('skyWorld');
  if (world) world.setAttribute('transform', `translate(${skyEditor.panX} ${skyEditor.panY}) scale(${skyEditor.zoom})`);
  renderSkylineVectors();
}

function resetSkyEditorView() {
  skyEditor.zoom = 1; skyEditor.panX = 0; skyEditor.panY = 0;
  applySkyTransform();
}

function focusSkyObject(idx) {
  const obj = (window.__prominentObjectsData || [])[idx];
  if (!obj) return;
  skyEditor.selected = idx;
  const w = Number(currentProfileData.image_width), h = Number(currentProfileData.image_height);
  const xs = Number(obj.x_start ?? obj.x), xe = Number(obj.x_end ?? obj.x);
  const span = Math.max(30, xe - xs);
  skyEditor.zoom = Math.max(1, Math.min(8, w / (span * 4)));
  const cx = (xs + xe) / 2, cy = Number(currentProfileData.horizon_y[Math.round(cx)] || h/2);
  skyEditor.panX = w/2 - skyEditor.zoom*cx;
  skyEditor.panY = h/2 - skyEditor.zoom*cy;
  applySkyTransform();
}

function updateHorizonFromAnchor(index, x, y) {
  const anchors = skyEditor.anchors, horizon = currentProfileData.horizon_y;
  const left = index > 0 ? anchors[index-1] : null, right = index+1 < anchors.length ? anchors[index+1] : null;
  x = Math.round(Math.max(left ? left.x+1 : 0, Math.min(right ? right.x-1 : horizon.length-1, x)));
  y = Math.max(0, Math.min(currentProfileData.image_height-1, y));
  anchors[index] = {x, y};
  const fill = (a, b) => { for (let px=a.x; px<=b.x; px++) horizon[px] = a.y + (b.y-a.y)*((px-a.x)/Math.max(1,b.x-a.x)); };
  if (left) fill(left, anchors[index]);
  if (right) fill(anchors[index], right);
  if (!left && !right) horizon[x] = y;
  skyEditor.dirty = true;
}

function addSkyAnchor(point) {
  const x = Math.round(point.x), horizon = currentProfileData.horizon_y;
  if (x < 1 || x >= horizon.length-1 || Math.abs(point.y-horizon[x]) > 10/skyEditor.zoom) return -1;
  if (skyEditor.anchors.some(p => Math.abs(p.x-x) < 2)) return -1;
  skyEditor.anchors.push({x, y:horizon[x]}); skyEditor.anchors.sort((a,b)=>a.x-b.x);
  return skyEditor.anchors.findIndex(p => p.x === x);
}

function addManualSkyObject(point) {
  const horizon = currentProfileData.horizon_y, x = Math.max(0, Math.min(horizon.length-1, Math.round(point.x)));
  const az = currentProfileData.az_min + x/(horizon.length-1)*(currentProfileData.az_max-currentProfileData.az_min);
  const el = interpolateProfileElevation(x);
  const half = Math.max(3, Math.round(horizon.length * .006));
  const obj = { id:(window.__prominentObjectsData||[]).length+1, label:document.getElementById('skyObjectType').value, object_class:document.getElementById('skyObjectType').value, x, x_start:Math.max(0,x-half), x_end:Math.min(horizon.length-1,x+half), azimuth:az, az_start:currentProfileData.az_min+Math.max(0,x-half)/(horizon.length-1)*(currentProfileData.az_max-currentProfileData.az_min), az_end:currentProfileData.az_min+Math.min(horizon.length-1,x+half)/(horizon.length-1)*(currentProfileData.az_max-currentProfileData.az_min), elevation:el, source:'manual_annotation', is_manual:true };
  window.__prominentObjectsData = [...(window.__prominentObjectsData||[]), obj];
  skyEditor.selected = window.__prominentObjectsData.length-1; skyEditor.dirty = true;
  setSkyEditorMode('navigate'); renderSkylineVectors();
}

function interpolateProfileElevation(x) {
  const els = clientProfileCurve?.elevations || [], w = Number(currentProfileData.image_width)-1;
  if (!els.length || w <= 0) return 0;
  const p = x/w*(els.length-1), i = Math.floor(p), j = Math.min(els.length-1,i+1);
  return Number(els[i] + (els[j]-els[i])*(p-i));
}

function installSkyEditorEvents() {
  const vp = document.getElementById('skylineEditorViewport');
  if (!vp || vp.dataset.ready) return;
  vp.dataset.ready = '1';
  vp.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    skyPointers.set(e.pointerId, {x:e.clientX,y:e.clientY});
    if (skyPointers.size === 2) {
      const pts=[...skyPointers.values()], cx=(pts[0].x+pts[1].x)/2, cy=(pts[0].y+pts[1].y)/2;
      const center=skyPointFromEvent({clientX:cx,clientY:cy},false);
      skyPinch={distance:Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y),zoom:skyEditor.zoom,panX:skyEditor.panX,panY:skyEditor.panY,cx:center.x,cy:center.y};
      skyEditor.drag=null; return;
    }
    const worldPoint = skyPointFromEvent(e, true), svgPoint = skyPointFromEvent(e, false);
    if (!worldPoint || !svgPoint) return;
    const anchor = e.target.closest?.('.pen-anchor');
    const handle = e.target.closest?.('.span-handle');
    const marker = e.target.closest?.('.object-marker');
    if (skyEditor.mode === 'edit' && handle) {
      skyEditor.drag = { type:'span', idx:Number(handle.dataset.object), side:handle.dataset.side };
    } else if (skyEditor.mode === 'edit' && anchor) {
      skyEditor.drag = { type:'anchor', idx:Number(anchor.dataset.anchor) };
    } else if (skyEditor.mode === 'edit') {
      const idx = addSkyAnchor(worldPoint);
      if (idx >= 0) skyEditor.drag = {type:'anchor', idx};
    } else if (skyEditor.mode === 'add') {
      addManualSkyObject(worldPoint);
    } else if (marker) {
      const idx = Number(marker.dataset.object), obj = (window.__prominentObjectsData||[])[idx];
      skyEditor.selected = idx; renderSkylineVectors();
      const tip = document.getElementById('skylineTooltip');
      tip.innerHTML = `<b>${obj.label || `Objek ${idx+1}`}</b><br>Az ${Number(obj.azimuth).toFixed(2)}° • Elevasi ${Number(obj.elevation).toFixed(2)}°`;
      tip.style.left = Math.min(vp.clientWidth-180, Math.max(8,e.clientX-vp.getBoundingClientRect().left+10))+'px';
      tip.style.top = Math.min(vp.clientHeight-60, Math.max(8,e.clientY-vp.getBoundingClientRect().top+10))+'px';
      tip.style.display = 'block';
    } else {
      skyEditor.drag = { type:'pan', startX:svgPoint.x, startY:svgPoint.y, panX:skyEditor.panX, panY:skyEditor.panY };
      document.getElementById('skylineTooltip').style.display = 'none';
    }
    vp.setPointerCapture(e.pointerId); e.preventDefault();
  });
  vp.addEventListener('pointermove', e => {
    if (skyPointers.has(e.pointerId)) skyPointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if (skyPointers.size === 2 && skyPinch) {
      const pts=[...skyPointers.values()], dist=Math.hypot(pts[0].x-pts[1].x,pts[0].y-pts[1].y);
      const center=skyPointFromEvent({clientX:(pts[0].x+pts[1].x)/2,clientY:(pts[0].y+pts[1].y)/2},false), cx=center.x, cy=center.y;
      const ratio=Math.max(.5,Math.min(14,skyPinch.zoom*dist/Math.max(1,skyPinch.distance)))/skyPinch.zoom;
      skyEditor.zoom=skyPinch.zoom*ratio; skyEditor.panX=cx-(skyPinch.cx-skyPinch.panX)*ratio; skyEditor.panY=cy-(skyPinch.cy-skyPinch.panY)*ratio;
      applySkyTransform(); e.preventDefault(); return;
    }
    if (!skyEditor.drag) return;
    const p = skyPointFromEvent(e, true), s = skyPointFromEvent(e, false);
    if (!p || !s) return;
    if (skyEditor.drag.type === 'anchor') updateHorizonFromAnchor(skyEditor.drag.idx, p.x, p.y);
    else if (skyEditor.drag.type === 'span') {
      const obj = (window.__prominentObjectsData||[])[skyEditor.drag.idx]; if (!obj) return;
      const x = Math.max(0,Math.min(currentProfileData.image_width-1,Math.round(p.x)));
      if (skyEditor.drag.side === 'left') obj.x_start = Math.min(x, Number(obj.x_end)-1);
      else obj.x_end = Math.max(x, Number(obj.x_start)+1);
      obj.x = Math.round((Number(obj.x_start)+Number(obj.x_end))/2);
      const azAt = q => currentProfileData.az_min+q/(currentProfileData.image_width-1)*(currentProfileData.az_max-currentProfileData.az_min);
      obj.az_start=azAt(obj.x_start); obj.az_end=azAt(obj.x_end); obj.azimuth=azAt(obj.x); obj.az_span=obj.az_end-obj.az_start; obj.is_manual_range=true;
      skyEditor.dirty=true;
    } else if (skyEditor.drag.type === 'pan') {
      skyEditor.panX=skyEditor.drag.panX+(s.x-skyEditor.drag.startX); skyEditor.panY=skyEditor.drag.panY+(s.y-skyEditor.drag.startY);
    }
    applySkyTransform(); e.preventDefault();
  });
  const endDrag = e => { skyPointers.delete(e.pointerId); if(skyPointers.size<2)skyPinch=null; if (skyEditor.drag) { skyEditor.drag=null; try{vp.releasePointerCapture(e.pointerId);}catch(_){} } };
  vp.addEventListener('pointerup', endDrag); vp.addEventListener('pointercancel', endDrag);
  vp.addEventListener('wheel', e => {
    e.preventDefault(); const before=skyPointFromEvent(e,true), screen=skyPointFromEvent(e,false); if(!before||!screen)return;
    const factor=Math.exp(-e.deltaY*.0015), old=skyEditor.zoom;
    skyEditor.zoom=Math.max(.5,Math.min(14,old*factor));
    skyEditor.panX=screen.x-skyEditor.zoom*before.x; skyEditor.panY=screen.y-skyEditor.zoom*before.y;
    applySkyTransform();
  }, {passive:false});
  vp.addEventListener('dblclick', e => {
    const world=skyPointFromEvent(e,true), screen=skyPointFromEvent(e,false); if(!world||!screen)return;
    skyEditor.zoom=Math.min(14,skyEditor.zoom*1.8); skyEditor.panX=screen.x-skyEditor.zoom*world.x; skyEditor.panY=screen.y-skyEditor.zoom*world.y; applySkyTransform();
  });
}

async function saveSkylineEdits() {
  const status=document.getElementById('skyEditorStatus'); status.textContent='Menyimpan koreksi...';
  try {
    const res=await fetch('/api/update_skyline',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({horizon_y:currentProfileData.horizon_y,objects:window.__prominentObjectsData||[],target_az:Number(document.getElementById('sliderAz')?.value)})});
    const data=await res.json(); if(data.error)throw new Error(data.error);
    currentProfileData={...currentProfileData,...data};
    clientProfileCurve={azimuths:data.profile_curve.az,elevations:data.profile_curve.el,dip_deg:data.target_analysis.dip_deg};
    window.__prominentObjectsData=data.prominent_objects||[]; renderProminentObjects(window.__prominentObjectsData);
    document.getElementById('resOverlayImg').src=data.overlay_base64; document.getElementById('resPlotImg').src=data.plot_base64;
    skyEditor.dirty=false; status.textContent='Koreksi tersimpan ke overlay, profil, dan laporan.'; renderSkylineVectors();
  } catch(err) { status.textContent='Gagal: '+err.message; }
}

document.addEventListener('keydown', e => { if(e.key==='Escape' && document.getElementById('skylineEditorModal')?.style.display==='flex') closeSkylineEditor(); });

