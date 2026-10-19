let currentCameraDeviceId = null;

function toggleHpCameraGuide() {
  const guide = document.getElementById('hpCamGuide');
  if (guide) {
    guide.style.display = guide.style.display === 'none' ? 'block' : 'none';
  }
}

function toggleDigicamGuide() {
  const guide = document.getElementById('digicamGuide');
  if (guide) {
    guide.style.display = guide.style.display === 'none' ? 'block' : 'none';
  }
}

async function checkCameraHardwareStatus() {
  try {
    const res = await fetch('/api/check_cameras');
    if (!res.ok) return;
    const data = await res.json();
    const notice = document.getElementById('digicamNotice');
    if (notice) {
      if (data.digicam_state === 'storage_mode') {
        notice.style.display = 'block';
      } else {
        notice.style.display = 'none';
      }
    }
  } catch (e) {
    console.warn("Gagal cek status hardware kamera:", e);
  }
}

async function refreshCameraDevices() {
  const btn = document.getElementById('btnRefreshCam');
  if (btn) {
    btn.innerHTML = 'Memindai...';
    btn.disabled = true;
  }
  try {
    await checkCameraHardwareStatus();
    await updateCameraDeviceList();
  } catch (err) {
    console.warn("Refresh kamera error:", err);
  } finally {
    if (btn) {
      btn.innerHTML = 'Segarkan';
      btn.disabled = false;
    }
  }
}

async function updateCameraDeviceList() {
  const sel = document.getElementById('cameraSourceSelect');
  if (!sel) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
    sel.innerHTML = '<option value="">WebView tidak mendukung akses kamera</option>';
    return;
  }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = devices.filter(d => d.kind === 'videoinput');
    if (videoDevices.length === 0) {
      sel.innerHTML = '<option value="">Kamera tidak ditemukan</option>';
      return;
    }

    // Jika label & deviceId kosong, artinya izin kamera belum diberikan.
    // Tampilkan opsi generik agar pengguna tetap bisa memilih.
    const noPermission = videoDevices.every(d => !d.deviceId || !d.label);

    sel.innerHTML = "";
    let autoPickIdx = -1;

    videoDevices.forEach((dev, idx) => {
      const opt = document.createElement('option');
      opt.value = dev.deviceId || "";

      if (noPermission) {
        opt.text = `Kamera ${idx + 1} (klik untuk mengaktifkan izin)`;
        sel.appendChild(opt);
        if (autoPickIdx === -1) autoPickIdx = idx;
        return;
      }

      let label = dev.label || `Kamera ${idx + 1}`;

      const isGeneral = /general-a-video|general|1b3f|genplus/i.test(label);
      const isLogi = /logi|c270|c920|c922|brio/i.test(label);
      const isIriun = /iriun/i.test(label);
      const isDroid = /droid/i.test(label);
      const isCamo = /camo|epoc/i.test(label);
      const isInternal = /1bcf:28c4|integrated|built-in|pc camera/i.test(label);
      const isUsb = /usb/i.test(label);

      if (isGeneral) {
        label = label + " (Kamera Saku USB)";
        if (autoPickIdx === -1) autoPickIdx = idx;
      } else if (isLogi) {
        label = label + " (Webcam Eksternal HD)";
        if (autoPickIdx === -1) autoPickIdx = idx;
      } else if (isUsb && !isInternal) {
        label = label + " (Kamera Teleskop USB)";
        if (autoPickIdx === -1) autoPickIdx = idx;
      } else if (isIriun || isDroid || isCamo) {
        label = label + " (Kamera Ponsel)";
      } else if (isInternal) {
        label = label + " (Kamera Laptop)";
      }

      opt.text = label;
      if (currentCameraDeviceId && dev.deviceId === currentCameraDeviceId) {
        opt.selected = true;
      }
      sel.appendChild(opt);
    });

    // Otomatis prioritaskan Digicam/USB eksternal jika pengguna belum memilih kamera tertentu
    if (!currentCameraDeviceId && autoPickIdx !== -1 && !noPermission) {
      sel.selectedIndex = autoPickIdx;
      currentCameraDeviceId = videoDevices[autoPickIdx].deviceId;
    }
  } catch (e) {
    console.warn("Gagal membaca daftar kamera:", e);
  }
}

if (navigator.mediaDevices && typeof navigator.mediaDevices.addEventListener === 'function') {
  navigator.mediaDevices.addEventListener('devicechange', async () => {
    await checkCameraHardwareStatus();
    await updateCameraDeviceList();
  });
}

async function onCameraDeviceSelected(deviceId) {
  if (!deviceId) return;
  currentCameraDeviceId = deviceId;
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
  await startLiveCamera(deviceId);
}

async function openCameraStream(targetId, timeoutMs) {
  // Buka satu kamera lalu pastikan benar-benar mengirim frame.
  // Digicam bermasalah sering "terbuka" tetapi tidak pernah mengirim data,
  // sehingga getUserMedia saja tidak cukup sebagai indikator keberhasilan.
  let stream;
  const constraints = targetId
    ? { video: { deviceId: { exact: targetId }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false }
    : { video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: { ideal: 'environment' } }, audio: false };
  try {
    stream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (strictErr) {
    console.warn('Kamera gagal dengan constraint ideal, mencoba konfigurasi fleksibel:', strictErr);
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: targetId ? { deviceId: { ideal: targetId } } : true,
        audio: false
      });
    } catch (looseErr) {
      throw strictErr;
    }
  }

  const video = document.getElementById('cameraVideo');
  video.srcObject = stream;
  try {
    await video.play();
    await new Promise((resolve, reject) => {
      if (video.videoWidth > 0 && video.videoHeight > 0) return resolve();
      const timer = setTimeout(() => {
        cleanup();
        const e = new Error('Kamera tidak mengirim frame video.');
        e.name = 'NoFrameError';
        reject(e);
      }, timeoutMs || 8000);
      const ready = () => {
        if (video.videoWidth > 0 && video.videoHeight > 0) {
          cleanup();
          resolve();
        }
      };
      function cleanup() {
        clearTimeout(timer);
        video.removeEventListener('loadeddata', ready);
        video.removeEventListener('resize', ready);
        video.removeEventListener('timeupdate', ready);
      }
      video.addEventListener('loadeddata', ready);
      video.addEventListener('resize', ready);
      video.addEventListener('timeupdate', ready);
    });
    return stream;
  } catch (err) {
    stream.getTracks().forEach(t => t.stop());
    video.srcObject = null;
    throw err;
  }
}

async function startLiveCamera(preferredDeviceId) {
  const wrapper = document.getElementById('liveCamWrapper');
  const video = document.getElementById('cameraVideo');
  wrapper.style.display = 'block';
  document.body.classList.add('camera-live-active');
  checkCameraHardwareStatus();

  // Hentikan stream yang sedang berjalan terlebih dahulu
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('MediaDevices/getUserMedia tidak tersedia pada WebView ini');
    }
    let targetId = preferredDeviceId || currentCameraDeviceId;

    // Jika deviceId kosong (izin belum diberikan), minta izin dulu lewat getUserMedia sederhana
    if (!targetId) {
      try {
        const probe = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        probe.getTracks().forEach(tk => tk.stop());
      } catch (permErr) {
        console.warn("Izin kamera belum diberikan:", permErr);
      }
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        try {
          const devices = await navigator.mediaDevices.enumerateDevices();
          const videoDevices = devices.filter(d => d.kind === 'videoinput' && d.deviceId);
          const extCam = videoDevices.find(d =>
            /general|genplus|1b3f|logi|c270|c920|c922|brio|teleskop|eyepiece|usb/i.test(d.label) &&
            !/1bcf:28c4|integrated|built-in/i.test(d.label)
          );
          if (extCam && extCam.deviceId) {
            targetId = extCam.deviceId;
            currentCameraDeviceId = targetId;
          }
        } catch (e) {}
      }
    }

    // Kumpulkan kandidat: kamera pilihan lebih dulu, lalu kamera lain.
    let allVideoIds = [];
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      allVideoIds = devices.filter(d => d.kind === 'videoinput' && d.deviceId).map(d => d.deviceId);
    } catch (e) {}
    const candidateIds = [];
    if (targetId) candidateIds.push(targetId);
    allVideoIds.forEach(id => { if (!candidateIds.includes(id)) candidateIds.push(id); });
    if (candidateIds.length === 0) candidateIds.push(null);

    let lastError = null;
    let switchedFrom = null;
    for (let i = 0; i < candidateIds.length; i++) {
      const id = candidateIds[i];
      try {
        cameraStream = await openCameraStream(id, 8000);
        if (id) currentCameraDeviceId = id;
        if (i > 0) switchedFrom = candidateIds[0];
        lastError = null;
        break;
      } catch (err) {
        lastError = err;
        console.warn('Kamera kandidat gagal:', id, err);
      }
    }
    if (!cameraStream) throw lastError || new Error('Tidak ada kamera yang mengirim frame.');
    if (switchedFrom) {
      const track = cameraStream.getVideoTracks()[0];
      const activeName = track ? (track.label || 'kamera lain') : 'kamera lain';
      const msg = document.getElementById('lblPhotoStatus');
      if (msg) {
        msg.textContent = 'Kamera awal tidak mengirim gambar — beralih ke ' + activeName;
        msg.style.color = '#fbbf24';
      }
    }

    try {
      const vTracks = cameraStream.getVideoTracks();
      if (vTracks && vTracks.length > 0 && vTracks[0].getSettings) {
        const settings = vTracks[0].getSettings();
        if (settings.deviceId) {
          currentCameraDeviceId = settings.deviceId;
        }
      }
    } catch (e) {}

    await updateCameraDeviceList();
    applyLiveCamFilters();
    drawLiveHudLoop();
    checkCameraHardwareStatus();
    video.onloadedmetadata = () => {
      video.play().catch(e => console.warn(e));
    };
  } catch (err) {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      cameraStream = null;
    }
    const name = err && err.name ? err.name : 'CameraError';
    let hint = 'Pastikan kamera tidak sedang dipakai aplikasi lain.';
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      hint = 'Aktifkan izin kamera untuk Terminal/Python atau aplikasi ini di System Settings → Privacy & Security → Camera, lalu buka ulang aplikasi.';
    } else if (name === 'NoFrameError') {
      hint = 'Perangkat terdeteksi tetapi tidak mengirim gambar (gejala yang sama terlihat di Photo Booth). Periksa kabel/port USB, pastikan mode PC Camera benar, lalu coba kamera lain.';
    } else if (name === 'NotReadableError' || name === 'AbortError') {
      hint = 'Perangkat terdeteksi tetapi stream tidak terbaca. Cabut USB, matikan digicam, sambungkan ulang langsung ke port USB, lalu pilih PC Camera.';
    } else if (name === 'OverconstrainedError' || name === 'NotFoundError') {
      hint = 'Pilih kamera pada daftar sumber lalu tekan Segarkan.';
    }
    alert(`Tidak dapat membuka kamera [${name}]: ${err.message}. ${hint}`);
    wrapper.style.display = 'none';
    document.body.classList.remove('camera-live-active');
  }
}

function stopLiveCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
  document.getElementById('liveCamWrapper').style.display = 'none';
  document.body.classList.remove('camera-live-active');
}

function toggleCameraFullscreen() {
  const wrapper = document.getElementById('liveCamWrapper');
  if (!wrapper) return;
  if (!document.fullscreenElement) {
    if (wrapper.requestFullscreen) {
      wrapper.requestFullscreen().catch(err => console.warn(err));
    } else if (wrapper.webkitRequestFullscreen) {
      wrapper.webkitRequestFullscreen();
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(err => console.warn(err));
    }
  }
}
