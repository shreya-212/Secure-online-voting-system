/**
 * ═══════════════════════════════════════════════════════════
 * TranslateEngine — Multi-language support for SecureVote
 * TWO-PHASE TRANSLATION:
 *   1. data-i18n tagged elements (explicit)
 *   2. Auto-scan: matches visible text against English dictionary values
 * Persists language choice in localStorage
 * Integrates with VoiceEngine for speech language
 * ═══════════════════════════════════════════════════════════
 */

const TranslateEngine = (() => {
    const STORAGE_KEY = 'securevote_language';
    let currentLang = 'en';
    let selectorEl = null;
    let reverseMap = null; // English text → translation key

    // ═══════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════

    function init() {
        currentLang = localStorage.getItem(STORAGE_KEY) || 'en';
        console.log('[TranslateEngine] Init, language:', currentLang);

        // Build reverse lookup: english text → key
        buildReverseMap();

        // Build language selector UI
        buildSelector();

        // Apply translations
        applyTranslations();

        // Observe DOM changes to translate dynamically inserted content
        observeDOM();
    }

    // Build reverse map: lowercase English text → translation key
    function buildReverseMap() {
        reverseMap = new Map();
        for (const [key, langs] of Object.entries(TRANSLATIONS)) {
            if (key.startsWith('_')) continue; // Skip meta keys
            const enText = langs.en;
            if (enText) {
                reverseMap.set(enText.toLowerCase().trim(), key);
            }
        }
        console.log('[TranslateEngine] Reverse map built:', reverseMap.size, 'entries');
    }

    // ═══════════════════════════════════════════
    // LANGUAGE SELECTOR UI
    // ═══════════════════════════════════════════

    function buildSelector() {
        selectorEl = document.createElement('div');
        selectorEl.className = 'lang-selector';
        selectorEl.innerHTML = `
            <button class="lang-btn" id="lang-toggle" title="Change Language">
                <span class="lang-icon">🌐</span>
                <span class="lang-current" id="lang-current-label">${TRANSLATIONS._languages[currentLang]?.native || 'English'}</span>
                <span class="lang-arrow">▾</span>
            </button>
            <div class="lang-dropdown" id="lang-dropdown">
                ${Object.entries(TRANSLATIONS._languages).map(([code, lang]) => `
                    <button class="lang-option ${code === currentLang ? 'active' : ''}" data-lang="${code}">
                        <span class="lang-option-flag">${lang.flag}</span>
                        <span class="lang-option-native">${lang.native}</span>
                        <span class="lang-option-name">${lang.name}</span>
                        ${code === currentLang ? '<span class="lang-check">✓</span>' : ''}
                    </button>
                `).join('')}
            </div>
        `;
        document.body.appendChild(selectorEl);

        // Toggle dropdown
        const toggleBtn = selectorEl.querySelector('#lang-toggle');
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            selectorEl.classList.toggle('open');
        });

        // Language option clicks
        selectorEl.querySelectorAll('.lang-option').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const lang = btn.dataset.lang;
                setLanguage(lang);
                selectorEl.classList.remove('open');
            });
        });

        // Close dropdown on outside click
        document.addEventListener('click', () => {
            selectorEl.classList.remove('open');
        });
    }

    // ═══════════════════════════════════════════
    // TRANSLATION LOGIC
    // ═══════════════════════════════════════════

    function setLanguage(lang) {
        if (!TRANSLATIONS._languages[lang]) return;
        currentLang = lang;
        localStorage.setItem(STORAGE_KEY, lang);
        console.log('[TranslateEngine] Language changed to:', lang);

        applyTranslations();
        updateSelector();

        // Update VoiceEngine language if available
        if (typeof VoiceEngine !== 'undefined' && VoiceEngine.speak) {
            const speechLang = TRANSLATIONS._speechLang[lang] || 'en-US';
            VoiceEngine.speak(TRANSLATIONS._languages[lang].native + '. ' +
                (TRANSLATIONS['app.tagline']?.[lang] || ''), { lang: speechLang });
        }
    }

    function applyTranslations() {
        // Phase 1: Translate all elements with data-i18n attributes
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translation = getTranslation(key);
            if (translation) {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    if (el.hasAttribute('placeholder')) el.placeholder = translation;
                } else {
                    el.textContent = translation;
                }
            }
        });

        // Translate data-i18n-placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            const translation = getTranslation(key);
            if (translation) el.placeholder = translation;
        });

        // Phase 2: Auto-scan DOM for text that matches English dictionary values
        autoTranslateDOM(document.body);

        // Update HTML lang attribute
        document.documentElement.lang = currentLang === 'en' ? 'en' : currentLang;
    }

    // ═══════════════════════════════════════════
    // AUTO-TRANSLATE (DOM SCANNING)
    // ═══════════════════════════════════════════

    const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION']);

    function autoTranslateDOM(root) {
        if (!root) return;

        const walker = document.createTreeWalker(
            root,
            NodeFilter.SHOW_ELEMENT,
            {
                acceptNode: (node) => {
                    // Skip non-visible, script, style, input elements
                    if (SKIP_TAGS.has(node.tagName)) return NodeFilter.FILTER_REJECT;
                    // Skip the language selector itself
                    if (node.classList && (node.classList.contains('lang-selector') ||
                        node.classList.contains('voice-controls') ||
                        node.classList.contains('guide-panel') ||
                        node.classList.contains('voice-transcript') ||
                        node.classList.contains('voice-status') ||
                        node.classList.contains('voice-hint')))
                        return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        let node;
        while (node = walker.nextNode()) {
            // Check direct text content of this element (not children)
            translateElementText(node);
        }
    }

    function translateElementText(el) {
        // Only process elements that have their own text (not nested elements' text)
        const childNodes = el.childNodes;

        for (let i = 0; i < childNodes.length; i++) {
            const child = childNodes[i];
            if (child.nodeType === Node.TEXT_NODE) {
                const originalText = child.textContent.trim();
                if (!originalText || originalText.length < 2) continue;

                // Try to find a translation for this text
                const translated = findTranslation(originalText);
                if (translated && translated !== originalText) {
                    // Preserve leading/trailing whitespace
                    const leadingSpace = child.textContent.match(/^\s*/)[0];
                    const trailingSpace = child.textContent.match(/\s*$/)[0];
                    child.textContent = leadingSpace + translated + trailingSpace;
                }
            }
        }

        // Also translate placeholder attributes
        if (el.hasAttribute && el.hasAttribute('placeholder')) {
            const ph = el.getAttribute('placeholder').trim();
            const translated = findTranslation(ph);
            if (translated && translated !== ph) {
                el.placeholder = translated;
            }
        }

        // Translate title attributes
        if (el.hasAttribute && el.hasAttribute('title')) {
            const ti = el.getAttribute('title').trim();
            const translated = findTranslation(ti);
            if (translated && translated !== ti) {
                el.title = translated;
            }
        }
    }

    function findTranslation(text) {
        if (!text) return null;
        const normalized = text.toLowerCase().trim();

        // Direct match
        const key = reverseMap.get(normalized);
        if (key) {
            return TRANSLATIONS[key]?.[currentLang] || text;
        }

        // Try without emojis (some text has emoji prefixes like "📷 Capture & Register Face")
        const noEmoji = normalized.replace(/[\u{1F000}-\u{1FFFF}]|[\u{2600}-\u{27BF}]|[\u{FE00}-\u{FE0F}]|[\u{1F900}-\u{1F9FF}]|[➕👤👥📋📊📷✓✅⚠️🗳️🔔🏆🏛️🏢🏘️📝🎤🎙️❓]/gu, '').trim();
        if (noEmoji !== normalized) {
            const key2 = reverseMap.get(noEmoji);
            if (key2) {
                // Keep the original emoji prefix
                const emojiPrefix = text.match(/^[\s\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F900}-\u{1F9FF}➕👤👥📋📊📷✓✅⚠️🗳️🔔🏆🏛️🏢🏘️📝🎤🎙️❓\s]*/u)?.[0] || '';
                const translated = TRANSLATIONS[key2]?.[currentLang] || text;
                // If the translation already has emoji, return as-is
                if (/[\u{1F000}-\u{1FFFF}]/u.test(translated)) return translated;
                return emojiPrefix + translated;
            }
        }

        return null;
    }

    // ═══════════════════════════════════════════
    // DOM OBSERVER (for dynamically loaded content)
    // ═══════════════════════════════════════════

    function observeDOM() {
        const observer = new MutationObserver((mutations) => {
            if (currentLang === 'en') return; // No need to translate English

            let needsTranslation = false;
            for (const mutation of mutations) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    for (const node of mutation.addedNodes) {
                        if (node.nodeType === Node.ELEMENT_NODE &&
                            !SKIP_TAGS.has(node.tagName) &&
                            !node.classList?.contains('lang-selector') &&
                            !node.classList?.contains('lang-dropdown')) {
                            autoTranslateDOM(node);
                        }
                    }
                }
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    function getTranslation(key) {
        const entry = TRANSLATIONS[key];
        if (!entry) return null;
        return entry[currentLang] || entry['en'] || null;
    }

    function updateSelector() {
        const label = selectorEl.querySelector('#lang-current-label');
        if (label) label.textContent = TRANSLATIONS._languages[currentLang]?.native || 'English';

        selectorEl.querySelectorAll('.lang-option').forEach(btn => {
            const isActive = btn.dataset.lang === currentLang;
            btn.classList.toggle('active', isActive);
            const check = btn.querySelector('.lang-check');
            if (isActive && !check) {
                btn.insertAdjacentHTML('beforeend', '<span class="lang-check">✓</span>');
            } else if (!isActive && check) {
                check.remove();
            }
        });
    }

    // ═══════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════

    return {
        init,
        setLanguage,
        getTranslation,
        t: getTranslation,
        applyTranslations,
        get currentLang() { return currentLang; },
        get speechLang() { return TRANSLATIONS._speechLang[currentLang] || 'en-US'; },
    };
})();

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => TranslateEngine.init());
} else {
    TranslateEngine.init();
}
