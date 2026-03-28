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

  // Preview for hidden attachment inputs (camera / file picker)
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
    });
  });
});
