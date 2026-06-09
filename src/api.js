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

export async function agentActApi(date, message) {
  const response = await fetch(`${API_BASE}/api/agent/act`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, message })
  });
  if (!response.ok) throw new Error('Failed to run agent action');
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

export async function fetchAgentTracesApi(limit = 5) {
  const response = await fetch(`${API_BASE}/api/agent/traces?limit=${limit}`);
  if (!response.ok) throw new Error('Failed to fetch agent traces');
  return response.json();
}

export async function fetchKnowledgeCandidatesApi(status = '') {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/candidates${query}`);
  if (!response.ok) throw new Error('Failed to fetch knowledge candidates');
  return response.json();
}

export async function createKnowledgeCandidateApi(candidate) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/candidates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(candidate)
  });
  if (!response.ok) throw new Error('Failed to create knowledge candidate');
  return response.json();
}

export async function fetchKnowledgeEvidenceApi(candidateId = '') {
  const query = candidateId ? `?candidate_id=${encodeURIComponent(candidateId)}` : '';
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/evidence${query}`);
  if (!response.ok) throw new Error('Failed to fetch knowledge evidence');
  return response.json();
}

export async function addKnowledgeEvidenceApi(candidateId, evidence) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/candidates/${candidateId}/evidence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(evidence)
  });
  if (!response.ok) throw new Error('Failed to add knowledge evidence');
  return response.json();
}

export async function approveKnowledgeEvidenceApi(evidenceId) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/evidence/${evidenceId}/approve`, {
    method: 'POST'
  });
  if (!response.ok) throw new Error('Failed to approve knowledge evidence');
  return response.json();
}

export async function approveKnowledgeEvidenceBulkApi(ids) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/evidence/bulk_approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to approve selected evidence'));
  return response.json();
}

export async function deleteKnowledgeEvidenceApi(evidenceId) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/evidence/${evidenceId}`, {
    method: 'DELETE'
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to delete knowledge evidence'));
  return response.json();
}

export async function deleteKnowledgeEvidenceBulkApi(ids) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/evidence/bulk/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to delete selected evidence'));
  return response.json();
}

export async function deleteKnowledgeCandidateApi(candidateId) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/candidates/${candidateId}`, {
    method: 'DELETE'
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to delete knowledge candidate'));
  return response.json();
}

export async function deleteKnowledgeCandidatesBulkApi(ids) {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/candidates/bulk/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids })
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to delete selected candidates'));
  return response.json();
}

export async function analyzeKnowledgeImageApi(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/image/analyze`, {
    method: 'POST',
    body: formData
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to analyze knowledge image'));
  return response.json();
}

export async function importKnowledgeImageItemsApi(items, sourceType = 'image_upload') {
  const response = await fetch(`${API_BASE}/api/knowledge/acquisition/image/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items, source_type: sourceType })
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, 'Failed to import knowledge image items'));
  return response.json();
}

async function readErrorMessage(response, fallback) {
  try {
    const data = await response.json();
    return data.detail || data.message || fallback;
  } catch (e) {
    return fallback;
  }
}
