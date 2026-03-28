// ── Navbar: hamburger toggle + active link ───────────────────────────────
(function () {
  const navbar   = document.getElementById('navbar');
  const toggle   = document.getElementById('navToggle');
  const links    = document.getElementById('navLinks');
  const backdrop = document.getElementById('navBackdrop');

  function openMenu() {
    navbar.classList.add('open');
    links.classList.add('open');
    backdrop.classList.remove('hidden');
    toggle.setAttribute('aria-expanded', 'true');
  }

  function closeMenu() {
    navbar.classList.remove('open');
    links.classList.remove('open');
    backdrop.classList.add('hidden');
    toggle.setAttribute('aria-expanded', 'false');
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      navbar.classList.contains('open') ? closeMenu() : openMenu();
    });
  }

  if (backdrop) backdrop.addEventListener('click', closeMenu);

  // Close on nav-link click (mobile)
  if (links) {
    links.querySelectorAll('.nav-link').forEach(function (a) {
      a.addEventListener('click', closeMenu);
    });
  }

  // Mark active link
  const path = window.location.pathname;
  if (links) {
    links.querySelectorAll('.nav-link').forEach(function (a) {
      const href = a.getAttribute('href');
      if (href && href !== '#' && path.startsWith(href) && href !== '/') {
        a.classList.add('active');
      } else if (href === '/properties' && path === '/properties') {
        a.classList.add('active');
      }
    });
  }
})();

// Switch category options and recurring label when type changes
function switchType(type) {
  const incomeOpts = document.getElementById('income-options');
  const expenseOpts = document.getElementById('expense-options');
  const recurringGroup = document.getElementById('recurringGroup');
  const recurringSpan = recurringGroup ? recurringGroup.querySelector('span') : null;
  const category = document.getElementById('category');

  if (incomeOpts) incomeOpts.style.display = type === 'income' ? '' : 'none';
  if (expenseOpts) expenseOpts.style.display = type === 'expense' ? '' : 'none';

  if (category) category.value = '';

  if (recurringSpan) {
    recurringSpan.textContent = type === 'income'
      ? 'Fast månedlig inntekt (gjentas hver måned)'
      : 'Fast månedlig utgift (gjentas hver måned)';
  }
}

// Attachment camera / file picker
function openAttachCamera(inputId) {
  const inp = document.getElementById(inputId);
  inp.accept = 'image/*';
  inp.setAttribute('capture', 'environment');
  inp.click();
}

function openAttachFile(inputId) {
  const inp = document.getElementById(inputId);
  inp.accept = 'image/*,.pdf';
  inp.removeAttribute('capture');
  inp.click();
}

// Image preview for property upload
document.addEventListener('DOMContentLoaded', function () {
  const imageInput = document.getElementById('image');
  const imagePreview = document.getElementById('imagePreview');

  if (imageInput && imagePreview) {
    imageInput.addEventListener('change', function () {
      const file = this.files[0];
      if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function (e) {
          imagePreview.src = e.target.result;
          imagePreview.classList.remove('hidden');
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Show selected filename for legacy file-upload-area inputs
  document.querySelectorAll('.file-upload-area').forEach(function (area) {
    const input = area.querySelector('.file-input');
    const textEl = area.querySelector('.file-upload-text');
    if (input && textEl) {
      input.addEventListener('change', function () {
        if (this.files[0]) textEl.textContent = this.files[0].name;
      });
    }
  });

  // Preview + AI receipt parsing for hidden attachment inputs
  document.querySelectorAll('.attach-input-hidden').forEach(function (input) {
    input.addEventListener('change', function () {
      const file = this.files[0];
      if (!file) return;
      const previewId = this.id + '-preview';
      const preview = document.getElementById(previewId);
      if (!preview) return;

      preview.innerHTML = '';
      preview.classList.remove('hidden');

      if (file.type.startsWith('image/')) {
        const img = document.createElement('img');
        img.className = 'attach-preview-img';
        const reader = new FileReader();
        reader.onload = (e) => { img.src = e.target.result; };
        reader.readAsDataURL(file);
        preview.appendChild(img);
      }

      const nameEl = document.createElement('span');
      nameEl.className = 'attach-preview-name';
      nameEl.textContent = file.name;
      preview.appendChild(nameEl);

      // Call AI for both images and PDFs
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      if (file.type.startsWith('image/') || isPdf) {
        parseReceipt(file, preview);
      }
    });
  });
});

// ── AI receipt parsing ───────────────────────────────────────────────────────
function parseReceipt(file, previewEl) {
  const statusEl = document.createElement('span');
  statusEl.className = 'attach-ai-status loading';
  statusEl.textContent = '✨ Leser kvittering...';
  previewEl.appendChild(statusEl);

  const fd = new FormData();
  fd.append('file', file);

  fetch('/transactions/parse-receipt', { method: 'POST', body: fd })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        statusEl.className = 'attach-ai-status error';
        statusEl.textContent = '⚠ ' + data.error;
        return;
      }

      const filled = [];

      if (data.amount != null) {
        const el = document.getElementById('amount');
        if (el && !el.value) { el.value = data.amount; el.classList.add('ai-filled'); filled.push('beløp'); }
      }

      if (data.date) {
        const el = document.getElementById('transaction_date');
        if (el) { el.value = data.date; el.classList.add('ai-filled'); filled.push('dato'); }
      }

      if (data.description) {
        const el = document.getElementById('notes');
        if (el && !el.value) { el.value = data.description; el.classList.add('ai-filled'); filled.push('notat'); }
      }

      statusEl.className = 'attach-ai-status success';
      statusEl.textContent = filled.length ? '✓ Hentet: ' + filled.join(', ') : '✓ Lest – ingen data funnet';
    })
    .catch(function () {
      statusEl.className = 'attach-ai-status error';
      statusEl.textContent = '⚠ Kunne ikke lese kvitteringen';
    });
}

