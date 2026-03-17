// Traffix - Utility JavaScript

(function() {
  'use strict';

  // Add loading state to forms on submit
  document.addEventListener('DOMContentLoaded', function() {
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
      form.addEventListener('submit', function(e) {
        var submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn && !submitBtn.classList.contains('btn-loading')) {
          // Store original button content
          submitBtn.dataset.original = submitBtn.innerHTML;
          
          // Add loading spinner (visual only - don't disable inputs)
          submitBtn.classList.add('btn-loading');
          submitBtn.innerHTML = '<span class="spinner"></span> Processing...';
          
          // Just add a visual class to the form, don't disable inputs
          form.classList.add('form-submitting');
        }
      });
    });
  });

  // Flash messages: auto-dismiss, pause on hover, dismiss button
  document.addEventListener('DOMContentLoaded', function() {
    var flashes = document.querySelectorAll('.flash');
    flashes.forEach(function(flash) {
      var timeoutId = null;
      var removeId = null;

      function dismiss() {
        if (!flash || !flash.isConnected) return;
        if (timeoutId) clearTimeout(timeoutId);
        if (removeId) clearTimeout(removeId);
        flash.style.opacity = '0';
        flash.style.transform = 'translateX(20px)';
        flash.style.transition = 'all 0.3s ease';
        removeId = setTimeout(function() {
          flash.remove();
        }, 300);
      }

      function schedule() {
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(dismiss, 5500);
      }

      var closeBtn = flash.querySelector('.flash-close');
      if (closeBtn) closeBtn.addEventListener('click', dismiss);

      flash.addEventListener('mouseenter', function() {
        if (timeoutId) clearTimeout(timeoutId);
      });
      flash.addEventListener('mouseleave', schedule);

      schedule();
    });
  });

})();

