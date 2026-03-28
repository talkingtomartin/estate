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

  // Show selected filename for attachment inputs
  document.querySelectorAll('.file-upload-area').forEach(function (area) {
    const input = area.querySelector('.file-input');
    const textEl = area.querySelector('.file-upload-text');
    if (input && textEl) {
      input.addEventListener('change', function () {
        if (this.files[0]) {
          textEl.textContent = this.files[0].name;
        }
      });
    }
  });
});
