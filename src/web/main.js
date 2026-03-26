// EyeScroll Web UI
const API_BASE = 'http://127.0.0.1:8765/api';

let lastFrameTime = 0;
let pendingCalibration = null;
let isCollecting = false;

const TARGET_FRAME_INTERVAL = 33;

// DOM Elements
const gazeDot = document.getElementById('gaze-dot');
const irisYVal = document.getElementById('iris-y-val');
const screenYEl = document.getElementById('screen-y');
const stateEl = document.getElementById('state');
const calibratedStatus = document.getElementById('calibrated-status');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const calibrateTopBtn = document.getElementById('calibrate-top');
const calibrateBottomBtn = document.getElementById('calibrate-bottom');
const calibrationStatus = document.getElementById('calibration-status');
const saveCalibrationBtn = document.getElementById('save-calibration');
const resetCalibrationBtn = document.getElementById('reset-calibration');

// Dialog elements
const confirmDialog = document.getElementById('confirm-dialog');
const confirmMessage = document.getElementById('confirm-message');
const confirmYesBtn = document.getElementById('confirm-yes');
const confirmNoBtn = document.getElementById('confirm-no');

// Zone detection
function getZone(screenY) {
  if (screenY < 0.1) return 'Up';
  if (screenY > 0.9) return 'Down';
  return 'Reading';
}

// Update connection status
function setConnected(connected) {
  if (statusDot) statusDot.className = connected ? 'connected' : '';
  if (statusText) statusText.textContent = connected ? 'Connected' : 'Disconnected';
}

// Hide confirm dialog
function hideConfirm() {
  confirmDialog.classList.add('hidden');
  pendingCalibration = null;
  isCollecting = false;
}

// Update gaze display
function updateGazeDisplay(data) {
  if (!data) return;

  const screenY = data.gaze_point?.[1] ?? 0.5;
  const rawX = data.gaze_point?.[0] ?? 0.5;
  const zone = getZone(screenY);

  if (irisYVal) irisYVal.textContent = data.iris_y?.toFixed(4) ?? '--';
  if (screenYEl) screenYEl.textContent = screenY.toFixed(3);
  if (stateEl) stateEl.textContent = data.state ?? '--';

  // Calibration status
  const cal = data.calibration;
  if (calibratedStatus) {
    if (cal?.calibrated) {
      calibratedStatus.textContent = `${cal.top_y?.toFixed(3)} / ${cal.bottom_y?.toFixed(3)}`;
      calibratedStatus.style.color = 'var(--accent)';
    } else {
      calibratedStatus.textContent = 'Not calibrated';
      calibratedStatus.style.color = '';
    }
  }

  // Update gaze dot
  if (gazeDot) {
    gazeDot.style.left = `${rawX * 100}%`;
    gazeDot.style.top = `${screenY * 100}%`;
    gazeDot.setAttribute('data-zone', zone);
  }
}

// Fetch state
async function fetchState() {
  try {
    const res = await fetch(`${API_BASE}/state`);
    const data = await res.json();
    setConnected(true);
    updateGazeDisplay(data);
  } catch (err) {
    setConnected(false);
  }
}

// Step 1: Show preparation dialog
function showPrepareDialog(target) {
  pendingCalibration = { target };
  const label = target === 'top' ? 'Look Up' : 'Look Down';
  const direction = target === 'top' ? '向上看' : '向下看';

  confirmMessage.innerHTML = `
    <strong>${label}</strong><br>
    <span style="color: var(--text-secondary)">请${direction}，点击"开始"后保持 2 秒</span>
  `;
  confirmYesBtn.style.display = '';
  confirmYesBtn.textContent = 'Start';
  confirmNoBtn.textContent = 'Cancel';
  confirmDialog.classList.remove('hidden');
}

// Step 2: Start collection
async function startCollection() {
  if (!pendingCalibration) return;

  const target = pendingCalibration.target;
  const label = target === 'top' ? 'Look Up' : 'Look Down';
  const direction = target === 'top' ? '向上看' : '向下看';

  isCollecting = true;

  // 更新对话框显示采集中
  confirmMessage.innerHTML = `
    <span class="collecting"></span>
    <strong>${label}</strong><br>
    <span style="color: var(--text-secondary)">${direction}并保持... <span id="countdown">2s</span></span>
  `;
  confirmYesBtn.style.display = 'none';
  confirmNoBtn.textContent = 'Cancel';

  // 倒计时
  let countdown = 2;
  const countdownEl = document.getElementById('countdown');
  const countdownInterval = setInterval(() => {
    countdown--;
    if (countdownEl && countdown > 0) {
      countdownEl.textContent = `${countdown}s`;
    }
  }, 1000);

  try {
    // Start collection
    await fetch(`${API_BASE}/calibrate/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target })
    });

    // Wait 2 seconds
    await new Promise(r => setTimeout(r, 2000));

    // Stop and get result
    const res = await fetch(`${API_BASE}/calibrate/stop`, { method: 'POST' });
    const result = await res.json();

    clearInterval(countdownInterval);

    if (result.success) {
      pendingCalibration = { target, value: result.value };
      // 更新对话框显示结果
      confirmMessage.innerHTML = `
        <strong>${label}</strong> 采集完成<br>
        <span style="font-size: 0.9em; color: var(--text-secondary)">
          iris_y = ${result.value.toFixed(4)} (${result.samples_count} samples)
        </span>
      `;
      confirmYesBtn.style.display = '';
      confirmYesBtn.textContent = 'Confirm';
      confirmNoBtn.textContent = 'Retry';
    } else {
      confirmMessage.innerHTML = `<span style="color: var(--status-up)">${result.error || 'Failed'}</span>`;
      confirmYesBtn.style.display = 'none';
      confirmNoBtn.textContent = 'Close';
    }
  } catch (err) {
    console.error('Calibration error:', err);
    clearInterval(countdownInterval);
    confirmMessage.innerHTML = '<span style="color: var(--status-up)">Connection error</span>';
    confirmYesBtn.style.display = 'none';
    confirmNoBtn.textContent = 'Close';
  } finally {
    isCollecting = false;
  }
}

// Step 3: Confirm calibration
async function confirmCalibration() {
  if (!pendingCalibration) return;

  const { target, value } = pendingCalibration;
  const label = target === 'top' ? 'Look Up' : 'Look Down';

  hideConfirm();
  calibrationStatus.textContent = `${label} confirmed: ${value.toFixed(4)}`;
  calibrationStatus.className = 'success';
}

// Handle dialog button clicks
function handleYesClick() {
  if (isCollecting) return;

  if (pendingCalibration?.value !== undefined) {
    // Step 3: Confirm the calibration
    confirmCalibration();
  } else {
    // Step 2: Start collection
    startCollection();
  }
}

function handleNoClick() {
  if (isCollecting) {
    // Cancel during collection
    hideConfirm();
    return;
  }

  if (pendingCalibration?.value !== undefined) {
    // Retry
    const target = pendingCalibration.target;
    hideConfirm();
    showPrepareDialog(target);
  } else {
    // Cancel
    hideConfirm();
  }
}

// Save calibration to file
async function saveCalibration() {
  if (!saveCalibrationBtn) return;
  saveCalibrationBtn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/calibration/save`, { method: 'POST' });
    const result = await res.json();
    calibrationStatus.textContent = result.success ? 'Saved' : (result.error || 'Failed');
    calibrationStatus.className = result.success ? 'success' : '';
  } catch (err) {
    calibrationStatus.textContent = 'Save failed';
  } finally {
    saveCalibrationBtn.disabled = false;
  }
}

// Reset calibration
async function resetCalibration() {
  if (!resetCalibrationBtn) return;
  resetCalibrationBtn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/calibration/reset`, { method: 'POST' });
    const result = await res.json();
    calibrationStatus.textContent = result.success ? 'Reset' : (result.error || 'Failed');
    calibrationStatus.className = '';
  } catch (err) {
    calibrationStatus.textContent = 'Reset failed';
  } finally {
    resetCalibrationBtn.disabled = false;
  }
}

// Event listeners
if (calibrateTopBtn) calibrateTopBtn.addEventListener('click', () => showPrepareDialog('top'));
if (calibrateBottomBtn) calibrateBottomBtn.addEventListener('click', () => showPrepareDialog('bottom'));
if (saveCalibrationBtn) saveCalibrationBtn.addEventListener('click', saveCalibration);
if (resetCalibrationBtn) resetCalibrationBtn.addEventListener('click', resetCalibration);
if (confirmYesBtn) confirmYesBtn.addEventListener('click', handleYesClick);
if (confirmNoBtn) confirmNoBtn.addEventListener('click', handleNoClick);

// Main loop
async function mainLoop(timestamp) {
  const elapsed = timestamp - lastFrameTime;
  if (elapsed >= TARGET_FRAME_INTERVAL) {
    lastFrameTime = timestamp - (elapsed % TARGET_FRAME_INTERVAL);
    await fetchState();
  }
  requestAnimationFrame(mainLoop);
}

// Start
requestAnimationFrame(mainLoop);
