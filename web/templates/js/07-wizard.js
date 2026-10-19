function goToStep(step) {
  step = Math.max(1, Math.min(WIZARD_MAX_STEP, parseInt(step, 10) || 1));
  wizardStep = step;
  for (let i = 1; i <= WIZARD_MAX_STEP; i++) {
    const panel = document.getElementById('stepPanel' + i);
    if (panel) panel.classList.toggle('active', i === step);
  }
  syncHeaderNav();
}

function syncHeaderNav() {
  const prev = document.getElementById('navPrevBtn');
  const next = document.getElementById('navNextBtn');
  const label = document.getElementById('navStepLabel');
  if (prev) prev.disabled = wizardStep <= 1;
  if (label) label.textContent = wizardStep + ' / ' + WIZARD_MAX_STEP;
  if (!next) return;
  next.disabled = false;
  const titles = {
    1: 'Lanjut ke parameter',
    2: 'Proses ekstraksi kontur',
    3: 'Lanjut ke laporan',
    4: 'Preview laporan PDF'
  };
  next.title = titles[wizardStep] || 'Lanjut';
}

function wizardNext() {
  if (wizardStep === 1) {
    advanceFromStep1();
  } else if (wizardStep === 2) {
    processImage();
  } else if (wizardStep === 3) {
    advanceToReportStep();
  } else {
    openReportPreview();
  }
}

function wizardPrev() {
  if (wizardStep <= 1) return;
  goToStep(wizardStep - 1);
}

function advanceFromStep1() {
  if (!selectedImageBase64) {
    alert("Pilih atau ambil citra terlebih dahulu sebelum melanjutkan.");
    return;
  }
  goToStep(2);
}

function advanceToReportStep() {
  if (!currentProfileData) {
    alert("Proses ekstraksi kontur terlebih dahulu sebelum membuka laporan.");
    return;
  }
  goToStep(4);
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
    document.getElementById('resultSection').style.display = 'grid';
    goToStep(3);
  })
  .catch(err => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('btnProcess').disabled = false;
    alert("Terjadi kesalahan jaringan atau server.");
  });
}

// Zero-latency slider: hitung langsung di ponsel klien dalam 0 milidetik!
