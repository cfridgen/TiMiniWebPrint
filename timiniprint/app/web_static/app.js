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

function log(msg) {
  $("status").textContent = msg;
}

function setConnectionState(text, stateClass = '') {
  const el = $('connectionState');
  el.textContent = text;
  el.classList.remove('is-scanning', 'is-connected', 'is-error');
  if (stateClass) {
    el.classList.add(stateClass);
  }
}

function setConnecting(active) {
  isConnecting = active;
  const spinner = $('connectSpinner');
  const connectBtn = $('connectBtn');
  if (active) {
    spinner.classList.add('is-active');
    connectBtn.disabled = true;
    connectBtn.textContent = 'Connecting...';
    return;
  }
  spinner.classList.remove('is-active');
  connectBtn.disabled = false;
  connectBtn.textContent = 'Connect';
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

function updateFontSummary() {
  const selectedFont = fontByKey(selectedFontKey);
  $('fontLabel').textContent = selectedFont ? selectedFont.label : 'No font selected';
  $('fontLabel').style.fontFamily = canUseFontForName(selectedFont)
    ? `${selectedFont.css_family}, sans-serif`
    : '';
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
        renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
      });
      grid.appendChild(option);
    });

    section.appendChild(grid);
    list.appendChild(section);
  });
}

function setFontPanelVisible(visible) {
  $('fontOverlay').classList.toggle('is-hidden', !visible);
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
      const name = d.display_name || 'Unknown';
      const badge = d.connected ? ' [connected]' : '';
      opt.textContent = `${name} (${d.address}) ${d.transport_badge || ''}${badge}`.trim();
      select.appendChild(opt);
    });

    if (data.devices.length === 0) {
      connectedTarget = null;
      connectedProfileKey = null;
      setConnectionState('No supported printers found.', 'is-error');
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
      log(`Using active printer: ${active.display_name || connectedTarget}.`);
      return;
    }

    connectedTarget = null;
    connectedProfileKey = selectedDeviceProfile();
    setConnectionState('Auto-connecting first detected printer...', 'is-scanning');
    await connectSelected(true);
  } catch (err) {
    log(`Scan failed: ${err}`);
    setConnectionState('Scan failed.', 'is-error');
  }
}

function payloadBase() {
  return {
    text: $('text').value,
    bluetooth: connectedTarget || selectedDeviceTarget(),
    serial: null,
    device_config: null,
    text_columns: currentColumnsValue(),
    text_hard_wrap: $('hardWrap').checked,
    text_font_key: selectedFontKey,
    darkness: Number($('darkness').value || 3),
  };
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
});

$('fontBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  previousFontKey = selectedFontKey;
  pendingFontKey = selectedFontKey;
  renderFontOptions();
  $('fontSizeOverlay').classList.add('is-hidden');
  setFontPanelVisible(true);
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
});

async function renderPreview(manual = false) {
  if (manual) {
    log('Rendering preview...');
  }
  const requestId = ++previewRequestSeq;
  try {
    const payload = payloadBase();
    payload.profile_key = connectedProfileKey || selectedDeviceProfile();
    const res = await fetch('/api/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
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
  log('Printing...');
  try {
    const res = await fetch('/api/print', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payloadBase())
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
    log(`Print failed: ${err}`);
  }
});

$('columns').addEventListener('input', () => {
  updateColumnsLabel();
  renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
});

$('text').addEventListener('input', () => {
  renderPreview(false).catch((err) => log(`Preview failed: ${err}`));
});

$('deviceSelect').addEventListener('change', () => {
  if (!connectedTarget) {
    connectedProfileKey = selectedDeviceProfile();
  }
});

async function init() {
  updateColumnsLabel();
  await loadFonts();
  await loadProfiles();
}

init().catch((err) => log(String(err)));
