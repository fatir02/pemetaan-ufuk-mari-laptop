
function openReportPreview() {
  const modal = document.getElementById('reportPreviewModal');
  const container = document.getElementById('docContainer');
  modal.style.display = 'flex';
  container.innerHTML = "<p style='color: #38bdf8; padding: 40px;'>Memuat dokumen PDF...</p>";

  const payload = {
    report_title: (document.getElementById('editReportTitle')?.value || '').trim() || "BERITA ACARA & LAPORAN PEMETAAN PROFIL UFUK MAR'I",
    instansi_name: (document.getElementById('editInstansi')?.value || '').trim() || "FAKULTAS SYARIAH - LABORATORIUM ASTRONOMI & ILMU FALAK",
    location_name: document.getElementById('editLocation').value.trim() || "Pos Observasi Falak Lapangan",
    observer_name: document.getElementById('editObserver').value.trim() || "Tim Falak & Astronomi",
    observer_notes: document.getElementById('textDesc').value.trim(),
    recommendation_text: document.getElementById('textRec').value.trim(),
    objects: getRenamedProminentObjects()
  };

  fetch('/api/preview_pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    if (data.error) {
      container.innerHTML = `<p style="color: #ef4444; padding: 40px;">Gagal memuat dokumen: ${data.error}</p>`;
      return;
    }

    container.innerHTML = "";
    data.pages.forEach((pageB64, idx) => {
      const card = document.createElement('div');
      card.className = "doc-page";
      card.innerHTML = `
        <img src="${pageB64}" alt="Halaman ${idx + 1}" loading="lazy">
        <div class="doc-page-footer">
          Dokumen Berita Acara Falak • Halaman ${idx + 1} dari ${data.pages.length}
        </div>
      `;
      container.appendChild(card);
    });

    resetZoom();
    const vp = document.getElementById('docViewport');
    if (vp) { vp.scrollTop = 0; vp.scrollLeft = 0; }
  })
  .catch(err => {
    container.innerHTML = `<p style="color: #ef4444; padding: 40px;">Koneksi gagal: ${err.message}</p>`;
  });
}

function closeReportPreview() {
  document.getElementById('reportPreviewModal').style.display = 'none';
}

const DOC_BASE_WIDTH = 650;

function setZoomScale(scale) {
  currentZoom = Math.max(0.4, Math.min(2.8, scale));
  const container = document.getElementById('docContainer');
  const viewport = document.getElementById('docViewport');

  // Zoom mengubah LEBAR halaman (bukan transform), sehingga bilah alat
  // di atas tidak ikut ter-zoom maupun terdorong keluar layar.
  if (container) container.style.width = Math.round(DOC_BASE_WIDTH * currentZoom) + 'px';

  // Pertahankan fokus pandangan di tengah saat perbesaran berubah
  if (viewport) {
    const ratioX = viewport.scrollWidth > viewport.clientWidth
      ? (viewport.scrollLeft + viewport.clientWidth / 2) / viewport.scrollWidth
      : 0.5;
    const ratioY = viewport.scrollHeight > viewport.clientHeight
      ? (viewport.scrollTop + viewport.clientHeight / 2) / viewport.scrollHeight
      : 0;
    requestAnimationFrame(() => {
      if (viewport.scrollWidth > viewport.clientWidth) {
        viewport.scrollLeft = ratioX * viewport.scrollWidth - viewport.clientWidth / 2;
      }
      if (viewport.scrollHeight > viewport.clientHeight) {
        viewport.scrollTop = ratioY * viewport.scrollHeight - viewport.clientHeight / 2;
      }
    });
  }

  document.getElementById('lblZoomLevel').innerText = Math.round(currentZoom * 100) + "%";
  document.getElementById('zoomSlider').value = Math.round(currentZoom * 100);
}

function stepZoom(delta) {
  setZoomScale(currentZoom + delta);
}

function resetZoom() {
  setZoomScale(1.0);
}

function fitWidthZoom() {
  const viewport = document.getElementById('docViewport');
  const vw = viewport.clientWidth - 32;
  const scale = Math.max(0.4, Math.min(2.0, vw / DOC_BASE_WIDTH));
  setZoomScale(scale);
}

// Dukungan Gestur Sentuh 2 Jari (Pinch-to-Zoom & Pan) pada Layar HP
let touchStartDist = 0;
let touchStartZoom = 1.0;

function getTouchesDist(touches) {
  const dx = touches[0].clientX - touches[1].clientX;
  const dy = touches[0].clientY - touches[1].clientY;
  return Math.sqrt(dx * dx + dy * dy);
}

const docView = document.getElementById('docViewport');
docView.addEventListener('touchstart', function(e) {
  if (e.touches.length === 2) {
    touchStartDist = getTouchesDist(e.touches);
    touchStartZoom = currentZoom;
  }
}, { passive: true });

docView.addEventListener('touchmove', function(e) {
  if (e.touches.length === 2 && touchStartDist > 0) {
    const curDist = getTouchesDist(e.touches);
    const factor = curDist / touchStartDist;
    setZoomScale(touchStartZoom * factor);
    e.preventDefault();
  }
}, { passive: false });

docView.addEventListener('touchend', function(e) {
  if (e.touches.length < 2) {
    touchStartDist = 0;
  }
}, { passive: true });

// ------------------------------------------------------------------
// PINCH ZOOM TOUCHPAD (Ctrl + scroll / cubit dua jari)
// Hanya KERTAS dokumen yang diperbesar. Bilah alat di atas tidak ikut.
// Tanpa ini, browser melakukan zoom halaman penuh sehingga navbar
// ikut membesar dan terdorong keluar layar.
// ------------------------------------------------------------------
function isPreviewOpen() {
  const m = document.getElementById('reportPreviewModal');
  return !!m && m.style.display === 'flex';
}

function applyPinchZoom(factor) {
  setZoomScale(currentZoom * factor);
}

docView.addEventListener('wheel', function(e) {
  // Ctrl+wheel = gestur pinch pada touchpad (dan Ctrl+scroll manual)
  if (!e.ctrlKey) return;
  e.preventDefault();
  e.stopPropagation();
  // deltaY negatif = cubit membuka = perbesar
  const factor = Math.exp(-e.deltaY * 0.0022);
  applyPinchZoom(factor);
}, { passive: false });

// Cubit di mana pun dalam modal preview (termasuk di atas bilah alat)
// tetap hanya memperbesar kertas, bukan seluruh halaman.
const previewModalEl = document.getElementById('reportPreviewModal');
if (previewModalEl) {
  previewModalEl.addEventListener('wheel', function(e) {
    if (!e.ctrlKey) return;
    e.preventDefault();
    e.stopPropagation();
    const factor = Math.exp(-e.deltaY * 0.0022);
    applyPinchZoom(factor);
  }, { passive: false });
}

// Kunci zoom halaman browser selama preview terbuka
document.addEventListener('wheel', function(e) {
  if (e.ctrlKey && isPreviewOpen()) {
    e.preventDefault();
  }
}, { passive: false });

// Safari / macOS trackpad: event gesture khusus
let gestureStartZoom = 1.0;
docView.addEventListener('gesturestart', function(e) {
  e.preventDefault();
  gestureStartZoom = currentZoom;
});
docView.addEventListener('gesturechange', function(e) {
  e.preventDefault();
  if (e.scale && gestureStartZoom) setZoomScale(gestureStartZoom * e.scale);
});
docView.addEventListener('gestureend', function(e) {
  e.preventDefault();
  gestureStartZoom = currentZoom;
});

// Pintasan papan tombol saat preview terbuka: Ctrl + / Ctrl - / Ctrl 0
document.addEventListener('keydown', function(e) {
  if (!isPreviewOpen() || !e.ctrlKey) return;
  if (e.key === '+' || e.key === '=') {
    e.preventDefault();
    stepZoom(0.2);
  } else if (e.key === '-' || e.key === '_') {
    e.preventDefault();
    stepZoom(-0.2);
  } else if (e.key === '0') {
    e.preventDefault();
    resetZoom();
  }
});

async function downloadCurrentPdf() {
  // Pastikan nama objek terbaru tersimpan di server sebelum PDF dibuat
  try { await applyObjectNames(); } catch (e) {}
  const loc = encodeURIComponent(document.getElementById('editLocation').value.trim() || "Pos Observasi");
  const obs = encodeURIComponent(document.getElementById('editObserver')?.value.trim() || "Tim Falak & Astronomi");
  const title = encodeURIComponent((document.getElementById('editReportTitle')?.value || '').trim());
  const inst = encodeURIComponent((document.getElementById('editInstansi')?.value || '').trim());
  window.open('/api/download_pdf?loc=' + loc + '&obs=' + obs + '&title=' + title + '&inst=' + inst, '_blank');
}

function downloadExcel() {
  const loc = encodeURIComponent(document.getElementById('editLocation').value.trim() || "Pos Observasi");
  const step = document.getElementById('selTableInterval').value || '0.5';
  window.open('/api/download_excel?loc=' + loc + '&step=' + step, '_blank');
}

function downloadCsv() {
  const loc = encodeURIComponent(document.getElementById('editLocation').value.trim() || "Pos Observasi");
  const step = document.getElementById('selTableInterval').value || '0.5';
  window.open('/api/download_csv?loc=' + loc + '&step=' + step, '_blank');
}

function openDataTableModal() {
  if (!clientProfileCurve || !clientProfileCurve.azimuths) {
    alert("Silakan proses foto atau muat gambar terlebih dahulu untuk melihat data numerik.");
    return;
  }
  const modal = document.getElementById('dataTableModal');
  modal.style.display = 'flex';
  renderDataTable(document.getElementById('selTableInterval').value || '0.5');
}

function closeDataTableModal() {
  document.getElementById('dataTableModal').style.display = 'none';
}

function renderDataTable(mode) {
  if (!clientProfileCurve || !clientProfileCurve.azimuths) return;
  const azs = clientProfileCurve.azimuths;
  const els = clientProfileCurve.elevations;
  const dip = clientProfileCurve.dip_deg || 0.20;

  let minEl = 999, maxEl = -999;
  for (let i = 0; i < els.length; i++) {
    if (els[i] < minEl) minEl = els[i];
    if (els[i] > maxEl) maxEl = els[i];
  }
  const minAz = azs[0];
  const maxAz = azs[azs.length - 1];

  document.getElementById('tblAzRange').innerText = minAz.toFixed(2) + "° s.d. " + maxAz.toFixed(2) + "°";
  document.getElementById('tblDipVal').innerText = "-" + dip.toFixed(2) + "°";
  document.getElementById('tblElevRange').innerText = (minEl >= 0 ? "+" : "") + minEl.toFixed(2) + "° s.d. " + (maxEl >= 0 ? "+" : "") + maxEl.toFixed(2) + "°";

  const tbody = document.getElementById('numericTableBody');
  tbody.innerHTML = "";

  let stepInterval = parseFloat(mode);
  if (isNaN(stepInterval) || stepInterval <= 0) stepInterval = 0.5;

  let selectedRows = [];
  if (stepInterval === 0.0) {
    for (let i = 0; i < azs.length; i++) {
      selectedRows.push({ az: azs[i], el: els[i] });
    }
  } else {
    let lastTarget = Math.floor(minAz / stepInterval) * stepInterval;
    while (lastTarget <= maxAz + 0.001) {
      if (lastTarget >= minAz - 0.001 && lastTarget <= maxAz + 0.001) {
        let bestIdx = 0, bestDiff = 9999;
        for (let i = 0; i < azs.length; i++) {
          const diff = Math.abs(azs[i] - lastTarget);
          if (diff < bestDiff) {
            bestDiff = diff;
            bestIdx = i;
          }
        }
        selectedRows.push({ az: azs[bestIdx], el: els[bestIdx] });
      }
      lastTarget += stepInterval;
    }
  }

  document.getElementById('tblSampleCount').innerText = selectedRows.length + " Titik Data";

  const latVal = parseFloat(String(document.getElementById('inpLat')?.value).replace(',', '.')) || -7.98;
  const lonVal = parseFloat(String(document.getElementById('inpLon')?.value).replace(',', '.')) || 110.3061;
  const altVal = parseFloat(document.getElementById('inpAlt')?.value) || 45;
  const locStr = (clientProfileCurve && clientProfileCurve.location_str)
    ? clientProfileCurve.location_str
    : `${latVal.toFixed(4)}°, ${lonVal.toFixed(4)}° (${Math.round(altVal)}m)`;

  let html = "";
  selectedRows.forEach((row, idx) => {
    const el = row.el;
    const az = row.az;
    const elStr = (el >= 0 ? "+" : "") + el.toFixed(2) + "°";
    const cmStr = getElevCmStr(el);
    const elevDisplay = `${elStr} / ${cmStr} cm`;

    let badgeHtml = "";
    if (el <= -dip + 0.05) {
      badgeHtml = '<span class="badge" style="background:#064e3b; color:#34d399; border:1px solid #059669;">Sangat Terbuka (Bebas)</span>';
    } else if (el <= 0.0) {
      badgeHtml = '<span class="badge" style="background:#065f46; color:#a7f3d0; border:1px solid #10b981;">Ufuk Rendah Terbuka</span>';
    } else if (el <= 1.2) {
      badgeHtml = '<span class="badge" style="background:#0c4a6e; color:#38bdf8; border:1px solid #0284c7;">Halangan Rendah (Aman)</span>';
    } else {
      badgeHtml = '<span class="badge" style="background:#451a03; color:#fcd34d; border:1px solid #d97706;">Halangan Tinggi (Waspada)</span>';
    }

    const bgCol = idx % 2 === 0 ? '#131b2a' : '#172235';
    html += `<tr style="background: ${bgCol}; border-bottom: 1px solid #1e293b;">
      <td style="padding: 8px 12px; color: #64748b; font-family: monospace; border-right: 1px solid #1e293b; text-align: center;">${idx + 1}</td>
      <td style="padding: 8px 12px; font-weight: bold; color: #38bdf8; font-family: monospace; border-right: 1px solid #1e293b; text-align: center;">${az.toFixed(2)}°</td>
      <td style="padding: 8px 12px; font-weight: bold; color: #f8fafc; font-family: monospace; border-right: 1px solid #1e293b; text-align: center;">${elevDisplay}</td>
      <td style="padding: 8px 12px; color: #cbd5e1; font-family: monospace; text-align: center;">${locStr}</td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function copyTableToClipboard() {
  const tbody = document.getElementById('numericTableBody');
  const rows = tbody.querySelectorAll('tr');
  if (rows.length === 0) {
    alert("Tidak ada data untuk disalin.");
    return;
  }
  const headerRow = ["No", "Azimut (°)", "Elevasi / cm", "Data Lokasi"].join("\\t");
  let tsv = headerRow + "\\n";
  rows.forEach(r => {
    const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
    tsv += cells.join("\\t") + "\\n";
  });
  navigator.clipboard.writeText(tsv).then(() => {
    alert("Tabel data berhasil disalin ke clipboard! Anda bisa langsung menempelkannya (paste) ke Microsoft Excel atau Google Sheets.");
  }).catch(err => {
    alert("Gagal menyalin: " + err.message);
  });
}

