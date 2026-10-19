
// Pengaturan Zoom, Kecerahan, dan Kontras Kamera Live
let camLiveZoom = 1.0;
let camLiveBrightness = 100;
let camLiveContrast = 100;

function applyLiveCamFilters() {
  const video = document.getElementById('cameraVideo');
  if (video) {
    video.style.transform = `scale(${camLiveZoom})`;
    video.style.transformOrigin = 'center center';
    video.style.filter = `brightness(${camLiveBrightness}%) contrast(${camLiveContrast}%)`;
  }
}

async function setLiveCamZoom(val) {
  camLiveZoom = parseFloat(val);
  const lbl = document.getElementById('lblLiveZoomVal');
  if (lbl) lbl.innerText = camLiveZoom.toFixed(1) + 'x';
  const slider = document.getElementById('camZoomSlider');
  if (slider && Math.abs(parseFloat(slider.value) - camLiveZoom) > 0.05) slider.value = camLiveZoom.toFixed(1);
  applyLiveCamFilters();

  // Kirim PTZ Hardware Zoom ke driver UVC jika didukung perangkat
  try {
    if (cameraStream) {
      const track = cameraStream.getVideoTracks()[0];
      if (track && track.getCapabilities) {
        const caps = track.getCapabilities();
        if (caps.zoom) {
          const clamped = Math.min(caps.zoom.max, Math.max(caps.zoom.min, camLiveZoom));
          await track.applyConstraints({ advanced: [{ zoom: clamped }] });
        }
      }
    }
  } catch (e) {}
}

function stepLiveCamZoom(delta) {
  let next = Math.max(1.0, Math.min(4.0, Math.round((camLiveZoom + delta) * 10) / 10));
  setLiveCamZoom(next);
}

function setLiveCamBrightness(val) {
  camLiveBrightness = parseInt(val);
  applyLiveCamFilters();
}

function setLiveCamContrast(val) {
  camLiveContrast = parseInt(val);
  applyLiveCamFilters();
}

function resetLiveCamFilters() {
  camLiveZoom = 1.0;
  camLiveBrightness = 100;
  camLiveContrast = 100;
  const sZoom = document.getElementById('camZoomSlider');
  if (sZoom) sZoom.value = "1.0";
  const sB = document.getElementById('camBrightnessSlider');
  if (sB) sB.value = "100";
  const sC = document.getElementById('camContrastSlider');
  if (sC) sC.value = "100";
  const lbl = document.getElementById('lblLiveZoomVal');
  if (lbl) lbl.innerText = "1.0x";
  applyLiveCamFilters();
}

function drawLiveHudLoop(timestamp) {
  const video = document.getElementById('cameraVideo');
  const canvas = document.getElementById('cameraOverlay');
  if (!cameraStream || video.paused || video.ended) return;

  if (!timestamp || timestamp - lastHudDrawTime > 32) {
    lastHudDrawTime = timestamp || 0;

    if (video.videoWidth > 0 && video.videoHeight > 0) {
      if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
      }

      const ctx = canvas.getContext('2d');
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const scale = Math.max(1, w / 960);
      const cx = w / 2.0;

      const tapeY = 10 * scale;
      const tapeH = 34 * scale;
      const vBarTop = tapeY + tapeH + (32 * scale);
      const vBarBot = h - (36 * scale);
      const vBarH = vBarBot - vBarTop;
      const vFovDeg = 47.0; // Kalibrasi rentang pandang vertikal (interval 20° pas dengan kaca atas & bawah)
      const pxPerDegV = vBarH / vFovDeg;

      // Titik acuan level 0° dan crosshair tengah disesuaikan presisi (+0.9° / pxPerDegV, diturunkan 0.1° dari sebelumnya) agar pas di tengah garis hitam
      const cy = (h / 2.0) + (h * 0.0516) - (0.9 * pxPerDegV);

      const curAz = liveCompassConnected ? liveCompassAzimuth : (parseFloat(document.getElementById('inpAzimuth').value) || 270.0);
      const curTilt = liveCompassConnected ? liveCompassTilt : (parseFloat(document.getElementById('inpTilt').value) || 0.0);
      const isWestLocked = Math.abs(curAz - 270.0) <= 2.5;
      const isLevel = Math.abs(curTilt) <= 0.8;

      // ==========================================================
      // 1. KOMPAS HORIZONTAL ARAH MATA ANGIN (Rentang 240° s.d. 300°)
      // ==========================================================
      const visibleFov = 64; // Menampilkan rentang derajat dari 240° (kiri) hingga 300° (kanan) saat bidik 270°
      const tapeW = Math.min(w * 0.72, 640 * scale); // Garis proporsional, rapi di tengah dan tidak penuh layar
      const tapeX = cx - (tapeW / 2); // Titik awal dihitung agar simetris di tengah

      ctx.save();
      // Baseline garis kompas horizontal sepanjang tapeW
      ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
      ctx.lineWidth = 1 * scale;
      ctx.beginPath();
      ctx.moveTo(tapeX, tapeY + tapeH);
      ctx.lineTo(tapeX + tapeW, tapeY + tapeH);
      ctx.stroke();

      // Skala derajat dihitung sesuai rentang FOV
      const pxPerDeg = tapeW / visibleFov;
      const startDeg = Math.floor(curAz - (visibleFov / 2) - 2);
      const endDeg = Math.ceil(curAz + (visibleFov / 2) + 2);

      for (let d = startDeg; d <= endDeg; d++) {
        const xPos = cx + (d - curAz) * pxPerDeg;
        // Batasi agar angka dan garis derajat tidak digambar di luar pita
        if (xPos < tapeX || xPos > tapeX + tapeW) continue;


        const normDeg = ((d % 360) + 360) % 360;

        if (normDeg % 45 === 0) {
          // Arah Mata Angin Utama (N, NE, E, SE, S, SW, W, NW)
          let card = "";
          if (normDeg === 0) card = "U";
          else if (normDeg === 45) card = "TL";
          else if (normDeg === 90) card = "T";
          else if (normDeg === 135) card = "TG";
          else if (normDeg === 180) card = "S";
          else if (normDeg === 225) card = "BD";
          else if (normDeg === 270) card = "B";
          else if (normDeg === 315) card = "BL";

          const isTargetWest = normDeg === 270;
          ctx.strokeStyle = isTargetWest ? "#10b981" : "#38bdf8";
          ctx.lineWidth = isTargetWest ? 2.5 * scale : 1.8 * scale;
          ctx.beginPath();
          ctx.moveTo(xPos, tapeY + tapeH);
          ctx.lineTo(xPos, tapeY + tapeH - (18 * scale));
          ctx.stroke();

          ctx.fillStyle = isTargetWest ? "#34d399" : "#38bdf8";
          ctx.font = `bold ${Math.round((isTargetWest ? 13 : 11) * scale)}px sans-serif`;
          ctx.textAlign = "center";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 4;
          ctx.fillText(isTargetWest ? "270° B" : card, xPos, tapeY + tapeH - (20 * scale));
          ctx.shadowBlur = 0;
        } else if (normDeg % 15 === 0) {
          // Angka derajat setiap 15°
          ctx.strokeStyle = "rgba(226, 232, 240, 0.85)";
          ctx.lineWidth = 1.2 * scale;
          ctx.beginPath();
          ctx.moveTo(xPos, tapeY + tapeH);
          ctx.lineTo(xPos, tapeY + tapeH - (12 * scale));
          ctx.stroke();

          ctx.fillStyle = "#cbd5e1";
          ctx.font = `bold ${Math.round(10 * scale)}px monospace`;
          ctx.textAlign = "center";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 3;
          ctx.fillText(String(normDeg), xPos, tapeY + tapeH - (14 * scale));
          ctx.shadowBlur = 0;
        } else if (normDeg % 5 === 0) {
          // Garis menengah setiap 5°
          ctx.strokeStyle = "rgba(255, 255, 255, 0.5)";
          ctx.lineWidth = 1 * scale;
          ctx.beginPath();
          ctx.moveTo(xPos, tapeY + tapeH);
          ctx.lineTo(xPos, tapeY + tapeH - (7 * scale));
          ctx.stroke();
        } else {
          // Garis mikro per 1°
          ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
          ctx.lineWidth = 0.8 * scale;
          ctx.beginPath();
          ctx.moveTo(xPos, tapeY + tapeH);
          ctx.lineTo(xPos, tapeY + tapeH - (3.5 * scale));
          ctx.stroke();
        }
      }
      ctx.restore();

      // Jarum penunjuk tengah kompas (Segitiga ▼)
      ctx.beginPath();
      ctx.moveTo(cx - (7 * scale), tapeY + (4 * scale));
      ctx.lineTo(cx + (7 * scale), tapeY + (4 * scale));
      ctx.lineTo(cx, tapeY + (14 * scale));
      ctx.closePath();
      ctx.fillStyle = isWestLocked ? "#10b981" : "#38bdf8";
      ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
      ctx.shadowBlur = 4;
      ctx.fill();
      ctx.shadowBlur = 0;

      // Nilai Angka Derajat Utama di Bawah Pita Kompas
      ctx.fillStyle = isWestLocked ? "#34d399" : "#ffffff";
      ctx.font = `bold ${Math.round(13 * scale)}px monospace`;
      ctx.textAlign = "center";
      ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
      ctx.shadowBlur = 4;
      const cardName = getCardinalDirection(curAz);
      const westIcon = isWestLocked ? "[BARAT] " : "";
      ctx.fillText(`${westIcon}${curAz.toFixed(1)}° ${cardName}`, cx, tapeY + tapeH + (18 * scale));
      ctx.shadowBlur = 0;

      // ==========================================================
      // 2. BAR VERTIKAL DERAJAT KEMIRINGAN (ELEVASI / TILT) DI SISI KIRI
      // ==========================================================
      const vBarX = Math.round(112 * scale); // Garis baseline vertikal di kiri layar (memberi ruang untuk label derajat/cm)

      ctx.save();
      // Baseline garis vertikal di sisi kiri layar
      ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
      ctx.lineWidth = 1 * scale;
      ctx.beginPath();
      ctx.moveTo(vBarX, vBarTop);
      ctx.lineTo(vBarX, vBarBot);
      ctx.stroke();

      // Skala derajat bergerak live mengikuti sudut curTilt
      const startPitch = Math.floor(curTilt - (vFovDeg / 2) - 2);
      const endPitch = Math.ceil(curTilt + (vFovDeg / 2) + 2);

      for (let p = startPitch; p <= endPitch; p++) {
        // Dalam fisika optik: sudut positif (menengadah ke langit) berada di atas cy
        const yPos = cy - (p - curTilt) * pxPerDegV;
        if (yPos < vBarTop || yPos > vBarBot) continue;

        const isZero = (p === 0);
        const isMajor = (p % 10 === 0);
        const isMedium = (p % 5 === 0);

        // Garis penanda skala (Tick Mark)
        ctx.beginPath();
        if (isZero) {
          ctx.strokeStyle = isLevel ? "#10b981" : "#38bdf8";
          ctx.lineWidth = 2.5 * scale;
          ctx.moveTo(vBarX - (24 * scale), yPos);
          ctx.lineTo(vBarX + (8 * scale), yPos);
        } else if (isMajor) {
          ctx.strokeStyle = "rgba(226, 232, 240, 0.9)";
          ctx.lineWidth = 1.5 * scale;
          ctx.moveTo(vBarX - (18 * scale), yPos);
          ctx.lineTo(vBarX + (4 * scale), yPos);
        } else if (isMedium) {
          ctx.strokeStyle = "rgba(255, 255, 255, 0.75)";
          ctx.lineWidth = 1.2 * scale;
          ctx.moveTo(vBarX - (14 * scale), yPos);
          ctx.lineTo(vBarX + (2 * scale), yPos);
        } else {
          // Garis mikro per 1° (tanpa teks angka agar tidak berdempetan)
          ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
          ctx.lineWidth = 0.8 * scale;
          ctx.moveTo(vBarX - (6 * scale), yPos);
          ctx.lineTo(vBarX, yPos);
        }
        ctx.stroke();

        // Label teks derajat dan sentimeter (Hanya untuk 0° UFUK dan kelipatan 5°: 5°, 10°, 15°, 20°)
        // Tidak menampilkan teks +1, +2, +3, -1, -2, -3 agar layar bersih
        if (isZero) {
          ctx.fillStyle = isLevel ? "#34d399" : "#38bdf8";
          ctx.font = `bold ${Math.round(10.5 * scale)}px sans-serif`;
          ctx.textAlign = "right";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 4;
          ctx.fillText("0°/0,00cm UFUK", vBarX - (28 * scale), yPos + (3.5 * scale));
          ctx.shadowBlur = 0;
        } else if (isMajor || isMedium) {
          const sign = p > 0 ? "+" : "-";
          const absP = Math.abs(p);
          const txt = `${sign}${absP}°/${getElevCmStr(absP)}cm`;

          ctx.fillStyle = isMajor ? "#f8fafc" : "#cbd5e1";
          ctx.font = `bold ${Math.round((isMajor ? 10 : 9) * scale)}px monospace`;
          ctx.textAlign = "right";
          ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
          ctx.shadowBlur = 3;
          ctx.fillText(txt, vBarX - (20 * scale), yPos + (3.5 * scale));
          ctx.shadowBlur = 0;
        }
      }
      ctx.restore();

      // Jarum penunjuk tetap di tengah tinggi layar (Segitiga ▶ menunjuk baseline)
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(vBarX + (3 * scale), cy);
      ctx.lineTo(vBarX + (13 * scale), cy - (6 * scale));
      ctx.lineTo(vBarX + (13 * scale), cy + (6 * scale));
      ctx.closePath();
      ctx.fillStyle = isLevel ? "#10b981" : "#38bdf8";
      ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
      ctx.shadowBlur = 4;
      ctx.fill();
      ctx.shadowBlur = 0;

      // Label Nilai Derajat Kemiringan Vertikal Digital di samping jarum penunjuk
      ctx.fillStyle = isLevel ? "#34d399" : "#ffffff";
      ctx.font = `bold ${Math.round(11.5 * scale)}px monospace`;
      ctx.textAlign = "left";
      ctx.shadowColor = "rgba(0, 0, 0, 0.9)";
      ctx.shadowBlur = 4;
      const tiltPrefix = curTilt > 0 ? "+" : (curTilt < 0 ? "-" : "");
      const absTilt = Math.abs(curTilt);
      const liveTiltCm = getElevCmStr(absTilt);
      ctx.fillText(`${tiltPrefix}${absTilt.toFixed(1)}°/${liveTiltCm}cm`, vBarX + (17 * scale), cy + (4 * scale));
      ctx.shadowBlur = 0;
      ctx.restore();

      // ==========================================================
      // 3. RETIKEL TITIK BIDIK TELESKOP BERSIH DI TENGAH LAYAR
      // ==========================================================
      // Menggantikan lingkaran besar dengan crosshair optik bersih tanpa menutupi ufuk
      const chGap = 6 * scale;
      const chLen = 16 * scale;
      ctx.strokeStyle = isLevel ? "#10b981" : "rgba(56, 189, 248, 0.75)";
      ctx.lineWidth = isLevel ? 1.8 * scale : 1.2 * scale;
      if (isLevel) {
        ctx.shadowColor = "rgba(16, 185, 129, 0.8)";
        ctx.shadowBlur = 6 * scale;
      }
      ctx.beginPath();
      // Garis horizontal kiri & kanan
      ctx.moveTo(cx - chGap - chLen, cy);
      ctx.lineTo(cx - chGap, cy);
      ctx.moveTo(cx + chGap, cy);
      ctx.lineTo(cx + chGap + chLen, cy);
      // Garis vertikal atas & bawah
      ctx.moveTo(cx, cy - chGap - chLen);
      ctx.lineTo(cx, cy - chGap);
      ctx.moveTo(cx, cy + chGap);
      ctx.lineTo(cx, cy + chGap + chLen);
      ctx.stroke();

      // Titik pusat bidik mikro di cx, cy
      ctx.beginPath();
      ctx.arc(cx, cy, 1.8 * scale, 0, 2 * Math.PI);
      ctx.fillStyle = isLevel ? "#34d399" : "#38bdf8";
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  }

  animFrameId = requestAnimationFrame(drawLiveHudLoop);
}

function captureLiveFrame() {
  const video = document.getElementById('cameraVideo');
  if (!cameraStream || video.videoWidth === 0) return;

  const hiddenCanvas = document.createElement('canvas');
  hiddenCanvas.width = video.videoWidth;
  hiddenCanvas.height = video.videoHeight;
  const ctx = hiddenCanvas.getContext('2d');

  // Terapkan penyesuaian kecerahan dan kontras
  if (typeof ctx.filter !== 'undefined') {
    ctx.filter = `brightness(${camLiveBrightness}%) contrast(${camLiveContrast}%)`;
  }

  // Jika pengguna melakukan zoom in, crop bagian tengah secara digital beresolusi penuh
  if (camLiveZoom > 1.01) {
    const cropW = video.videoWidth / camLiveZoom;
    const cropH = video.videoHeight / camLiveZoom;
    const cropX = (video.videoWidth - cropW) / 2;
    const cropY = (video.videoHeight - cropH) / 2;
    ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  } else {
    ctx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  }
  if (typeof ctx.filter !== 'undefined') {
    ctx.filter = 'none';
  }

  const b64 = hiddenCanvas.toDataURL('image/jpeg', 0.95);
  const slotNum = activeSlotIndex + 1;
  setPhotoToSlot(activeSlotIndex, b64, `Jepretan Kamera (Slot ${slotNum})`);
  stopLiveCamera();

  // Dapatkan azimuth saat ini
  const azVal = (typeof currentLiveCompassAzimuth !== 'undefined' && currentLiveCompassAzimuth !== null) ? currentLiveCompassAzimuth : (parseFloat(document.getElementById('inpAzimuth')?.value) || 270.0);

  // Simpan langsung ke folder 'hasil_jepretan' di disk laptop
  const lbl = document.getElementById('lblLastSavedCapture');
  if (lbl) {
    lbl.innerHTML = "Menyimpan gambar ke hasil_jepretan/...";
  }

  fetch('/api/save_capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: b64,
      slot_index: activeSlotIndex,
      azimuth: azVal
    })
  })
  .then(r => r.json())
  .then(res => {
    if (res.status === 'success') {
      if (lbl) {
        lbl.innerHTML = `Tersimpan: <b style="color: #4ade80;">${res.filename}</b> (${res.size_kb} KB, ${res.resolution}) di <b>hasil_jepretan/</b>`;
      }
    } else {
      if (lbl) lbl.innerText = "Gagal simpan: " + (res.message || "Error");
    }
  })
  .catch(e => {
    console.warn("Gagal simpan capture:", e);
    if (lbl) lbl.innerText = "Error menyimpan file jepretan";
  });
}

async function openCapturesFolder() {
  try {
    const res = await fetch('/api/open_captures_folder', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      console.log("Folder dibuka:", data.folder);
    }
  } catch (e) {
    alert("Gagal membuka folder: " + e.message);
  }
}

async function importFromSdCard() {
  try {
    const lbl = document.getElementById('lblLastSavedCapture');
    if (lbl) lbl.innerHTML = "Memeriksa perangkat kamera...";
    const res = await fetch('/api/import_sdcard_photos', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      if (data.copied_count > 0) {
        alert(`Berhasil mengimpor ${data.copied_count} foto dari kamera ke folder 'hasil_jepretan'!\\n\\nFile:\\n${data.files.join('\\n')}`);
        if (lbl) {
          lbl.innerHTML = `Berhasil impor <b style="color: #4ade80;">${data.copied_count} foto</b> dari SD card ke <b>hasil_jepretan/</b>`;
        }
        openCapturesFolder();
      } else {
        alert("Tidak ditemukan file foto baru di kartu SD kamera yang terpasang.\\n\\nTips: Saat kamera berada di mode Webcam, foto diambil menggunakan tombol 'AMBIL FRAME (SPASI)' dan otomatis tersimpan.");
        if (lbl) {
          lbl.innerHTML = `hasil_jepretan/ (Tidak ada foto baru di kartu SD)`;
        }
      }
    }
  } catch (e) {
    alert("Gagal impor dari SD Card: " + e.message);
  }
}

