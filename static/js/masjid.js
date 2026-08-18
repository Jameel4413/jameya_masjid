/**
 * Masjid Hisab — UI Enhancements & Lightning Fast SPA Engine
 */
(function () {
    'use strict';

    /* ---- Sidebar (mobile) ---- */
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileMenuMoreBtn = document.getElementById('mobileMenuMoreBtn');
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

    function toggleSidebar() {
        if (sidebar?.classList.contains('active')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    }

    sidebarToggle?.addEventListener('click', toggleSidebar);
    mobileMenuMoreBtn?.addEventListener('click', toggleSidebar);

    sidebarOverlay?.addEventListener('click', closeSidebar);

    /* ---- Auto-dismiss alerts ---- */
    function initAlerts() {
        document.querySelectorAll('.alert-pro[data-auto-dismiss]').forEach((alert) => {
            if (alert.dataset.dismissInit) return;
            alert.dataset.dismissInit = 'true';
            setTimeout(() => {
                alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-8px)';
                setTimeout(() => alert.remove(), 400);
            }, 4500);
        });
    }

    initAlerts();

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

    /* Global Bootstrap Modal events — hide mobile bottom nav & re-init Choices */
    document.addEventListener('show.bs.modal', function () {
        const nav = document.querySelector('.mobile-bottom-nav');
        if (nav) {
            nav.style.setProperty('display', 'none', 'important');
            nav.style.setProperty('visibility', 'hidden', 'important');
        }
    }, true);

    document.addEventListener('hidden.bs.modal', function () {
        const nav = document.querySelector('.mobile-bottom-nav');
        if (nav && !document.querySelector('.modal.show')) {
            nav.style.removeProperty('display');
            nav.style.removeProperty('visibility');
        }
    }, true);

    document.addEventListener('shown.bs.modal', function (e) {
        const modal = e.target;
        if (modal && modal.querySelectorAll) {
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
        }
    }, true);

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
    function initFormLoading() {
        document.querySelectorAll('form[data-loading]').forEach((form) => {
            if (form.dataset.loadingAttached) return;
            form.dataset.loadingAttached = 'true';
            form.addEventListener('submit', function () {
                const btn = form.querySelector('[type="submit"]');
                if (btn && !btn.disabled) {
                    btn.disabled = true;
                    const original = btn.innerHTML;
                    btn.dataset.originalHtml = original;
                    btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin me-1"></i> Processing...`;
                }
            });
        });
    }

    initFormLoading();

    /* ---- Urdu Phonetic Keyboard Handler ---- */
    const urduPhoneticMap = {
        'a': 'ا', 'A': 'آ',
        'b': 'ب', 'B': 'ب',
        'c': 'چ', 'C': 'ث',
        'd': 'د', 'D': 'ڈ',
        'e': 'ع', 'E': 'ء',
        'f': 'ف', 'F': 'ف',
        'g': 'گ', 'G': 'غ',
        'h': 'ح', 'H': 'ھ',
        'i': 'ی', 'I': 'ٰ',
        'j': 'ج', 'J': 'ض',
        'k': 'ک', 'K': 'خ',
        'l': 'ل', 'L': 'ل',
        'm': 'م', 'M': 'ں',
        'n': 'ن', 'N': 'ں',
        'o': 'ہ', 'O': 'ۃ',
        'p': 'پ', 'P': 'ُ',
        'q': 'ق', 'Q': 'ٹ',
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
            if (input.dataset.urduInit) return;
            input.dataset.urduInit = 'true';
            input.addEventListener('keypress', function(e) {
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

    document.addEventListener('DOMContentLoaded', enableUrduKeyboard);

    /* =========================================================
     * LIGHTNING FAST NATIVE SPA NAVIGATION ENGINE
     * ========================================================= */
    function getProgressBar() {
        let bar = document.getElementById('spa-top-progress');
        if (!bar) {
            bar = document.createElement('div');
            bar.id = 'spa-top-progress';
            document.body.appendChild(bar);
        }
        return bar;
    }

    let progressTimer = null;
    function startProgressBar() {
        const bar = getProgressBar();
        bar.style.transition = 'width 0.15s ease, opacity 0.15s ease';
        bar.style.opacity = '1';
        bar.style.width = '20%';

        clearInterval(progressTimer);
        progressTimer = setInterval(() => {
            const currentWidth = parseFloat(bar.style.width) || 20;
            if (currentWidth < 88) {
                bar.style.width = (currentWidth + Math.random() * 12) + '%';
            }
        }, 120);
    }

    function finishProgressBar() {
        clearInterval(progressTimer);
        const bar = getProgressBar();
        bar.style.width = '100%';
        setTimeout(() => {
            bar.style.opacity = '0';
            setTimeout(() => {
                bar.style.width = '0%';
            }, 200);
        }, 120);
    }

    function updateActiveLinks(pathname) {
        document.querySelectorAll('.mobile-bottom-nav-link, .nav-link-custom, .dropdown-item-pro').forEach((link) => {
            const href = link.getAttribute('href');
            if (href && !href.startsWith('javascript') && !href.startsWith('#')) {
                try {
                    const linkPath = new URL(href, window.location.origin).pathname;
                    if (linkPath === pathname) {
                        link.classList.add('active');
                    } else {
                        link.classList.remove('active');
                    }
                } catch (e) {}
            }
        });
    }

    function reexecuteScripts(container) {
        container.querySelectorAll('script').forEach((oldScript) => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach((attr) => newScript.setAttribute(attr.name, attr.value));
            newScript.textContent = oldScript.textContent;
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    function reinitUIComponents() {
        initChoices();
        initAlerts();
        initFormLoading();
        enableUrduKeyboard();
        closeSidebar();
    }

    window.reinitPageUI = reinitUIComponents;

    function loadPageSPA(url, pushState) {
        startProgressBar();

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then((res) => {
            if (!res.ok) throw new Error('Network response not ok');
            return res.text();
        })
        .then((html) => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const newContentArea = doc.querySelector('.content-area');
            const currentContentArea = document.querySelector('.content-area');

            if (newContentArea && currentContentArea) {
                currentContentArea.innerHTML = newContentArea.innerHTML;
                document.title = doc.title;

                if (pushState) {
                    window.history.pushState({ url: url }, doc.title, url);
                }

                updateActiveLinks(new URL(url, window.location.origin).pathname);
                reexecuteScripts(currentContentArea);
                reinitUIComponents();
                window.scrollTo({ top: 0, behavior: 'instant' });
            } else {
                window.location.href = url;
            }
            finishProgressBar();
        })
        .catch((err) => {
            console.warn('SPA Navigation fallback:', err);
            finishProgressBar();
            window.location.href = url;
        });
    }

    /* Intercept click on navigation links */
    document.addEventListener('click', function (e) {
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href || href === 'javascript:void(0)' || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:') || link.getAttribute('target') === '_blank' || link.hasAttribute('data-no-spa')) {
            return;
        }

        if (href.includes('export_pdf') || href.includes('logout') || href.includes('admin')) {
            return;
        }

        try {
            const targetUrl = new URL(href, window.location.origin);
            if (targetUrl.origin !== window.location.origin) return;

            e.preventDefault();
            loadPageSPA(targetUrl.href, true);
        } catch (err) {}
    });

    /* Handle browser back and forward buttons */
    window.addEventListener('popstate', function (e) {
        if (e.state && e.state.url) {
            loadPageSPA(e.state.url, false);
        } else {
            window.location.reload();
        }
    });

    /* Touch / Hover Prefetching for instant response */
    const prefetchUrl = (url) => {
        if (!url || url === 'javascript:void(0)' || url.startsWith('#')) return;
        if (!document.querySelector(`link[rel="prefetch"][href="${url}"]`)) {
            const link = document.createElement('link');
            link.rel = 'prefetch';
            link.href = url;
            document.head.appendChild(link);
        }
    };

    document.addEventListener('touchstart', function(e) {
        const link = e.target.closest('a');
        if (link) {
            const href = link.getAttribute('href');
            if (href && !href.startsWith('javascript') && !href.startsWith('#')) {
                prefetchUrl(href);
            }
        }
    }, { passive: true });

})();
