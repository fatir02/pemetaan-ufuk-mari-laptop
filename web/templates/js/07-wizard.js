function setStepUnlocked(step, unlocked) {
  const btn = document.getElementById('stepBtn' + step);
  if (btn) btn.disabled = !unlocked;
}

function goToStep(step) {
  step = Math.max(1, Math.min(WIZARD_MAX_STEP, parseInt(step, 10) || 1));
  wizardStep = step;
  for (let i = 1; i <= WIZARD_MAX_STEP; i++) {
    const panel = document.getElementById('stepPanel' + i);
    const btn = document.getElementById('stepBtn' + i);
    if (panel) panel.classList.toggle('active', i === step);
    if (btn) {
      btn.classList.toggle('active', i === step);
      btn.classList.toggle('done', i < step);
      btn.setAttribute('aria-selected', i === step ? 'true' : 'false');
    }
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function goToStepFromStepper(step) {
  // Stepper hanya boleh membuka langkah yang sudah terbuka.
  // Tombol navigasi bawah memakai goToStep() langsung agar tidak ikut terkunci.
  const btn = document.getElementById('stepBtn' + step);
  if (btn && btn.disabled && step !== wizardStep) return;
  goToStep(step);
}

function advanceFromStep1() {
  if (!selectedImageBase64) {
    alert("Pilih atau ambil citra terlebih dahulu sebelum melanjutkan.");
    return;
  }
  setStepUnlocked(2, true);
  goToStep(2);
}

function advanceToReportStep() {
  if (!currentProfileData) {
    alert("Proses ekstraksi kontur terlebih dahulu sebelum membuka laporan.");
    return;
  }
  setStepUnlocked(4, true);
  goToStep(4);
}

function unlockWizardThrough(step) {
  for (let i = 1; i <= Math.min(step, WIZARD_MAX_STEP); i++) {
    setStepUnlocked(i, true);
  }
}

function processImage() {
  if (!selectedImageBase64) {
    alert("Silakan potret foto atau pilih gambar dari galeri terlebih dahulu.");
    return;
  }

  document.getElementById('loadingText').innerText = "Sedang mengekstrak kontur ufuk secara instan...";
  document.getElementById('loading').style.display = 'block';
  document.getElementById('btnProcess').disabled = true;

  const payload = {
    image_base64: selectedImageBase64,
    azimuth: parseFloat(document.getElementById('inpAzimuth').value) || 270.0,
    tilt: parseFloat(document.getElementById('inpTilt').value) || 0.0,
    hfov: parseFloat(document.getElementById('inpHfov')?.value) || 60.0,
    latitude: parseFloat(String(document.getElementById('inpLat').value).replace(',', '.')) || -7.98,
    longitude: parseFloat(String(document.getElementById('inpLon').value).replace(',', '.')) || 110.306,
    altitude: parseFloat(document.getElementById('inpAlt')?.value) || 45.0
  };

  fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('btnProcess').disabled = false;

    if (data.error) {
      alert("Gagal memproses gambar: " + data.error);
      return;
    }

    // Analisis baru: bersihkan nama objek dari citra sebelumnya
    prominentObjectNames = {};
    window.__prominentObjectsData = null;

    currentProfileData = data;
    clientProfileCurve = {
      azimuths: data.profile_curve.az,
      elevations: data.profile_curve.el,
      dip_deg: data.target_analysis.dip_deg || 0.20
    };

    document.getElementById('resOverlayImg').src = data.overlay_base64;
    const elPlot = document.getElementById('resPlotImg');
    if (elPlot) elPlot.src = data.plot_base64;
    resetImgZoom();
    
    const slider = document.getElementById('sliderAz');
    slider.min = data.az_min.toFixed(2);
    slider.max = data.az_max.toFixed(2);
    slider.value = payload.azimuth.toFixed(2);
    document.getElementById('lblSliderAz').innerText = payload.azimuth.toFixed(2) + "°";
    if (document.getElementById('lblMinAz')) document.getElementById('lblMinAz').innerText = data.az_min.toFixed(1) + "°";
    if (document.getElementById('lblMaxAz')) document.getElementById('lblMaxAz').innerText = data.az_max.toFixed(1) + "°";

    updateTargetDisplay(payload.azimuth, data.target_analysis);
    if (data.prominent_objects) {
      renderProminentObjects(data.prominent_objects);
    }

    if (document.getElementById('rightPlaceholder')) {
      document.getElementById('rightPlaceholder').style.display = 'none';
    }
    document.getElementById('resultSection').style.display = 'block';
    unlockWizardThrough(4);
    goToStep(3);
  })
  .catch(err => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('btnProcess').disabled = false;
    alert("Terjadi kesalahan jaringan atau server.");
  });
}

// Zero-latency slider: hitung langsung di ponsel klien dalam 0 milidetik!
