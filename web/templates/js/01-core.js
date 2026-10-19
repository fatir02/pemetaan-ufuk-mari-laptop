let selectedImageBase64 = null;
let currentProfileData = null;
let cameraStream = null;
let animFrameId = null;
let currentZoom = 1.0;
let sliderDebounceTimer = null;
let lastHudDrawTime = 0;
let clientProfileCurve = null;
let liveCompassConnected = false;
let liveCompassAzimuth = 270.0;
let liveCompassTilt = 0.0;
let liveCompassStatus = "";
let liveCompassPort = "";
let liveCompassMag = 0;
let liveCompassGyro = 0;
let skyEditor = { mode: 'navigate', zoom: 1, panX: 0, panY: 0, anchors: [], selected: -1, drag: null, dirty: false };
let skyPointers = new Map();
let skyPinch = null;

// Tabel kalibrasi presisi derajat ke sentimeter (cm) sesuai acuan pengukuran optik falak jarak 30cm:
// 1°/0,52cm, 2°/1,04cm, 3°/1,57cm, 4°/2,09cm, 5°/2,62cm, 10°/5,28cm, 15°/8,03cm, 20°/10,91cm
const CALIB_DEG_CM = {
  1: "0,52", 2: "1,04", 3: "1,57", 4: "2,09", 5: "2,62",
  6: "3,15", 7: "3,68", 8: "4,21", 9: "4,75", 10: "5,28",
  11: "5,83", 12: "6,37", 13: "6,92", 14: "7,47", 15: "8,03",
  16: "8,60", 17: "9,17", 18: "9,74", 19: "10,32", 20: "10,91"
};

function getElevCmStr(d) {
  const a = Math.abs(d);
  if (a < 0.001) return "0,00";
  const intA = Math.round(a);
  if (Math.abs(a - intA) < 0.05 && CALIB_DEG_CM[intA]) {
    return CALIB_DEG_CM[intA];
  }
  // Rumus tangen jarak 30 cm: 30 * tan(theta)
  const cm = 30.0 * Math.tan((a * Math.PI) / 180.0);
  const floored = Math.floor(cm * 100) / 100;
  return floored.toFixed(2).replace('.', ',');
}

function getCardinalDirection(deg) {
  deg = ((deg % 360) + 360) % 360;
  if (deg >= 337.5 || deg < 22.5) return "UTARA";
  if (deg >= 22.5 && deg < 67.5) return "TIMUR LAUT";
  if (deg >= 67.5 && deg < 112.5) return "TIMUR";
  if (deg >= 112.5 && deg < 157.5) return "TENGGARA";
  if (deg >= 157.5 && deg < 202.5) return "SELATAN";
  if (deg >= 202.5 && deg < 247.5) return "BARAT DAYA";
  if (deg >= 247.5 && deg < 292.5) return "BARAT";
  return "BARAT LAUT";
}

async function pollCompassData() {
  try {
    const res = await fetch('/api/compass');
    if (!res.ok) return;
    const data = await res.json();
    const badge = document.getElementById('compassLiveBadge');
    const banner = document.getElementById('liveSensorBanner');
    const bannerText = document.getElementById('sensorBannerText');
    const bannerCalib = document.getElementById('sensorBannerCalib');

    liveCompassConnected = Boolean(data.connected);
    liveCompassStatus = data.status || "";
    liveCompassPort = data.port || "";
    liveCompassMag = data.cal_mag || 0;
    liveCompassGyro = data.cal_gyro || 0;

    if (data.connected) {
      liveCompassAzimuth = (data.azimuth !== undefined && data.azimuth !== null) ? Number(data.azimuth) : 270.0;
      liveCompassTilt = (data.tilt !== undefined && data.tilt !== null) ? Number(data.tilt) : 0.0;
      const azInp = document.getElementById('inpAzimuth');
      const tiltInp = document.getElementById('inpTilt');
      if (azInp && document.activeElement !== azInp) {
        azInp.value = liveCompassAzimuth.toFixed(1);
      }
      if (tiltInp && document.activeElement !== tiltInp) {
        tiltInp.value = liveCompassTilt.toFixed(1);
      }

      const isWest = Math.abs(liveCompassAzimuth - 270.0) <= 2.5;
      const cardName = getCardinalDirection(liveCompassAzimuth);

      if (banner) {
        banner.style.background = isWest ? 'rgba(6, 78, 59, 0.4)' : 'rgba(14, 116, 144, 0.25)';
        banner.style.borderColor = isWest ? '#10b981' : '#0284c7';
      }
      if (bannerText) {
        bannerText.innerHTML = `<b style="color:${isWest ? '#34d399' : '#38bdf8'}">${data.port || 'COM'} Terhubung:</b> ${liveCompassAzimuth.toFixed(1)}° (${cardName}) | Tilt ${liveCompassTilt > 0 ? '+' : ''}${liveCompassTilt.toFixed(1)}°`;
      }
      if (bannerCalib) {
        bannerCalib.innerHTML = `<span style="color:#facc15">Mag: ${data.cal_mag || 0}/3</span> | <span style="color:#38bdf8">Gyro: ${data.cal_gyro || 0}/3</span>`;
      }

      if (badge) {
        badge.style.borderColor = isWest ? '#10b981' : '#0284c7';
        badge.innerHTML = '<span style="color:' + (isWest ? '#10b981' : '#38bdf8') + '; font-weight: 700;">' +
          (isWest ? 'Terkunci Barat: ' : '') + data.port + ': ' + liveCompassAzimuth.toFixed(1) + '° (' + cardName + ' | Tilt ' +
          (liveCompassTilt > 0 ? '+' : '') + liveCompassTilt.toFixed(1) + '°)</span>' +
          '<span style="color: #94a3b8; font-size: 0.72rem;">Mag: ' + (data.cal_mag || 0) + '/3 | Gyro: ' + (data.cal_gyro || 0) + '/3</span>';
      }
    } else {
      const isBusy = (data.status || '').includes('sibuk') || (data.status || '').includes('terkunci');
      if (banner) {
        banner.style.background = isBusy ? 'rgba(153, 27, 27, 0.35)' : 'rgba(30, 41, 59, 0.6)';
        banner.style.borderColor = isBusy ? '#ef4444' : '#475569';
      }
      if (bannerText) {
        bannerText.innerHTML = isBusy 
          ? `<b style="color:#f87171">${data.status}</b>` 
          : `<span style="color: #94a3b8;">${data.status || 'Sensor terputus'}</span>`;
      }
      if (bannerCalib) {
        bannerCalib.innerHTML = isBusy ? '<span style="color:#fca5a5; font-size: 0.72rem;">(Tutup window Serial Monitor)</span>' : '';
      }

      if (badge) {
        badge.style.borderColor = isBusy ? '#ef4444' : '#334155';
        badge.innerHTML = '<span style="color: ' + (isBusy ? '#f87171' : '#94a3b8') + ';">' + (data.status || 'Sensor tidak terdeteksi') + '</span>';
      }
    }
  } catch (err) {}
}
setInterval(pollCompassData, 200);

// Jam Falak Presisi (WIB UTC+7 & UTC)
function updateClocks() {
  const now = new Date();
  const utcStr = now.toISOString().substr(11, 8);
  const wibTime = new Date(now.getTime() + (7 * 3600 * 1000));
  const wibStr = wibTime.toISOString().substr(11, 8);
  const elWib = document.getElementById('clockWib');
  const elUtc = document.getElementById('clockUtc');
  if (elWib) elWib.innerText = wibStr;
  if (elUtc) elUtc.innerText = utcStr;
}
setInterval(updateClocks, 1000);
updateClocks();

// Konversi Sudut ke Sexagesimal DMS (+DD° MM' SS.SS")
function formatDms(deg) {
  const sign = deg < 0 ? "-" : "+";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const remMin = (abs - d) * 60;
  const m = Math.floor(remMin);
  const s = ((remMin - m) * 60).toFixed(1);
  return sign + String(d).padStart(2, '0') + "° " + String(m).padStart(2, '0') + "' " + String(s).padStart(4, '0') + '"';
}

// Pengelolaan 3 Slot Foto & Pilihan Foto
