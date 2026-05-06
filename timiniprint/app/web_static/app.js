const $ = (id) => document.getElementById(id);

function log(msg) {
  $("status").textContent = msg;
}

async function loadProfiles() {
  const res = await fetch('/api/profiles');
  const data = await res.json();
  const select = $('profile');
  select.innerHTML = '';
  data.profiles.forEach((p) => {
    const opt = document.createElement('option');
    opt.value = p.profile_key;
    opt.textContent = `${p.profile_key} (${p.width}px)`;
    select.appendChild(opt);
  });
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
  const res = await fetch('/api/scan', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({})
  });
  const data = await res.json();
  if (!res.ok) {
    log(`Scan failed: ${JSON.stringify(data)}`);
    return;
  }
  const lines = data.devices
    .map((d) => `${d.display_name} (${d.address}) ${d.transport_badge}`)
    .join('\n');
  log(lines || 'No supported printers found.');
});

$('previewBtn').addEventListener('click', async () => {
  log('Rendering preview...');
  const payload = payloadBase();
  payload.profile_key = $('profile').value || null;
  const res = await fetch('/api/preview', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!res.ok) {
    log(`Preview failed: ${JSON.stringify(data)}`);
    return;
  }
  $('preview').src = data.image_data;
  log(`Preview ready (${data.width}x${data.height}).`);
});

$('printBtn').addEventListener('click', async () => {
  log('Printing...');
  const res = await fetch('/api/print', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payloadBase())
  });
  const data = await res.json();
  if (!res.ok) {
    log(`Print failed: ${JSON.stringify(data)}`);
    return;
  }
  log(data.message);
});

loadProfiles().catch((err) => log(String(err)));
