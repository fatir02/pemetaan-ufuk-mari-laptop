let photoSlots = [null, null, null];
let activeSlotIndex = 0;

function updatePhotoSlotsUI() {
  for (let i = 0; i < 3; i++) {
    const card = document.getElementById('slotCard' + i);
    const img = document.getElementById('slotImg' + i);
    const empty = document.getElementById('slotEmpty' + i);
    const badge = document.getElementById('slotBadge' + i);
    if (!card) continue;

    if (i === activeSlotIndex) {
      card.classList.add('active');
    } else {
      card.classList.remove('active');
    }

    if (photoSlots[i] && photoSlots[i].b64) {
      img.src = photoSlots[i].b64;
      img.style.display = 'block';
      if (empty) empty.style.display = 'none';
      if (badge) badge.innerText = `Slot ${i + 1}`;
    } else {
      img.src = '';
      img.style.display = 'none';
      if (empty) empty.style.display = 'flex';
      if (badge) badge.innerText = `Slot ${i + 1} (Kosong)`;
    }
  }

  // Perbarui preview foto utama
  const preview = document.getElementById('rawPreview');
  const dropArea = document.getElementById('dropArea');
  const lblStatus = document.getElementById('lblPhotoStatus');
  const activeSlot = photoSlots[activeSlotIndex];

  if (activeSlot && activeSlot.b64) {
    selectedImageBase64 = activeSlot.b64;
    if (preview) {
      preview.src = activeSlot.b64;
      preview.style.display = 'block';
    }
    if (dropArea) {
      dropArea.style.display = 'none';
    }
  } else {
    selectedImageBase64 = null;
    if (preview) {
      preview.src = '';
      preview.style.display = 'none';
    }
    if (dropArea) {
      dropArea.style.display = 'block';
      dropArea.classList.remove('active');
    }
    if (lblStatus) {
      lblStatus.innerText = `Slot ${activeSlotIndex + 1} kosong - Silakan pilih / muat foto`;
      lblStatus.style.color = '#38bdf8';
    }
  }
}

function selectPhotoSlot(idx) {
  if (idx < 0 || idx >= 3) return;
  activeSlotIndex = idx;
  if (!photoSlots[idx] || !photoSlots[idx].b64) {
    // Jika slot masih kosong, langsung buka dialog pemilihan file untuk mengisi slot ini
    document.getElementById('galleryInput').click();
  } else {
    updatePhotoSlotsUI();
  }
}

function deleteActivePhotoSlot() {
  if (!photoSlots[activeSlotIndex]) {
    alert("Slot " + (activeSlotIndex + 1) + " memang masih kosong.");
    return;
  }
  photoSlots[activeSlotIndex] = null;
  // Otomatis pindah ke slot lain yang masih terisi jika ada
  let nextIdx = photoSlots.findIndex(s => s && s.b64);
  if (nextIdx !== -1) {
    activeSlotIndex = nextIdx;
  }
  updatePhotoSlotsUI();
}

function setPhotoToSlot(slotIdx, b64, statusText) {
  photoSlots[slotIdx] = {
    b64: b64,
    status: statusText || ("Foto Slot " + (slotIdx + 1))
  };
  activeSlotIndex = slotIdx;
  updatePhotoSlotsUI();
}

function displayLoadedImage(b64, statusText) {
  setPhotoToSlot(activeSlotIndex, b64, statusText);
  stopLiveCamera();
}

function compressAndSetImage(file, targetSlot, statusText) {
  const reader = new FileReader();
  reader.onload = function(e) {
    const dataUrl = e.target.result;
    setPhotoToSlot(targetSlot, dataUrl, statusText);

    // Pertahankan detail menara/antena kecil. Dimensi 1280 px sebelumnya
    // dapat mengecilkan struktur jauh menjadi hanya 1 px lalu hilang oleh JPEG.
    const img = new Image();
    img.onload = function() {
      let w = img.width;
      let h = img.height;
      const maxDim = 2560;
      if (w > maxDim || h > maxDim) {
        if (w > h) {
          h = Math.round((h * maxDim) / w);
          w = maxDim;
        } else {
          w = Math.round((w * maxDim) / h);
          h = maxDim;
        }
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);
        const compressed = canvas.toDataURL('image/jpeg', 0.94);
        if (photoSlots[targetSlot]) {
          photoSlots[targetSlot].b64 = compressed;
          if (activeSlotIndex === targetSlot) {
            selectedImageBase64 = compressed;
            const prev = document.getElementById('rawPreview');
            if (prev) prev.src = compressed;
          }
          const slotImg = document.getElementById('slotImg' + targetSlot);
          if (slotImg) slotImg.src = compressed;
        }
      }
    };
    img.src = dataUrl;
  };
  reader.readAsDataURL(file);
}

function onFileSelected(input) {
  if (input.files && input.files.length > 0) {
    const files = Array.from(input.files).slice(0, 3);
    const sourceName = input.id === 'galleryInput' ? 'Penyimpanan Berkas' : 'Kamera / Webcam';

    files.forEach((file, fIdx) => {
      let slotTarget = activeSlotIndex;
      if (fIdx > 0) {
        const emptyIdx = photoSlots.findIndex((s, idx) => (!s || !s.b64) && idx !== activeSlotIndex);
        if (emptyIdx !== -1) {
          slotTarget = emptyIdx;
        } else {
          slotTarget = (activeSlotIndex + fIdx) % 3;
        }
      }
      compressAndSetImage(file, slotTarget, file.name || ("Foto " + sourceName));
    });
    input.value = "";
    stopLiveCamera();
  }
}

function loadSamplePhoto() {
  fetch('/api/sample_image')
    .then(res => res.json())
    .then(data => {
      setPhotoToSlot(activeSlotIndex, data.image_base64, "Foto contoh lanskap ufuk terpasang");
    })
    .catch(err => {
      alert("Gagal memuat contoh foto: " + err.message);
    });
}

// Render pop up chips objek menonjol (angka derajat horizontal dan vertikal)
// Setiap chip memiliki kolom input nama objek yang bisa diubah manual oleh pengguna.
