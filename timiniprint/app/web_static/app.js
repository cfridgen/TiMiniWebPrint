const $ = (id) => document.getElementById(id);
let I18N = { en: {}, de: {}, fr: {} };

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
let statusHistory = [];
let busyWaitCount = 0;
let busyPrintCount = 0;
let isPrinting = false;
let printAbortController = null;
let debugEntries = [];
let clientDebugEntries = [];
let debugPollTimer = null;
let debugRenderedText = '';
let debugUiEnabled = false;
let buildInfoState = {
  version: '',
  buildId: '',
  startedAt: '',
};
let currentLanguage = 'en';

function readStoredLanguage() {
  try {
    return localStorage.getItem('selectedLanguage');
  } catch (_err) {
    return null;
  }
}

function storeSelectedLanguage(language) {
  try {
    localStorage.setItem('selectedLanguage', language);
  } catch (_err) {
    // Ignore storage failures; language switching must keep working.
  }
}

function t(key, vars = {}) {
  const selected = I18N[currentLanguage] || I18N.en;
  let value = selected[key] || I18N.en[key] || key;
  Object.entries(vars).forEach(([name, raw]) => {
    value = value.replaceAll(`{${name}}`, String(raw));
  });
  return value;
}

function detectInitialLanguage() {
  const savedLang = readStoredLanguage();
  if (savedLang && ['de', 'en', 'fr'].includes(savedLang)) {
    return savedLang;
  }
  const browserLang = String(navigator.language || '').toLowerCase();
  if (browserLang.startsWith('de')) return 'de';
  if (browserLang.startsWith('fr')) return 'fr';
  return 'en';
}

async function loadTranslations() {
  const [enResponse, deResponse, frResponse] = await Promise.all([
    fetch('/static/i18n/en.json'),
    fetch('/static/i18n/de.json'),
    fetch('/static/i18n/fr.json'),
  ]);

  if (enResponse.ok) {
    I18N.en = await enResponse.json();
  }
  if (deResponse.ok) {
    I18N.de = await deResponse.json();
  }
  if (frResponse.ok) {
    I18N.fr = await frResponse.json();
  }
}

function applyStaticTranslations() {
  const appTitle = document.querySelector('.hero h1');
  const appSubtitle = document.querySelector('.hero p');
  if (appTitle) appTitle.textContent = t('app.title');
  if (appSubtitle) appSubtitle.textContent = t('app.subtitle');

  const statusHistoryTitle = document.querySelector('#statusHistoryPanel .status-history-title');
  if (statusHistoryTitle) statusHistoryTitle.textContent = t('status.recent');
  const debugTitle = document.querySelector('#debugLogPanel .status-history-title');
  if (debugTitle) debugTitle.textContent = t('debug.title');

  const printerLabel = document.querySelector('label[for="deviceSelect"]');
  if (printerLabel) printerLabel.textContent = t('printer.label');
  const textLabel = document.querySelector('#syncFontToggleRow label[for="text"]');
  if (textLabel) textLabel.textContent = t('text.label');
  const autoFillRow = document.querySelector('#syncFontToggleRow label');
  if (autoFillRow) {
    const checkbox = autoFillRow.querySelector('input');
    autoFillRow.innerHTML = '';
    if (checkbox) autoFillRow.appendChild(checkbox);
    autoFillRow.append(` ${t('text.autofill')}`);
  }
  const darknessLabel = document.querySelector('label[for="darkness"]');
  if (darknessLabel) darknessLabel.textContent = t('darkness.label');

  const fontOverlayTitle = document.querySelector('#fontOverlay .overlay-title');
  if (fontOverlayTitle) fontOverlayTitle.textContent = t('font.title');
  const sizeOverlayTitle = document.querySelector('#fontSizeOverlay .overlay-title');
  if (sizeOverlayTitle) sizeOverlayTitle.textContent = t('font.size.title');
  const smallHint = document.querySelector('#fontSizeOverlay .slider-hint');
  if (smallHint) smallHint.textContent = t('font.small');

  $('busyMessage').textContent = t('busy.pleaseWait');
  $('busyHideBtn').textContent = t('busy.hide');
  $('busyCancelBtn').textContent = t('busy.cancel');
  const printerBusyMessage = $('printerBusyMessage');
  if (printerBusyMessage) {
    printerBusyMessage.textContent = t('busy.scanningConnecting');
  }
  $('statusToastText').textContent = t('status.ready');
  $('refreshBtn').textContent = t('printer.refresh');
  $('fontBtn').textContent = t('font.button');
  $('fontSizeBtn').textContent = t('font.size.button');
  $('fontCancelBtn').textContent = t('button.cancel');
  $('fontOkBtn').textContent = t('button.ok');
  $('fontSizeCancelBtn').textContent = t('button.cancel');
  $('fontSizeOkBtn').textContent = t('button.ok');
  $('previewBtn').textContent = t('preview.refresh');
  if (!isPrinting) $('printBtn').textContent = t('print.label');
  if (!isConnecting) $('connectBtn').textContent = t('printer.connect');
  $('debugLogBtn').textContent = t('debug.button');
  $('debugRefreshBtn').textContent = t('debug.refresh');
  $('debugClearBtn').textContent = t('debug.clear');
  $('debugLogMeta').textContent = t('debug.noEntriesYet');
  if ($('debugLogText').value === '' || $('debugLogText').value === t('debug.noEntriesYet')) {
    $('debugLogText').value = t('debug.noEntriesYet');
  }

  $('statusHistoryBtn').title = t('status.historyTitle');
  $('debugLogBtn').title = t('debug.buttonTitle');
  $('connectSpinner').title = t('printer.spinner');
    const langMenuTitle = $('languageMenuTitle');
    if (langMenuTitle) {
      langMenuTitle.textContent = t('lang.menuTitle');
    }
    const langOptionDe = $('langOptionDe');
    if (langOptionDe) {
      langOptionDe.textContent = `🇩🇪 ${t('lang.german')}`;
    }
    const langOptionEn = $('langOptionEn');
    if (langOptionEn) {
      langOptionEn.textContent = `🇬🇧 ${t('lang.english')}`;
    }
    const langOptionFr = $('langOptionFr');
    if (langOptionFr) {
      langOptionFr.textContent = `🇫🇷 ${t('lang.french')}`;
    }
}

function updateLanguageToggle() {
  const btn = $('langToggleBtn');
  if (!btn) return;
  if (currentLanguage === 'de') {
    btn.textContent = '🇩🇪';
  } else if (currentLanguage === 'fr') {
    btn.textContent = '🇫🇷';
  } else {
    btn.textContent = '🇬🇧';
  }
  btn.title = t('lang.switch');
  btn.setAttribute('aria-label', t('lang.switch'));
}

function setLanguageMenuVisible(visible) {
  const wrapper = $('languageMenuWrapper');
  const panel = $('languageMenuPanel');
  const btn = $('langToggleBtn');
  if (!wrapper || !panel || !btn) {
    console.warn('Language menu wrapper/panel/button not found');
    return;
  }
  panel.classList.toggle('is-hidden', !visible);
  btn.classList.toggle('is-active', visible);
  btn.setAttribute('aria-expanded', visible ? 'true' : 'false');
}

function updateLanguageMenuState() {
  const langOptionDe = $('langOptionDe');
  const langOptionEn = $('langOptionEn');
  const langOptionFr = $('langOptionFr');
  
  if (langOptionDe) {
    const isActive = currentLanguage === 'de';
    if (isActive) {
      langOptionDe.classList.add('is-active');
      langOptionDe.setAttribute('aria-checked', 'true');
    } else {
      langOptionDe.classList.remove('is-active');
      langOptionDe.setAttribute('aria-checked', 'false');
    }
  }
  if (langOptionEn) {
    const isActive = currentLanguage === 'en';
    if (isActive) {
      langOptionEn.classList.add('is-active');
      langOptionEn.setAttribute('aria-checked', 'true');
    } else {
      langOptionEn.classList.remove('is-active');
      langOptionEn.setAttribute('aria-checked', 'false');
    }
  }
  if (langOptionFr) {
    const isActive = currentLanguage === 'fr';
    if (isActive) {
      langOptionFr.classList.add('is-active');
      langOptionFr.setAttribute('aria-checked', 'true');
    } else {
      langOptionFr.classList.remove('is-active');
      langOptionFr.setAttribute('aria-checked', 'false');
    }
  }
}

function initLanguageMenu() {
  const wrapper = $('languageMenuWrapper');
  const btn = $('langToggleBtn');
  const panel = $('languageMenuPanel');
  if (!wrapper || !btn || !panel) {
    console.warn('Language menu elements not found during init');
    return;
  }
  setLanguageMenuVisible(false);
  updateLanguageMenuState();
}

function setLanguage(language) {
  if (language === 'de') {
    currentLanguage = 'de';
  } else if (language === 'fr') {
    currentLanguage = 'fr';
  } else {
    currentLanguage = 'en';
  }
  storeSelectedLanguage(currentLanguage);
  document.documentElement.lang = currentLanguage;
  applyStaticTranslations();
  updateLanguageToggle();
  updateLanguageMenuState();
  updateColumnsLabel();
  updateFontSummary();
  renderFontOptions();
  _updateDebugUiDisplay();
  if (!connectedTarget) {
    setConnectionState(t('printer.notConnected'));
  }
  statusHistory = [t('status.ready')];
  log(t('status.ready'));
  renderDebugPanel(true);
}

function connectedBadge() {
  return t('runtime.connectedBadge');
}

function localizeRuntimeText(text) {
  let value = String(text);
  const replacements = (I18N[currentLanguage] && I18N[currentLanguage]['runtime.replacements']) || [];
  replacements.forEach((rule) => {
    if (!rule || !rule.pattern) {
      return;
    }
    const regex = new RegExp(rule.pattern, rule.flags || 'u');
    value = value.replace(regex, rule.replacement || '');
  });
  return value;
}

function nowIso() {
  return new Date().toISOString();
}

function formatBuildTime(ts) {
  if (!ts) {
    return t('meta.unknown');
  }
  const parsed = new Date(String(ts));
  if (Number.isNaN(parsed.getTime())) {
    return String(ts);
  }
  return parsed.toLocaleString(currentLanguage === 'de' ? 'de-DE' : 'en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

// ============================================================================
// Unified Debug Mode Management
// ============================================================================

async function setupDebugMode() {
  // Load build info from backend API
  await _loadBuildInfoFromBackend();
  
  // Initialize debug UI state (always starts disabled)
  debugUiEnabled = false;
  _updateDebugUiDisplay();
  _configureDebugUiVisibility(false);
  
  // Attach event handler for debug badge toggle
  _attachDebugToggleHandler();
}

async function toggleDebugMode() {
  debugUiEnabled = !debugUiEnabled;
  _updateDebugUiDisplay();
  _configureDebugUiVisibility(debugUiEnabled);
  
  if (!debugUiEnabled) {
    await setDebugPanelVisible(false);
    return;
  }
  
  addClientDebug('system', t('log.debugInit'));
  renderDebugPanel(true);
  await setDebugPanelVisible(true);
}

// Private helper: Load build info from backend
async function _loadBuildInfoFromBackend() {
  const el = $('buildInfo');
  if (!el) {
    return;
  }
  try {
    const res = await fetch('/api/build-info');
    if (!res.ok) {
      buildInfoState = {
        version: '',
        buildId: '',
        startedAt: '',
      };
      return;
    }
    const data = await res.json();
    buildInfoState = {
      version: data && data.version ? String(data.version) : '',
      buildId: data && data.build_id ? String(data.build_id) : '',
      startedAt: formatBuildTime(data && data.started_at ? data.started_at : ''),
    };
  } catch (_err) {
    buildInfoState = {
      version: '',
      buildId: '',
      startedAt: '',
    };
  }
}

// Private helper: Update the build info badge display
function _updateDebugUiDisplay() {
  const el = $('buildInfo');
  if (!el) {
    return;
  }
  if (!debugUiEnabled) {
    el.textContent = t('debug.initialBadge');
    el.title = t('debug.enableMode');
    el.classList.add('is-debug-toggle');
    return;
  }
  el.classList.remove('is-debug-toggle');
  const versionText = buildInfoState.version || t('meta.notAvailable');
  const buildIdText = buildInfoState.buildId || t('meta.localBuild');
  const startedText = buildInfoState.startedAt || t('meta.notAvailable');
  el.textContent = `v${versionText} | ${buildIdText} | ${startedText}`;
  el.title = currentLanguage === 'de'
    ? `${t('debug.versionLabel')} ${versionText}\n${t('debug.buildLabel')} ${buildIdText}\n${t('debug.startedLabel')} ${startedText}`
    : `${t('debug.versionLabel')} ${versionText}\n${t('debug.buildLabel')} ${buildIdText}\n${t('debug.startedLabel')} ${startedText}`;
}

// Private helper: Configure debug UI element visibility
function _configureDebugUiVisibility(enabled) {
  const section = $('debugLogSection');
  const button = $('debugLogBtn');
  const autofillRow = $('syncFontToggleRow');
  
  if (section) {
    section.classList.toggle('is-enabled', enabled);
  }
  if (button) {
    button.style.display = enabled ? '' : 'none';
  }
  if (autofillRow) {
    autofillRow.style.display = enabled ? 'flex' : 'none';
  }
  
  if (!enabled) {
    stopDebugPolling();
  }
}

// Private helper: Attach debug badge click toggle handler
function _attachDebugToggleHandler() {
  const buildInfoButton = $('buildInfo');
  if (buildInfoButton) {
    buildInfoButton.addEventListener('click', async () => {
      await toggleDebugMode();
    });
  }
}

function addClientDebug(kind, message, context = null) {
  if (!debugUiEnabled) {
    return;
  }
  clientDebugEntries.push({
    ts: nowIso(),
    kind,
    message,
    context,
  });
  if (clientDebugEntries.length > 40) {
    clientDebugEntries = clientDebugEntries.slice(clientDebugEntries.length - 40);
  }
}

function log(msg) {
  const text = localizeRuntimeText(String(msg || ''));
  addClientDebug('ui', text);
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

function renderDebugPanel(force = false) {
  if (!debugUiEnabled) {
    return;
  }
  const textField = $('debugLogText');
  const meta = $('debugLogMeta');
  if (!textField || !meta) {
    return;
  }
  const mergedEntries = [...debugEntries, ...clientDebugEntries]
    .sort((left, right) => String(left.ts || '').localeCompare(String(right.ts || '')));

  const latest = mergedEntries.length > 0 ? mergedEntries[mergedEntries.length - 1] : null;
  const nextText = mergedEntries.length > 0
    ? mergedEntries.map((entry) => formatDebugEntry(entry)).join('\n\n')
    : t('debug.noEntriesYet');

  const hasSelection = textField.selectionStart !== textField.selectionEnd;
  const isFocused = document.activeElement === textField;
  const preserveSelection = !force && isFocused && hasSelection;

  if (preserveSelection && nextText !== debugRenderedText) {
    meta.textContent = `${mergedEntries.length} entries (latest: ${latest && latest.ts ? latest.ts : t('meta.notAvailable')}, paused while selecting)`;
    return;
  }

  if (mergedEntries.length === 0) {
    debugRenderedText = nextText;
    textField.value = nextText;
    meta.textContent = t('debug.noEntries');
    return;
  }

  meta.textContent = `${mergedEntries.length} entries (latest: ${latest.ts || t('meta.notAvailable')})`;

  if (nextText !== debugRenderedText) {
    const oldScrollTop = textField.scrollTop;
    const wasNearBottom = (textField.scrollHeight - textField.clientHeight - textField.scrollTop) < 12;
    debugRenderedText = nextText;
    textField.value = nextText;
    if (wasNearBottom) {
      textField.scrollTop = textField.scrollHeight;
    } else {
      textField.scrollTop = oldScrollTop;
    }
  }
}

async function refreshDebugLog(showErrors = true) {
  if (!debugUiEnabled) {
    return;
  }
  try {
    const res = await fetch('/api/debug/logs?limit=160');
    const data = await parseJsonOrLog(res, 'Debug log failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      addClientDebug('error', 'Debug log request failed', data);
      renderDebugPanel();
      if (showErrors) {
        log(`Debug log failed: ${JSON.stringify(data)}`);
      }
      return;
    }
    debugEntries = Array.isArray(data.entries) ? data.entries : [];
    renderDebugPanel();
  } catch (err) {
    addClientDebug('error', `Debug log fetch failed: ${err}`);
    renderDebugPanel();
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
  if (!debugUiEnabled) {
    return;
  }
  const panel = $('debugLogPanel');
  const statusPanel = $('statusHistoryPanel');
  const meta = $('debugLogMeta');
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

  if (meta) {
    meta.textContent = t('debug.loading');
  }
  await refreshDebugLog(false);
  stopDebugPolling();
  debugPollTimer = setInterval(() => {
    refreshDebugLog(false).catch(() => {});
  }, 1200);
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
  el.textContent = localizeRuntimeText(text);
  el.classList.remove('is-scanning', 'is-connected', 'is-error');
  if (stateClass) {
    el.classList.add(stateClass);
  }
}

function setBusy(active, msg = t('busy.pleaseWait'), mode = 'wait') {
  const globalOverlay = $('busyOverlay');
  const globalMsgEl = $('busyMessage');
  const cancelBtn = $('busyCancelBtn');
  const printerOverlay = $('printerBusyOverlay');
  const printerMsgEl = $('printerBusyMessage');

  if (mode === 'print') {
    if (!globalOverlay) return;
    if (globalMsgEl) globalMsgEl.textContent = msg;
    if (cancelBtn) {
      cancelBtn.classList.toggle('is-hidden', false);
    }
    if (active) {
      globalOverlay.classList.remove('is-force-hidden');
    }
    globalOverlay.classList.toggle('is-active', active);
    if (!active) {
      globalOverlay.classList.remove('is-force-hidden');
    }
    return;
  }

  if (printerMsgEl) printerMsgEl.textContent = msg;
  if (printerOverlay) {
    printerOverlay.classList.toggle('is-active', active);
  }
}

function beginBusy(msg, mode = 'wait') {
  if (mode === 'print') {
    busyPrintCount += 1;
  } else {
    busyWaitCount += 1;
  }
  setBusy(true, msg, mode);
}

function endBusy(mode = 'wait') {
  if (mode === 'print') {
    busyPrintCount = Math.max(0, busyPrintCount - 1);
    if (busyPrintCount === 0) {
      setBusy(false, t('busy.pleaseWait'), 'print');
    }
    return;
  }

  busyWaitCount = Math.max(0, busyWaitCount - 1);
  if (busyWaitCount === 0) {
    setBusy(false, t('busy.pleaseWait'), 'wait');
  }
}

function setConnecting(active) {
  isConnecting = active;
  if (active) {
    beginBusy(t('busy.scanningConnecting'), 'wait');
  } else {
    endBusy('wait');
  }
  const spinner = $('connectSpinner');
  const connectBtn = $('connectBtn');
  if (active) {
    spinner.classList.add('is-active');
    connectBtn.disabled = true;
    connectBtn.textContent = t('printer.connecting');
    return;
  }
  spinner.classList.remove('is-active');
  connectBtn.textContent = t('printer.connect');
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
  option.textContent = localizeRuntimeText(labelText);
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
    return t('font.defaultBuiltIn');
  }
  const family = font.family === 'serif' ? t('font.family.serif') : t('font.family.sans');
  const width = font.width === 'fixed' ? t('font.width.fixed') : t('font.width.variable');
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
  if (!debugUiEnabled) {
    return;
  }
  if (!$('syncFontToggle') || !$('syncFontToggle').checked) return;
  const selectedFont = fontByKey(selectedFontKey);
  const fontLabel = selectedFont ? selectedFont.label : t('font.noSelection');
  $('text').value = `${fontLabel}\n${currentColumnsValue()} cpl`;
}

function updateFontSummary() {
  const selectedFont = fontByKey(selectedFontKey);
  $('fontLabel').textContent = selectedFont ? selectedFont.label : t('font.noSelection');
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
    { title: t('font.group.serif.fixed'), family: 'serif', width: 'fixed' },
    { title: t('font.group.serif.variable'), family: 'serif', width: 'variable' },
    { title: t('font.group.sans.fixed'), family: 'sans', width: 'fixed' },
    { title: t('font.group.sans.variable'), family: 'sans', width: 'variable' },
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
        <div class="font-sample" style="font-family: ${font.css_family}, sans-serif;">${t('font.sample')}</div>
      `;
      option.addEventListener('click', () => {
        pendingFontKey = font.key;
        selectedFontKey = font.key;
        renderFontOptions();
        updateFontSummary();
        if (debugUiEnabled) {
          syncTextToFontSummary();
        }
        renderPreview(false).catch((err) => log(t('log.previewFailed', { error: err })));
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
      log(t('log.fontListFailed', { error: JSON.stringify(data) }));
      return;
    }
    fontCatalog = Array.isArray(data.fonts) ? data.fonts : [];
    if (fontCatalog.length === 0) {
      log(t('log.noBundledFonts'));
      return;
    }
    const defaultKey = data.default_font_key || fontCatalog[0].key;
    selectedFontKey = defaultKey;
    pendingFontKey = defaultKey;
    updateFontSummary();
  } catch (err) {
    log(t('log.fontListFailed', { error: err }));
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
    renderPreview(false).catch((err) => log(t('log.previewFailed', { error: err })));
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
  beginBusy(t('busy.scanning'), 'wait');
  setConnectionState(t('connection.scanning'), 'is-scanning');
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
      log(t('log.scanFailed', { error: JSON.stringify(data) }));
      setConnectionState(t('connection.scanFailed'), 'is-error');
      return;
    }

    select.innerHTML = '';
    data.devices.forEach((d) => {
      const opt = document.createElement('option');
      opt.value = d.address;
      opt.dataset.profileKey = d.profile_key || '';
      opt.dataset.connected = d.connected ? 'true' : 'false';
      const name = d.display_name || t('device.unknown');
      const badge = d.connected ? ` ${connectedBadge()}` : '';
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
      setConnectionState(t('log.noSupportedPrinters'), 'is-error');
      updateConnectButtonState();
      log(t('log.noSupportedPrinters'));
      return;
    }

    const active = data.active_printer;
    if (active && active.target) {
      connectedTarget = active.target;
      connectedProfileKey = active.profile_key || selectedDeviceProfile();
      upsertConnectedOption(
        connectedTarget,
        connectedProfileKey,
        `${active.display_name || connectedTarget} (${connectedTarget}) ${active.transport_badge || ''} ${connectedBadge()}`.trim()
      );
      setConnectionState(t('connection.connected', { name: active.display_name || connectedTarget }), 'is-connected');
      updateConnectButtonState();
      log(t('log.usingActivePrinter', { name: active.display_name || connectedTarget }));
      return;
    }

    connectedTarget = null;
    connectedProfileKey = selectedDeviceProfile();
    updateConnectButtonState();
    setConnectionState(t('connection.autoconnect'), 'is-scanning');
    await connectSelected(true);
    if (!connectedTarget) {
      setConnectionState(t('connection.autoconnectFailed'), 'is-error');
    }
  } catch (err) {
    log(t('log.scanFailed', { error: err }));
    setConnectionState(t('connection.scanFailed'), 'is-error');
    updateConnectButtonState();
  } finally {
    endBusy('wait');
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
  log(t('connection.scanning'));
  await loadProfiles();
});

async function connectSelected(autoConnect = false) {
  const target = selectedDeviceTarget();
  if (!target) {
    if (!autoConnect) {
      log(t('log.noPrinterSelected'));
    }
    return;
  }
  setConnectionState(autoConnect ? t('connection.autoconnect') : t('log.connecting'), 'is-scanning');
  setConnecting(true);
  log(autoConnect ? t('log.autoConnecting') : t('log.connecting'));
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
      log(t('log.connectFailed', { error: JSON.stringify(data) }));
      setConnectionState(t('printer.notConnected'), 'is-error');
      return;
    }
    connectedTarget = target;
    connectedProfileKey = data.profile_key || selectedDeviceProfile();
    upsertConnectedOption(
      connectedTarget,
      connectedProfileKey,
      `${data.display_name || target} (${connectedTarget}) ${data.transport_badge || ''} ${connectedBadge()}`.trim()
    );
    setConnectionState(t('connection.connected', { name: data.display_name || target }), 'is-connected');
    updateConnectButtonState();
    log(t('log.connectedTo', { name: data.display_name || target }));
  } catch (err) {
    log(t('log.connectFailed', { error: err }));
    setConnectionState(t('printer.notConnected'), 'is-error');
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
    renderPreview(false).catch((err) => log(t('log.previewFailed', { error: err })));
  }
});

$('fontSizeOkBtn').addEventListener('click', (e) => {
  e.stopPropagation();
  $('fontSizeOverlay').classList.add('is-hidden');
  updateColumnsLabel();
  renderPreview(false).catch((err) => log(t('log.previewFailed', { error: err })));
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
  renderPreview(false).catch((err) => log(t('log.previewFailed', { error: err })));
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

  const lmw = $('languageMenuWrapper');
  const lmp = $('languageMenuPanel');
  const ltb = $('langToggleBtn');
  if (lmw && lmp && ltb && !lmp.classList.contains('is-hidden')) {
    const clickedInsidePanel = lmp.contains(e.target);
    const clickedToggle = ltb.contains(e.target);
    if (!clickedInsidePanel && !clickedToggle) {
      setLanguageMenuVisible(false);
    }
  }
});

async function renderPreview(manual = false) {
  if (manual) {
    log(t('log.renderingPreview'));
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
      log(t('log.previewFailed', { error: JSON.stringify(data) }));
      return;
    }
    // Ignore stale responses when user types quickly and newer requests are in flight.
    if (requestId !== previewRequestSeq) {
      return;
    }
    $('preview').src = data.image_data;
    $('preview').classList.add('is-visible');
    log(t('log.previewReady', { width: data.width, height: data.height }));
  } catch (err) {
    log(t('log.previewFailed', { error: err }));
  }
}

$('printBtn').addEventListener('click', async () => {
  if (isPrinting) {
    log(t('log.printInProgress'));
    return;
  }
  log(t('log.printing'));
  isPrinting = true;
  printAbortController = new AbortController();
  $('printBtn').disabled = true;
  $('printBtn').textContent = t('print.printing');
  beginBusy(t('busy.printing'), 'print');
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
      log(t('log.printFailed', { error: JSON.stringify(data) }));
      return;
    }
    log(data.message);
  } catch (err) {
    if (err && err.name === 'AbortError') {
      log(t('log.printCancelled'));
      return;
    }
    log(t('log.printFailed', { error: err }));
  } finally {
    isPrinting = false;
    printAbortController = null;
    $('printBtn').disabled = false;
    $('printBtn').textContent = t('print.label');
    endBusy('print');
  }
});

$('busyHideBtn').addEventListener('click', () => {
  $('busyOverlay').classList.add('is-force-hidden');
});

$('busyCancelBtn').addEventListener('click', () => {
  $('busyOverlay').classList.add('is-force-hidden');
  if (isPrinting && printAbortController) {
    log(t('log.cancellingPrint'));
    try {
      printAbortController.abort();
    } catch (err) {
      log(t('log.cancelFailed', { error: err }));
    }
  }
});

$('columns').addEventListener('input', () => {
  updateColumnsLabel();
  if (debugUiEnabled) {
    syncTextToFontSummary();
  }
  schedulePreview();
});

$('columns').addEventListener('change', () => {
  updateColumnsLabel();
  if (debugUiEnabled) {
    syncTextToFontSummary();
  }
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
      log(t('log.debugClearFailed', { error: JSON.stringify(data) }));
      return;
    }
    log(data.message || t('log.debugCleared'));
    await refreshDebugLog(false);
  } catch (err) {
    log(t('log.debugClearFailed', { error: err }));
  }
});

// Bind language menu handlers explicitly (not optional chaining)
function setupLanguageMenuHandlers() {
  const btn = $('langToggleBtn');
  const optDe = $('langOptionDe');
  const optEn = $('langOptionEn');
  const optFr = $('langOptionFr');
  const panel = $('languageMenuPanel');
  
  if (!btn || !optDe || !optEn || !optFr || !panel) {
    console.error('Language menu elements missing: btn=' + !!btn + ', optDe=' + !!optDe + ', optEn=' + !!optEn + ', optFr=' + !!optFr + ', panel=' + !!panel);
    return;
  }

  btn.addEventListener('click', function(e) {
    e.stopPropagation();
    const isOpen = !panel.classList.contains('is-hidden');
    setLanguageMenuVisible(!isOpen);
  });

  optDe.addEventListener('click', function(e) {
    e.stopPropagation();
    setLanguage('de');
    setLanguageMenuVisible(false);
  });

  optEn.addEventListener('click', function(e) {
    e.stopPropagation();
    setLanguage('en');
    setLanguageMenuVisible(false);
  });

  optFr.addEventListener('click', function(e) {
    e.stopPropagation();
    setLanguage('fr');
    setLanguageMenuVisible(false);
  });
}

window.addEventListener('resize', () => {
  positionFontOverlay();
});

async function init() {
  await loadTranslations();
  setLanguage(detectInitialLanguage());
  setupLanguageMenuHandlers();
  initLanguageMenu();
  await setupDebugMode();
  updateColumnsLabel();
  await loadFonts();
  await loadProfiles();
  updateConnectButtonState();
  await renderPreview(false);
}

init().catch((err) => log(String(err)));
