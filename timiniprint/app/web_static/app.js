const $ = (id) => document.getElementById(id);

function log(msg) {
  $("status").textContent = msg;
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
  try {
    const res = await fetch('/api/profiles');
    const data = await parseJsonOrLog(res, 'Profile load failed');
    if (!data) {
      return;
    }
    if (!res.ok) {
      log(`Profile load failed: ${JSON.stringify(data)}`);
      return;
    }
    const select = $('profile');
    select.innerHTML = '';
    data.profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.profile_key;
      opt.textContent = `${p.profile_key} (${p.width}px)`;
      select.appendChild(opt);
    });
  } catch (err) {
    log(`Profile load failed: ${err}`);
  }
}

function payloadBase() {
  return {
    text: $('text').value,
    bluetooth: $('bluetooth').value || null,
    serial: $('serial').value || null,
    device_config: $('deviceConfig').value || null,
    text_columns: Number($('columns').value || 15),
    text_hard_wrap: $('hardWrap').checked,
    darkness: Number($('darkness').value || 3),
  };
}

$('scanBtn').addEventListener('click', async () => {
  log('Scanning...');
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
      return;
    }
    const lines = data.devices
      .map((d) => `${d.display_name} (${d.address}) ${d.transport_badge}`)
      .join('\n');
    log(lines || 'No supported printers found.');
  } catch (err) {
    log(`Scan failed: ${err}`);
  }
});

$('previewBtn').addEventListener('click', async () => {
  log('Rendering preview...');
  try {
    const payload = payloadBase();
    payload.profile_key = $('profile').value || null;
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
    $('preview').src = data.image_data;
    $('preview').classList.add('is-visible');
    log(`Preview ready (${data.width}x${data.height}).`);
  } catch (err) {
    log(`Preview failed: ${err}`);
  }
});

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

loadProfiles().catch((err) => log(String(err)));
