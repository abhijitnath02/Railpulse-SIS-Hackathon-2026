const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// Item 9 (auth/RBAC): the dashboard's "simulate live delay event" button
// hits an operator-only endpoint now, so the demo needs a token. Rather
// than build a login screen for a hackathon demo dashboard, we silently
// log in as the seeded "operator" demo account on first use and cache the
// token in memory for the rest of the session. A real deployment would
// replace this with an actual login screen — see backend/seed.py for the
// demo credentials this stands in for.
let _demoTokenPromise = null;

async function getDemoOperatorToken() {
  if (!_demoTokenPromise) {
    _demoTokenPromise = fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: "operator", password: "operator123" }),
    })
      .then((res) => {
        if (!res.ok) throw new Error("Demo login failed");
        return res.json();
      })
      .then((data) => data.access_token);
  }
  return _demoTokenPromise;
}

async function request(path, options = {}) {
  // All read endpoints now require at least "viewer" role (see the
  // backend auth fix applied after the initial dashboard build — /trains,
  // /eta/journey, /anomalies, /historical/* were briefly open with no
  // auth at all, which was a real gap, not by design). The demo operator
  // token satisfies viewer-level checks too (roles are hierarchical), so
  // every request attaches it rather than only the explicitly
  // operator-only actions.
  const token = await getDemoOperatorToken();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {
      /* response wasn't JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

// Kept as an alias: every request is authed now, but call sites that were
// written expecting an explicitly-named "this needs auth" helper (the
// operator-only mutating actions below) still read clearly with this name.
const authedRequest = request;

export function listTrains() {
  return request("/trains");
}

export function getJourney(trainNo, currentStationCode) {
  const params = new URLSearchParams({ train_no: trainNo, current_station_code: currentStationCode });
  return request(`/eta/journey?${params.toString()}`);
}

export function simulateDelayEvent(trainNo, stationCode, extraMinutes) {
  // Requires operator (or admin) role — see backend/routers/simulate.py.
  return authedRequest("/simulate/delay-event", {
    method: "POST",
    body: JSON.stringify({ train_no: trainNo, station_code: stationCode, extra_minutes: extraMinutes }),
  });
}

export function subscribeToAlerts(trainNo, channel, destination, minDelayMinutes = 5.0) {
  return authedRequest("/alerts/subscribe", {
    method: "POST",
    body: JSON.stringify({
      train_no: trainNo,
      channel,
      destination,
      min_delay_minutes: minDelayMinutes,
    }),
  });
}

export function listAnomalies(limit = 10) {
  const params = new URLSearchParams({ limit: String(limit) });
  return request(`/anomalies?${params.toString()}`);
}

export function getHistoricalMeta() {
  return request("/historical/meta");
}

export function predictHistorical(payload) {
  return request("/historical/predict", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
