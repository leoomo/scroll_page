const API_BASE = 'http://127.0.0.1:8765';
let calibrationTimer = null;

const connectionDot = document.getElementById('connection-dot');
const stateText = document.getElementById('state-text');
const offsetMarker = document.getElementById('offset-marker');
const btnCalibrate = document.getElementById('btn-calibrate');
const toggleEnabled = document.getElementById('toggle-enabled');
const btnSettings = document.getElementById('btn-settings');
const settingsPanel = document.getElementById('settings-panel');
const scrollDistanceSlider = document.getElementById('scroll-distance');
const scrollDistanceVal = document.getElementById('scroll-distance-val');
const sensitivitySlider = document.getElementById('sensitivity');
const sensitivityVal = document.getElementById('sensitivity-val');
const btnResetCalibration = document.getElementById('btn-reset-calibration');
const calibrationOverlay = document.getElementById('calibration-overlay');
const calibrationText = document.getElementById('calibration-text');
const calibrationCountdown = document.getElementById('calibration-countdown');
const calibrationResult = document.getElementById('calibration-result');

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

        if (data.head_offset !== null && data.head_offset !== undefined) {
            const range = 0.05;
            const clamped = Math.max(-range, Math.min(range, -data.head_offset));
            const percent = ((clamped + range) / (range * 2)) * 100;
            offsetMarker.style.top = `${percent}%`;
            offsetMarker.classList.remove('hidden');
        } else {
            offsetMarker.classList.add('hidden');
        }
    } catch (e) {
        connectionDot.className = 'status-dot error';
    }

    requestAnimationFrame(fetchState);
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
        calibrationTimer = setInterval(async () => {
            remaining--;
            calibrationCountdown.textContent = remaining;
            if (remaining <= 0) {
                clearInterval(calibrationTimer);
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
            }, 1500);
        } else {
            calibrationText.textContent = result.error || 'Calibration failed';
        }
    } catch (e) {
        calibrationText.textContent = 'Error';
    }
}

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
    const threshold = parseFloat((0.06 - (val - 1) * (0.05 / 9)).toFixed(3));
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

requestAnimationFrame(fetchState);
