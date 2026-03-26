// EyeScroll Web UI
const { invoke } = window.__TAURI__.core;

let trackingActive = false;
let lastGazeData = null;

// DOM Elements
const gazeDot = document.getElementById('gaze-dot');
const rawX = document.getElementById('raw-x');
const rawY = document.getElementById('raw-y');
const screenY = document.getElementById('screen-y');
const zoneEl = document.getElementById('zone');
const stateEl = document.getElementById('state');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const calibrateTopBtn = document.getElementById('calibrate-top');
const calibrateBottomBtn = document.getElementById('calibrate-bottom');
const calibrationStatus = document.getElementById('calibration-status');
const toggleTrackingBtn = document.getElementById('toggle-tracking');

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
  rawX.textContent = gazeData.raw_x?.toFixed(3) ?? '-';
  rawY.textContent = gazeData.raw_y?.toFixed(3) ?? '-';
  screenY.textContent = gazeData.screen_y?.toFixed(3) ?? '-';
  zoneEl.textContent = gazeData.zone ?? '-';
  stateEl.textContent = gazeData.state ?? '-';

  // Update gaze dot position
  // screen_y: 0 = top, 1 = bottom
  // x: 0 = left, 1 = right
  if (gazeData.raw_x !== null && gazeData.screen_y !== null) {
    const x = gazeData.raw_x * 100;
    const y = gazeData.screen_y * 100;
    gazeDot.style.left = `${x}%`;
    gazeDot.style.top = `${y}%`;

    // Color based on zone
    if (gazeData.zone === 'up') {
      gazeDot.style.background = '#ef4444';
      gazeDot.style.boxShadow = '0 0 20px #ef4444';
    } else if (gazeData.zone === 'down') {
      gazeDot.style.background = '#22c55e';
      gazeDot.style.boxShadow = '0 0 20px #22c55e';
    } else {
      gazeDot.style.background = '#f59e0b';
      gazeDot.style.boxShadow = '0 0 20px #f59e0b';
    }
  }
}

// Fetch and display gaze data
async function fetchGazeData() {
  try {
    const gaze = await invoke('get_gaze');
    const stateData = await invoke('get_state');
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
      calibrationStatus.textContent = `Top calibrated: y=${result.top_y?.toFixed(3)}`;
      calibrationStatus.style.color = '#4ade80';
    }
  } catch (error) {
    console.error('Calibrate top failed:', error);
  }
});

// Calibrate bottom
calibrateBottomBtn.addEventListener('click', async () => {
  try {
    const result = await invoke('calibrate_bottom');
    if (result.success) {
      calibrationStatus.textContent = `Bottom calibrated: y=${result.bottom_y?.toFixed(3)}`;
      calibrationStatus.style.color = '#4ade80';
    }
  } catch (error) {
    console.error('Calibrate bottom failed:', error);
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

// Slider value updates
document.getElementById('dwell-time').addEventListener('input', (e) => {
  document.getElementById('dwell-value').textContent = e.target.value;
});

document.getElementById('zone-ratio').addEventListener('input', (e) => {
  document.getElementById('zone-ratio-value').textContent = e.target.value;
});

document.getElementById('up-dwell-time').addEventListener('input', (e) => {
  document.getElementById('up-dwell-value').textContent = e.target.value;
});

document.getElementById('up-zone-ratio').addEventListener('input', (e) => {
  document.getElementById('up-zone-ratio-value').textContent = e.target.value;
});

// Main loop
async function mainLoop() {
  await fetchGazeData();
  setTimeout(mainLoop, 33); // ~30fps
}

// Start
checkConnection();
setTimeout(mainLoop, 100);
