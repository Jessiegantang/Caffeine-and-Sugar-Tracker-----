const API_BASE = 'http://localhost:8000';

export async function fetchLogsApi() {
  const response = await fetch(`${API_BASE}/api/logs`);
  if (!response.ok) throw new Error('Failed to fetch logs');
  return response.json();
}

export async function syncLogsApi(logs) {
  const response = await fetch(`${API_BASE}/api/sync_logs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(logs)
  });
  if (!response.ok) throw new Error('Failed to sync logs');
  return response.json();
}

export async function deleteLogApi(id) {
  const response = await fetch(`${API_BASE}/api/logs/${id}`, {
    method: 'DELETE'
  });
  if (!response.ok) throw new Error('Failed to delete log');
  return response.json();
}

export async function logDrinkApi(logData) {
  const response = await fetch(`${API_BASE}/api/log_drink`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(logData)
  });
  if (!response.ok) throw new Error('Failed to log drink');
  return response.json();
}

export async function fetchDailyAgentInsightsApi(date) {
  const response = await fetch(`${API_BASE}/api/agent/daily_insights?date=${date}`);
  if (!response.ok) throw new Error('Failed to fetch daily insights');
  return response.json();
}

export async function fetchDailyReportApi(date) {
  const response = await fetch(`${API_BASE}/api/agent/reports/daily?date=${date}`);
  if (!response.ok) throw new Error('Failed to fetch daily report');
  return response.json();
}

export async function fetchWeeklyReportApi(date) {
  const response = await fetch(`${API_BASE}/api/agent/reports/weekly?date=${date}`);
  if (!response.ok) throw new Error('Failed to fetch weekly report');
  return response.json();
}

export async function saveSleepDataApi(date, hours) {
  const response = await fetch(`${API_BASE}/api/sleep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, sleep_hours: parseFloat(hours) })
  });
  if (!response.ok) throw new Error('Failed to save sleep data');
  return response.json();
}

export async function fetchChatHistoryApi(date) {
  const response = await fetch(`${API_BASE}/api/chat?date=${date}`);
  if (!response.ok) throw new Error('Failed to fetch chat history');
  return response.json();
}

export async function sendChatMessageApi(date, message) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, message })
  });
  if (!response.ok) throw new Error('Failed to send chat message');
  return response.json();
}

export async function parseIntakeApi(date, message) {
  const response = await fetch(`${API_BASE}/api/agent/parse_intake`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, message })
  });
  if (!response.ok) throw new Error('Failed to parse intake');
  return response.json();
}

export async function fetchUserPreferencesApi() {
  const response = await fetch(`${API_BASE}/api/user/preferences`);
  if (!response.ok) throw new Error('Failed to fetch user preferences');
  return response.json();
}

export async function clearUserPreferencesApi() {
  const response = await fetch(`${API_BASE}/api/user/preferences`, {
    method: 'DELETE'
  });
  if (!response.ok) throw new Error('Failed to clear user preferences');
  return response.json();
}

export async function createHealthPlanApi(date, goal) {
  const response = await fetch(`${API_BASE}/api/health/plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, goal })
  });
  if (!response.ok) throw new Error('Failed to create health plan');
  return response.json();
}

export async function fetchActiveHealthPlanApi() {
  const response = await fetch(`${API_BASE}/api/health/plans/active`);
  if (!response.ok) throw new Error('Failed to fetch active health plan');
  return response.json();
}

export async function refreshActiveHealthPlanApi(date) {
  const response = await fetch(`${API_BASE}/api/health/plans/active/progress?date=${date}`, {
    method: 'POST'
  });
  if (!response.ok) throw new Error('Failed to refresh health plan');
  return response.json();
}
