(function () {
  var form = document.getElementById('register-form');
  if (!form) return;

  form.addEventListener('submit', function (e) {
    var password = document.getElementById('password');
    var confirm = document.getElementById('confirm-password');
    if (password && confirm && password.value !== confirm.value) {
      e.preventDefault();
      confirm.setCustomValidity('Passwords do not match');
      confirm.reportValidity();
    } else if (confirm) {
      confirm.setCustomValidity('');
    }
  });

  var confirmEl = document.getElementById('confirm-password');
  if (confirmEl) {
    confirmEl.addEventListener('input', function () {
      this.setCustomValidity('');
    });
  }
})();
