function onSliderTargetChanged(val) {
  const azVal = parseFloat(val);
  document.getElementById('lblSliderAz').innerText = azVal.toFixed(2) + "°";

  if (clientProfileCurve && clientProfileCurve.azimuths) {
    const azs = clientProfileCurve.azimuths;
    const els = clientProfileCurve.elevations;
    let closestIdx = 0;
    let minDiff = 9999;
    for (let i = 0; i < azs.length; i++) {
      const diff = Math.abs(azs[i] - azVal);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }
    const targetAlt = els[closestIdx];
    const dip = clientProfileCurve.dip_deg;

    // Analisis instan di memori JS ponsel
    let category = "Ufuk Terbuka";
    let status = "Cukup Layak";
    let severity = "Cukup Layak";
    if (targetAlt <= -dip + 0.05) {
      category = "Ufuk Terbuka Bebas"; severity = "Sangat Baik";
    } else if (targetAlt <= 0.0) {
      category = "Ufuk Rendah Terbuka"; severity = "Sangat Baik";
    } else if (targetAlt <= 1.2) {
      category = "Halangan Rendah"; severity = "Cukup Layak";
    } else {
      category = "Halangan Bukit/Gunung"; severity = "Perlu Waspada";
    }

    updateTargetDisplay(azVal, {
      target_alt: targetAlt,
      dip_deg: dip,
      severity: severity,
      category: category
    });
  }

  // Perbarui visual plot latar belakang dengan debounce cepat 90ms
  if (sliderDebounceTimer) clearTimeout(sliderDebounceTimer);
  sliderDebounceTimer = setTimeout(() => {
    fetch('/api/recalculate_target', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_az: azVal })
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        const elPlot = document.getElementById('resPlotImg');
        if (elPlot) elPlot.src = data.plot_base64;
        document.getElementById('resOverlayImg').src = data.overlay_base64;
        if (data.prominent_objects) {
          renderProminentObjects(data.prominent_objects);
        }
      }
    });
  }, 90);
}

function updateTargetDisplay(targetAz, analysis) {
  const altStr = (analysis.target_alt >= 0 ? "+" : "") + analysis.target_alt.toFixed(2) + "°";
  if (document.getElementById('resTargetAlt')) {
    document.getElementById('resTargetAlt').innerText = altStr;
  }
  if (document.getElementById('resTargetAltDms')) {
    document.getElementById('resTargetAltDms').innerText = formatDms(analysis.target_alt);
  }
  const dipVal = analysis.dip_deg || 0.20;
  if (document.getElementById('resDip')) {
    document.getElementById('resDip').innerText = "-" + dipVal.toFixed(2) + "°";
  }
  if (document.getElementById('resDipDms')) {
    document.getElementById('resDipDms').innerText = formatDms(-dipVal);
  }
  if (document.getElementById('resDeltaHakiki')) {
    const delta = analysis.target_alt - 0.0;
    document.getElementById('resDeltaHakiki').innerText = (delta >= 0 ? "+" : "") + delta.toFixed(2) + "°";
  }
  if (document.getElementById('resStatusTxt')) {
    document.getElementById('resStatusTxt').innerText = analysis.severity || analysis.status || "Layak";
  }
  const cat = analysis.category || analysis.status || "Ufuk Terbuka";
  if (document.getElementById('resCategoryTxt')) {
    document.getElementById('resCategoryTxt').innerText = cat;
  }
  
  const smartDesc = `Tinggi rintangan ufuk pada azimut sasaran ${targetAz.toFixed(2)}° sebesar ${altStr} (${cat}).`;
  if (document.getElementById('resDescText')) {
    document.getElementById('resDescText').innerText = smartDesc;
  }
  if (document.getElementById('textDesc')) {
    document.getElementById('textDesc').value = smartDesc;
  }

  let smartRec = "";
  if (analysis.target_alt <= 0.0) {
    smartRec = `Bebas rintangan pada azimut ${targetAz.toFixed(2)}°. Profil elevasi berada di 0° sehingga mendukung pemantauan hilal.`;
  } else if (analysis.target_alt <= 1.2) {
    smartRec = `Terdapat rintangan rendah setinggi ${altStr}. Hilal dengan elevasi di atas 1,5° dapat terpantau.`;
  } else {
    smartRec = `Terdapat rintangan setinggi ${altStr} pada azimut ${targetAz.toFixed(2)}°. Hilal dengan elevasi di bawah nilai tersebut akan terhalang.`;
  }
  document.getElementById('textRec').value = smartRec;
}
