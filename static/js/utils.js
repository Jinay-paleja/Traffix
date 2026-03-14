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

  // Auto-dismiss flash messages after 5 seconds
  document.addEventListener('DOMContentLoaded', function() {
    var flashes = document.querySelectorAll('.flash');
    flashes.forEach(function(flash) {
      setTimeout(function() {
        flash.style.opacity = '0';
        flash.style.transform = 'translateX(20px)';
        flash.style.transition = 'all 0.3s ease';
        setTimeout(function() {
          flash.remove();
        }, 300);
      }, 5000);
    });
  });

})();

