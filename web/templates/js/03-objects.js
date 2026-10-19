let prominentObjectNames = {};
let autoApplyTimer = null;

function renderProminentObjects(objects) {
  const container = document.getElementById('prominentObjectsContainer');
  const list = document.getElementById('prominentObjectsList');
  if (!container || !list) return;

  if (!objects || objects.length === 0) {
    container.style.display = 'none';
    list.innerHTML = '';
    return;
  }

  container.style.display = 'block';
  list.innerHTML = '';
  window.__prominentObjectsData = objects;

  const countEl = document.getElementById('prominentCount');
  if (countEl) countEl.textContent = String(objects.length);

  objects.forEach((obj, idx) => {
    const key = String(idx + 1);
    const savedName = prominentObjectNames[key];
    const displayName = savedName || obj.label || `Objek ${idx + 1}`;

    const chip = document.createElement('div');
    chip.className = 'prominent-chip';
    chip.dataset.az = obj.azimuth.toFixed(2);
    chip.dataset.idx = key;
    chip.title = 'Klik untuk membuka editor kontur pada objek ini';
    chip.onclick = () => openSkylineEditor(idx);

    const badge = document.createElement('span');
    badge.className = 'chip-badge';
    badge.textContent = `#${idx + 1}`;

    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'chip-name-input';
    nameInput.value = displayName;
    nameInput.placeholder = `Nama objek ${idx + 1}`;
    nameInput.title = 'Ketik nama objek sesuai pengamatan lapangan';
    nameInput.onclick = (e) => e.stopPropagation();
    nameInput.oninput = function() {
      const val = this.value;
      prominentObjectNames[key] = val;
      // Sinkronkan label pada data objek aktif agar ikut terbawa ke gambar & PDF
      const arr = window.__prominentObjectsData || [];
      if (arr[idx]) arr[idx].label = val.trim() || `Objek ${idx + 1}`;
      // Terapkan otomatis ke gambar setelah pengguna berhenti mengetik
      scheduleAutoApply();
    };
    nameInput.onkeydown = function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.blur();
        applyObjectNames();
      }
    };
    nameInput.onblur = function() {
      scheduleAutoApply(120);
    };

    const azStart = (typeof obj.az_start === 'number') ? obj.az_start : obj.azimuth;
    const azEnd = (typeof obj.az_end === 'number') ? obj.az_end : obj.azimuth;
    const hasSpan = (typeof obj.az_span === 'number') && obj.az_span > 0.05;
    const azText = hasSpan
      ? `${azStart.toFixed(1)}°–${azEnd.toFixed(1)}°`
      : `${obj.azimuth.toFixed(1)}°`;
    const elText = (obj.elevation >= 0 ? '+' : '') + obj.elevation.toFixed(2) + '°';

    const angles = document.createElement('span');
    angles.className = 'chip-angles';
    angles.innerHTML =
      `<span><span class="chip-angle-label">Az</span> <b>${azText}</b></span>` +
      `<span><span class="chip-angle-label">Alt</span> <b>${elText}</b></span>`;

    const aimBtn = document.createElement('button');
    aimBtn.type = 'button';
    aimBtn.className = 'chip-aim';
    aimBtn.textContent = 'Bidik';
    aimBtn.title = 'Arahkan penanda azimut ke objek ini';
    aimBtn.onclick = (e) => {
      e.stopPropagation();
      jumpToAzimuth(obj.azimuth, idx);
    };

    chip.appendChild(badge);
    chip.appendChild(nameInput);
    chip.appendChild(aimBtn);
    chip.appendChild(angles);
    list.appendChild(chip);
  });
}

// Terapkan nama otomatis (debounce) agar gambar langsung berubah saat mengetik
function scheduleAutoApply(delay) {
  if (autoApplyTimer) clearTimeout(autoApplyTimer);
  autoApplyTimer = setTimeout(() => {
    autoApplyTimer = null;
    applyObjectNames(true);
  }, typeof delay === 'number' ? delay : 650);
}

function getRenamedProminentObjects() {
  // Sumber kebenaran utama: nilai yang sedang tampil di kotak input.
  // Ini mencegah nama hilang saat panel di-render ulang oleh server.
  const inputs = document.querySelectorAll('#prominentObjectsList .chip-name-input');
  const arr = window.__prominentObjectsData || [];
  const out = [];
  const count = Math.max(inputs.length, arr.length);
  for (let i = 0; i < count; i++) {
    const base = arr[i] ? { ...arr[i] } : { id: i + 1 };
    let label = '';
    if (inputs[i]) {
      label = String(inputs[i].value || '').trim();
    }
    if (!label) {
      label = String(prominentObjectNames[String(i + 1)] || base.label || '').trim();
    }
    base.label = label || `Objek ${i + 1}`;
    out.push(base);
  }
  return out;
}

async function applyObjectNames(silent) {
  const status = document.getElementById('lblRenameStatus');
  const objs = getRenamedProminentObjects();
  if (!objs.length) {
    if (status && !silent) { status.style.color = '#f87171'; status.textContent = 'Belum ada objek terdeteksi.'; }
    return;
  }
  if (status && !silent) { status.style.color = '#94a3b8'; status.textContent = 'Menerapkan nama...'; }
  try {
    const res = await fetch('/api/rename_objects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ objects: objs })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    const img = document.getElementById('resOverlayImg');
    if (img && data.overlay_base64) img.src = data.overlay_base64;
    if (data.prominent_objects) {
      // Simpan label baru tanpa menghapus isi input yang sedang diketik
      window.__prominentObjectsData = data.prominent_objects;
    }
    if (status && !silent) {
      status.style.color = '#34d399';
      status.textContent = 'Nama objek berhasil diterapkan ke gambar & laporan.';
      setTimeout(() => { if (status) status.textContent = ''; }, 3500);
    }
  } catch (err) {
    if (status) { status.style.color = '#f87171'; status.textContent = 'Gagal: ' + err.message; }
  }
}

function jumpToAzimuth(azVal, objectIndex) {
  const slider = document.getElementById('sliderAz');
  if (slider) {
    slider.value = azVal.toFixed(2);
  }
  onSliderTargetChanged(azVal);

  // Tandai visual chip yang aktif
  document.querySelectorAll('.prominent-chip').forEach(btn => {
    if (Math.abs(parseFloat(btn.dataset.az) - azVal) < 0.15) {
      btn.classList.add('chip-active');
    } else {
      btn.classList.remove('chip-active');
    }
  });

  // Tentukan objek yang dibidik: pakai indeks eksplisit, atau cari yang terdekat
  let idx = Number.isInteger(objectIndex) ? objectIndex : -1;
  if (idx < 0) {
    const objs = window.__prominentObjectsData || [];
    let best = -1, bestDiff = Infinity;
    objs.forEach((o, i) => {
      const d = Math.abs(Number(o.azimuth) - azVal);
      if (d < bestDiff) { bestDiff = d; best = i; }
    });
    if (best >= 0 && bestDiff < 0.6) idx = best;
  }

  // Langsung buka fullscreen pada titik yang dibidik
  openSkylineEditor(idx);
  if (idx >= 0) {
    focusSkyObject(idx);
    // Marker dirender ulang oleh focusSkyObject, jadi label ditulis setelahnya
    requestAnimationFrame(() => showSkyTargetName(idx));
  }
}

// Tampilkan nama objek tepat pada titik bidik di dalam editor fullscreen
function showSkyTargetName(idx) {
  const tip = document.getElementById('skylineTooltip');
  if (!tip) return;
  const objs = window.__prominentObjectsData || [];
  const obj = objs[idx];
  if (!obj) { tip.style.display = 'none'; return; }

  const label = (obj.label && String(obj.label).trim()) || `Objek ${idx + 1}`;
  const el = Number(obj.elevation);
  tip.innerHTML =
    `<b>${escapeHtmlText(label)}</b>` +
    `<span>${Number(obj.azimuth).toFixed(2)}° · ${(el >= 0 ? '+' : '') + el.toFixed(2)}°</span>`;
  tip.style.display = 'block';

  const marker = document.querySelector(`#skyVectors .object-marker[data-object="${idx}"]`);
  const svg = document.getElementById('skylineEditorSvg');
  if (marker && svg) {
    const r = marker.getBoundingClientRect();
    const sr = svg.getBoundingClientRect();
    const centerX = r.left - sr.left + r.width / 2;
    const topY = r.top - sr.top;
    const tipW = tip.offsetWidth || 150;
    const tipH = tip.offsetHeight || 40;
    tip.style.left = Math.max(8, Math.min(sr.width - tipW - 8, centerX - tipW / 2)) + 'px';
    tip.style.top = Math.max(8, topY - tipH - 10) + 'px';
  }
}

function escapeHtmlText(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
}

