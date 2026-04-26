/**
 * ═══════════════════════════════════════════════════════════
 * VoiceEngine — Full Voice Control for SecureVote
 * Uses Web Speech API (SpeechSynthesis + SpeechRecognition)
 * Zero external dependencies — works in Chrome, Edge, Safari
 * ═══════════════════════════════════════════════════════════
 */

const VoiceEngine = (() => {
    // ─── State ───
    let synth = null;
    let recognition = null;
    let isListening = false;
    let isSpeaking = false;
    let commands = [];
    let guideSteps = [];
    let guideIndex = -1;
    let guideActive = false;
    let transcriptTimeout = null;
    let hintTimeout = null;
    let initialized = false;
    let pageContext = {};
    let restartTimer = null;

    // ─── DOM References ───
    let micBtn, guideBtn, transcriptEl, statusEl, guidePanel, guideOverlay, hintEl;

    // ═══════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════

    function init(options = {}) {
        if (initialized) return;
        initialized = true;
        pageContext = options;

        console.log('[VoiceEngine] Initializing...');

        // Check browser support
        synth = window.speechSynthesis;
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (SpeechRec) {
            recognition = new SpeechRec();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';
            recognition.maxAlternatives = 3;

            recognition.onresult = handleSpeechResult;

            recognition.onstart = () => {
                console.log('[VoiceEngine] Recognition started');
            };

            recognition.onend = () => {
                console.log('[VoiceEngine] Recognition ended, isListening:', isListening);
                if (isListening) {
                    // Auto-restart with a small delay to avoid rapid restarts
                    clearTimeout(restartTimer);
                    restartTimer = setTimeout(() => {
                        if (isListening) {
                            try {
                                recognition.start();
                                console.log('[VoiceEngine] Recognition restarted');
                            } catch (e) {
                                console.warn('[VoiceEngine] Restart failed:', e.message);
                            }
                        }
                    }, 300);
                }
            };

            recognition.onerror = (e) => {
                console.warn('[VoiceEngine] Recognition error:', e.error);
                if (e.error === 'not-allowed') {
                    showHint('⚠️ Microphone permission denied. Please allow mic access and reload.');
                    isListening = false;
                    updateMicState();
                    hideStatus();
                } else if (e.error === 'network') {
                    showHint('⚠️ Network error. Speech recognition requires internet for Chrome.');
                } else if (e.error === 'no-speech') {
                    // This is normal — user is just silent, don't show error
                    console.log('[VoiceEngine] No speech detected, continuing to listen...');
                } else if (e.error === 'audio-capture') {
                    showHint('⚠️ No microphone found. Please connect a mic and reload.');
                    isListening = false;
                    updateMicState();
                    hideStatus();
                }
            };

            console.log('[VoiceEngine] SpeechRecognition available');
        } else {
            console.warn('[VoiceEngine] SpeechRecognition NOT available in this browser');
        }

        // Register built-in commands first, then page-specific ones
        registerBuiltinCommands();
        if (options.commands) {
            options.commands.forEach(c => registerCommand(c.patterns, c.handler, c.description));
        }
        if (options.guideSteps) {
            guideSteps = options.guideSteps;
        }

        // Build UI
        buildUI();

        // Load voices
        if (synth) {
            synth.getVoices();
        }

        console.log('[VoiceEngine] Ready. Commands registered:', commands.length);
    }

    // ═══════════════════════════════════════════
    // UI BUILDING
    // ═══════════════════════════════════════════

    function buildUI() {
        // Transcript bubble
        transcriptEl = document.createElement('div');
        transcriptEl.className = 'voice-transcript';
        transcriptEl.innerHTML = `
            <div class="transcript-label">🎤 Heard</div>
            <div class="transcript-text"></div>
        `;
        document.body.appendChild(transcriptEl);

        // Status indicator
        statusEl = document.createElement('div');
        statusEl.className = 'voice-status';
        document.body.appendChild(statusEl);

        // Voice hint
        hintEl = document.createElement('div');
        hintEl.className = 'voice-hint';
        document.body.appendChild(hintEl);

        // Guide overlay
        guideOverlay = document.createElement('div');
        guideOverlay.className = 'guide-overlay';
        guideOverlay.addEventListener('click', closeGuide);
        document.body.appendChild(guideOverlay);

        // Guide panel
        guidePanel = document.createElement('div');
        guidePanel.className = 'guide-panel';
        guidePanel.innerHTML = `
            <div class="guide-panel-header">
                <h3>🎙️ Guide Me</h3>
                <button class="guide-panel-close" onclick="VoiceEngine.closeGuide()" title="Close">✕</button>
            </div>
            <div class="guide-panel-body" id="guide-steps-container"></div>
            <div class="guide-panel-footer">
                <button onclick="VoiceEngine.guidePrev()">◀ Previous</button>
                <button class="primary" onclick="VoiceEngine.guideNext()">Next ▶</button>
            </div>
        `;
        document.body.appendChild(guidePanel);

        // Floating controls
        const controls = document.createElement('div');
        controls.className = 'voice-controls';

        guideBtn = document.createElement('button');
        guideBtn.className = 'voice-guide-btn';
        guideBtn.innerHTML = '❓';
        guideBtn.title = 'Guide Me — Voice walkthrough';
        guideBtn.addEventListener('click', toggleGuide);

        micBtn = document.createElement('button');
        micBtn.className = 'voice-mic-btn';
        micBtn.innerHTML = '🎤';
        micBtn.title = 'Click to start voice control';
        micBtn.addEventListener('click', toggleListening);

        controls.appendChild(guideBtn);
        controls.appendChild(micBtn);
        document.body.appendChild(controls);
    }

    // ═══════════════════════════════════════════
    // SPEECH SYNTHESIS (TTS)
    // ═══════════════════════════════════════════

    function speak(text, options = {}) {
        if (!synth) return Promise.resolve();

        return new Promise((resolve) => {
            // Cancel any ongoing speech
            synth.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = options.rate || 0.95;
            utterance.pitch = options.pitch || 1.0;
            utterance.volume = options.volume || 1.0;
            utterance.lang = options.lang || 'en-US';

            // Try to pick a good voice
            const voices = synth.getVoices();
            const preferred = voices.find(v =>
                v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Microsoft') || v.name.includes('Samantha') || v.name.includes('Zira') || v.name.includes('David'))
            ) || voices.find(v => v.lang.startsWith('en'));
            if (preferred) utterance.voice = preferred;

            utterance.onstart = () => {
                isSpeaking = true;
                updateMicState();
                setStatus('Speaking...', 'speaking');
                console.log('[VoiceEngine] Speaking:', text.substring(0, 60) + '...');
            };

            utterance.onend = () => {
                isSpeaking = false;
                updateMicState();
                hideStatus();
                resolve();
            };

            utterance.onerror = (e) => {
                console.warn('[VoiceEngine] Speech error:', e.error);
                isSpeaking = false;
                updateMicState();
                hideStatus();
                resolve();
            };

            synth.speak(utterance);

            // Chrome bug: long text pauses and never resumes
            // Workaround: resume periodically
            const resumeInterval = setInterval(() => {
                if (!synth.speaking) {
                    clearInterval(resumeInterval);
                } else {
                    synth.resume();
                }
            }, 5000);
        });
    }

    function stopSpeaking() {
        if (synth) {
            synth.cancel();
            isSpeaking = false;
            updateMicState();
            hideStatus();
        }
    }

    // ═══════════════════════════════════════════
    // SPEECH RECOGNITION (STT)
    // ═══════════════════════════════════════════

    function startListening() {
        if (!recognition) {
            showHint('⚠️ Voice recognition not supported. Use Chrome or Edge.');
            return;
        }
        if (isListening) return;

        // Stop speaking first to avoid echo feedback
        stopSpeaking();

        isListening = true;
        try {
            recognition.start();
            console.log('[VoiceEngine] Starting recognition...');
        } catch (e) {
            console.warn('[VoiceEngine] Start error:', e.message);
            // If already started, abort and restart
            try {
                recognition.abort();
                setTimeout(() => {
                    try { recognition.start(); } catch (e2) {}
                }, 200);
            } catch (e2) {}
        }
        updateMicState();
        setStatus('Listening...', 'listening');
        showHint('🎤 Listening... Say a command like <code>"guide me"</code> or <code>"go to elections"</code>');
    }

    function stopListening() {
        isListening = false;
        clearTimeout(restartTimer);
        if (recognition) {
            try { recognition.abort(); } catch (e) {}
        }
        updateMicState();
        hideStatus();
        hideTranscript();
        console.log('[VoiceEngine] Stopped listening');
    }

    function toggleListening() {
        if (isListening) {
            stopListening();
        } else {
            startListening();
        }
    }

    function handleSpeechResult(event) {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            if (result.isFinal) {
                finalTranscript += result[0].transcript;
            } else {
                interimTranscript += result[0].transcript;
            }
        }

        // Show interim results
        if (interimTranscript) {
            showTranscript(interimTranscript, true);
        }

        // Process final result
        if (finalTranscript) {
            const cleaned = finalTranscript.trim().toLowerCase();
            console.log('[VoiceEngine] Final transcript:', cleaned);
            showTranscript(finalTranscript.trim(), false);
            const matched = processCommand(cleaned);
            console.log('[VoiceEngine] Command matched:', matched);
        }
    }

    // ═══════════════════════════════════════════
    // COMMAND PROCESSING
    // ═══════════════════════════════════════════

    function registerCommand(patterns, handler, description) {
        commands.push({
            patterns: Array.isArray(patterns) ? patterns : [patterns],
            handler,
            description: description || ''
        });
    }

    function processCommand(text) {
        for (const cmd of commands) {
            for (const pattern of cmd.patterns) {
                if (typeof pattern === 'string') {
                    if (text.includes(pattern)) {
                        console.log('[VoiceEngine] Matched command:', cmd.description, '| Pattern:', pattern);
                        try {
                            cmd.handler(text);
                        } catch (e) {
                            console.error('[VoiceEngine] Command handler error:', e);
                        }
                        return true;
                    }
                } else if (pattern instanceof RegExp) {
                    const match = text.match(pattern);
                    if (match) {
                        console.log('[VoiceEngine] Matched regex command:', cmd.description);
                        try {
                            cmd.handler(text, match);
                        } catch (e) {
                            console.error('[VoiceEngine] Command handler error:', e);
                        }
                        return true;
                    }
                }
            }
        }
        // No command matched — show what we heard and hint
        console.log('[VoiceEngine] No command matched for:', text);
        showHint(`❓ Heard: "${text}". Try <code>"guide me"</code> or <code>"go to elections"</code>`);
        return false;
    }

    function registerBuiltinCommands() {
        // Navigation
        registerCommand(
            ['go to dashboard', 'open dashboard', 'dashboard'],
            () => { speak('Going to dashboard.'); setTimeout(() => window.location.href = '/dashboard/', 1200); },
            'Navigate to dashboard'
        );
        registerCommand(
            ['go to elections', 'open elections', 'show elections', 'elections page', 'elections'],
            () => { speak('Going to elections.'); setTimeout(() => window.location.href = '/elections/', 1200); },
            'Navigate to elections'
        );
        registerCommand(
            ['go to results', 'open results', 'show results', 'results page', 'results'],
            () => { speak('Going to results.'); setTimeout(() => window.location.href = '/results/', 1200); },
            'Navigate to results'
        );
        registerCommand(
            ['go to admin', 'open admin', 'admin panel', 'admin'],
            () => { speak('Going to admin panel.'); setTimeout(() => window.location.href = '/admin-panel/', 1200); },
            'Navigate to admin panel'
        );
        registerCommand(
            ['register face', 'face registration', 'register my face', 'face id'],
            () => { speak('Going to face registration.'); setTimeout(() => window.location.href = '/register-face/', 1200); },
            'Navigate to face registration'
        );

        // Guide
        registerCommand(
            ['guide me', 'help me', 'what can i do', 'what can i say', 'help'],
            () => openGuide(),
            'Open the Guide Me panel'
        );

        // Stop
        registerCommand(
            ['stop', 'pause', 'quiet', 'shut up', 'be quiet', 'silence'],
            () => { stopSpeaking(); showHint('🔇 Speech stopped.'); },
            'Stop speaking'
        );

        // Logout
        registerCommand(
            ['log out', 'logout', 'sign out'],
            () => {
                speak('Logging out. Goodbye!');
                setTimeout(() => {
                    if (typeof clearAuth === 'function') clearAuth();
                    window.location.href = '/';
                }, 1500);
            },
            'Log out of the system'
        );

        // Read page
        registerCommand(
            ['read page', 'read this page', 'read everything'],
            () => {
                const mainContent = document.querySelector('.container') || document.body;
                const textContent = mainContent.innerText.substring(0, 1500);
                speak(textContent);
            },
            'Read visible page content aloud'
        );

        // Next/previous for guide
        registerCommand(['next', 'next step'], () => guideNext(), 'Next guide step');
        registerCommand(['previous', 'go back'], () => guidePrev(), 'Previous guide step');
    }

    // ═══════════════════════════════════════════
    // GUIDE ME
    // ═══════════════════════════════════════════

    function openGuide() {
        if (guideSteps.length === 0) {
            speak('No guide is available for this page.');
            return;
        }

        guideActive = true;
        guideIndex = 0;
        guidePanel.classList.add('open');
        guideOverlay.classList.add('visible');
        guideBtn.classList.add('active');

        renderGuideSteps();
        speakCurrentStep();
    }

    function closeGuide() {
        guideActive = false;
        guideIndex = -1;
        guidePanel.classList.remove('open');
        guideOverlay.classList.remove('visible');
        guideBtn.classList.remove('active');
        stopSpeaking();
    }

    function toggleGuide() {
        if (guidePanel.classList.contains('open')) {
            closeGuide();
        } else {
            openGuide();
        }
    }

    function renderGuideSteps() {
        const container = document.getElementById('guide-steps-container');
        if (!container) return;

        container.innerHTML = guideSteps.map((step, i) => {
            let stateClass = '';
            if (i === guideIndex) stateClass = 'active';
            else if (i < guideIndex) stateClass = 'done';

            return `
                <div class="guide-step ${stateClass}" onclick="VoiceEngine.guideGoTo(${i})">
                    <span class="guide-step-number">${i < guideIndex ? '✓' : i + 1}</span>
                    <span class="guide-step-text">${step.text}</span>
                </div>
            `;
        }).join('');
    }

    async function speakCurrentStep() {
        if (guideIndex < 0 || guideIndex >= guideSteps.length) return;
        const step = guideSteps[guideIndex];

        renderGuideSteps();

        // Speak the step text
        await speak(step.speak || step.text);

        // Execute action if the step has one
        if (step.action && typeof step.action === 'function') {
            step.action();
        }
    }

    function guideNext() {
        if (!guideActive) return;
        if (guideIndex < guideSteps.length - 1) {
            guideIndex++;
            speakCurrentStep();
        } else {
            speak('That was the last step. You can close the guide now.');
        }
    }

    function guidePrev() {
        if (!guideActive) return;
        if (guideIndex > 0) {
            guideIndex--;
            speakCurrentStep();
        } else {
            speak('This is the first step.');
        }
    }

    function guideGoTo(index) {
        if (!guideActive) return;
        guideIndex = index;
        speakCurrentStep();
    }

    // ═══════════════════════════════════════════
    // UI HELPERS
    // ═══════════════════════════════════════════

    function updateMicState() {
        if (!micBtn) return;
        micBtn.classList.remove('listening', 'speaking');
        if (isListening) micBtn.classList.add('listening');
        else if (isSpeaking) micBtn.classList.add('speaking');
    }

    function showTranscript(text, interim) {
        if (!transcriptEl) return;
        const textEl = transcriptEl.querySelector('.transcript-text');
        textEl.textContent = text;
        textEl.className = `transcript-text ${interim ? 'interim' : ''}`;
        transcriptEl.classList.add('visible');

        clearTimeout(transcriptTimeout);
        if (!interim) {
            transcriptTimeout = setTimeout(() => transcriptEl.classList.remove('visible'), 4000);
        }
    }

    function hideTranscript() {
        if (transcriptEl) transcriptEl.classList.remove('visible');
    }

    function setStatus(text, type) {
        if (!statusEl) return;
        statusEl.className = `voice-status visible ${type}`;
        const waveform = type === 'listening'
            ? ' <span class="voice-waveform"><span class="bar"></span><span class="bar"></span><span class="bar"></span><span class="bar"></span></span>'
            : '';
        statusEl.innerHTML = text + waveform;
    }

    function hideStatus() {
        if (statusEl) statusEl.classList.remove('visible');
    }

    function showHint(html) {
        if (!hintEl) return;
        hintEl.innerHTML = html;
        hintEl.classList.add('visible');
        clearTimeout(hintTimeout);
        hintTimeout = setTimeout(() => hintEl.classList.remove('visible'), 5000);
    }

    // ═══════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════

    return {
        init,
        speak,
        stopSpeaking,
        startListening,
        stopListening,
        toggleListening,
        registerCommand,
        openGuide,
        closeGuide,
        guideNext,
        guidePrev,
        guideGoTo,
        showHint,

        // Expose state for page scripts
        get isListening() { return isListening; },
        get isSpeaking() { return isSpeaking; },
        get guideActive() { return guideActive; },
    };
})();

// Load voices (Chrome needs a small delay)
if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
}
