const API_BASE = 'http://127.0.0.1:8765';
const WS_BASE = 'ws://127.0.0.1:8765';
const SENSITIVITY_BASE = 0.04;
const SENSITIVITY_STEP = 0.035 / 9;
let calibrationTimer = null;
let lastRightCmdTime = 0;
let lastWsAction = null;

const connectionDot = document.getElementById('connection-dot');
const stateText = document.getElementById('state-text');
const btnCalibrate = document.getElementById('btn-calibrate');
const toggleEnabled = document.getElementById('toggle-enabled');
const btnSettings = document.getElementById('btn-settings');
const settingsPanel = document.getElementById('settings-panel');

// Global shortcut: double-press right Command to toggle tracking
import { register } from '@tauri-apps/plugin-global-shortcut';

let shortcutRegistered = false;
async function registerToggleShortcut() {
    if (shortcutRegistered) return;
    try {
        await register('Shift', async () => {
            const now = Date.now();
            if (now - lastRightCmdTime < 400) {
                toggleEnabled.checked = !toggleEnabled.checked;
                const endpoint = toggleEnabled.checked ? '/api/enable' : '/api/disable';
                await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
            }
            lastRightCmdTime = now;
        });
        shortcutRegistered = true;
    } catch (e) {
        console.warn('Global shortcut failed:', e);
        document.getElementById('state-text').textContent = 'Shortcut error: ' + e;
    }
}
registerToggleShortcut();

const scrollDistanceSlider = document.getElementById('scroll-distance');
const scrollDistanceVal = document.getElementById('scroll-distance-val');
const sensitivitySlider = document.getElementById('sensitivity');
const sensitivityVal = document.getElementById('sensitivity-val');
const btnResetCalibration = document.getElementById('btn-reset-calibration');
const calibrationOverlay = document.getElementById('calibration-overlay');
const calibrationText = document.getElementById('calibration-text');
const calibrationCountdown = document.getElementById('calibration-countdown');
const calibrationResult = document.getElementById('calibration-result');

// WebSocket for real-time scroll direction flash
let ws = null;
function connectWs() {
    ws = new WebSocket(`${WS_BASE}/ws`);
    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'state_update' && msg.data.action && msg.data.action !== lastWsAction) {
                lastWsAction = msg.data.action;
                const iframe = document.getElementById('test-article');
                if (iframe && iframe.contentWindow) {
                    const dir = msg.data.action.includes('down') ? 'down' : 'up';
                    iframe.contentWindow.postMessage({ type: 'scroll', direction: dir }, '*');
                }
            } else if (!msg.data.action) {
                lastWsAction = null;
            }
        } catch (_) {}
    };
    ws.onclose = () => { setTimeout(connectWs, 2000); };
    ws.onerror = () => { ws.close(); };
}
connectWs();

const STATE_LABELS = {
    idle: 'IDLE',
    dwelling_down: 'DWELLING',
    dwelling_up: 'DWELLING',
    continuous_down: 'SCROLLING',
    continuous_up: 'SCROLLING',
};

async function fetchState() {
    try {
        const res = await fetch(`${API_BASE}/api/state`);
        const data = await res.json();

        connectionDot.className = 'status-dot';
        if (data.face_detected) {
            connectionDot.classList.add('connected');
        } else {
            connectionDot.classList.add('disconnected');
        }

        stateText.textContent = STATE_LABELS[data.state] || data.state.toUpperCase();
    } catch (e) {
        connectionDot.className = 'status-dot error';
    }

    setTimeout(fetchState, 200);
}

async function startCalibration() {
    calibrationOverlay.classList.remove('hidden');
    calibrationText.classList.remove('hidden');
    calibrationText.textContent = 'Align your gaze here';
    calibrationCountdown.classList.remove('hidden');
    calibrationCountdown.textContent = '3';
    calibrationResult.classList.add('hidden');

    try {
        await fetch(`${API_BASE}/api/calibrate/neutral`, { method: 'POST' });

        let remaining = 3;
        // Poll calibration progress
        const progressTimer = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/api/calibrate/progress`);
                const progress = await res.json();
                if (progress.calibrating) {
                    calibrationText.textContent = progress.face_detected
                        ? `Collecting samples... (${progress.samples})`
                        : 'No face detected - look at camera';
                }
            } catch (_) {}
        }, 200);

        calibrationTimer = setInterval(async () => {
            remaining--;
            calibrationCountdown.textContent = remaining;
            if (remaining <= 0) {
                clearInterval(calibrationTimer);
                clearInterval(progressTimer);
                calibrationTimer = null;
                await stopCalibration();
            }
        }, 1000);
    } catch (e) {
        calibrationText.textContent = 'Failed to start';
        setTimeout(() => calibrationOverlay.classList.add('hidden'), 2000);
    }
}

async function stopCalibration() {
    try {
        const res = await fetch(`${API_BASE}/api/calibrate/neutral/stop`, { method: 'POST' });
        const result = await res.json();

        calibrationCountdown.classList.add('hidden');

        if (result.success) {
            await fetch(`${API_BASE}/api/calibration/save`, { method: 'POST' });

            calibrationText.classList.add('hidden');
            calibrationResult.classList.remove('hidden');
            calibrationResult.textContent = `Calibrated (${result.sample_count} samples)`;

            connectionDot.classList.add('flash');
            setTimeout(() => {
                connectionDot.classList.remove('flash');
                calibrationOverlay.classList.add('hidden');
                calibrationResult.classList.add('hidden');
                // Auto-focus the iframe so head-scroll works immediately
                const iframe = document.getElementById('test-article');
                if (iframe) {
                    iframe.focus();
                    iframe.contentWindow?.scrollTo({ top: 0, behavior: 'smooth' });
                    iframe.contentWindow?.postMessage({ type: 'scroll', direction: null }, '*');
                }
            }, 1500);
        } else {
            calibrationText.textContent = result.error || 'Calibration failed';
        }
    } catch (e) {
        calibrationText.textContent = 'Error';
    }
}

// Initialize sliders from backend config
async function initSliders() {
    try {
        const res = await fetch(`${API_BASE}/api/config`);
        const cfg = await res.json();
        if (cfg.scroll_distance != null) {
            scrollDistanceSlider.value = cfg.scroll_distance;
            scrollDistanceVal.textContent = cfg.scroll_distance;
        }
        if (cfg.head_down_threshold != null) {
            // Reverse-engineer slider value from threshold
            // threshold = 0.08 - (val - 1) * (0.05 / 9)
            const threshold = Math.abs(cfg.head_down_threshold);
            const val = Math.round(1 + (SENSITIVITY_BASE - threshold) / SENSITIVITY_STEP);
            const clamped = Math.max(1, Math.min(10, val));
            sensitivitySlider.value = clamped;
            sensitivityVal.textContent = clamped;
        }
    } catch (_) {}
}
initSliders();

btnSettings.addEventListener('click', () => {
    settingsPanel.classList.toggle('hidden');
});

toggleEnabled.addEventListener('change', async () => {
    const endpoint = toggleEnabled.checked ? '/api/enable' : '/api/disable';
    await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
});

scrollDistanceSlider.addEventListener('input', () => {
    scrollDistanceVal.textContent = scrollDistanceSlider.value;
});

scrollDistanceSlider.addEventListener('change', async () => {
    await fetch(`${API_BASE}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scroll_distance: parseInt(scrollDistanceSlider.value) }),
    });
});

sensitivitySlider.addEventListener('input', () => {
    sensitivityVal.textContent = sensitivitySlider.value;
});

sensitivitySlider.addEventListener('change', async () => {
    const val = parseInt(sensitivitySlider.value);
    const threshold = parseFloat((SENSITIVITY_BASE - (val - 1) * SENSITIVITY_STEP).toFixed(3));
    await fetch(`${API_BASE}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            head_down_threshold: threshold,
            head_up_threshold: -threshold,
        }),
    });
});

btnResetCalibration.addEventListener('click', async () => {
    await fetch(`${API_BASE}/api/calibration/reset`, { method: 'POST' });
});

btnCalibrate.addEventListener('click', startCalibration);

setTimeout(fetchState, 200);
