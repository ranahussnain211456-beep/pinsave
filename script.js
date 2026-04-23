/* =========================================================
   PinSave – script.js
   All interactive functionality for the Pinterest Downloader
   ========================================================= */

/* ── DARK / LIGHT MODE ── */
(function initTheme() {
  const saved = localStorage.getItem('pinsave-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
})();

function updateThemeIcon(theme) {
  const icon = document.getElementById('themeIcon');
  if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
}

const themeToggle = document.getElementById('themeToggle');
if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('pinsave-theme', next);
    updateThemeIcon(next);
  });
}

/* ── MOBILE NAV TOGGLE ── */
const navToggle = document.getElementById('navToggle');
const navLinks  = document.getElementById('navLinks');

if (navToggle && navLinks) {
  navToggle.addEventListener('click', () => {
    navLinks.classList.toggle('open');
    const isOpen = navLinks.classList.contains('open');
    navToggle.setAttribute('aria-expanded', isOpen);
    const spans = navToggle.querySelectorAll('span');
    if (isOpen) {
      spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
      spans[1].style.opacity   = '0';
      spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
    } else {
      spans[0].style.transform = '';
      spans[1].style.opacity   = '';
      spans[2].style.transform = '';
    }
  });

  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      const spans = navToggle.querySelectorAll('span');
      spans[0].style.transform = '';
      spans[1].style.opacity   = '';
      spans[2].style.transform = '';
    });
  });
}

/* ── BACKEND URL ─────────────────────────────────────────────────────────────
   If you run server.py locally, keep this as http://localhost:5000
   If you deploy to a server, change it to your server's URL.
   ────────────────────────────────────────────────────────────────────────── */
const API_BASE = 'http://localhost:5000';

/* ── URL VALIDATION ── */
function isPinterestUrl(url) {
  try {
    const u = new URL(url.trim());
    return (
      u.hostname.includes('pinterest.') ||
      u.hostname.includes('pin.it') ||
      u.hostname.includes('klickpin.com')
    );
  } catch {
    return false;
  }
}

/* ── UI STATE MANAGER ── */
function setDownloaderState(state, data) {
  const progressWrap = document.getElementById('progressWrap');
  const resultBox    = document.getElementById('resultBox');
  const errorBox     = document.getElementById('errorBox');
  const downloadBtn  = document.getElementById('downloadBtn');

  // Reset all sections
  if (progressWrap) progressWrap.style.display = 'none';
  if (resultBox)    resultBox.style.display    = 'none';
  if (errorBox)     errorBox.style.display     = 'none';

  if (downloadBtn) {
    downloadBtn.disabled = false;
    const btnText = downloadBtn.querySelector('.btn-text');
    if (btnText) btnText.textContent = 'Download';
  }

  // Loading state
  if (state === 'loading') {
    if (progressWrap) progressWrap.style.display = 'flex';
    if (downloadBtn) {
      downloadBtn.disabled = true;
      const btnText = downloadBtn.querySelector('.btn-text');
      if (btnText) btnText.textContent = 'Processing…';
    }
  }

  // ✅ Success state — show real download link
  if (state === 'success' && data) {
    if (resultBox) {
      resultBox.style.display = 'block';
      const saveBtn = document.getElementById('saveBtn');
      if (saveBtn) {
        saveBtn.href     = data.videoUrl;
        saveBtn.target   = '_blank';
        saveBtn.rel      = 'noopener noreferrer';
        saveBtn.download = data.filename || 'pinterest-video.mp4';
      }
    }
  }

  // ❌ Error state
  if (state === 'error' && data) {
    if (errorBox) {
      errorBox.style.display = 'block';
      const errMsg = document.getElementById('errorMsg');
      if (errMsg) errMsg.textContent = data.message || 'Something went wrong. Please try again.';
    }
  }
}

/* ── PROGRESS MESSAGE ANIMATION ── */
function runProgressMessages() {
  const messages = [
    'Opening page…',
    'Bypassing bot detection…',
    'Extracting video URL…',
    'Almost done…',
  ];
  let idx = 0;
  const progressText = document.getElementById('progressText');
  if (!progressText) return null;

  progressText.textContent = messages[0];
  return setInterval(() => {
    idx = (idx + 1) % messages.length;
    progressText.textContent = messages[idx];
  }, 1000);
}

/* ── MAIN DOWNLOAD FUNCTION ─────────────────────────────────────────────────
   Calls your local Flask server (server.py) which uses Playwright
   to scrape Pinterest and extract the real video URL.
   ────────────────────────────────────────────────────────────────────────── */
async function fetchPinterestVideo(url) {
  try {
    const apiUrl  = `${API_BASE}/api/download?url=${encodeURIComponent(url)}`;
    const res     = await fetch(apiUrl);
    const data    = await res.json();

    if (data.success && data.videoUrl) {
      return {
        ok:       true,
        videoUrl: data.videoUrl,
        filename: data.filename || 'pinterest-video.mp4',
        quality:  data.quality  || 'HD',
      };
    }

    return {
      ok:      false,
      message: data.error || 'No video found on this page.',
    };

  } catch (err) {
    // Backend not running or network issue
    return {
      ok:      false,
      message: '⚠️ Server not running. Please start server.py first:\n\npython server.py',
    };
  }
}

/* ── DOWNLOAD BUTTON HANDLER ── */
async function handleDownload() {
  const input = document.getElementById('pinterestUrl');
  const url   = input ? input.value.trim() : '';
  const downloadBtn = document.getElementById('downloadBtn');

  // Prevent double-click / duplicate calls
  if (downloadBtn && downloadBtn.disabled) return;

  setDownloaderState('idle');

  // Validate input
  if (!url) {
    setDownloaderState('error', { message: 'Please paste a Pinterest video URL first.' });
    if (input) input.focus();
    return;
  }

  if (!isPinterestUrl(url)) {
    setDownloaderState('error', {
      message: "That doesn't look like a Pinterest URL. Please paste a valid pinterest.com link.",
    });
    return;
  }

  // Show loading + start progress animation
  setDownloaderState('loading');
  const timer = runProgressMessages();

  try {
    const result = await fetchPinterestVideo(url);

    clearInterval(timer);

    if (result.ok) {
      setDownloaderState('success', {
        videoUrl: result.videoUrl,
        filename: result.filename,
      });
    } else {
      setDownloaderState('error', { message: result.message });
    }
  } catch (err) {
    clearInterval(timer);
    setDownloaderState('error', {
      message: 'A network error occurred. Please check your connection and try again.',
    });
  }
}

/* ── KEYBOARD & PASTE SHORTCUTS ── */
const urlInput = document.getElementById('pinterestUrl');
if (urlInput) {
  // Enter key triggers download
  urlInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') handleDownload();
  });

  // Paste event — just clear any previous error, don't auto-download
  urlInput.addEventListener('paste', function () {
    setTimeout(() => {
      setDownloaderState('idle');
    }, 120);
  });
}

/* ── FAQ ACCORDION ── */
function toggleFaq(btn) {
  const item   = btn.closest('.faq-item');
  const answer = item.querySelector('.faq-answer');
  const isOpen = item.classList.contains('open');

  document.querySelectorAll('.faq-item.open').forEach(el => {
    el.classList.remove('open');
    el.querySelector('.faq-answer').classList.remove('open');
  });

  if (!isOpen) {
    item.classList.add('open');
    answer.classList.add('open');
  }
}

/* ── DEVICE GUIDE TABS ── */
function switchTab(btn, id) {
  document.querySelectorAll('.device-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.device-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  const target = document.getElementById(id);
  if (target) target.classList.add('active');
}

/* ── LEGAL PAGE TABS ── */
(function initLegalTabs() {
  const tabs = document.querySelectorAll('.legal-tab');
  if (!tabs.length) return;
  tabs.forEach(tab => {
    tab.addEventListener('click', function () {
      tabs.forEach(t => t.classList.remove('active'));
      this.classList.add('active');
    });
  });
})();

/* ── CONTACT FORM ── */
function submitContactForm() {
  const name    = document.getElementById('name');
  const email   = document.getElementById('email');
  const subject = document.getElementById('subject');
  const message = document.getElementById('message');

  if (!name || !name.value.trim())          { flashField(name,    'Please enter your name.');           return; }
  if (!email || !isValidEmail(email.value)) { flashField(email,   'Please enter a valid email.');       return; }
  if (!subject || !subject.value)           { flashField(subject, 'Please select a topic.');            return; }
  if (!message || message.value.trim().length < 10) { flashField(message, 'Please write at least 10 characters.'); return; }

  const btn = document.querySelector('.contact-form .btn-download');
  if (btn) {
    btn.disabled = true;
    const t = btn.querySelector('.btn-text');
    if (t) t.textContent = 'Sending…';
  }

  setTimeout(() => {
    const form    = document.getElementById('contactForm');
    const success = document.getElementById('formSuccess');
    if (form)    form.style.display    = 'none';
    if (success) success.style.display = 'block';
  }, 1400);
}

function resetContactForm() {
  const form    = document.getElementById('contactForm');
  const success = document.getElementById('formSuccess');
  if (form && success) {
    form.querySelectorAll('input, select, textarea').forEach(el => el.value = '');
    const btn = form.querySelector('.btn-download');
    if (btn) {
      btn.disabled = false;
      const t = btn.querySelector('.btn-text');
      if (t) t.textContent = 'Send Message';
    }
    success.style.display = 'none';
    form.style.display    = 'flex';
  }
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function flashField(el, msg) {
  if (!el) return;
  el.style.borderColor = 'var(--red)';
  el.style.boxShadow   = '0 0 0 4px rgba(230,0,35,0.15)';
  el.focus();
  el.setAttribute('placeholder', msg);
  setTimeout(() => {
    el.style.borderColor = '';
    el.style.boxShadow   = '';
  }, 2500);
}

/* ── SMOOTH SCROLL ── */
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', function (e) {
    const id     = this.getAttribute('href').slice(1);
    const target = document.getElementById(id);
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

/* ── SCROLL REVEAL ── */
(function initScrollReveal() {
  const els = document.querySelectorAll(
    '.feature-card, .step-item, .guide-step-card, .faq-item, .contact-card'
  );
  if (!('IntersectionObserver' in window)) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity   = '1';
        entry.target.style.transform = 'translateY(0)';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  els.forEach((el, i) => {
    el.style.opacity    = '0';
    el.style.transform  = 'translateY(20px)';
    el.style.transition = `opacity 0.5s ease ${i * 0.06}s, transform 0.5s ease ${i * 0.06}s`;
    observer.observe(el);
  });
})();
