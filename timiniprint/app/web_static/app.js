const $ = (id) => document.getElementById(id);
let connectedTarget = null;
let connectedProfileKey = null;
let isConnecting = false;
let previewRequestSeq = 0;
let fontCatalog = [];
let selectedFontKey = null;
let pendingFontKey = null;
let previousFontKey = null;
let previousColumnsValue = null;
let previewDebounceTimer = null;
let statusHideTimer = null;
let statusHistory = ['Ready.'];
let busyLockCount = 0;
let isPrinting = false;
let printAbortController = null;
let debugEntries = [];
let debugPollTimer = null;

function log(msg) {
  const text = String(msg || '');
  statusHistory.push(text);
  if (statusHistory.length > 5) {
    statusHistory = statusHistory.slice(statusHistory.length - 5);
  }

  const toastText = $('statusToastText');
  const toast = $('statusToast');
  if (toastText && toast) {
    toastText.textContent = text;
    toast.classList.add('is-visible');
    if (statusHideTimer) {
      clearTimeout(statusHideTimer);
    }
    statusHideTimer = setTimeout(() => {
      toast.classList.remove('is-visible');
      statusHideTimer = null;
    }, 2800);
  }

  const list = $('statusHistoryList');
  if (list) {
    list.innerHTML = '';
    [...statusHistory].reverse().forEach((entry) => {
      const item = document.createElement('li');
      item.textContent = entry;
      list.appendChild(item);
    });
  }
}

function formatDebugEntry(entry) {
  const ts = entry && entry.ts ? String(entry.ts) : '';
  const kind = entry && entry.kind ? String(entry.kind).toUpperCase() : 'INFO';
  const message = entry && entry.message ? String(entry.message) : '';
  const context = entry && entry.context ? JSON.stringify(entry.context) : '';
  return context ? `${ts} [${kind}] ${message}\n${context}` : `${ts} [${kind}] ${message}`;
}

function renderDebugPanel() {
  const list = $('debugLogList');
  const meta = $('debugLogMeta');
  if (!list || !meta) {
    return;
  }
  list.innerHTML = '';
  if (!Array.isArray(debugEntries) || debugEntries.length === 0) {
    const item = document.createElement('li');
    item.textContent = 'No debug entries yet.';
    list.appendChild(item);
    meta.textContent = 'No debug entries.';
    return;
  }

  const latest = debugEntries[debugEntries.length - 1];
  meta.textContent = `${debugEntries.length} entries (latest: ${latest.ts || 'n/a'})`;

  [...debugEntries].reverse().forEach((entry) => {
    const item = document.createElement('li');
    item.textContent = formatDebugEntry(entry);
    list.appendChild(item);
  });
}

async function refreshDebugLog(showErrors = true) {
  try {
    const res = await fetch('/api/debug/logs?limit=160');
    const data = await parseJsonOrLog(res, 'Debug log failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      if (showErrors) {
        log(`Debug log failed: ${JSON.stringify(data)}`);
      }
      return;
    }
    debugEntries = Array.isArray(data.entries) ? data.entries : [];
    renderDebugPanel();
  } catch (err) {
    if (showErrors) {
      log(`Debug log failed: ${err}`);
    }
  }
}

function stopDebugPolling() {
  if (debugPollTimer) {
    clearInterval(debugPollTimer);
    debugPollTimer = null;
  }
}

async function setDebugPanelVisible(visible) {
  const panel = $('debugLogPanel');
  const statusPanel = $('statusHistoryPanel');
  if (!panel) {
    return;
  }
  panel.classList.toggle('is-hidden', !visible);
  if (statusPanel && visible) {
    statusPanel.classList.add('is-hidden');
  }
  if (!visible) {
    stopDebugPolling();
    return;
  }

  await refreshDebugLog(false);
  stopDebugPolling();
  debugPollTimer = setInterval(() => {
    refreshDebugLog(false).catch(() => {});
  }, 3000);
}

function updateConnectButtonState() {
  const connectBtn = $('connectBtn');
  if (!connectBtn) {
    return;
  }
  const select = $('deviceSelect');
  const selected = selectedDeviceTarget();
  const selectedOption = select ? select.options[select.selectedIndex] : null;
  const alreadyConnected = Boolean(
    (selectedOption && selectedOption.dataset.connected === 'true') ||
    (connectedTarget && selected && connectedTarget === selected)
  );
  connectBtn.disabled = isConnecting || !selected || alreadyConnected;
}

function setConnectionState(text, stateClass = '') {
  const el = $('connectionState');
  el.textContent = text;
  el.classList.remove('is-scanning', 'is-connected', 'is-error');
  if (stateClass) {
    el.classList.add(stateClass);
  }
}

function setBusy(active, msg = 'Bitte warten…', mode = 'wait') {
  const overlay = $('busyOverlay');
  const msgEl = $('busyMessage');
  const cancelBtn = $('busyCancelBtn');
  if (!overlay) return;
  if (msgEl) msgEl.textContent = msg;
  if (cancelBtn) {
    cancelBtn.classList.toggle('is-hidden', mode !== 'print');
  }
  if (active) {
    overlay.classList.remove('is-force-hidden');
  }
  overlay.classList.toggle('is-active', active);
  if (!active) {
    overlay.classList.remove('is-force-hidden');
  }
}

function beginBusy(msg, mode = 'wait') {
  busyLockCount += 1;
  setBusy(true, msg, mode);
}

function endBusy() {
  busyLockCount = Math.max(0, busyLockCount - 1);
  if (busyLockCount === 0) {
    setBusy(false);
  }
}

function setConnecting(active) {
  isConnecting = active;
  if (active) {
    beginBusy('Scanning / connecting printer…', 'wait');
  } else {
    endBusy();
  }
  const spinner = $('connectSpinner');
  const connectBtn = $('connectBtn');
  if (active) {
    spinner.classList.add('is-active');
    connectBtn.disabled = true;
    connectBtn.textContent = 'Connecting...';
    return;
  }
  spinner.classList.remove('is-active');
  connectBtn.textContent = 'Connect';
  updateConnectButtonState();
}

function upsertConnectedOption(target, profileKey, labelText) {
  const select = $('deviceSelect');
  let option = [...select.options].find((o) => o.value === target);
  if (!option) {
    option = document.createElement('option');
    option.value = target;
    select.appendChild(option);
  }
  option.dataset.profileKey = profileKey || option.dataset.profileKey || '';
  option.dataset.connected = 'true';
  option.textContent = labelText;
  select.value = target;
}

function selectedDeviceTarget() {
  const select = $('deviceSelect');
  return select.value || null;
}

function selectedDeviceProfile() {
  const select = $('deviceSelect');
  const option = select.options[select.selectedIndex];
  if (!option) {
    return null;
  }
  return option.dataset.profileKey || null;
}

function currentColumnsValue() {
  const sliderMin = Number($('columns').min || 15);
  const sliderMax = Number($('columns').max || 52);
  const sliderValue = Number($('columns').value || sliderMax);
  return sliderMax - sliderValue + sliderMin;
}

function fontByKey(fontKey) {
  return fontCatalog.find((font) => font.key === fontKey) || null;
}

function describeFont(font) {
  if (!font) {
    return 'Default built-in font';
  }
  const family = font.family === 'serif' ? 'Serif' : 'Sans';
  const width = font.width === 'fixed' ? 'Fixed width' : 'Variable width';
  return `${family}, ${width}`;
}

function isMostlyLatinText(text) {
  return /^[A-Za-z0-9\s.,:;!?()\-_'"+&/|]+$/.test(text);
}

function canUseFontForName(font) {
  if (!font || !font.css_family || !isMostlyLatinText(font.label || '')) {
    return false;
  }
  const marker = `${font.key || ''} ${font.label || ''} ${font.css_family || ''}`;
  return !/(symbol|emoji|icon|dingbat|material)/i.test(marker);
}

function syncTextToFontSummary() {
  if (!$('syncFontToggle') || !$('syncFontToggle').checked) return;
  const selectedFont = fontByKey(selectedFontKey);
  const fontLabel = selectedFont ? selectedFont.label : 'No font selected';
  $('text').value = `${fontLabel}\n${currentColumnsValue()} cpl`;
}

function updateFontSummary() {
  const selectedFont = fontByKey(selectedFontKey);
  $('fontLabel').textContent = selectedFont ? selectedFont.label : 'No font selected';
  $('fontLabel').style.fontFamily = canUseFontForName(selectedFont)
    ? `${selectedFont.css_family}, sans-serif`
    : '';
  $('text').style.fontFamily = selectedFont ? `${selectedFont.css_family}, sans-serif` : '';
  $('fontMeta').textContent = `${currentColumnsValue()} cpl`;
}

function renderFontOptions() {
  const list = $('fontList');
  list.innerHTML = '';
  const groups = [
    { title: 'Serif · Fixed Width', family: 'serif', width: 'fixed' },
    { title: 'Serif · Variable Width', family: 'serif', width: 'variable' },
    { title: 'Sans · Fixed Width', family: 'sans', width: 'fixed' },
    { title: 'Sans · Variable Width', family: 'sans', width: 'variable' },
  ];

  groups.forEach((group) => {
    const fonts = fontCatalog.filter((font) => font.family === group.family && font.width === group.width);
    if (fonts.length === 0) {
      return;
    }

    const section = document.createElement('div');
    section.className = 'font-group';

    const title = document.createElement('div');
    title.className = 'font-group-title';
    title.textContent = group.title;
    section.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'font-grid';

    fonts.forEach((font) => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'font-option';
      if (font.key === pendingFontKey) {
        option.classList.add('is-selected');
      }
      option.dataset.fontKey = font.key;
      const nameFont = canUseFontForName(font) ? `${font.css_family}, sans-serif` : 'inherit';
      option.innerHTML = `
        <div class="font-name" style="font-family: ${nameFont};">${font.label}</div>
        <div class="font-tags">${describeFont(font)}</div>
        <div class="font-sample" style="font-family: ${font.css_family}, sans-serif;">ABC 123 | The quick brown fox</div>
      `;
      option.addEventListener('click', () => {
        pendingFontKey = font.key;
        selectedFontKey = font.key;
        renderFontOptions();
        updateFontSummary();
        syncTextToFontSummary();
        renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
      });
      grid.appendChild(option);
    });

    section.appendChild(grid);
    list.appendChild(section);
  });
}

function setFontPanelVisible(visible) {
  const overlay = $('fontOverlay');
  overlay.classList.toggle('is-hidden', !visible);
  if (visible) {
    // Double rAF: first frame removes display:none, second frame has layout
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const selected = overlay.querySelector('.is-selected');
      if (!selected) return;
      // offsetTop of selected relative to overlay (the scroll container)
      const itemTop = selected.getBoundingClientRect().top - overlay.getBoundingClientRect().top + overlay.scrollTop;
      const itemHeight = selected.offsetHeight;
      overlay.scrollTop = itemTop - overlay.clientHeight / 2 + itemHeight / 2;
    }));
  }
}

function positionFontOverlay() {
  const overlay = $('fontOverlay');
  const trigger = $('fontBtn');
  if (!overlay || !trigger || overlay.classList.contains('is-hidden')) {
    return;
  }

  overlay.style.top = '';
  overlay.style.bottom = '';

  const triggerRect = trigger.getBoundingClientRect();
  const overlayHeight = Math.min(overlay.scrollHeight || 0, 430);
  const spaceBelow = window.innerHeight - triggerRect.bottom;
  const spaceAbove = triggerRect.top;
  const preferAbove = spaceAbove > spaceBelow && spaceAbove >= overlayHeight - 40;

  if (preferAbove) {
    overlay.style.top = `${-(overlayHeight - triggerRect.height)}px`;
    return;
  }

  overlay.style.top = 'calc(100% + 10px)';
}

async function loadFonts() {
  try {
    const res = await fetch('/api/fonts');
    const data = await parseJsonOrLog(res, 'Font list failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Font list failed: ${JSON.stringify(data)}`);
      return;
    }
    fontCatalog = Array.isArray(data.fonts) ? data.fonts : [];
    if (fontCatalog.length === 0) {
      log('No bundled fonts available.');
      return;
    }
    const defaultKey = data.default_font_key || fontCatalog[0].key;
    selectedFontKey = defaultKey;
    pendingFontKey = defaultKey;
    updateFontSummary();
  } catch (err) {
    log(`Font list failed: ${err}`);
  }
}

function updateColumnsLabel() {
  $('columnsValue').textContent = `${currentColumnsValue()} cpl`;
  updateFontSummary();
}

function editorTextValue() {
  return $('text').value || '';
}

function schedulePreview() {
  if (previewDebounceTimer) {
    clearTimeout(previewDebounceTimer);
  }
  previewDebounceTimer = setTimeout(() => {
    renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
  }, 120);
}

async function parseJsonOrLog(res, context) {
  try {
    return await res.json();
  } catch (err) {
    log(`${context}: invalid JSON response: ${err}`);
    return null;
  }
}

async function loadProfiles() {
  if (isConnecting) {
    return;
  }
  beginBusy('Scanning for printers…', 'wait');
  setConnectionState('Scanning for printers...', 'is-scanning');
  const select = $('deviceSelect');
  try {
    const res = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({})
    });
    const data = await parseJsonOrLog(res, 'Scan failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Scan failed: ${JSON.stringify(data)}`);
      setConnectionState('Scan failed.', 'is-error');
      return;
    }

    select.innerHTML = '';
    data.devices.forEach((d) => {
      const opt = document.createElement('option');
      opt.value = d.address;
      opt.dataset.profileKey = d.profile_key || '';
      opt.dataset.connected = d.connected ? 'true' : 'false';
      const name = d.display_name || 'Unknown';
      const badge = d.connected ? ' [connected]' : '';
      opt.textContent = `${name} (${d.address}) ${d.transport_badge || ''}${badge}`.trim();
      select.appendChild(opt);
    });

    if (Array.isArray(data.failures) && data.failures.length > 0) {
      data.failures.forEach((failure) => {
        log(`Scan warning [${failure.transport}]: ${failure.error}`);
        if (failure.hint) {
          log(`Scan hint [${failure.transport}]: ${failure.hint}`);
        }
        if (failure.details) {
          log(`Scan details [${failure.transport}]: ${JSON.stringify(failure.details)}`);
        }
      });
    }

    if (data.devices.length === 0) {
      connectedTarget = null;
      connectedProfileKey = null;
      setConnectionState('No supported printers found.', 'is-error');
      updateConnectButtonState();
      log('No supported printers found.');
      return;
    }

    const active = data.active_printer;
    if (active && active.target) {
      connectedTarget = active.target;
      connectedProfileKey = active.profile_key || selectedDeviceProfile();
      upsertConnectedOption(
        connectedTarget,
        connectedProfileKey,
        `${active.display_name || connectedTarget} (${connectedTarget}) ${active.transport_badge || ''} [connected]`.trim()
      );
      setConnectionState(`Connected: ${active.display_name || connectedTarget}`, 'is-connected');
      updateConnectButtonState();
      log(`Using active printer: ${active.display_name || connectedTarget}.`);
      return;
    }

    connectedTarget = null;
    connectedProfileKey = selectedDeviceProfile();
    updateConnectButtonState();
    setConnectionState('Auto-connecting first detected printer...', 'is-scanning');
    await connectSelected(true);
  } catch (err) {
    log(`Scan failed: ${err}`);
    setConnectionState('Scan failed.', 'is-error');
    updateConnectButtonState();
  } finally {
    endBusy();
  }
}

function payloadBase() {
  return {
    text: editorTextValue(),
    profile_key: connectedProfileKey || selectedDeviceProfile(),
    bluetooth: connectedTarget || selectedDeviceTarget(),
    serial: null,
    device_config: null,
    text_columns: currentColumnsValue(),
    text_font_key: selectedFontKey,
    darkness: Number($('darkness').value || 3),
  };
}

async function buildPrintPayload() {
  return payloadBase();
}

$('refreshBtn').addEventListener('click', async () => {
  log('Scanning for printers...');
  await loadProfiles();
});

async function connectSelected(autoConnect = false) {
  const target = selectedDeviceTarget();
  if (!target) {
    if (!autoConnect) {
      log('No printer selected.');
    }
    return;
  }
  setConnecting(true);
  log(autoConnect ? 'Auto-connecting...' : 'Connecting...');
  try {
    const res = await fetch('/api/connect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({target})
    });
    const data = await parseJsonOrLog(res, 'Connect failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Connect failed: ${JSON.stringify(data)}`);
      setConnectionState('Not connected.', 'is-error');
      return;
    }
    connectedTarget = target;
    connectedProfileKey = data.profile_key || selectedDeviceProfile();
    upsertConnectedOption(
      connectedTarget,
      connectedProfileKey,
      `${data.display_name || target} (${connectedTarget}) ${data.transport_badge || ''} [connected]`.trim()
    );
    setConnectionState(`Connected: ${data.display_name || target}`, 'is-connected');
    updateConnectButtonState();
    log(`Connected to ${data.display_name || target}.`);
  } catch (err) {
    log(`Connect failed: ${err}`);
    setConnectionState('Not connected.', 'is-error');
  } finally {
    setConnecting(false);
  }
}

$('connectBtn').addEventListener('click', async () => {
  await connectSelected(false);
});

$('previewBtn').addEventListener('click', async () => {
  await renderPreview(true);
});

$('fontSizeBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  previousColumnsValue = Number($('columns').value);
  $('fontOverlay').classList.add('is-hidden');
  $('fontSizeOverlay').classList.remove('is-hidden');
});

$('fontSizeCancelBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  $('fontSizeOverlay').classList.add('is-hidden');
  if (previousColumnsValue !== null) {
    $('columns').value = String(previousColumnsValue);
    updateColumnsLabel();
    renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
  }
});

$('fontSizeOkBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  $('fontSizeOverlay').classList.add('is-hidden');
  updateColumnsLabel();
  renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
});

$('fontBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  previousFontKey = selectedFontKey;
  pendingFontKey = selectedFontKey;
  renderFontOptions();
  $('fontSizeOverlay').classList.add('is-hidden');
  setFontPanelVisible(true);
  positionFontOverlay();
});

$('fontCancelBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  selectedFontKey = previousFontKey;
  pendingFontKey = previousFontKey;
  updateFontSummary();
  setFontPanelVisible(false);
  renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
});

$('fontOkBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  previousFontKey = selectedFontKey;
  setFontPanelVisible(false);
});

document.addEventListener('click', (e) => {
  const fso = $('fontSizeOverlay');
  if (fso && !fso.classList.contains('is-hidden') &&
      !fso.contains(e.target) && e.target.id !== 'fontSizeBtn') {
    fso.classList.add('is-hidden');
  }
  const fo = $('fontOverlay');
  if (fo && !fo.classList.contains('is-hidden') &&
      !fo.contains(e.target) && e.target.id !== 'fontBtn') {
    previousFontKey = selectedFontKey;
    fo.classList.add('is-hidden');
  }
  const shp = $('statusHistoryPanel');
  const shb = $('statusHistoryBtn');
  if (shp && !shp.classList.contains('is-hidden') &&
      !shp.contains(e.target) && e.target !== shb) {
    shp.classList.add('is-hidden');
  }
  const dlp = $('debugLogPanel');
  const dlb = $('debugLogBtn');
  if (dlp && !dlp.classList.contains('is-hidden') &&
      !dlp.contains(e.target) && e.target !== dlb) {
    setDebugPanelVisible(false).catch((err) => log(`Debug panel failed: ${err}`));
  }
});

async function renderPreview(manual = false) {
  if (manual) {
    log('Rendering preview...');
  }
  const requestId = ++previewRequestSeq;
  try {
    const res = await fetch('/api/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payloadBase())
    });
    const data = await parseJsonOrLog(res, 'Preview failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Preview failed: ${JSON.stringify(data)}`);
      return;
    }
    // Ignore stale responses when user types quickly and newer requests are in flight.
    if (requestId !== previewRequestSeq) {
      return;
    }
    $('preview').src = data.image_data;
    $('preview').classList.add('is-visible');
    log(`Preview ready (${data.width}x${data.height}).`);
  } catch (err) {
    log(`Preview failed: ${err}`);
  }
}

$('printBtn').addEventListener('click', async () => {
  if (isPrinting) {
    log('Print already in progress.');
    return;
  }
  log('Printing...');
  isPrinting = true;
  printAbortController = new AbortController();
  $('printBtn').disabled = true;
  $('printBtn').textContent = 'Printing...';
  beginBusy('Printing…', 'print');
  try {
    const payload = await buildPrintPayload();
    const res = await fetch('/api/print', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
      signal: printAbortController.signal,
    });
    const data = await parseJsonOrLog(res, 'Print failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Print failed: ${JSON.stringify(data)}`);
      return;
    }
    log(data.message);
  } catch (err) {
    if (err && err.name === 'AbortError') {
      log('Print request cancelled. Printer may continue if it already started.');
      return;
    }
    log(`Print failed: ${err}`);
  } finally {
    isPrinting = false;
    printAbortController = null;
    $('printBtn').disabled = false;
    $('printBtn').textContent = 'Print Label';
    endBusy();
  }
});

$('busyHideBtn').addEventListener('click', () => {
  $('busyOverlay').classList.add('is-force-hidden');
});

$('busyCancelBtn').addEventListener('click', () => {
  $('busyOverlay').classList.add('is-force-hidden');
  if (isPrinting && printAbortController) {
    log('Cancelling print request...');
    try {
      printAbortController.abort();
    } catch (err) {
      log(`Cancel request failed: ${err}`);
    }
  }
});

$('columns').addEventListener('input', () => {
  updateColumnsLabel();
  syncTextToFontSummary();
  schedulePreview();
});

$('columns').addEventListener('change', () => {
  updateColumnsLabel();
  syncTextToFontSummary();
  schedulePreview();
});

$('text').addEventListener('input', () => {
  schedulePreview();
});

$('deviceSelect').addEventListener('change', () => {
  if (!connectedTarget) {
    connectedProfileKey = selectedDeviceProfile();
  }
  updateConnectButtonState();
});

$('statusHistoryBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  setDebugPanelVisible(false).catch((err) => log(`Debug panel failed: ${err}`));
  $('statusHistoryPanel').classList.toggle('is-hidden');
});

$('debugLogBtn').addEventListener('click', async (e) => {
  e.stopPropagation();
  $('statusHistoryPanel').classList.add('is-hidden');
  const panel = $('debugLogPanel');
  const visible = panel.classList.contains('is-hidden');
  await setDebugPanelVisible(visible);
});

$('debugRefreshBtn').addEventListener('click', async (e) => {
  e.stopPropagation();
  await refreshDebugLog(true);
});

$('debugClearBtn').addEventListener('click', async (e) => {
  e.stopPropagation();
  try {
    const res = await fetch('/api/debug/clear', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({}),
    });
    const data = await parseJsonOrLog(res, 'Debug clear failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Debug clear failed: ${JSON.stringify(data)}`);
      return;
    }
    log(data.message || 'Debug log cleared.');
    await refreshDebugLog(false);
  } catch (err) {
    log(`Debug clear failed: ${err}`);
  }
});

window.addEventListener('resize', () => {
  positionFontOverlay();
});

async function init() {
  updateColumnsLabel();
  await loadFonts();
  await loadProfiles();
  updateConnectButtonState();
  await renderPreview(false);
}

init().catch((err) => log(String(err)));
