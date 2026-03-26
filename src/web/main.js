// EyeScroll Web UI
const { invoke } = window.__TAURI__.core;

let trackingActive = false;
let lastGazeData = null;
let lastFrameTime = 0;
const TARGET_FRAME_INTERVAL = 33; // ~30fps

// DOM Elements
const gazeDot = document.getElementById('gaze-dot');
const rawX = document.getElementById('raw-x');
const rawY = document.getElementById('raw-y');
const screenYEl = document.getElementById('screen-y');
const stateEl = document.getElementById('state');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const calibrateTopBtn = document.getElementById('calibrate-top');
const calibrateBottomBtn = document.getElementById('calibrate-bottom');
const calibrationStatus = document.getElementById('calibration-status');
const toggleTrackingBtn = document.getElementById('toggle-tracking');

// Zone labels for accessibility
const ZONE_LABELS = {
  up: 'Up',
  down: 'Down',
  reading: 'Reading',
  none: '—'
};

// Update connection status
function setConnected(connected) {
  if (connected) {
    statusDot.classList.remove('disconnected');
    statusDot.classList.add('connected');
    statusText.textContent = 'Connected';
  } else {
    statusDot.classList.remove('connected');
    statusDot.classList.add('disconnected');
    statusText.textContent = 'Disconnected';
  }
}

// Update gaze visualization
function updateGazeDisplay(gazeData) {
  if (!gazeData) return;

  // Update text
  rawX.textContent = gazeData.raw_x?.toFixed(3) ?? '—';
  rawY.textContent = gazeData.raw_y?.toFixed(3) ?? '—';
  screenYEl.textContent = gazeData.screen_y?.toFixed(3) ?? '—';
  stateEl.textContent = gazeData.state ?? '—';

  // Update gaze dot position
  if (gazeData.raw_x !== null && gazeData.screen_y !== null) {
    const x = gazeData.raw_x * 100;
    const y = gazeData.screen_y * 100;
    gazeDot.style.left = `${x}%`;
    gazeDot.style.top = `${y}%`;

    // Update zone label for accessibility
    const zone = gazeData.zone || 'none';
    gazeDot.setAttribute('data-zone', ZONE_LABELS[zone] || '—');

    // Color based on zone
    let color, shadow;
    if (zone === 'up') {
      color = '#ef4444';
      shadow = '0 0 16px #ef4444';
    } else if (zone === 'down') {
      color = '#22c55e';
      shadow = '0 0 16px #22c55e';
    } else {
      color = '#f59e0b';
      shadow = '0 0 16px #f59e0b';
    }
    gazeDot.style.background = color;
    gazeDot.style.boxShadow = shadow;
  }
}

// Fetch and display gaze data
async function fetchGazeData() {
  try {
    const [gaze, stateData] = await Promise.all([
      invoke('get_gaze'),
      invoke('get_state')
    ]);
    setConnected(true);

    const combined = {
      ...gaze,
      state: stateData?.state
    };
    updateGazeDisplay(combined);
    lastGazeData = combined;
  } catch (error) {
    console.error('Failed to fetch gaze:', error);
    setConnected(false);
  }
}

// Check connection
async function checkConnection() {
  try {
    const connected = await invoke('check_connection');
    setConnected(connected);
  } catch (error) {
    setConnected(false);
  }
}

// Calibrate top
calibrateTopBtn.addEventListener('click', async () => {
  try {
    const result = await invoke('calibrate_top');
    if (result.success) {
      calibrationStatus.textContent = `Top calibrated: ${result.top_y?.toFixed(3)}`;
      calibrationStatus.classList.add('success');
    }
  } catch (error) {
    console.error('Calibrate top failed:', error);
    calibrationStatus.textContent = 'Calibration failed';
    calibrationStatus.classList.remove('success');
  }
});

// Calibrate bottom
calibrateBottomBtn.addEventListener('click', async () => {
  try {
    const result = await invoke('calibrate_bottom');
    if (result.success) {
      calibrationStatus.textContent = `Bottom calibrated: ${result.bottom_y?.toFixed(3)}`;
      calibrationStatus.classList.add('success');
    }
  } catch (error) {
    console.error('Calibrate bottom failed:', error);
    calibrationStatus.textContent = 'Calibration failed';
    calibrationStatus.classList.remove('success');
  }
});

// Toggle tracking
toggleTrackingBtn.addEventListener('click', async () => {
  try {
    trackingActive = !trackingActive;
    await invoke('set_enabled', { enabled: trackingActive });
    toggleTrackingBtn.textContent = trackingActive ? 'Stop Tracking' : 'Start Tracking';
    toggleTrackingBtn.classList.toggle('active', trackingActive);
  } catch (error) {
    console.error('Toggle tracking failed:', error);
  }
});

// Load config from backend and update sliders
async function loadConfig() {
  try {
    const cfg = await invoke('get_config');
    document.getElementById('dwell-time').value = cfg.dwell_time_ms;
    document.getElementById('dwell-value').textContent = `${cfg.dwell_time_ms}ms`;
    document.getElementById('zone-ratio').value = cfg.scroll_zone_ratio * 100;
    document.getElementById('zone-ratio-value').textContent = `${Math.round(cfg.scroll_zone_ratio * 100)}%`;
    document.getElementById('up-dwell-time').value = cfg.up_dwell_time_ms;
    document.getElementById('up-dwell-value').textContent = `${cfg.up_dwell_time_ms}ms`;
    document.getElementById('up-zone-ratio').value = cfg.up_scroll_ratio * 100;
    document.getElementById('up-zone-ratio-value').textContent = `${Math.round(cfg.up_scroll_ratio * 100)}%`;
    document.getElementById('enable-down').checked = cfg.up_scroll_enabled !== undefined ? cfg.up_scroll_enabled : true;
    document.getElementById('enable-up').checked = cfg.up_scroll_enabled;
  } catch (error) {
    console.error('Failed to load config:', error);
  }
}

// Save config to backend
async function saveConfig() {
  try {
    const cfg = {
      dwell_time_ms: parseInt(document.getElementById('dwell-time').value),
      scroll_zone_ratio: parseInt(document.getElementById('zone-ratio').value) / 100,
      up_dwell_time_ms: parseInt(document.getElementById('up-dwell-time').value),
      up_scroll_ratio: parseInt(document.getElementById('up-zone-ratio').value) / 100,
      up_scroll_enabled: document.getElementById('enable-up').checked
    };
    await invoke('set_config', { configData: cfg });
  } catch (error) {
    console.error('Failed to save config:', error);
  }
}

// Debounce helper
function debounce(fn, delay) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
}

// Slider value updates with display and config persistence
const debouncedSaveConfig = debounce(saveConfig, 500);

document.getElementById('dwell-time').addEventListener('input', (e) => {
  document.getElementById('dwell-value').textContent = `${e.target.value}ms`;
  debouncedSaveConfig();
});

document.getElementById('zone-ratio').addEventListener('input', (e) => {
  document.getElementById('zone-ratio-value').textContent = `${e.target.value}%`;
  debouncedSaveConfig();
});

document.getElementById('up-dwell-time').addEventListener('input', (e) => {
  document.getElementById('up-dwell-value').textContent = `${e.target.value}ms`;
  debouncedSaveConfig();
});

document.getElementById('up-zone-ratio').addEventListener('input', (e) => {
  document.getElementById('up-zone-ratio-value').textContent = `${e.target.value}%`;
  debouncedSaveConfig();
});

document.getElementById('enable-up').addEventListener('change', debouncedSaveConfig);

// Main loop using requestAnimationFrame
async function mainLoop(timestamp) {
  // Throttle to ~30fps
  const elapsed = timestamp - lastFrameTime;
  if (elapsed >= TARGET_FRAME_INTERVAL) {
    lastFrameTime = timestamp - (elapsed % TARGET_FRAME_INTERVAL);
    await fetchGazeData();
  }
  requestAnimationFrame(mainLoop);
}

// Start
checkConnection();
loadConfig();
requestAnimationFrame(mainLoop);
