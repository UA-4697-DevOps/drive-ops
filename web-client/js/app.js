/**
 * DriveOps – Orders Dashboard
 *
 * Fetches drivers and trip-requests from the driver-service via nginx proxy
 * and renders them as live-updating tables.
 *
 * All API calls go through nginx reverse proxy paths:
 *   /api/drivers            → driver-service:8082/drivers
 *   /api/v1/trip-requests   → driver-service:8082/api/v1/trip-requests
 */

'use strict';

const REFRESH_INTERVAL_MS = 10_000;

// -----------------------------------------------------------------------
// DOM refs
// -----------------------------------------------------------------------
const driversBody   = document.getElementById('drivers-body');
const driversCount  = document.getElementById('drivers-count');
const driversStatus = document.getElementById('drivers-status');

const tripsBody   = document.getElementById('trips-body');
const tripsCount  = document.getElementById('trips-count');
const tripsStatus = document.getElementById('trips-status');

const countdownEl  = document.getElementById('countdown');
const refreshBtn   = document.getElementById('refresh-btn');

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

/** Shorten a UUID to its first segment for display — less noisy in a table. */
function shortId(uuid) {
  if (!uuid) return '—';
  const parts = uuid.split('-');
  return `<span class="monospace" title="${uuid}">${parts[0]}…</span>`;
}

/** Map a status string to a coloured pill. */
function statusPill(status) {
  if (!status) return '<span class="pill pill-gray">—</span>';
  const s = String(status).toLowerCase();
  let cls = 'pill-gray';
  if (['active', 'online', 'completed', 'accepted', 'true'].includes(s))  cls = 'pill-green';
  if (['inactive', 'offline', 'rejected', 'false'].includes(s))           cls = 'pill-red';
  if (['pending', 'in_progress', 'assigned'].includes(s))                 cls = 'pill-yellow';
  if (['created', 'new'].includes(s))                                      cls = 'pill-blue';
  return `<span class="pill ${cls}">${status}</span>`;
}

/** Fetch JSON and return [data, null] or [null, errorString]. */
async function fetchJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
    const data = await res.json();
    return [data, null];
  } catch (err) {
    return [null, err.message];
  }
}

/** Set the status-dot colour: 'ok' | 'error' | '' */
function setStatus(dotEl, state) {
  dotEl.className = `status-dot ${state}`;
}

// -----------------------------------------------------------------------
// Render drivers
// -----------------------------------------------------------------------
async function loadDrivers() {
  const [drivers, err] = await fetchJSON('/api/drivers');

  if (err) {
    setStatus(driversStatus, 'error');
    driversCount.textContent = '!';
    driversBody.innerHTML = `<tr class="error-row"><td colspan="5">⚠ Failed to load drivers: ${err}</td></tr>`;
    return;
  }

  setStatus(driversStatus, 'ok');
  driversCount.textContent = drivers.length;

  if (drivers.length === 0) {
    driversBody.innerHTML = `<tr><td colspan="5" class="loading">No drivers found.</td></tr>`;
    return;
  }

  driversBody.innerHTML = drivers.map(d => `
    <tr>
      <td>${shortId(d.id)}</td>
      <td>${escapeHtml(d.first_name ?? '—')}</td>
      <td>${escapeHtml(d.last_name  ?? '—')}</td>
      <td>${escapeHtml(d.phone_number ?? '—')}</td>
      <td>${statusPill(d.is_active ? 'active' : 'inactive')}</td>
    </tr>
  `).join('');
}

// -----------------------------------------------------------------------
// Render trip requests
// -----------------------------------------------------------------------
async function loadTripRequests() {
  const [trips, err] = await fetchJSON('/api/v1/trip-requests');

  if (err) {
    setStatus(tripsStatus, 'error');
    tripsCount.textContent = '!';
    tripsBody.innerHTML = `<tr class="error-row"><td colspan="6">⚠ Failed to load trip requests: ${err}</td></tr>`;
    return;
  }

  setStatus(tripsStatus, 'ok');

  // The endpoint returns either an array or an object with a list key.
  const list = Array.isArray(trips) ? trips : (trips.trip_requests ?? trips.data ?? Object.values(trips));

  tripsCount.textContent = list.length;

  if (list.length === 0) {
    tripsBody.innerHTML = `<tr><td colspan="6" class="loading">No trip requests found.</td></tr>`;
    return;
  }

  tripsBody.innerHTML = list.map(t => `
    <tr>
      <td>${shortId(t.trip_id ?? t.id)}</td>
      <td>${escapeHtml(t.passenger_id ?? t.chat_id ?? '—')}</td>
      <td>${escapeHtml(t.origin      ?? t.pickup_location ?? '—')}</td>
      <td>${escapeHtml(t.destination ?? t.dropoff_location ?? '—')}</td>
      <td>${statusPill(t.status)}</td>
      <td>${shortId(t.driver_id ?? t.assigned_driver_id)}</td>
    </tr>
  `).join('');
}

// -----------------------------------------------------------------------
// XSS-safe string escaping
// -----------------------------------------------------------------------
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// -----------------------------------------------------------------------
// Countdown timer + auto-refresh
// -----------------------------------------------------------------------
let secondsLeft = REFRESH_INTERVAL_MS / 1000;

function tick() {
  secondsLeft -= 1;
  countdownEl.textContent = secondsLeft;
  if (secondsLeft <= 0) {
    refreshAll();
  }
}

function refreshAll() {
  secondsLeft = REFRESH_INTERVAL_MS / 1000;
  countdownEl.textContent = secondsLeft;
  loadDrivers();
  loadTripRequests();
}

refreshBtn.addEventListener('click', refreshAll);

// -----------------------------------------------------------------------
// Init
// -----------------------------------------------------------------------
(function init() {
  loadDrivers();
  loadTripRequests();
  setInterval(tick, 1000);
})();
