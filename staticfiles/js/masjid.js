/**
 * Masjid Hisab — UI Enhancements
 */
(function () {
    'use strict';

    /* ---- Sidebar (mobile) ---- */
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    function closeSidebar() {
        sidebar?.classList.remove('active');
        sidebarOverlay?.classList.remove('active');
        document.body.style.overflow = '';
    }

    function openSidebar() {
        sidebar?.classList.add('active');
        sidebarOverlay?.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    sidebarToggle?.addEventListener('click', () => {
        if (sidebar?.classList.contains('active')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    sidebarOverlay?.addEventListener('click', closeSidebar);

    /* ---- Auto-dismiss alerts ---- */
    document.querySelectorAll('.alert-pro[data-auto-dismiss]').forEach((alert) => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-8px)';
            setTimeout(() => alert.remove(), 400);
        }, 4500);
    });

    /* ---- Choices.js — beautiful dropdowns ---- */
    function initChoices() {
        if (typeof Choices === 'undefined') return;

        document.querySelectorAll('select.form-select-pro, select.form-select-enhanced').forEach((el) => {
            if (el.dataset.choicesInit === 'true') return;

            const isInModal = el.closest('.modal');
            new Choices(el, {
                searchEnabled: el.options.length > 8,
                itemSelectText: '',
                shouldSort: false,
                position: isInModal ? 'bottom' : 'auto',
                classNames: {
                    containerOuter: 'choices',
                },
            });
            el.dataset.choicesInit = 'true';
        });
    }

    initChoices();

    /* Re-init Choices when modals open (hidden selects need fresh init) */
    document.querySelectorAll('.modal').forEach((modal) => {
        modal.addEventListener('shown.bs.modal', () => {
            modal.querySelectorAll('select.form-select-pro:not([data-choices-init="true"])').forEach((el) => {
                if (typeof Choices !== 'undefined') {
                    new Choices(el, {
                        searchEnabled: false,
                        itemSelectText: '',
                        shouldSort: false,
                    });
                    el.dataset.choicesInit = 'true';
                }
            });
        });
    });

    /* ---- Payment type toggles (Imam Salary) ---- */
    window.toggleAmountField = function (selectElem, salaryId) {
        const amountDiv = document.getElementById('amountInputDiv' + salaryId);
        const amountInput = amountDiv?.querySelector('input[name="amount_paid"]');
        if (!amountDiv) return;

        if (selectElem.value === 'full') {
            amountDiv.style.display = 'none';
            if (amountInput) amountInput.removeAttribute('required');
        } else {
            amountDiv.style.display = 'block';
            if (amountInput) amountInput.setAttribute('required', 'required');
        }
    };

    window.toggleCreateAmountField = function (selectElem) {
        const amountDiv = document.getElementById('createAmountInputDiv');
        const amountInput = amountDiv?.querySelector('input[name="initial_amount_paid"]');
        if (!amountDiv) return;

        if (selectElem.value === 'installment') {
            amountDiv.style.display = 'block';
            if (amountInput) amountInput.setAttribute('required', 'required');
        } else {
            amountDiv.style.display = 'none';
            if (amountInput) amountInput.removeAttribute('required');
        }
    };

    /* ---- Form submit loading state ---- */
    document.querySelectorAll('form[data-loading]').forEach((form) => {
        form.addEventListener('submit', function () {
            const btn = form.querySelector('[type="submit"]');
            if (btn && !btn.disabled) {
                btn.disabled = true;
                const original = btn.innerHTML;
                btn.dataset.originalHtml = original;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
            }
        });
    });

    /* ---- Number input — prevent negative where min=0 ---- */
    document.querySelectorAll('input[type="number"][min="0"]').forEach((input) => {
        input.addEventListener('keydown', (e) => {
            if (e.key === '-' || e.key === 'e') e.preventDefault();
        });
    });

    /* ---- Sync PDF Export Modal with active URL filters ---- */
    const exportPdfModal = document.getElementById('exportPdfModal');
    if (exportPdfModal) {
        exportPdfModal.addEventListener('show.bs.modal', () => {
            const urlParams = new URLSearchParams(window.location.search);
            const year = urlParams.get('year');
            const month = urlParams.get('month');

            const yearSelect = document.getElementById('pdfExportYear');
            const monthSelect = document.getElementById('pdfExportMonth');

            if (yearSelect && year) {
                yearSelect.value = year;
            }
            if (monthSelect) {
                if (month) {
                    monthSelect.value = month;
                } else if (urlParams.has('month') && month === '') {
                    monthSelect.value = 'all';
                }
            }
        });
    }

    const exportImamPdfModal = document.getElementById('exportImamPdfModal');
    if (exportImamPdfModal) {
        exportImamPdfModal.addEventListener('show.bs.modal', () => {
            const urlParams = new URLSearchParams(window.location.search);
            const year = urlParams.get('year');
            const month = urlParams.get('month');

            const yearSelect = document.getElementById('imamPdfExportYear');
            const monthSelect = document.getElementById('imamPdfExportMonth');

            if (yearSelect && year) {
                yearSelect.value = year;
            }
            if (monthSelect) {
                if (month) {
                    monthSelect.value = month;
                } else if (urlParams.has('month') && month === '') {
                    monthSelect.value = 'all';
                }
            }
        });
    }

    /* ---- Roman Urdu to Urdu Phonetic Keyboard ---- */
    const urduPhoneticMap = {
        'a': 'ا', 'A': 'آ',
        'b': 'ب', 'B': 'ب',
        'c': 'چ', 'C': 'ث',
        'd': 'د', 'D': 'ڈ',
        'e': 'ع', 'E': 'ع',
        'f': 'ف', 'F': 'ف',
        'g': 'گ', 'G': 'غ',
        'h': 'ہ', 'H': 'ح',
        'i': 'ی', 'I': 'ی',
        'j': 'ج', 'J': 'ض',
        'k': 'ک', 'K': 'خ',
        'l': 'ل', 'L': 'ل',
        'm': 'م', 'M': 'م',
        'n': 'ن', 'N': 'ں',
        'o': 'و', 'O': 'و',
        'p': 'پ', 'P': 'پ',
        'q': 'ق', 'Q': 'ق',
        'r': 'ر', 'R': 'ڑ',
        's': 'س', 'S': 'ص',
        't': 'ت', 'T': 'ٹ',
        'u': 'ئ', 'U': 'ء',
        'v': 'ط', 'V': 'ظ',
        'w': 'و', 'W': 'و',
        'x': 'ش', 'X': 'ژ',
        'y': 'ے', 'Y': 'ے',
        'z': 'ز', 'Z': 'ذ',
        ',': '،', '.': '۔', '?': '؟'
    };

    function enableUrduKeyboard() {
        if (typeof CURRENT_LANG === 'undefined' || CURRENT_LANG !== 'ur') {
            return;
        }

        document.querySelectorAll('input[type="text"], textarea').forEach(input => {
            input.addEventListener('keypress', function(e) {
                // If ctrl or alt is pressed, ignore
                if (e.ctrlKey || e.altKey) return;
                
                const char = e.key;
                if (urduPhoneticMap.hasOwnProperty(char)) {
                    e.preventDefault();
                    
                    const urduChar = urduPhoneticMap[char];
                    const start = this.selectionStart;
                    const end = this.selectionEnd;
                    
                    const text = this.value;
                    this.value = text.substring(0, start) + urduChar + text.substring(end);
                    
                    this.selectionStart = this.selectionEnd = start + 1;
                }
            });
        });
    }

    // Initialize Urdu keyboard if language is Urdu
    document.addEventListener('DOMContentLoaded', enableUrduKeyboard);

})();
