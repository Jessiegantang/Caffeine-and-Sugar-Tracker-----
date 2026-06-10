// ==========================================
// Caffeine and Sugar Tracker - Main Coordinator
// ==========================================

import { PRESET_TEMPLATES, CAFFEINE_LIMIT, SUGAR_LIMIT, SWEETENER_SUGAR_DENSITIES } from './src/config.js';
import {
  calculateAlcohol
} from './src/calculator.js';
import {
  loadLogs,
  saveLogs,
  loadCustomDrinks,
  saveCustomDrinks,
  addDrinkToLibrary,
  getLogsForDate,
  getWeeklyLogs
} from './src/storage.js';
import { renderWeeklyChart } from './src/chart.js';
// Legacy rules import removed
import { 
  TYPE_DEFINITIONS, 
  getDrinkById, 
  searchDrinks,
  getAllDrinks,
  loadDatabaseAsync,
  getDatabase
} from './src/drinks-database.js';


import * as api from './src/api.js';
import { state, elements } from './src/state.js';
import { fetchChatHistory, handleSendMessage } from './src/components/ChatBox.js';
import { initDatabasePanel, renderDatabasePanel } from './src/components/DatabasePanel.js';

// Legacy Application State removed, now in src/state.js
function getElementByIdSafe(id, defaultValue = null) {
  const element = document.getElementById(id);
  return element || defaultValue;
}

// ==========================================
// Initialization
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {

  // Set default dates
  const todayStr = getLocalDateString();
  state.selectedDate = todayStr;
  state.calendarMonth = todayStr.slice(0, 7);
  elements.filterDate.value = todayStr;
  elements.inputDate.value = todayStr;

  await loadInitialData();
  setDefaultTimes();
  setupEventListeners();
  initDatabasePanel(() => renderHotDrinks());
  setupMemoryDebugApi();
  renderHotDrinks();
  renderApp();
  renderAgentWorkspace();
});

function setupMemoryDebugApi() {
  window.DrinkMindMemory = {
    list: () => api.fetchUserPreferencesApi(),
    clear: () => api.clearUserPreferencesApi()
  };
  window.DrinkMindPlans = {
    create: (goal, date = state.selectedDate) => api.createHealthPlanApi(date, goal),
    active: () => api.fetchActiveHealthPlanApi(),
    refresh: (date = state.selectedDate) => api.refreshActiveHealthPlanApi(date)
  };
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, '&#096;');
}

// Load from backend and fallback to local storage
async function loadInitialData() {
  await loadDatabaseAsync();
  state.customDrinks = loadCustomDrinks();
  
  try {
    const dbLogs = await api.fetchLogsApi();
    if (dbLogs && dbLogs.length > 0) {
      state.logs = dbLogs;
      saveLogs(state.logs);
    }
  } catch(e) {
    console.error('Failed to load logs from backend:', e);
  }
  
  // Fallback to local storage
  state.logs = loadLogs();
  
  // Auto-sync local logs to backend if backend was empty
  if (state.logs && state.logs.length > 0) {
    try {
      await api.syncLogsApi(state.logs);
      console.log('Synced local logs to backend');
    } catch(e) {
      console.error('Failed to sync local logs to backend', e);
    }
  }
}

// Get local date as YYYY-MM-DD
function getLocalDateString() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// Set default form times (Start = current, End = current + 30 mins)
function setDefaultTimes() {
  const now = new Date();
  const formatTime = (date) => {
    const hh = String(date.getHours()).padStart(2, '0');
    const mm = String(date.getMinutes()).padStart(2, '0');
    return `${hh}:${mm}`;
  };
  
  elements.inputStartTime.value = formatTime(now);
  
  // Default end time is 30 minutes later
  const future = new Date(now.getTime() + 30 * 60 * 1000);
  elements.inputEndTime.value = formatTime(future);
}

// ==========================================
// Event Listeners
// ==========================================
function setupEventListeners() {
  // Navigation Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const tabTarget = e.currentTarget.dataset.tab;
      
      // Update Tab CSS
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      
      // Update Content Panels
      document.querySelectorAll('.tab-content').forEach(panel => {
        panel.style.display = 'none';
      });
      const activePanel = document.getElementById(tabTarget);
      if (activePanel) {
        activePanel.style.display = 'block';
      }

      // Show/Hide main content wrapper based on tab
      const mainContent = document.getElementById('main-content');
      const leftSidebar = document.getElementById('workspace-left');
      
      if (tabTarget === 'tab-database') {
        mainContent.style.display = 'none';
        // Force render database panel after a short delay to ensure DOM is ready
        setTimeout(() => {
          renderDatabasePanel();
        }, 100);
      } else {
        mainContent.style.display = 'block';
        leftSidebar.style.display = 'block';
      }

      state.activeTab = tabTarget;
      renderApp();
    });
  });

  // Date Filters
  elements.filterDate.addEventListener('change', (e) => {
    state.selectedDate = e.target.value;
    state.calendarMonth = state.selectedDate.slice(0, 7);
    renderApp();
  });

  elements.calendarPrevMonth.addEventListener('click', () => {
    state.calendarMonth = shiftMonth(state.calendarMonth, -1);
    renderCalendar();
  });

  elements.calendarNextMonth.addEventListener('click', () => {
    state.calendarMonth = shiftMonth(state.calendarMonth, 1);
    renderCalendar();
  });

  // Time "Now" buttons
  elements.startTimeNow.addEventListener('click', () => {
    elements.inputStartTime.value = getCurrentTimeString();
  });
  
  elements.endTimeNow.addEventListener('click', () => {
    elements.inputEndTime.value = getCurrentTimeString();
  });

  // Volume presets
  document.querySelectorAll('.volume-preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      elements.inputVolume.value = e.target.dataset.vol;
    });
  });

  // Drink Search Input
  elements.drinkSearchInput.addEventListener('input', (e) => {
    const keyword = e.target.value.trim();
    if (keyword.length >= 2) {
      performDrinkSearch(keyword);
    } else {
      elements.drinkSearchResults.style.display = 'none';
    }
  });

  elements.drinkSearchBtn.addEventListener('click', () => {
    const keyword = elements.drinkSearchInput.value.trim();
    if (keyword) {
      performDrinkSearch(keyword);
    }
  });

  // Clear database drink reference on manual modification
  elements.inputBrand.addEventListener('input', () => {
    state.currentDrinkFromDatabase = null;
  });
  elements.inputName.addEventListener('input', () => {
    state.currentDrinkFromDatabase = null;
  });
  elements.form.querySelectorAll('input[name="drink-type"]').forEach(radio => {
    radio.addEventListener('change', () => {
      state.currentDrinkFromDatabase = null;
    });
  });

  // Form submit (Add log)
  elements.form.addEventListener('submit', (e) => {
    e.preventDefault();
    handleAddDrink();
  });

  // Sleep input
  const saveSleepBtn = document.getElementById('save-sleep-btn');
  if (saveSleepBtn) {
    saveSleepBtn.addEventListener('click', () => {
      const hours = document.getElementById('input-sleep').value;
      saveSleepData(state.selectedDate, hours);
    });
  }

  // Companion Chat Events
  document.getElementById('chat-send-btn')?.addEventListener('click', handleSendMessage);
  document.getElementById('chat-input')?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  });
  window.addEventListener('drinkmind:intake-parsed', (e) => {
    applyParsedIntakeToForm(e.detail);
  });
  window.addEventListener('drinkmind:nutrition-result', (e) => {
    state.lastNutritionResult = e.detail || null;
    renderNutritionExplainabilityPanel();
  });
  elements.nutritionExplainabilityPanel?.addEventListener('submit', (event) => {
    if (event.target?.id === 'nutrition-feedback-form') {
      event.preventDefault();
      handleNutritionFeedbackSubmit(event.target);
    }
  });
  document.getElementById('agent-refresh-btn')?.addEventListener('click', renderAgentWorkspace);
  document.getElementById('plan-create-btn')?.addEventListener('click', handleCreateVisiblePlan);
  document.getElementById('memory-clear-btn')?.addEventListener('click', async () => {
    await api.clearUserPreferencesApi();
    await renderAgentWorkspace();
  });

}

// Helper to get HH:MM of now
function getCurrentTimeString() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}

async function handleCreateVisiblePlan() {
  const input = document.getElementById('plan-goal-input');
  const goal = input?.value?.trim();
  if (!goal) return;
  await api.createHealthPlanApi(state.selectedDate, goal);
  input.value = '';
  await renderAgentWorkspace();
}

async function renderAgentWorkspace() {
  await Promise.allSettled([
    renderActivePlanPanel(),
    renderMemoryPanel(),
    renderTracePanel()
  ]);
  renderNutritionExplainabilityPanel();
}

async function renderActivePlanPanel() {
  const panel = document.getElementById('active-plan-panel');
  if (!panel) return;
  try {
    await api.refreshActiveHealthPlanApi(state.selectedDate);
    const data = await api.fetchActiveHealthPlanApi();
    const plan = data.plan;
    if (!plan) {
      panel.className = 'agent-panel-body muted';
      panel.textContent = 'No active plan';
      return;
    }
    const current = (plan.plan_content || []).find(item => item.day === plan.current_day) || (plan.plan_content || [])[0];
    panel.className = 'agent-panel-body';
    panel.innerHTML = `
      <div class="agent-kv"><span>Target</span><strong>${escapeHtml(plan.target)}</strong></div>
      <div class="agent-kv"><span>Day</span><strong>${plan.current_day}/${plan.total_days}</strong></div>
      ${current ? `<div class="agent-current-step">${escapeHtml(current.suggestion)}</div>` : ''}
      <div class="agent-plan-days">
        ${(plan.plan_content || []).map(item => `
          <span class="plan-day-pill status-${escapeHtml(item.status)}">${item.day}</span>
        `).join('')}
      </div>
    `;
  } catch (e) {
    panel.className = 'agent-panel-body muted';
    panel.textContent = 'Backend unavailable';
  }
}

async function renderMemoryPanel() {
  const panel = document.getElementById('memory-list');
  if (!panel) return;
  try {
    const data = await api.fetchUserPreferencesApi();
    const entries = Object.entries(data.preferences || {});
    if (entries.length === 0) {
      panel.className = 'agent-panel-body muted';
      panel.textContent = 'No memory';
      return;
    }
    panel.className = 'agent-panel-body';
    panel.innerHTML = entries.map(([key, value]) => `
      <div class="agent-kv"><span>${escapeHtml(key)}</span><strong>${escapeHtml(Array.isArray(value) ? value.join(', ') : value)}</strong></div>
    `).join('');
  } catch (e) {
    panel.className = 'agent-panel-body muted';
    panel.textContent = 'Backend unavailable';
  }
}

async function renderTracePanel() {
  const panel = document.getElementById('trace-list');
  if (!panel) return;
  try {
    const data = await api.fetchAgentTracesApi(5);
    const traces = data.traces || [];
    if (traces.length === 0) {
      panel.className = 'agent-panel-body muted';
      panel.textContent = 'No traces';
      return;
    }
    panel.className = 'agent-panel-body trace-stack';
    panel.innerHTML = traces.map(trace => `
      <div class="trace-row">
        <div><strong>${escapeHtml(trace.intent || 'unknown')}</strong><span>${escapeHtml(trace.final_action || '')}</span></div>
        <small>${escapeHtml((trace.agents_called || []).join(' > '))}</small>
      </div>
    `).join('');
  } catch (e) {
    panel.className = 'agent-panel-body muted';
    panel.textContent = 'Backend unavailable';
  }
}

function renderNutritionExplainabilityPanel() {
  const panel = elements.nutritionExplainabilityPanel || document.getElementById('nutrition-explainability-panel');
  if (!panel) return;

  const result = state.lastNutritionResult;
  if (!result) {
    panel.className = 'agent-panel-body muted';
    panel.textContent = 'No nutrition estimate yet';
    return;
  }

  const explainability = result.explainability || {};
  const components = explainability.components || result.composition?.components || [];
  const reasoning = explainability.reasoning || result.reasoning || [];
  const assumptions = explainability.assumptions || result.composition?.assumptions || [];
  const warnings = explainability.warnings || result.composition?.warnings || [];
  const usedComposition = Boolean(explainability.used_composition);
  const usedKnowledge = Boolean(explainability.used_knowledge_match);
  const retrievalScore = explainability.retrieval_score ?? result.retrieval_score;
  const matchedId = explainability.matched_knowledge_id ?? result.matched_knowledge_id;
  const feedback = explainability.feedback || result.feedback || null;
  const graphTrace = Array.isArray(explainability.graph_trace) ? explainability.graph_trace : [];
  const verification = explainability.verification || null;
  const confidenceValue = result.confidence ?? explainability.confidence ?? 0;
  const userSource = mapEstimateSource(result, explainability, feedback);
  const userExplanation = getEstimateExplanation(userSource, explainability, result);

  panel.className = 'agent-panel-body nutrition-explainability-body';
  panel.innerHTML = `
    <div class="estimate-result-summary">
      ${renderNutritionMetric('Caffeine', `${formatNumber(result.caffeine)} mg`)}
      ${renderNutritionMetric('Sugar', `${formatNumber(result.sugarContent)} g`)}
      ${renderNutritionMetric('Confidence', mapConfidenceLevel(confidenceValue))}
      ${renderNutritionMetric('Source', userSource)}
    </div>

    <div class="estimate-explanation">${escapeHtml(userExplanation)}</div>

    ${renderNutritionTechnicalDetails({
      result,
      explainability,
      usedKnowledge,
      matchedId,
      retrievalScore,
      usedComposition,
      components,
      reasoning,
      assumptions,
      warnings,
      graphTrace,
      verification,
      feedback
    })}
    ${renderNutritionFeedbackForm(result)}
  `;
}

function mapConfidenceLevel(value) {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return 'Low';
  if (num >= 0.8) return 'High';
  if (num >= 0.55) return 'Medium';
  return 'Low';
}

function mapEstimateSource(result, explainability, feedback) {
  const method = String(result.estimation_method || explainability.method || '').toLowerCase();
  const source = String(result.data_source || '').toLowerCase();
  if (feedback?.corrected || method.includes('feedback') || source.includes('user')) return 'User corrected';
  if (explainability.used_knowledge_match || result.matched_knowledge_id || source.includes('knowledge')) return 'Knowledge match';
  if (explainability.used_composition || result.composition || method.includes('composition')) return 'Composition estimate';
  return 'Fallback estimate';
}

function getEstimateExplanation(source, explainability, result) {
  if (source === 'User corrected') {
    return 'This estimate includes a user correction saved for this drink log.';
  }
  if (source === 'Knowledge match') {
    return 'This uses a reviewed drink knowledge match.';
  }
  if (source === 'Composition estimate') {
    return 'No trusted product match was found, so this was estimated from likely ingredients.';
  }
  if (result.feedback_notice) {
    return result.feedback_notice;
  }
  if (explainability.warnings?.length) {
    return 'This is a fallback estimate and may need correction if you have label details.';
  }
  return 'This is a fallback estimate based on the available drink details.';
}

function renderNutritionTechnicalDetails(details) {
  const {
    result,
    explainability,
    usedKnowledge,
    matchedId,
    retrievalScore,
    usedComposition,
    components,
    reasoning,
    assumptions,
    warnings,
    graphTrace,
    verification,
    feedback
  } = details;

  return `
    <details class="nutrition-technical-details">
      <summary>Technical details</summary>
      <div class="nutrition-technical-stack">
        <div class="nutrition-explain-section">
          <div class="nutrition-explain-title">Method</div>
          <div class="explain-chips">
            <span class="explain-chip">method: ${escapeHtml(result.estimation_method || explainability.method || 'Unknown')}</span>
            <span class="explain-chip">raw source: ${escapeHtml(result.data_source || 'Unknown')}</span>
          </div>
        </div>

        <div class="nutrition-explain-section">
          <div class="nutrition-explain-title">Knowledge match</div>
          <div class="explain-chips">
            <span class="explain-chip">used: ${usedKnowledge ? 'yes' : 'no'}</span>
            ${matchedId ? `<span class="explain-chip">id: ${escapeHtml(matchedId)}</span>` : ''}
            ${retrievalScore !== null && retrievalScore !== undefined ? `<span class="explain-chip">score: ${escapeHtml(Number(retrievalScore).toFixed(3))}</span>` : ''}
          </div>
        </div>

        ${renderLangGraphWorkflow(graphTrace, verification)}

        <div class="nutrition-explain-section">
          <div class="nutrition-explain-title">Composition</div>
          ${usedComposition
            ? renderComponentsTable(components)
            : '<div class="nutrition-empty-note">Not used; exact knowledge match was available.</div>'}
        </div>

        ${renderTextList('Reasoning', reasoning)}
        ${renderTextList('Assumptions', assumptions)}
        ${renderTextList('Warnings', warnings, 'warning')}
        ${renderFeedbackMetadata(feedback, result.feedback_notice)}
      </div>
    </details>
  `;
}

function renderLangGraphWorkflow(graphTrace, verification) {
  if (!graphTrace || graphTrace.length === 0) {
    return '';
  }

  const warnings = normalizeTextList(verification?.warnings || []);
  const issues = normalizeTextList(verification?.issues || []);
  const passed = verification?.passed;

  return `
    <div class="nutrition-explain-section langgraph-workflow-section">
      <div class="nutrition-explain-title">LangGraph 工作流</div>
      <ol class="langgraph-step-list">
        ${graphTrace.map((step, index) => `
          <li class="langgraph-step">
            <span class="langgraph-step-index">${index + 1}</span>
            <span class="langgraph-step-name">${escapeHtml(step)}</span>
          </li>
        `).join('')}
      </ol>
      ${verification ? `
        <div class="langgraph-verification">
          <div class="explain-chips">
            <span class="explain-chip">验证通过：${formatVerificationPassed(passed)}</span>
          </div>
          ${warnings.length ? renderInlineTextList('警告', warnings, 'warning') : ''}
          ${issues.length ? renderInlineTextList('问题', issues, 'issue') : ''}
        </div>
      ` : ''}
    </div>
  `;
}

function formatVerificationPassed(value) {
  if (value === undefined || value === null) return '未知';
  return value ? '是' : '否';
}

function renderInlineTextList(label, items, tone = '') {
  const values = normalizeTextList(items);
  if (values.length === 0) return '';
  return `
    <div class="langgraph-verification-list ${tone ? `tone-${tone}` : ''}">
      <span>${escapeHtml(label)}</span>
      <ul>
        ${values.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
      </ul>
    </div>
  `;
}

function showLogExplainability(log) {
  if (!log) return;
  if (log.explainability) {
    state.lastNutritionResult = {
      log_id: log.id,
      brand: log.brand,
      name: log.name,
      type: log.type,
      volume: log.volume,
      caffeine: log.caffeine,
      sugarContent: log.sugarContent,
      confidence: log.confidence,
      estimation_method: log.estimation_method,
      data_source: log.data_source,
      matched_knowledge_id: log.matched_knowledge_id,
      retrieval_score: log.retrieval_score,
      reasoning: normalizeTextList(log.reasoning),
      composition: log.composition || null,
      explainability: log.explainability
    };
  } else {
    state.lastNutritionResult = {
      log_id: log.id,
      brand: log.brand,
      name: log.name,
      type: log.type,
      volume: log.volume,
      caffeine: log.caffeine,
      sugarContent: log.sugarContent,
      confidence: log.confidence,
      estimation_method: log.estimation_method || 'Unknown',
      data_source: log.data_source || 'Unknown',
      matched_knowledge_id: log.matched_knowledge_id || null,
      retrieval_score: log.retrieval_score ?? null,
      reasoning: ['No explainability saved for this log'],
      composition: null,
      explainability: {
        method: log.estimation_method || 'Unknown',
        used_composition: false,
        used_knowledge_match: Boolean(log.matched_knowledge_id),
        matched_knowledge_id: log.matched_knowledge_id || null,
        retrieval_score: log.retrieval_score ?? null,
        confidence: log.confidence ?? 0,
        reasoning: ['No explainability saved for this log'],
        components: [],
        assumptions: [],
        warnings: ['No explainability saved for this log']
      }
    };
  }
  renderNutritionExplainabilityPanel();
  document.getElementById('agent-workspace')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderNutritionMetric(label, value) {
  return `
    <div class="nutrition-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderComponentsTable(components) {
  if (!components || components.length === 0) {
    return '<div class="nutrition-empty-note">No components returned.</div>';
  }
  return `
    <div class="nutrition-component-list">
      ${components.map(component => `
        <div class="nutrition-component-row">
          <div>
            <strong>${escapeHtml(component.name || 'component')}</strong>
            <span>${escapeHtml(component.category || 'unknown')}</span>
          </div>
          <div>${escapeHtml(formatAmount(component.amount, component.unit))}</div>
          <div>${formatNumber(component.caffeine_mg)}mg</div>
          <div>${formatNumber(component.sugar_g)}g</div>
          <div>${formatConfidence(component.confidence ?? 0)}</div>
          <small>${escapeHtml(component.basis || '')}</small>
        </div>
      `).join('')}
    </div>
  `;
}

function renderFeedbackMetadata(feedback, notice = '') {
  if (!feedback && !notice) return '';
  return `
    <div class="nutrition-explain-section feedback-summary">
      <div class="nutrition-explain-title">Feedback</div>
      ${notice ? `<div class="feedback-notice">${escapeHtml(notice)}</div>` : ''}
      ${feedback ? `
        <div class="explain-chips">
          <span class="explain-chip">source: ${escapeHtml(feedback.source_type || 'user_feedback')}</span>
          <span class="explain-chip">high delta: ${feedback.high_delta ? 'yes' : 'no'}</span>
        </div>
        ${feedback.source_note ? `<div class="nutrition-empty-note">${escapeHtml(feedback.source_note)}</div>` : ''}
      ` : ''}
    </div>
  `;
}

function renderNutritionFeedbackForm(result) {
  const logId = result?.log_id;
  if (!logId) return '';
  const corrected = result.explainability?.feedback?.corrected || result.feedback?.corrected || {};
  const brand = corrected.brand ?? result.brand ?? '';
  const name = corrected.name ?? result.name ?? '';
  const type = corrected.type ?? result.type ?? 'coffee';
  const volume = corrected.volume ?? result.volume ?? 500;
  const caffeine = corrected.caffeine ?? result.caffeine ?? 0;
  const sugarContent = corrected.sugarContent ?? result.sugarContent ?? 0;

  return `
    <form id="nutrition-feedback-form" class="nutrition-feedback-form" data-log-id="${escapeAttr(logId)}">
      <div class="nutrition-explain-title">Correct estimate</div>
      <div class="feedback-form-grid feedback-form-grid-simple">
        <label>Caffeine<input name="caffeine" type="number" min="0" max="800" step="0.1" value="${escapeAttr(caffeine)}" required></label>
        <label>Sugar<input name="sugarContent" type="number" min="0" max="150" step="0.1" value="${escapeAttr(sugarContent)}" required></label>
      </div>
      <label class="feedback-note-label">Source note<textarea name="source_note" rows="2" placeholder="Package label says caffeine 120mg, sugar 18g"></textarea></label>
      <div class="feedback-options">
        <label><input type="checkbox" name="apply_to_log" checked> Update this log</label>
      </div>
      <details class="feedback-advanced-details">
        <summary>Advanced correction fields</summary>
        <div class="feedback-form-grid">
          <label>Brand<input name="brand" value="${escapeAttr(brand)}"></label>
          <label>Name<input name="name" value="${escapeAttr(name)}" required></label>
          <label>Type<select name="type">${renderFeedbackTypeOptions(type)}</select></label>
          <label>Volume<input name="volume" type="number" min="10" max="2000" value="${escapeAttr(volume)}" required></label>
        </div>
        <div class="feedback-options">
          <label><input type="checkbox" name="submit_as_evidence"> Add to review queue</label>
        </div>
      </details>
      <div class="feedback-actions">
        <button type="submit" class="btn btn-primary">Submit correction</button>
        <span class="feedback-status" id="nutrition-feedback-status"></span>
      </div>
    </form>
  `;
}

function renderFeedbackTypeOptions(selected) {
  return Object.entries(TYPE_DEFINITIONS).map(([value, def]) => (
    `<option value="${escapeAttr(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(value)}</option>`
  )).join('');
}

function renderTextList(title, items, tone = '') {
  const list = normalizeTextList(items);
  if (list.length === 0) return '';
  return `
    <div class="nutrition-explain-section ${tone ? `tone-${tone}` : ''}">
      <div class="nutrition-explain-title">${escapeHtml(title)}</div>
      <ul class="nutrition-text-list">
        ${list.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
      </ul>
    </div>
  `;
}

function normalizeTextList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(item => typeof item === 'string' ? item : JSON.stringify(item));
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(item => String(item)) : [String(parsed)];
    } catch (e) {
      return [value];
    }
  }
  return [String(value)];
}

function formatAmount(amount, unit) {
  const numeric = Number(amount ?? 0);
  return `${Number.isFinite(numeric) ? numeric.toFixed(numeric % 1 === 0 ? 0 : 1) : amount} ${unit || ''}`.trim();
}

function formatNumber(value) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0';
}

async function handleNutritionFeedbackSubmit(form) {
  const status = document.getElementById('nutrition-feedback-status');
  const logId = form.dataset.logId;
  const submitAsEvidence = Boolean(form.elements.submit_as_evidence?.checked);
  const sourceNote = form.elements.source_note?.value.trim() || '';
  if (submitAsEvidence && !sourceNote) {
    if (status) {
      status.textContent = 'Evidence note is required for review queue.';
      status.className = 'feedback-status error';
    }
    return;
  }

  const payload = {
    corrected: {
      brand: form.elements.brand?.value.trim() || null,
      name: form.elements.name?.value.trim(),
      type: form.elements.type?.value,
      volume: Number(form.elements.volume?.value),
      caffeine: Number(form.elements.caffeine?.value),
      sugarContent: Number(form.elements.sugarContent?.value)
    },
    source_type: 'user_feedback',
    source_note: sourceNote,
    apply_to_log: Boolean(form.elements.apply_to_log?.checked),
    submit_as_evidence: submitAsEvidence
  };

  if (status) {
    status.textContent = 'Submitting...';
    status.className = 'feedback-status';
  }
  form.querySelector('button[type="submit"]')?.setAttribute('disabled', 'true');

  try {
    const data = await api.submitNutritionFeedbackApi(logId, payload);
    const updatedLog = data.log;
    if (payload.apply_to_log) {
      const dbLogs = await api.fetchLogsApi();
      state.logs = dbLogs || [];
      saveLogs(state.logs);
      renderApp();
    }
    const noticeParts = [];
    if (payload.apply_to_log) noticeParts.push('This log was updated.');
    if (data.evidence || payload.submit_as_evidence) noticeParts.push('Feedback added to review queue.');
    state.lastNutritionResult = buildNutritionResultFromLog(updatedLog, noticeParts.join(' ') || 'Feedback saved');
    renderNutritionExplainabilityPanel();
  } catch (e) {
    if (status) {
      status.textContent = e.message || 'Feedback failed';
      status.className = 'feedback-status error';
    }
  } finally {
    form.querySelector('button[type="submit"]')?.removeAttribute('disabled');
  }
}

function buildNutritionResultFromLog(log, notice = '') {
  return {
    log_id: log.id,
    brand: log.brand,
    name: log.name,
    type: log.type,
    volume: log.volume,
    caffeine: log.caffeine,
    sugarContent: log.sugarContent,
    confidence: log.confidence,
    estimation_method: log.estimation_method || 'Unknown',
    data_source: log.data_source || 'Unknown',
    matched_knowledge_id: log.matched_knowledge_id || null,
    retrieval_score: log.retrieval_score ?? null,
    reasoning: normalizeTextList(log.reasoning),
    composition: log.composition || null,
    explainability: log.explainability || {
      method: log.estimation_method || 'Unknown',
      used_composition: false,
      used_knowledge_match: Boolean(log.matched_knowledge_id),
      matched_knowledge_id: log.matched_knowledge_id || null,
      retrieval_score: log.retrieval_score ?? null,
      confidence: log.confidence ?? 0,
      reasoning: normalizeTextList(log.reasoning),
      components: [],
      assumptions: [],
      warnings: []
    },
    feedback_notice: notice
  };
}

// Helper to auto-fill the log form
function applyDrinkDataToForm(data) {
  state.currentDrinkFromDatabase = null; // Clear database drink link
  elements.inputBrand.value = data.brand || '';
  elements.inputName.value = data.name;
  elements.inputVolume.value = data.volume;
  elements.inputBaseSugarOverride.value = data.baseSugarOverride || '';
  
  // Set Radio for Drink Type
  const typeRadio = elements.form.querySelector(`input[name="drink-type"][value="${data.type}"]`);
  if (typeRadio) typeRadio.checked = true;
  
  // Set Radio for Sugar Level
  const sugarRadio = elements.form.querySelector(`input[name="sugar-level"][value="${data.sugar}"]`);
  if (sugarRadio) sugarRadio.checked = true;

  // Flash border to give visual cue
  const formSection = document.querySelector('.form-section');
  formSection.style.borderColor = 'var(--caffeine-primary)';
  setTimeout(() => {
    formSection.style.borderColor = 'var(--border-color)';
  }, 500);
}

function applyParsedIntakeToForm(parsedIntake) {
  if (!parsedIntake || parsedIntake.intent !== 'log_drink') return;
  if (parsedIntake.missing_fields && parsedIntake.missing_fields.length > 0) return;

  applyDrinkDataToForm({
    brand: parsedIntake.brand || '',
    name: parsedIntake.name,
    type: parsedIntake.type || 'coffee',
    sugar: parsedIntake.sugar || 'unknown',
    volume: parsedIntake.volume || 500
  });

  elements.inputDate.value = state.selectedDate;
  if (parsedIntake.time === 'now') {
    const current = getCurrentTimeString();
    elements.inputStartTime.value = current;
    elements.inputEndTime.value = current;
  } else if (/^\d{2}:\d{2}$/.test(parsedIntake.time || '')) {
    elements.inputStartTime.value = parsedIntake.time;
    elements.inputEndTime.value = parsedIntake.time;
  }
}

// ==========================================
// Log & Library Actions
// ==========================================

function handleAddDrink() {
  const logDate = elements.inputDate.value;
  const brand = elements.inputBrand.value.trim();
  const name = elements.inputName.value.trim();
  const type = elements.form.querySelector('input[name="drink-type"]:checked')?.value;
  const sugar = elements.form.querySelector('input[name="sugar-level"]:checked')?.value;
  const volume = parseInt(elements.inputVolume.value, 10);
  let abv = type === 'alcohol' ? inferAlcoholAbv(name) : 0;
  const startTime = elements.inputStartTime.value;
  const endTime = elements.inputEndTime.value;
  const baseSugarOverride = parseFloat(elements.inputBaseSugarOverride.value) || null;

  const saveLibrary = elements.saveToLibrary.checked;
  
  // Form validation
  const errors = [];
  if (!logDate) {
    errors.push('请选择日期');
  }
  if (!name || name.length < 2) {
    errors.push('请输入饮品名称');
  }
  if (!type) {
    errors.push('请选择饮品类型');
  }
  if (!sugar) {
    errors.push('请选择甜度');
  }
  if (isNaN(volume) || volume < 10 || volume > 2000) {
    errors.push('容量必须在10-2000ml之间');
  }
  
  if (errors.length > 0) {
    alert('请填写完整信息：\n' + errors.join('\n'));
    return;
  }

  console.log('=== handleAddDrink Debug ===');
  console.log('state.currentDrinkFromDatabase:', state.currentDrinkFromDatabase);
  console.log('name:', name);
  console.log('type:', type);
  console.log('sugar:', sugar);
  console.log('volume:', volume);
  console.log('baseSugarOverride:', baseSugarOverride);
  
  // Perform Calculations
  let caffeine = 0;
  let baseSugarDensity = baseSugarOverride !== null ? baseSugarOverride : 0;
  
  if (state.currentDrinkFromDatabase) {
    const drink = state.currentDrinkFromDatabase;
    // Override ABV from database if present
    if (type === 'alcohol' && drink.abv !== undefined) {
      abv = drink.abv;
    }
  }
  const sugarContent = 0;
  const alcoholContent = calculateAlcohol(volume, abv);

  const newLog = {
    id: 'log_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
    date: logDate,
    brand,
    name,
    type,
    sugar,
    volume,
    startTime,
    endTime,
    caffeine,
    sugarContent,
    isCalculating: true, // Optimistic UI flag
    alcoholContent,
    abv,
    baseSugarDensity
  };

  // Add to state and save
  state.logs.push(newLog);
  saveLogs(state.logs);

  // If checkbox is checked, save this drink to the library database
  if (saveLibrary) {
    state.customDrinks = addDrinkToLibrary(state.customDrinks, { brand, name, type, sugar, volume });
  }

  // Reset form and date picker
  elements.form.reset();
  elements.saveToLibrary.checked = false;
  elements.inputDate.value = logDate; // Retain current log date
  elements.inputBaseSugarOverride.value = ''; // Reset base sugar override
  setDefaultTimes();
  state.currentDrinkFromDatabase = null; // Clear database drink link

  // If logged on a different date, switch the view date filter so the user sees it immediately!
  if (state.selectedDate !== logDate) {
    state.selectedDate = logDate;
    state.calendarMonth = logDate.slice(0, 7);
    elements.filterDate.value = logDate;
  }

  renderApp();
  triggerAgentAnalysis(newLog);
}

// Delete a drink log
async function deleteLog(id) {
  state.logs = state.logs.filter(log => log.id !== id);
  saveLogs(state.logs);
  renderApp();
  
  try {
    await api.deleteLogApi(id);
    // Trigger Agent refresh for today so it recalculates without the deleted drink
    fetchDailyAgentInsights(state.selectedDate);
  } catch (e) {
    console.error('Failed to delete log from backend:', e);
  }
}

// Delete a custom drink library entry
function deleteLibraryItem(id, event) {
  event.stopPropagation(); // Avoid triggering form load
  state.customDrinks = state.customDrinks.filter(item => item.id !== id);
  saveCustomDrinks(state.customDrinks);
  renderApp();
}

// ==========================================
// Render Flow
// ==========================================

function renderApp() {
  // 1. Render always-visible library grid
  renderLibrary();

  if (state.activeTab === 'tab-daily') {
    renderDailyPanel();
    renderWeeklyPanel();
  } else if (state.activeTab === 'tab-database') {
    renderDatabasePanel();
  }
}

// Render Custom Drink Library
function renderLibrary() {
  elements.libraryCount.textContent = state.customDrinks.length;
  
  if (state.customDrinks.length === 0) {
    elements.libraryEmpty.style.display = 'block';
    elements.libraryGrid.style.display = 'none';
  } else {
    elements.libraryEmpty.style.display = 'none';
    elements.libraryGrid.style.display = 'grid';
    elements.libraryGrid.innerHTML = '';

    state.customDrinks.forEach(item => {
      const card = document.createElement('button');
      card.className = 'library-item';
      card.addEventListener('click', () => applyDrinkDataToForm(item));

      const brandSpan = document.createElement('span');
      brandSpan.className = 'chip-brand';
      brandSpan.textContent = item.brand || '自选';

      const nameSpan = document.createElement('span');
      nameSpan.className = 'chip-name';
      nameSpan.textContent = item.name;

      const sizeSpan = document.createElement('span');
      sizeSpan.className = 'chip-size';
      const sugarText = getSugarTextCN(item.sugar);
      sizeSpan.textContent = `${item.volume}ml (${sugarText})`;

      const delBtn = document.createElement('button');
      delBtn.className = 'library-item-del-btn';
      delBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      `;
      delBtn.title = '删除此常用饮品';
      delBtn.addEventListener('click', (e) => deleteLibraryItem(item.id, e));

      card.appendChild(brandSpan);
      card.appendChild(nameSpan);
      card.appendChild(sizeSpan);
      card.appendChild(delBtn);
      
      elements.libraryGrid.appendChild(card);
    });
  }
}

// Render DAILY dashboard tab
function renderDailyPanel() {
  const dateLogs = getLogsForDate(state.logs, state.selectedDate);

  // Compute Daily Totals
  const totalCaffeine = dateLogs.reduce((sum, l) => sum + l.caffeine, 0);
  const totalSugar = dateLogs.reduce((sum, l) => sum + l.sugarContent, 0);
  const totalAlcohol = dateLogs.reduce((sum, l) => sum + (l.alcoholContent || 0), 0);

  // Render Daily Gauges
  elements.caffeineTotal.textContent = totalCaffeine;
  elements.sugarTotal.textContent = totalSugar.toFixed(1);
  elements.alcoholTotal.textContent = totalAlcohol.toFixed(1);

  // Update SVG rings (circumference = 377)
  const updateRing = (el, val, max) => {
    const percentage = Math.min(val / max, 1);
    const offset = 377 - (percentage * 377);
    el.setAttribute('stroke-dashoffset', offset);
  };
  
  updateRing(elements.caffeineProgress, totalCaffeine, CAFFEINE_LIMIT);
  updateRing(elements.sugarProgress, totalSugar, SUGAR_LIMIT);

  // Render Daily Logs List
  renderDailyLogs(dateLogs);
  renderCalendar();

  // Run Daily Insights
  renderDailyInsights(dateLogs, totalCaffeine, totalSugar, totalAlcohol);
  fetchDailyAgentInsights(state.selectedDate);
}

function formatConfidence(value) {
  const confidence = Number(value ?? 1);
  return `${Math.round(confidence * 100)}%`;
}

function formatOptionalMeta(label, value) {
  if (value === undefined || value === null || value === '') return '';
  return `<span class="explain-chip">${label}: ${value}</span>`;
}

function renderReasoningItems(reasoning) {
  if (!reasoning) return '';
  try {
    const reasons = typeof reasoning === 'string' ? JSON.parse(reasoning) : reasoning;
    const list = Array.isArray(reasons) ? reasons : [String(reasons)];
    return list.map(r => `<li>${r}</li>`).join('');
  } catch(e) {
    return `<li>${reasoning}</li>`;
  }
}

function renderExplainability(log) {
  const hasExplainability = log.data_source || log.estimation_method || log.reasoning;
  if (!hasExplainability) return '';

  const retrievalScore = log.retrieval_score !== undefined && log.retrieval_score !== null
    ? Number(log.retrieval_score).toFixed(3)
    : null;

  return `
    <div class="log-explainability">
      <div class="explain-header">
        <span>Nutrition pipeline</span>
        ${log.confidence !== undefined ? `<strong>${formatConfidence(log.confidence)}</strong>` : ''}
      </div>
      <div class="explain-chips">
        ${formatOptionalMeta('source', log.data_source)}
        ${formatOptionalMeta('method', log.estimation_method)}
        ${formatOptionalMeta('knowledge', log.matched_knowledge_id)}
        ${formatOptionalMeta('retrieval', retrievalScore)}
        ${formatOptionalMeta('trace', log.agent_trace_id)}
      </div>
      ${log.reasoning ? `
        <ul class="explain-reasoning">
          ${renderReasoningItems(log.reasoning)}
        </ul>
      ` : ''}
    </div>
  `;
}

// Render Daily Logs
function renderDailyLogs(dateLogs) {
  elements.logsCount.textContent = dateLogs.length;

  if (dateLogs.length === 0) {
    elements.logsEmpty.style.display = 'block';
    elements.logsGrid.style.display = 'none';
  } else {
    elements.logsEmpty.style.display = 'none';
    elements.logsGrid.style.display = 'flex';
    elements.logsGrid.innerHTML = '';

    // Sort descending by start time
    const sortedLogs = [...dateLogs].sort((a, b) => b.startTime.localeCompare(a.startTime));

    sortedLogs.forEach(log => {
      const typeIcon = getTypeIcon(log.type);
      const sugarText = getSugarTextCN(log.sugar);
      const alcoholText = log.alcoholContent ? `<div class="log-stat-item"><span class="log-stat-label">估算酒精</span><span class="log-stat-val alcohol-num">${log.alcoholContent} g</span></div>` : '';

      const explainabilityBadge = log.explainability
        ? '<span class="log-explainability-badge is-saved">Explainable</span>'
        : '<span class="log-explainability-badge is-missing">No reasoning saved</span>';

      const logCard = document.createElement('div');
      logCard.className = `log-card type-${log.type}`;
      logCard.tabIndex = 0;
      logCard.title = 'View saved nutrition explainability';

      logCard.innerHTML = `
        <div class="log-card-left">
          <div class="log-type-icon">${typeIcon}</div>
          <div class="log-info-meta">
            <div class="log-title-row">
              ${log.brand ? `<span class="log-brand">${log.brand}</span>` : ''}
              <span class="log-name">${log.name}</span>
              <span class="log-type-badge">${getTypeTextCN(log.type)}</span>
              ${explainabilityBadge}
            </div>
            <div class="log-time-range">
              ⏰ 饮用时间：${log.startTime} - ${log.endTime} (${log.volume}ml | ${sugarText})
            </div>
            ${renderExplainability(log)}
          </div>
        </div>
        
        <div class="log-stats">
          ${log.isCalculating ? `
            <div class="log-stat-item" style="color: #a855f7; font-weight: 600;">
              <span class="log-stat-val">⏳ Agent 推断中...</span>
            </div>
          ` : `
            <div class="log-stat-item">
              <span class="log-stat-label">估算咖啡因</span>
              <span class="log-stat-val caffeine-num">${log.caffeine} mg</span>
            </div>
            <div class="log-stat-item">
              <span class="log-stat-label">估算糖分</span>
              <span class="log-stat-val sugar-num">${log.sugarContent} g</span>
            </div>
            ${alcoholText}
          `}
          <button type="button" class="log-del-btn" title="删除记录">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      `;

      logCard.querySelector('.log-del-btn').addEventListener('click', () => deleteLog(log.id));
      logCard.addEventListener('click', (event) => {
        if (event.target.closest('.log-del-btn')) return;
        showLogExplainability(log);
      });
      logCard.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          showLogExplainability(log);
        }
      });
      elements.logsGrid.appendChild(logCard);
    });
  }
}

// Render Daily Advice list
async function renderDailyInsights(dateLogs, totalCaffeine, totalSugar, totalAlcohol) {
  elements.insightsList.innerHTML = '<div style="color: #64748b; padding: 20px; text-align: center;">正在由 DrinkMind Agent 生成今日摄入分析...</div>';
  
  if (dateLogs.length === 0) {
    elements.insightsList.innerHTML = '';
    const item = document.createElement('div');
    item.className = `insight-item level-info`;
    item.innerHTML = `
      <div class="insight-icon">💧</div>
      <div class="insight-content">
        <h4>开始记录饮品</h4>
        <p>记录下今天的第一杯饮品，Agent 将自动为您生成有温度的摄入分析。</p>
      </div>
    `;
    elements.insightsList.appendChild(item);
    return;
  }
  
  try {
    const data = await api.fetchDailyReportApi(state.selectedDate);
    let dailyInsights = data.insights || [];
    
    elements.insightsList.innerHTML = '';
    if (dailyInsights.length === 0) {
      dailyInsights.push({
        level: 'success',
        title: '今日饮品摄入控制优秀！',
        message: '您的饮品摄入保持在完美的健康限值内，继续保持良好的状态！',
        icon: '✅'
      });
    }

  // Populate UI
    dailyInsights.forEach(ins => {
      const item = document.createElement('div');
      item.className = `insight-item level-${ins.level}`;
      item.innerHTML = `
        <div class="insight-icon">${ins.icon}</div>
        <div class="insight-content">
          <h4>${ins.title}</h4>
          <p>${ins.message}</p>
        </div>
      `;
      elements.insightsList.appendChild(item);
    });
  } catch (e) {
    elements.insightsList.innerHTML = '<div style="color: #ef4444; padding: 20px; text-align: center;">无法连接到 DrinkMind Agent。</div>';
  }
}

// Render WEEKLY trend tab
function renderWeeklyPanel() {
  const todayStr = getLocalDateString();
  const { weeklyLogs, weekDates } = getWeeklyLogs(state.logs, todayStr);

  // 1. Render Aggregates
  const totalCaffeine = weeklyLogs.reduce((sum, l) => sum + l.caffeine, 0);
  const totalSugar = weeklyLogs.reduce((sum, l) => sum + l.sugarContent, 0);
  const totalAlcohol = weeklyLogs.reduce((sum, l) => sum + (l.alcoholContent || 0), 0);

  // Calculate active tracking days
  const activeDays = new Set(weeklyLogs.map(l => l.date)).size;

  elements.weeklyCaffeineTotal.textContent = totalCaffeine;
  elements.weeklySugarTotal.textContent = totalSugar.toFixed(1);
  elements.weeklyAlcoholTotal.textContent = totalAlcohol.toFixed(1);
  elements.weeklyActiveDays.textContent = activeDays;

  // 2. Render SVG Weekly Bar Chart
  renderWeeklyChart(elements.weeklyChartContainer, state.logs, weekDates);

  // 3. Render Weekly Insights Warnings
  renderWeeklyInsights(weeklyLogs, weekDates);
}

// Render Weekly Insights
async function renderWeeklyInsights(weeklyLogs, weekDates) {
  elements.weeklyInsightsList.innerHTML = '<div style="color: #64748b; padding: 20px; text-align: center;">正在由 DrinkMind Agent 生成周度关联评估...</div>';
  
  if (weeklyLogs.length === 0) {
    elements.weeklyInsightsList.innerHTML = '<div style="color: #64748b; padding: 20px; text-align: center;">过去7天没有饮品记录。</div>';
    return;
  }
  
  try {
    // Fetch weekly report from agent
    const data = await api.fetchWeeklyReportApi(getLocalDateString());
    const weeklyInsights = data.insights || [];
    
    elements.weeklyInsightsList.innerHTML = '';
    
    if (weeklyInsights.length === 0) {
      const item = document.createElement('div');
      item.className = `insight-item level-success`;
      item.innerHTML = `
        <div class="insight-icon">🌟</div>
        <div class="insight-content">
          <h4>本周趋势完美</h4>
          <p>您本周的各项饮品指标保持在理想水平。</p>
        </div>
      `;
      elements.weeklyInsightsList.appendChild(item);
    } else {
      weeklyInsights.forEach(ins => {
        const item = document.createElement('div');
        item.className = `insight-item level-${ins.level}`;
        item.innerHTML = `
          <div class="insight-icon">${ins.icon}</div>
          <div class="insight-content">
            <h4>${ins.title}</h4>
            <p>${ins.message}</p>
          </div>
        `;
        elements.weeklyInsightsList.appendChild(item);
      });
    }
  } catch (e) {
    elements.weeklyInsightsList.innerHTML = '<div style="color: #ef4444; padding: 20px; text-align: center;">无法连接到 DrinkMind Agent。</div>';
  }
}

// ==========================================
// Localization Helpers
// ==========================================

function getSugarTextCN(sugar) {
  switch (sugar) {
    case 'none': return '不另外加糖 (0%)';
    case 'unknown': return '糖分未知 (自动估算)';
    case 'three': return '三分糖 (30%)';
    case 'half': return '半糖 (50%)';
    case 'seven': return '七分糖 (70%)';
    case 'full': return '全糖 (100%)';
    default: return '未知';
  }
}

function getTypeTextCN(type) {
  switch (type) {
    case 'coffee': return '咖啡';
    case 'teacoffee': return '茶咖';
    case 'tea': return '原叶茶';
    case 'milktea': return '奶茶';
    case 'fruittea': return '果茶';
    case 'soda': return '汽水';
    case 'alcohol': return '酒精';
    default: return '其他';
  }
}

function getTypeIcon(type) {
  switch (type) {
    case 'coffee': return '☕';
    case 'teacoffee': return '🥥';
    case 'tea': return '🍵';
    case 'milktea': return '🧋';
    case 'fruittea': return '🍋';
    case 'soda': return '🥤';
    case 'alcohol': return '🍺';
    default: return '🥤';
  }
}

function inferAlcoholAbv(name) {
  const lower = (name || '').toLowerCase();
  if (lower.includes('啤酒') || lower.includes('beer')) return 4.0;
  if (lower.includes('葡萄酒') || lower.includes('wine') || lower.includes('红酒')) return 12.0;
  if (lower.includes('鸡尾酒') || lower.includes('cocktail') || lower.includes('莫吉托')) return 12.0;
  if (lower.includes('威士忌') || lower.includes('whisky') || lower.includes('伏特加') || lower.includes('vodka')) return 40.0;
  return 5.0;
}

function shiftMonth(monthStr, delta) {
  const [year, month] = monthStr.split('-').map(Number);
  const d = new Date(year, month - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function renderCalendar() {
  if (!elements.calendarGrid || !state.calendarMonth) return;
  const [year, month] = state.calendarMonth.split('-').map(Number);
  const firstDay = new Date(year, month - 1, 1);
  const daysInMonth = new Date(year, month, 0).getDate();
  const startWeekday = (firstDay.getDay() + 6) % 7;

  elements.calendarMonthLabel.textContent = `${year}年${month}月`;
  elements.calendarGrid.innerHTML = '';

  const countsByDate = state.logs.reduce((acc, log) => {
    acc[log.date] = (acc[log.date] || 0) + 1;
    return acc;
  }, {});

  for (let i = 0; i < startWeekday; i++) {
    const blank = document.createElement('div');
    blank.className = 'calendar-day empty';
    elements.calendarGrid.appendChild(blank);
  }

  const todayStr = getLocalDateString();
  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'calendar-day';
    if (dateStr === state.selectedDate) btn.classList.add('selected');
    if (dateStr === todayStr) btn.classList.add('today');
    if (countsByDate[dateStr]) btn.classList.add('has-log');
    btn.innerHTML = `<span>${day}</span>${countsByDate[dateStr] ? `<small>${countsByDate[dateStr]}条</small>` : ''}`;
    btn.addEventListener('click', () => {
      state.selectedDate = dateStr;
      state.calendarMonth = dateStr.slice(0, 7);
      elements.filterDate.value = dateStr;
      elements.inputDate.value = dateStr;
      renderApp();
    });
    elements.calendarGrid.appendChild(btn);
  }
}

function performDrinkSearch(keyword) {
  const results = searchDrinks(keyword);
  
  if (results.length === 0) {
    elements.drinkSearchResults.style.display = 'none';
    return;
  }
  
  elements.drinkSearchResults.style.display = 'block';
  elements.drinkSearchResults.innerHTML = `
    <div class="search-results-header">找到 ${results.length} 个结果</div>
    <div class="search-results-list">
      ${results.map(item => `
        <button class="search-result-item" data-drink-id="${item.id}" data-drink-type="${item.type}">
          <span class="search-result-brand">${item.brand}</span>
          <span class="search-result-name">${item.name}</span>
          <span class="search-result-meta">${item.defaultVolume}ml</span>
          <span class="search-result-info">
            ☕ ${item.caffeine}mg | 🍬 ${item.baseSugar}g
          </span>
        </button>
      `).join('')}
    </div>
  `;
  
  document.querySelectorAll('.search-result-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const drinkId = btn.dataset.drinkId;
      const drinkType = btn.dataset.drinkType;
      loadDrinkFromDatabase(drinkId, drinkType);
      elements.drinkSearchResults.style.display = 'none';
      elements.drinkSearchInput.value = '';
    });
  });
}

function loadDrinkFromDatabase(drinkId, drinkType) {
  const drink = getDrinkById(drinkId);
  if (!drink) return;
  
  elements.inputBrand.value = drink.brand || '';
  elements.inputName.value = drink.name;
  elements.inputVolume.value = drink.defaultVolume;
  elements.inputBaseSugarOverride.value = drink.baseSugar || '';
  
  const typeRadio = elements.form.querySelector(`input[name="drink-type"][value="${drinkType}"]`);
  if (typeRadio) typeRadio.checked = true;
  
  const sugarRadio = elements.form.querySelector(`input[name="sugar-level"][value="none"]`);
  if (sugarRadio) sugarRadio.checked = true;
  
  state.currentDrinkFromDatabase = { ...drink, type: drinkType };
  
  const formSection = document.querySelector('.form-section');
  formSection.style.borderColor = 'var(--caffeine-primary)';
  setTimeout(() => {
    formSection.style.borderColor = 'var(--border-color)';
  }, 500);
}

function renderHotDrinks() {
  const hotDrinks = [
    'luckin-americano',
    'luckin-coconut-americano', 
    'luckin-latte',
    'cotti-americano',
    'starbucks-americano',
    'heytea-milk-tea',
    'mixue-milk-tea',
    'cola'
  ];
  
  const db = getDatabase();
  let html = '';
  hotDrinks.forEach(drinkId => {
    for (const [type, category] of Object.entries(db)) {
      const drink = category.items.find(item => item.id === drinkId);
      if (drink) {
        html += `
          <button class="template-chip" data-drink-id="${drinkId}" data-drink-type="${type}">
            <span class="chip-brand">${drink.brand}</span>
            <span class="chip-name">${drink.name}</span>
            <span class="chip-size">${drink.defaultVolume}ml</span>
          </button>
        `;
        break;
      }
    }
  });
  
  elements.hotDrinksList.innerHTML = html;
  
  document.querySelectorAll('.template-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const drinkId = btn.dataset.drinkId;
      const drinkType = btn.dataset.drinkType;
      if (drinkId && drinkType) {
        loadDrinkFromDatabase(drinkId, drinkType);
      }
    });
  });
}

function updateDrinkCalculationDisplay() {
  if (!state.currentDrinkFromDatabase) return;
  
  const drink = state.currentDrinkFromDatabase;
  const volume = parseInt(elements.inputVolume.value, 10) || drink.defaultVolume;
  
  const sugarLevel = elements.form.querySelector('input[name="sugar-level"]:checked')?.value || 'none';
  const multiplier = sugarLevel === 'none' ? 0 : 
                     sugarLevel === 'three' ? 0.3 :
                     sugarLevel === 'half' ? 0.5 :
                     sugarLevel === 'seven' ? 0.7 : 1.0;
  
  const addedSugar = drink.baseSugar * multiplier;
  const totalSugar = drink.baseSugar + addedSugar;
  
  const caffeine = Math.round((drink.caffeine * volume) / drink.defaultVolume);
}

// ==========================================

// ==========================================
// Agent Analytics Interaction
// ==========================================

async function triggerAgentAnalysis(logData) {
  const badge = document.getElementById('agent-risk-badge');
  if (!badge) return;
  
  badge.textContent = 'Agent 分析中...';
  badge.style.background = '#fbbf24';
  
  try {
    const data = await api.logDrinkApi(logData);
    if (data.status === 'success') {
      state.lastNutritionResult = data.nutrition_result
        ? {
            ...data.nutrition_result,
            log_id: logData.id,
            brand: logData.brand,
            name: logData.name,
            type: logData.type,
            volume: logData.volume
          }
        : null;
      renderNutritionExplainabilityPanel();
      updateAgentUI(data.agent_analysis);
      
      // 同步后端最新的数据（因为 Agent 可能会修改数值）
      try {
        const dbLogs = await api.fetchLogsApi();
        if (dbLogs && dbLogs.length > 0) {
          state.logs = dbLogs;
          saveLogs(state.logs);
          
          // 局部刷新面板数值，避免循环调用 agent
          const dateLogs = state.logs.filter(l => l.date === state.selectedDate);
          const tc = dateLogs.reduce((s, l) => s + l.caffeine, 0);
          const ts = dateLogs.reduce((s, l) => s + l.sugarContent, 0);
          const ta = dateLogs.reduce((s, l) => s + (l.alcoholContent || 0), 0);
          
          const elCaf = document.getElementById('caffeine-total');
          const elSug = document.getElementById('sugar-total');
          if(elCaf) elCaf.textContent = tc;
          if(elSug) elSug.textContent = ts.toFixed(1);
          
          const ur = (el, val, max) => {
            if(!el) return;
            const p = Math.min(val / max, 1);
            el.setAttribute('stroke-dashoffset', 377 - (p * 377));
          };
          ur(document.getElementById('caffeine-progress'), tc, CAFFEINE_LIMIT);
          ur(document.getElementById('sugar-progress'), ts, SUGAR_LIMIT);
          
          renderDailyLogs(dateLogs);
          
          // Refresh the daily insights report and weekly panel to reflect the new drink!
          renderDailyInsights(dateLogs, tc, ts, ta);
          if (state.activeTab === 'tab-daily') {
              renderWeeklyPanel();
          }
        }
      } catch (err) {
        console.error('Failed to sync logs after agent analysis:', err);
      }
    }
  } catch (e) {
    console.error('Agent API error:', e);
    badge.textContent = 'API 连接失败';
    badge.style.background = '#ef4444';
    text.textContent = '请确保后端 Python 服务在 8000 端口运行。';
  }
}

async function fetchDailyAgentInsights(date) {
  const badge = document.getElementById('agent-risk-badge');
  if (!badge) return;
  
  badge.textContent = '分析中...';
  badge.style.background = '#fbbf24';
  
  try {
    const data = await api.fetchDailyAgentInsightsApi(date);
    if (data) {
      updateAgentUI(data);
      // 必须同步后端被 Agent 更新的数值到前端看板
      try {
        const dbLogs = await api.fetchLogsApi();
        if (dbLogs && dbLogs.length > 0) {
          state.logs = dbLogs;
          saveLogs(state.logs);
          const dateLogs = state.logs.filter(l => l.date === state.selectedDate);
          const tc = dateLogs.reduce((s, l) => s + l.caffeine, 0);
          const ts = dateLogs.reduce((s, l) => s + l.sugarContent, 0);
          const elCaf = document.getElementById('caffeine-total');
          const elSug = document.getElementById('sugar-total');
          if(elCaf) elCaf.textContent = tc;
          if(elSug) elSug.textContent = ts.toFixed(1);
          const ur = (el, val, max) => {
            if(!el) return;
            const p = Math.min(val / max, 1);
            el.setAttribute('stroke-dashoffset', 377 - (p * 377));
          };
          ur(document.getElementById('caffeine-progress'), tc, CAFFEINE_LIMIT);
          ur(document.getElementById('sugar-progress'), ts, SUGAR_LIMIT);
          renderDailyLogs(dateLogs);
        }
      } catch (err) {
        console.error('Failed to sync logs in fetchDailyAgentInsights:', err);
      }
    }
  } catch (e) {
    badge.textContent = '未连接';
    badge.style.background = '#94a3b8';
  }
  
  // Load chat history for the new date
  await fetchChatHistory();
}

function updateAgentUI(analysis) {
  const badge = document.getElementById('agent-risk-badge');
  if (!badge) return;
  
  badge.textContent = analysis.risk_level || '分析完成';
  if (analysis.risk_level === '低风险') {
    badge.style.background = '#10b981';
  } else if (analysis.risk_level === '高风险') {
    badge.style.background = '#ef4444';
  } else {
    badge.style.background = '#f59e0b';
  }
  
  // Update Budget Progress Bars
  const budgetCaffeine = analysis.budget_caffeine || 400;
  const budgetSugar = analysis.budget_sugar || 50;
  const consumedCaffeine = analysis.caffeine_total || 0;
  const consumedSugar = analysis.sugar_total || 0;
  
  const caffeineText = document.getElementById('caffeine-budget-text');
  const caffeineBar = document.getElementById('caffeine-budget-bar');
  if (caffeineText && caffeineBar) {
    caffeineText.textContent = `${consumedCaffeine.toFixed(1)} / ${budgetCaffeine.toFixed(1)} mg`;
    let caffeinePct = (consumedCaffeine / budgetCaffeine) * 100;
    if (caffeinePct > 100) caffeinePct = 100;
    caffeineBar.style.width = `${caffeinePct}%`;
    caffeineBar.style.background = caffeinePct >= 100 ? '#ef4444' : '#c084fc';
  }
  
  const sugarText = document.getElementById('sugar-budget-text');
  const sugarBar = document.getElementById('sugar-budget-bar');
  if (sugarText && sugarBar) {
    sugarText.textContent = `${consumedSugar.toFixed(1)} / ${budgetSugar.toFixed(1)} g`;
    let sugarPct = (consumedSugar / budgetSugar) * 100;
    if (sugarPct > 100) sugarPct = 100;
    sugarBar.style.width = `${sugarPct}%`;
    sugarBar.style.background = sugarPct >= 100 ? '#ef4444' : '#f472b6';
  }
}

async function saveSleepData(date, hours) {
  try {
    await api.saveSleepDataApi(date, hours);
    alert('睡眠数据已同步给 Agent！');
    fetchDailyAgentInsights(date); // Refresh insights
  } catch (e) {
    alert('保存睡眠数据失败，请检查后端是否开启。');
  }
}


