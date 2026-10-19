async function zeroCurrentTilt() {
  try {
    const res = await fetch('/api/compass/zero_tilt', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      liveCompassTilt = data.tilt || 0.0;
      const inp = document.getElementById('inpTilt');
      if (inp) inp.value = (data.tilt || 0.0).toFixed(1);
      alert(`Kalibrasi kemiringan selesai.\nPosisi kamera dinolkan menjadi 0.0° Level.\nOffset tersimpan: ${data.tilt_offset}°`);
    }
  } catch (err) {
    alert("Gagal mengalibrasi kemiringan: " + err.message);
  }
}

// Tombol Spasi & Enter untuk memicu jepretan saat kamera live aktif
window.addEventListener('keydown', function(e) {
  const liveWrapper = document.getElementById('liveCamWrapper');
  if (liveWrapper && liveWrapper.style.display !== 'none') {
    const activeTag = document.activeElement ? document.activeElement.tagName.toUpperCase() : '';
    if (activeTag === 'INPUT' || activeTag === 'TEXTAREA' || activeTag === 'SELECT') return;
    if (e.code === 'Space' || e.key === ' ' || e.code === 'Enter') {
      e.preventDefault();
      captureLiveFrame();
    }
  }
});

function getGPS() {
  if (!navigator.geolocation) {
    alert("Geolocation tidak didukung pada browser ini.");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    pos => {
      document.getElementById('inpLat').value = pos.coords.latitude.toFixed(5);
      document.getElementById('inpLon').value = pos.coords.longitude.toFixed(5);
      if (pos.coords.altitude) {
        document.getElementById('inpAlt').value = Math.round(pos.coords.altitude);
      }
      alert("Lokasi GPS berhasil disinkronkan!");
    },
    err => {
      alert("Gagal membaca GPS: " + err.message + ". Silakan isi secara manual.");
    },
    { enableHighAccuracy: true }
  );
}

// ==========================================
// NAVIGASI LANGKAH (WIZARD)
// ==========================================
let wizardStep = 1;
const WIZARD_MAX_STEP = 4;

