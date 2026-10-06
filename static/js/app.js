document.addEventListener('DOMContentLoaded', () => {
  // ---------- Dark mode toggle (saved in this browser) ----------
  const root = document.documentElement;
  const setTheme = (t) => {
    root.setAttribute('data-theme', t);
    root.setAttribute('data-bs-theme', t);
    try { localStorage.setItem('mrs-theme', t); } catch (e) { /* private mode */ }
    document.querySelectorAll('.theme-toggle').forEach((b) => {
      b.setAttribute('aria-pressed', String(t === 'dark'));
      b.title = t === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
    });
  };
  setTheme(root.getAttribute('data-theme') || 'light');
  document.querySelectorAll('.theme-toggle').forEach((btn) => {
    btn.addEventListener('click', () => setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'));
  });

  // ---------- Password show/hide (login) ----------
  const togglePwd = document.getElementById('togglePwd');
  if (togglePwd) {
    togglePwd.addEventListener('click', () => {
      const input = document.getElementById('password');
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      togglePwd.innerHTML = show ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  }

  // ---------- Custom emergency numbers (saved in this browser) ----------
  const EM_KEY = 'mrs-emergency-numbers';
  const EM_MAX = 10;
  const DEFAULT_NUMBERS = [
    { name: 'Emergency services', phone: '112', fixed: true },
    { name: 'Nearest hospitals', phone: 'Auto', fixed: true },
  ];
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const loadNumbers = () => {
    try {
      const v = JSON.parse(localStorage.getItem(EM_KEY) || '[]');
      return Array.isArray(v) ? v.filter((n) => n && typeof n.phone === 'string').slice(0, EM_MAX) : [];
    } catch (e) { return []; }
  };
  const saveNumbers = (list) => { try { localStorage.setItem(EM_KEY, JSON.stringify(list)); } catch (e) {} };
  const allNumbers = () => DEFAULT_NUMBERS.concat(loadNumbers());

  function renderEmergencyMenus() {
    const custom = loadNumbers();
    const rows = allNumbers().map((n) =>
      `<li><i class="bi ${n.fixed ? 'bi-hospital' : 'bi-person-fill'}"></i><span>${esc(n.name || 'Contact')}</span><span class="em-num">${esc(n.phone)}</span></li>`).join('');
    const hint = custom.length ? '' : '<li><span class="em-empty">No personal numbers added yet.</span></li>';
    document.querySelectorAll('.em-list').forEach((ul) => { ul.innerHTML = rows + hint; });

    const list = document.getElementById('emNumList');
    if (list) {
      const fixed = DEFAULT_NUMBERS.map((n) =>
        `<li><i class="bi bi-hospital text-danger"></i><div><div class="em-name">${esc(n.name)}</div><div class="em-num ms-0">${esc(n.phone)}</div></div><span class="em-lock ms-auto">Always</span></li>`).join('');
      const own = custom.map((n, i) =>
        `<li><i class="bi bi-person-fill text-danger"></i><div><div class="em-name">${esc(n.name || 'Contact')}</div><div class="em-num ms-0">${esc(n.phone)}</div></div>` +
        `<button type="button" class="em-del ms-auto" data-index="${i}" aria-label="Remove ${esc(n.name || n.phone)}" title="Remove"><i class="bi bi-trash3"></i></button></li>`).join('');
      list.innerHTML = fixed + (own || '<li class="em-empty-row">Add a family member, doctor or caregiver above.</li>');
      document.getElementById('emNumCount').textContent = `(${custom.length}/${EM_MAX} added)`;
    }
  }
  renderEmergencyMenus();

  const emForm = document.getElementById('emNumForm');
  if (emForm) {
    const nameIn = document.getElementById('emNumName');
    const phoneIn = document.getElementById('emNumPhone');
    const err = document.getElementById('emNumError');
    const digits = (t) => t.replace(/\D/g, '');
    emForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const name = nameIn.value.trim().replace(/\s+/g, ' ');
      const phone = phoneIn.value.trim().replace(/\s+/g, ' ');
      const list = loadNumbers();
      let msg = '';
      if (!phone) msg = 'Enter a phone number.';
      else if (!/^[+0-9\s\-()]+$/.test(phone) || digits(phone).length < 3 || digits(phone).length > 15) msg = 'Enter a valid phone number (3-15 digits; +, spaces, - and brackets allowed).';
      else if (list.length >= EM_MAX) msg = `You can save up to ${EM_MAX} numbers. Remove one to add another.`;
      else if (allNumbers().some((n) => digits(n.phone) && digits(n.phone) === digits(phone))) msg = 'This number is already in the list.';
      err.textContent = msg;
      phoneIn.classList.toggle('is-invalid', !!msg);
      if (msg) { phoneIn.focus(); return; }
      list.push({ name: name || 'Contact', phone });
      saveNumbers(list);
      emForm.reset();
      renderEmergencyMenus();
      nameIn.focus();
    });
    phoneIn.addEventListener('input', () => { phoneIn.classList.remove('is-invalid'); err.textContent = ''; });
    document.getElementById('emNumList').addEventListener('click', (e) => {
      const btn = e.target.closest('.em-del');
      if (!btn) return;
      const list = loadNumbers();
      list.splice(Number(btn.dataset.index), 1);
      saveNumbers(list);
      renderEmergencyMenus();
    });
    const numModal = document.getElementById('emergencyNumbersModal');
    numModal.addEventListener('shown.bs.modal', () => nameIn.focus());
    numModal.addEventListener('hidden.bs.modal', () => { err.textContent = ''; phoneIn.classList.remove('is-invalid'); emForm.reset(); });
  }
  // Keep every open tab in sync when numbers change elsewhere
  window.addEventListener('storage', (e) => { if (e.key === EM_KEY) renderEmergencyMenus(); });

  // ---------- Emergency modal: connecting timer ----------
  const modal = document.getElementById('emergencyModal');
  if (modal) {
    let timer = null;
    const timerEl = document.getElementById('emergencyTimer');
    const statusEl = document.getElementById('emergencyStatus');
    const callList = document.getElementById('emergencyCallingList');
    const renderCalling = (s) => {
      if (!callList) return;
      callList.innerHTML = allNumbers().map((n, i) => {
        // Numbers are alerted one after another, one second apart
        const done = s >= i + 2;
        return `<li><i class="bi ${n.fixed ? 'bi-hospital' : 'bi-person-fill'} text-danger"></i><span>${esc(n.name || 'Contact')}</span>` +
          `<span class="em-num">${esc(n.phone)}</span><span class="em-state ${done ? 'done' : ''}">${done ? 'Alerted' : 'Calling...'}</span></li>`;
      }).join('');
    };
    modal.addEventListener('show.bs.modal', () => renderCalling(0));
    modal.addEventListener('shown.bs.modal', () => {
      let s = 0;
      timerEl.textContent = '00:00';
      statusEl.innerHTML = 'Connecting<span class="dots"></span>';
      clearInterval(timer);
      timer = setInterval(() => {
        s += 1;
        timerEl.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
        if (s === 3) statusEl.innerHTML = 'Alerting nearest hospitals<span class="dots"></span>';
        renderCalling(s);
      }, 1000);
    });
    // Stop the timer when the modal closes so it never keeps running in the background
    modal.addEventListener('hidden.bs.modal', () => clearInterval(timer));
  }

  // ---------- Assessment form ----------
  const form = document.getElementById('assessmentForm');
  if (!form) return;

  const photoInput = document.getElementById('photo');
  const photoData = document.getElementById('photoData');
  const preview = document.getElementById('photoPreview');
  const removeBtn = document.getElementById('removePhoto');
  const photoError = document.getElementById('photoError');
  const placeholder = '<i class="bi bi-person-fill"></i>';
  const MAX = 2 * 1024 * 1024;

  photoInput.addEventListener('change', () => {
    photoError.textContent = '';
    const file = photoInput.files[0];
    if (!file) return;
    if (!/^image\/(jpeg|png|webp|gif)$/.test(file.type)) {
      photoError.textContent = 'Please choose a JPG, PNG, WEBP or GIF image.';
      photoInput.value = '';
      return;
    }
    if (file.size > MAX) {
      photoError.textContent = 'Photo must be smaller than 2 MB.';
      photoInput.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      preview.innerHTML = '';
      const img = document.createElement('img');
      img.src = e.target.result;
      img.alt = 'Patient photo';
      preview.appendChild(img);
      photoData.value = '';            // the new file upload takes priority on the server
      removeBtn.classList.remove('d-none');
    };
    reader.readAsDataURL(file);
  });

  removeBtn.addEventListener('click', () => {
    photoInput.value = '';
    photoData.value = '';
    preview.innerHTML = placeholder;
    removeBtn.classList.add('d-none');
    photoError.textContent = '';
  });

  // ---------- Common-symptom chips: click to add, click again to remove ----------
  const symptomsInput = document.getElementById('symptoms');
  const chips = document.querySelectorAll('#symptomChips .chip');
  const currentSymptoms = () => symptomsInput.value.split(',').map((x) => x.trim()).filter(Boolean);
  const syncChips = () => {
    const have = currentSymptoms().map((x) => x.toLowerCase());
    chips.forEach((c) => {
      const on = have.includes(c.dataset.symptom);
      c.classList.toggle('active', on);
      c.setAttribute('aria-pressed', String(on));
    });
  };
  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      const list = currentSymptoms();
      const i = list.findIndex((x) => x.toLowerCase() === chip.dataset.symptom);
      if (i >= 0) list.splice(i, 1); else list.push(chip.dataset.symptom);
      symptomsInput.value = list.join(', ');
      symptomsInput.classList.remove('is-invalid');
      symptomsInput.setCustomValidity('');
      syncChips();
    });
  });
  symptomsInput.addEventListener('input', syncChips);
  syncChips();

  // Clear form — also clears values the server pre-filled after a submit
  document.getElementById('resetBtn').addEventListener('click', () => {
    form.querySelectorAll('input:not([type=hidden]), textarea').forEach((el) => {
      if (el.type === 'file') el.value = ''; else el.value = '';
      el.classList.remove('is-invalid');
    });
    form.querySelectorAll('select').forEach((el) => { el.selectedIndex = 0; });
    syncChips();
    removeBtn.click();
    form.classList.remove('was-validated');
    const results = document.getElementById('results');
    if (results) results.remove();
    const errs = document.getElementById('formErrors');
    if (errs) errs.remove();
    document.getElementById('name').focus();
  });

  // Client-side validation (the server validates again) + prevent double submits
  const predictBtn = document.getElementById('predictBtn');
  form.addEventListener('submit', (e) => {
    const symptoms = document.getElementById('symptoms');
    symptoms.setCustomValidity(symptoms.value.split(',').some((s) => s.trim()) ? '' : 'required');
    ['name', 'symptoms'].forEach((id) => {
      const el = document.getElementById(id);
      if (el.value.trim() === '' && el.value !== '') el.value = '';   // whitespace-only counts as empty
    });
    if (!form.checkValidity()) {
      e.preventDefault();
      form.classList.add('was-validated');
      const firstInvalid = form.querySelector(':invalid');
      if (firstInvalid) { firstInvalid.focus(); firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      return;
    }
    // The PDF button downloads a file and the page stays - so don't lock the form for it
    if (e.submitter && e.submitter.id === 'pdfBtn') return;
    predictBtn.disabled = true;
    predictBtn.querySelector('.btn-label').classList.add('d-none');
    predictBtn.querySelector('.btn-loading').classList.remove('d-none');
  });

  // Restore the button if the user navigates back (bfcache)
  window.addEventListener('pageshow', () => {
    predictBtn.disabled = false;
    predictBtn.querySelector('.btn-label').classList.remove('d-none');
    predictBtn.querySelector('.btn-loading').classList.add('d-none');
  });

  // Scroll to results / errors after a submit
  const target = document.getElementById('results') || document.getElementById('formErrors');
  if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
