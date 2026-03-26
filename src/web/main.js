// EyeScroll Web UI - HTTP API 版本
const API_BASE = 'http://127.0.0.1:8765/api';

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

// 新增：显示 iris_y 值
let irisYDisplay = document.getElementById('iris-y');
if (!irisYDisplay) {
  irisYDisplay = document.createElement('p');
  irisYDisplay.innerHTML = 'Iris Y <span id="iris-y-val">—</span>';
  irisYDisplay.querySelector('span').id = 'iris-y-val';
  document.querySelector('.gaze-data').appendChild(irisYDisplay);
}
const irisYVal = document.getElementById('iris-y-val');

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
  rawX.textContent = gazeData.gaze_point?.[0]?.toFixed(3) ?? '—';
  screenYEl.textContent = gazeData.gaze_point?.[1]?.toFixed(3) ?? '—';
  stateEl.textContent = gazeData.state ?? '—';

  // 显示 iris_y 原始值
  if (gazeData.iris_y !== undefined) {
    irisYVal.textContent = gazeData.iris_y.toFixed(4);
  }

  // Update gaze dot position
  if (gazeData.gaze_point) {
    const x = gazeData.gaze_point[0] * 100;
    const y = gazeData.gaze_point[1] * 100;
    gazeDot.style.left = `${x}%`;
    gazeDot.style.top = `${y}%`;

    // Determine zone
    let zone = 'reading';
    if (y > 80) zone = 'down';
    else if (y < 10) zone = 'up';

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
    const response = await fetch(`${API_BASE}/state`);
    const data = await response.json();
    setConnected(true);
    updateGazeDisplay(data);
    lastGazeData = data;
  } catch (error) {
    console.error('Failed to fetch gaze:', error);
    setConnected(false);
  }
}

// Calibrate top - 采集 2 秒后取稳定值
calibrateTopBtn.addEventListener('click', async () => {
  try {
    calibrateTopBtn.disabled = true;
    calibrateTopBtn.textContent = '采集中... (2秒)';
    calibrationStatus.textContent = '请保持向上看...';
    calibrationStatus.classList.remove('success');

    // 开始采集
    await fetch(`${API_BASE}/calibrate/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: 'top' })
    });

    // 等待 2 秒
    await new Promise(r => setTimeout(r, 2000));

    // 停止采集并获取结果
    const response = await fetch(`${API_BASE}/calibrate/stop`, { method: 'POST' });
    const result = await response.json();

    if (result.success) {
      calibrationStatus.textContent = `Top: iris_y = ${result.value.toFixed(4)} (${result.samples_count} samples)`;
      calibrationStatus.classList.add('success');
    } else {
      calibrationStatus.textContent = 'Calibration failed: ' + (result.error || 'Unknown error');
    }
  } catch (error) {
    console.error('Calibrate top failed:', error);
    calibrationStatus.textContent = 'Calibration failed';
    calibrationStatus.classList.remove('success');
  } finally {
    calibrateTopBtn.disabled = false;
    calibrateTopBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/></svg>Look at Camera`;
  }
});

// Calibrate bottom - 采集 2 秒后取稳定值
calibrateBottomBtn.addEventListener('click', async () => {
  try {
    calibrateBottomBtn.disabled = true;
    calibrateBottomBtn.textContent = '采集中... (2秒)';
    calibrationStatus.textContent = '请保持向下看...';
    calibrationStatus.classList.remove('success');

    // 开始采集
    await fetch(`${API_BASE}/calibrate/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: 'bottom' })
    });

    // 等待 2 秒
    await new Promise(r => setTimeout(r, 2000));

    // 停止采集并获取结果
    const response = await fetch(`${API_BASE}/calibrate/stop`, { method: 'POST' });
    const result = await response.json();

    if (result.success) {
      calibrationStatus.textContent = `Bottom: iris_y = ${result.value.toFixed(4)} (${result.samples_count} samples)`;
      calibrationStatus.classList.add('success');
    } else {
      calibrationStatus.textContent = 'Calibration failed: ' + (result.error || 'Unknown error');
    }
  } catch (error) {
    console.error('Calibrate bottom failed:', error);
    calibrationStatus.textContent = 'Calibration failed';
    calibrationStatus.classList.remove('success');
  } finally {
    calibrateBottomBtn.disabled = false;
    calibrateBottomBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12l7 7 7-7"/></svg>Look at Screen Bottom`;
  }
});

// Toggle tracking
toggleTrackingBtn.addEventListener('click', async () => {
  try {
    trackingActive = !trackingActive;
    const response = await fetch(`${API_BASE}/enabled`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: trackingActive })
    });
    toggleTrackingBtn.textContent = trackingActive ? 'Stop Tracking' : 'Start Tracking';
    toggleTrackingBtn.classList.toggle('active', trackingActive);
  } catch (error) {
    console.error('Toggle tracking failed:', error);
  }
});

// Main loop using requestAnimationFrame
async function mainLoop(timestamp) {
  const elapsed = timestamp - lastFrameTime;
  if (elapsed >= TARGET_FRAME_INTERVAL) {
    lastFrameTime = timestamp - (elapsed % TARGET_FRAME_INTERVAL);
    await fetchGazeData();
  }
  requestAnimationFrame(mainLoop);
}

// Start
requestAnimationFrame(mainLoop);
