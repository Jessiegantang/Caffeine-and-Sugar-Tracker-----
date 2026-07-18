import * as api from '../api.js';
import { state } from '../state.js';
import { saveLogs } from '../storage.js';

export function useAgentInsights() {
  let insightRequest = 0;

  async function syncLogsFromBackend() {
    const logs = await api.fetchLogsApi();
    if (!Array.isArray(logs)) return;
    state.logs = logs;
    saveLogs(logs);
  }

  async function analyzeLog(log) {
    state.agentStatus = 'loading';
    try {
      const data = await api.logDrinkApi(log);
      if (data.status !== 'success') {
        state.agentStatus = 'error';
        return;
      }
      state.lastNutritionResult = data.nutrition_result
        ? { ...data.nutrition_result, log_id: log.id, brand: log.brand, name: log.name, type: log.type, volume: log.volume }
        : null;
      state.agentAnalysis = data.agent_analysis || null;
      state.agentStatus = 'ready';
      try {
        await syncLogsFromBackend();
      } catch (error) {
        console.error('Failed to sync logs after agent analysis:', error);
      }
    } catch (error) {
      console.error('Agent API error:', error);
      state.agentStatus = 'error';
    }
  }

  async function refreshDailyInsights(date) {
    if (!date) return;
    const request = ++insightRequest;
    state.agentStatus = 'loading';
    try {
      const data = await api.fetchDailyAgentInsightsApi(date);
      if (request !== insightRequest || state.selectedDate !== date) return;
      state.agentAnalysis = data || null;
      state.agentStatus = 'ready';
      try {
        await syncLogsFromBackend();
      } catch (error) {
        console.error('Failed to sync logs after daily insights:', error);
      }
    } catch {
      if (request === insightRequest) state.agentStatus = 'error';
    }
  }

  return { analyzeLog, refreshDailyInsights, syncLogsFromBackend };
}
