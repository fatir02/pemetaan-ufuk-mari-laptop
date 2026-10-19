function resetObservation() {
  selectedImageBase64 = null;
  document.getElementById('rawPreview').style.display = 'none';
  document.getElementById('resultSection').style.display = 'none';
  if (document.getElementById('rightPlaceholder')) {
    document.getElementById('rightPlaceholder').style.display = 'block';
  }
  const dropArea = document.getElementById('dropArea');
  if (dropArea) {
    dropArea.style.display = 'block';
    dropArea.classList.remove('active');
  }
  document.getElementById('lblPhotoStatus').innerText = "Belum ada foto yang dipilih";
  document.getElementById('lblPhotoStatus').style.color = "#94a3b8";
  resetImgZoom();
  // Kembali ke langkah awal dan kunci kembali langkah lanjutan.
  setStepUnlocked(2, false);
  setStepUnlocked(3, false);
  setStepUnlocked(4, false);
  goToStep(1);
}

// ==========================================
// INTERACTIVE IMAGE: PINCH-ZOOM & AZIMUTH DRAG
// ==========================================
let imgZoomScale = 1.0;
let imgPanX = 0, imgPanY = 0;
let imgInitialPinchDist = null;
let imgInitialZoom = 1.0;
let isInteractingAzimuth = false;
let isPanningImg = false;
let imgPanStartX = 0, imgPanStartY = 0;

function applyImgZoomTransform() {
  const vp = document.getElementById('zoomPanViewport');
  const badge = document.getElementById('zoomLevelBadge');
  if (vp) {
    vp.style.transform = "translate(" + imgPanX + "px, " + imgPanY + "px) scale(" + imgZoomScale + ")";
  }
  if (badge) {
    badge.innerText = Math.round(imgZoomScale * 100) + "%";
  }
}

function zoomInImg() {
  imgZoomScale = Math.min(4.0, imgZoomScale + 0.3);
  applyImgZoomTransform();
}

function zoomOutImg() {
  imgZoomScale = Math.max(1.0, imgZoomScale - 0.3);
  if (imgZoomScale <= 1.05) {
    imgZoomScale = 1.0;
    imgPanX = 0;
    imgPanY = 0;
  }
  applyImgZoomTransform();
}

function resetImgZoom() {
  imgZoomScale = 1.0;
  imgPanX = 0;
  imgPanY = 0;
  applyImgZoomTransform();
}

function getNormalizedImgX(clientX) {
  const img = document.getElementById('resOverlayImg');
  if (!img) return null;
  const rect = img.getBoundingClientRect();
  if (rect.width <= 0) return null;
  const relX = (clientX - rect.left) / rect.width;
  return Math.max(0.0, Math.min(1.0, relX));
}

function updateAzimuthFromImageX(clientX) {
  const relX = getNormalizedImgX(clientX);
  if (relX === null) return;
  const slider = document.getElementById('sliderAz');
  if (!slider) return;
  const minAz = parseFloat(slider.min) || 262.5;
  const maxAz = parseFloat(slider.max) || 277.5;
  const newAz = minAz + relX * (maxAz - minAz);
  slider.value = newAz.toFixed(2);
  onSliderTargetChanged(newAz);
}

function initInteractiveImage() {
  const container = document.getElementById('imgInteractiveContainer');
  if (!container) return;

  container.addEventListener('touchstart', function(e) {
    if (e.touches.length === 1) {
      if (imgZoomScale <= 1.1) {
        isInteractingAzimuth = true;
        updateAzimuthFromImageX(e.touches[0].clientX);
      } else {
        isPanningImg = true;
        imgPanStartX = e.touches[0].clientX - imgPanX;
        imgPanStartY = e.touches[0].clientY - imgPanY;
      }
    } else if (e.touches.length === 2) {
      isInteractingAzimuth = false;
      isPanningImg = false;
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      imgInitialPinchDist = Math.hypot(dx, dy);
      imgInitialZoom = imgZoomScale;
    }
  }, { passive: false });

  container.addEventListener('touchmove', function(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
      if (isInteractingAzimuth) {
        updateAzimuthFromImageX(e.touches[0].clientX);
      } else if (isPanningImg) {
        imgPanX = e.touches[0].clientX - imgPanStartX;
        imgPanY = e.touches[0].clientY - imgPanStartY;
        applyImgZoomTransform();
      }
    } else if (e.touches.length === 2 && imgInitialPinchDist) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.hypot(dx, dy);
      const factor = dist / imgInitialPinchDist;
      imgZoomScale = Math.min(4.5, Math.max(1.0, imgInitialZoom * factor));
      applyImgZoomTransform();
    }
  }, { passive: false });

  container.addEventListener('touchend', function(e) {
    if (e.touches.length === 0) {
      isInteractingAzimuth = false;
      isPanningImg = false;
      imgInitialPinchDist = null;
      if (imgZoomScale <= 1.05) {
        imgZoomScale = 1.0;
        imgPanX = 0;
        imgPanY = 0;
        applyImgZoomTransform();
      }
    } else if (e.touches.length === 1 && imgZoomScale > 1.0) {
      isPanningImg = true;
      imgPanStartX = e.touches[0].clientX - imgPanX;
      imgPanStartY = e.touches[0].clientY - imgPanY;
    }
  });

  let isMouseDown = false;
  container.addEventListener('mousedown', function(e) {
    if (e.button !== 0) return;
    isMouseDown = true;
    if (imgZoomScale <= 1.1) {
      updateAzimuthFromImageX(e.clientX);
    } else {
      isPanningImg = true;
      imgPanStartX = e.clientX - imgPanX;
      imgPanStartY = e.clientY - imgPanY;
    }
  });

  window.addEventListener('mousemove', function(e) {
    if (!isMouseDown) return;
    if (imgZoomScale <= 1.1) {
      updateAzimuthFromImageX(e.clientX);
    } else if (isPanningImg) {
      imgPanX = e.clientX - imgPanStartX;
      imgPanY = e.clientY - imgPanStartY;
      applyImgZoomTransform();
    }
  });

  window.addEventListener('mouseup', function() {
    isMouseDown = false;
    isPanningImg = false;
  });

  container.addEventListener('wheel', function(e) {
    e.preventDefault();
    const delta = e.deltaY < 0 ? 0.25 : -0.25;
    imgZoomScale = Math.min(4.5, Math.max(1.0, imgZoomScale + delta));
    if (imgZoomScale <= 1.05) {
      imgZoomScale = 1.0;
      imgPanX = 0;
      imgPanY = 0;
    }
    applyImgZoomTransform();
  }, { passive: false });

  container.addEventListener('dblclick', function() {
    resetImgZoom();
  });
}

// Interaksi klik & seret langsung pada Grafik Kurva Profil Elevasi vs Azimut
function updateAzimuthFromPlotClientX(clientX) {
  const img = document.getElementById('resPlotImg');
  if (!img) return;
  const rect = img.getBoundingClientRect();
  if (rect.width <= 0) return;

  const relX = (clientX - rect.left) / rect.width;

  // Sumbu plot Matplotlib: left = 0.13, right = 0.96 (lebar area koordinat = 0.83)
  const leftBound = 0.13;
  const rightBound = 0.96;
  const plotWidth = rightBound - leftBound;

  const clampedX = Math.max(leftBound, Math.min(rightBound, relX));
  const axisFraction = (clampedX - leftBound) / plotWidth;

  const slider = document.getElementById('sliderAz');
  if (!slider) return;
  const minAz = parseFloat(slider.min) || 240.0;
  const maxAz = parseFloat(slider.max) || 300.0;

  const newAz = minAz + axisFraction * (maxAz - minAz);
  slider.value = newAz.toFixed(2);
  onSliderTargetChanged(newAz);
}

function initInteractivePlot() {
  const wrapper = document.getElementById('plotInteractiveWrapper');
  const img = document.getElementById('resPlotImg');
  const targetEl = wrapper || img;
  if (!targetEl) return;

  let isPlotMouseDown = false;

  targetEl.addEventListener('mousedown', function(e) {
    if (e.button !== 0) return;
    isPlotMouseDown = true;
    updateAzimuthFromPlotClientX(e.clientX);
  });

  window.addEventListener('mousemove', function(e) {
    if (!isPlotMouseDown) return;
    updateAzimuthFromPlotClientX(e.clientX);
  });

  window.addEventListener('mouseup', function() {
    isPlotMouseDown = false;
  });

  targetEl.addEventListener('touchstart', function(e) {
    if (e.touches.length === 1) {
      updateAzimuthFromPlotClientX(e.touches[0].clientX);
    }
  }, { passive: true });

  targetEl.addEventListener('touchmove', function(e) {
    if (e.touches.length === 1) {
      updateAzimuthFromPlotClientX(e.touches[0].clientX);
    }
  }, { passive: true });
}

// Dukungan Drag & Drop pada area pemilihan foto
const dropAreaEl = document.getElementById('dropArea');
if (dropAreaEl) {
  ['dragenter', 'dragover'].forEach(evt => {
    dropAreaEl.addEventListener(evt, e => {
      e.preventDefault();
      e.stopPropagation();
      dropAreaEl.style.borderColor = '#38bdf8';
      dropAreaEl.style.backgroundColor = '#1e293b';
    }, false);
  });
  ['dragleave', 'drop'].forEach(evt => {
    dropAreaEl.addEventListener(evt, e => {
      e.preventDefault();
      e.stopPropagation();
      dropAreaEl.style.borderColor = '#334155';
      dropAreaEl.style.backgroundColor = '#0f172a';
    }, false);
  });
  dropAreaEl.addEventListener('drop', e => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      const fakeInput = { files: dt.files, id: 'galleryInput' };
      onFileSelected(fakeInput);
    }
  });
}

// Dukungan paste gambar langsung (Ctrl+V) dari clipboard
window.addEventListener('paste', function(e) {
  const items = (e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData) || {}).items;
  if (!items) return;
  for (let i = 0; i < items.length; i++) {
    if (items[i].kind === 'file' && items[i].type.startsWith('image/')) {
      const file = items[i].getAsFile();
      if (file) {
        compressAndSetImage(file, activeSlotIndex, "Foto Hasil Tempel (Paste Clipboard)");
        stopLiveCamera();
      }
      break;
    }
  }
});

document.addEventListener('DOMContentLoaded', function() {
  initInteractiveImage();
  initInteractivePlot();
  updatePhotoSlotsUI();
});
