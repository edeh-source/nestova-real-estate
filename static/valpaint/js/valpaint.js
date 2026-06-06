/* valpaint.js — client-side logic for the Valpaint × Nestova app */
(function () {
  'use strict';

  // ── Scroll reveal (mirrors Nestova's pattern from index.html) ────────────
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('revealed');
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08, rootMargin: '0px 0px -40px 0px' }
  );
  document.querySelectorAll('[data-reveal]').forEach(el => revealObserver.observe(el));


  // ── AJAX enquiry form ────────────────────────────────────────────────────
  document.querySelectorAll('#vpEnquiryForm').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();

      const submitBtn   = form.querySelector('.vp-form__submit');
      const submitText  = form.querySelector('.vp-form__submit-text');
      const submitLoad  = form.querySelector('.vp-form__submit-loading');
      const successBox  = form.querySelector('.vp-form__success');

      // Show loading state
      submitBtn.disabled = true;
      if (submitText) submitText.style.display = 'none';
      if (submitLoad) submitLoad.style.display = 'inline-flex';

      const data = new FormData(form);

      fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: data,
      })
        .then(function (res) { return res.json(); })
        .then(function (json) {
          if (json.status === 'ok') {
            // Success — hide form fields, show success message
            form.querySelectorAll('.vp-form__row, .vp-form__field, .vp-form__submit')
                .forEach(function (el) { el.style.display = 'none'; });
            if (successBox) successBox.style.display = 'flex';
          } else {
            // Validation errors
            resetSubmitBtn();
            if (json.errors) {
              Object.keys(json.errors).forEach(function (field) {
                const input = form.querySelector('[name="' + field + '"]');
                if (input) {
                  let errorEl = input.parentElement.querySelector('.vp-form__error');
                  if (!errorEl) {
                    errorEl = document.createElement('div');
                    errorEl.className = 'vp-form__error';
                    input.parentElement.appendChild(errorEl);
                  }
                  errorEl.textContent = json.errors[field][0].message || json.errors[field][0];
                }
              });
            }
          }
        })
        .catch(function () {
          resetSubmitBtn();
          alert('Something went wrong. Please try again or contact us on WhatsApp.');
        });

      function resetSubmitBtn() {
        submitBtn.disabled = false;
        if (submitText) submitText.style.display = '';
        if (submitLoad) submitLoad.style.display = 'none';
      }
    });
  });


  // ── Mobile filter drawer (product list page) ─────────────────────────────
  const toggleBtn  = document.getElementById('vpFiltersToggle');
  const closeBtn   = document.getElementById('vpFiltersClose');
  const filtersEl  = document.getElementById('vpFilters');

  if (toggleBtn && filtersEl) {
    let overlay = null;

    function openFilters() {
      filtersEl.classList.add('open');
      // Create backdrop overlay
      overlay = document.createElement('div');
      overlay.style.cssText =
        'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9998;' +
        'backdrop-filter:blur(3px);animation:fadeIn 0.3s ease';
      overlay.addEventListener('click', closeFilters);
      document.body.appendChild(overlay);
      document.body.style.overflow = 'hidden';
    }

    function closeFilters() {
      filtersEl.classList.remove('open');
      if (overlay) { overlay.remove(); overlay = null; }
      document.body.style.overflow = '';
    }

    toggleBtn.addEventListener('click', openFilters);
    if (closeBtn) closeBtn.addEventListener('click', closeFilters);

    // Auto-submit filter form on radio change (desktop UX enhancement)
    const filterForm = document.getElementById('vpFilterForm');
    if (filterForm) {
      filterForm.querySelectorAll('input[type="radio"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
          // Only auto-submit on desktop (drawer closed)
          if (window.innerWidth > 768) filterForm.submit();
        });
      });
    }
  }


  // ── Smooth scroll for anchor links (enquire button, etc.) ───────────────
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        const offset = parseInt(getComputedStyle(document.documentElement)
                               .getPropertyValue('--nav-height') || '80', 10) + 20;
        const top = target.getBoundingClientRect().top + window.scrollY - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });


  // ── Radio button visual sync (vp-radio--active class) ───────────────────
  document.querySelectorAll('.vp-radio input[type="radio"]').forEach(function (radio) {
    // Set initial active state from checked
    if (radio.checked) radio.closest('.vp-radio').classList.add('vp-radio--active');

    radio.addEventListener('change', function () {
      // Remove active from all in the same group
      document.querySelectorAll('.vp-radio input[name="' + this.name + '"]')
              .forEach(function (r) {
                r.closest('.vp-radio').classList.remove('vp-radio--active');
              });
      // Add to this one
      if (this.checked) this.closest('.vp-radio').classList.add('vp-radio--active');
    });
  });

})();