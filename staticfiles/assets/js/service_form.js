/**
 * Service Request Form - Interaction Logic
 * Author: Nestova Design Team
 */

document.addEventListener('DOMContentLoaded', function () {
    // Elements
    const form = document.getElementById('wizard-form');
    const formSteps = document.querySelectorAll('.form-step');
    const progressSteps = document.querySelectorAll('.progress-step');
    const progressBg = document.querySelector('.progress-bg');
    const btnNext = document.querySelector('.btn-next');
    const btnPrev = document.querySelector('.btn-prev');
    const fileInput = document.getElementById('id_reference_images');
    const fileUploadWrapper = document.querySelector('.file-upload-wrapper');
    const fileUploadContent = document.querySelector('.file-upload-content');
    const filePreview = document.querySelector('.file-preview');

    let currentStep = 0;

    // Initialize
    updateFormSteps();
    updateProgress();

    // Event Listeners
    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (validateStep(currentStep)) {
                currentStep++;
                if (currentStep >= formSteps.length) {
                    submitForm();
                } else {
                    updateFormSteps();
                    updateProgress();
                }
            }
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            currentStep--;
            if (currentStep < 0) currentStep = 0;
            updateFormSteps();
            updateProgress();
        });
    }

    // File Upload Drag & Drop
    if (fileUploadWrapper && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            fileUploadWrapper.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            fileUploadWrapper.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            fileUploadWrapper.addEventListener(eventName, unhighlight, false);
        });

        function highlight() {
            fileUploadWrapper.classList.add('dragover');
        }

        function unhighlight() {
            fileUploadWrapper.classList.remove('dragover');
        }

        fileUploadWrapper.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }

        fileInput.addEventListener('change', function () {
            handleFiles(this.files);
        });
    }

    function handleFiles(files) {
        if (!files.length) return;

        // Update input files if drag-dropped (optional/tricky for security)
        // Here we just preview

        filePreview.innerHTML = '';
        if (files.length > 0) {
            fileUploadContent.style.display = 'none';
        } else {
            fileUploadContent.style.display = 'block';
        }

        Array.from(files).forEach(file => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = document.createElement('div');
                    img.className = 'preview-item';
                    img.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
                    filePreview.appendChild(img);
                };
                reader.readAsDataURL(file);
            } else {
                // For non-images
                const item = document.createElement('div');
                item.className = 'preview-item p-2 bg-light d-flex align-items-center justify-content-center text-center';
                item.innerHTML = `<small>${file.name.substring(0, 8)}...</small>`;
                filePreview.appendChild(item);
            }
        });
    }

    // Functions
    function updateFormSteps() {
        formSteps.forEach((step, index) => {
            if (index === currentStep) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        });

        // Update buttons
        if (currentStep === 0) {
            btnPrev.style.display = 'none';
            btnNext.innerHTML = 'Next Step <i class="bi bi-arrow-right"></i>';
        } else if (currentStep === formSteps.length - 1) {
            btnPrev.style.display = 'inline-flex';
            btnNext.innerHTML = 'Submit Request <i class="bi bi-send"></i>';
        } else {
            btnPrev.style.display = 'inline-flex';
            btnNext.innerHTML = 'Next Step <i class="bi bi-arrow-right"></i>';
        }

        // Smooth scroll to top of form
        if (currentStep > 0) {
            const formHeader = document.querySelector('.form-header');
            if (formHeader) {
                formHeader.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }

    function updateProgress() {
        progressSteps.forEach((step, index) => {
            if (index < currentStep + 1) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }

            if (index < currentStep) {
                step.classList.add('completed');
                step.innerHTML = '<i class="bi bi-check-lg"></i>';
            } else {
                step.classList.remove('completed');
                step.innerHTML = index + 1;
            }
        });

        const progressPercent = ((currentStep) / (progressSteps.length - 1)) * 100;
        progressBg.style.width = `${progressPercent}%`;
    }

    function validateStep(stepIndex) {
        // Simple validation for required fields in current step
        const currentStepEl = formSteps[stepIndex];
        const inputs = currentStepEl.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;

        inputs.forEach(input => {
            if (!input.value.trim()) {
                isValid = false;
                input.classList.add('is-invalid');

                // Add shake animation
                input.parentElement.animate([
                    { transform: 'translateX(0)' },
                    { transform: 'translateX(-10px)' },
                    { transform: 'translateX(10px)' },
                    { transform: 'translateX(0)' }
                ], {
                    duration: 300,
                    iterations: 1
                });

                // Remove invalid class on input
                input.addEventListener('input', () => {
                    input.classList.remove('is-invalid');
                }, { once: true });
            } else {
                input.classList.remove('is-invalid');
            }
        });

        return isValid;
    }

    function submitForm() {
        // Show loading state
        btnNext.disabled = true;
        btnNext.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sending...';

        // Submit the form
        form.submit();
    }
});
