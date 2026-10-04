const $ = id => document.getElementById(id);
let initialized = false, lastAddress = '', refreshing = false;
async function api(path, value) {
  const response = await fetch('/api/' + path, value === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Surf-UI': '1'},
    body: JSON.stringify(value)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
function showInvitation(pairing) {
  $('invitation').hidden = !pairing.active;
  $('cancel').hidden = !pairing.active;
  $('pair').disabled = Boolean(pairing.active);
  if (pairing.publicAddress) lastAddress = pairing.publicAddress;
  $('address').textContent = lastAddress || 'Set your Umbrel LAN address above.';
  $('code').textContent = pairing.code || '';
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const state = await api('state');
    if (!initialized) {
      $('dashboard-url').value = state.settings.dashboard_url;
      $('public-address').value = state.settings.public_address;
      $('adaptive').checked = state.settings.adaptive_video;
      initialized = true;
    }
    $('status').textContent = state.ready ? `Surf ${state.server.version} is ready.` : state.message;
    showInvitation(state.pairing);
    $('pair').disabled = !state.ready || Boolean(state.pairing.active);
    $('candidates').replaceChildren();
    for (const candidate of state.candidates) {
      if (candidate.paired) continue;
      const p = document.createElement('p'), words = document.createElement('strong');
      p.textContent = `Verification for ${candidate.deviceName || 'iPad'}:`;
      words.textContent = candidate.phrase;
      p.append(words); $('candidates').append(p);
    }
    $('devices').replaceChildren();
    if (!state.devices.length) $('devices').textContent = 'No paired devices yet.';
    for (const device of state.devices) {
      const row = document.createElement('div'), name = document.createElement('span'), button = document.createElement('button');
      row.className = 'device'; name.textContent = device.name || device.deviceName || device.id;
      button.textContent = 'Revoke'; button.className = 'secondary';
      button.onclick = async () => {
        if (!confirm(`Revoke ${name.textContent}? It will need to pair again.`)) return;
        try { await api('revoke', {id: device.id}); await refresh(); }
        catch (error) { $('status').textContent = error.message; }
      };
      row.append(name, button); $('devices').append(row);
    }
  } catch (error) { $('status').textContent = error.message; }
  finally { refreshing = false; }
}
$('settings').onsubmit = async event => {
  event.preventDefault();
  const button = event.submitter; button.disabled = true;
  try {
    await api('settings', {dashboard_url: $('dashboard-url').value,
      public_address: $('public-address').value, adaptive_video: $('adaptive').checked});
    lastAddress = $('public-address').value;
    $('status').textContent = 'Saved. Surf is restarting and opening your dashboard…';
  } catch (error) { $('status').textContent = error.message; }
  finally { button.disabled = false; }
};
$('pair').onclick = async () => {
  $('pair').disabled = true;
  try { showInvitation(await api('pair', {})); }
  catch (error) { $('status').textContent = error.message; $('pair').disabled = false; }
};
$('cancel').onclick = async () => {
  try { await api('pair/cancel', {}); await refresh(); }
  catch (error) { $('status').textContent = error.message; }
};
refresh();
setInterval(refresh, 2500);
