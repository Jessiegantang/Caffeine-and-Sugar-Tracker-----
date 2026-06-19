// ==========================================
// Caffeine and Sugar Tracker - Main Coordinator
// ==========================================

import { PRESET_TEMPLATES, CAFFEINE_LIMIT, SUGAR_LIMIT } from './src/config.js';
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
  renderNutritionExplainabilityPanel();
});

function setupMemoryDebugApi() {
  window.DrinkMindMemory = {
    list: () => api.fetchUserPreferencesApi(),
    clear: () => api.clearUserPreferencesApi()
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
  window.addEventListener('drinkmind:add-parsed-intake', (e) => {
    applyParsedIntakeToForm(e.detail);
    handleAddDrink();
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
}

// Helper to get HH:MM of now
function getCurrentTimeString() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}

function renderNutritionExplainabilityPanel() {
  const panel = elements.nutritionExplainabilityPanel || document.getElementById('nutrition-explainability-panel');
  if (!panel) return;

  const result = state.lastNutritionResult;
  if (!result) {
    panel.className = 'agent-panel-body muted';
    panel.textContent = '暂无营养估算结果';
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
      ${renderNutritionMetric('咖啡因', `${formatNumber(result.caffeine)} mg`)}
      ${renderNutritionMetric('糖分', `${formatNumber(result.sugarContent)} g`)}
      ${renderNutritionMetric('置信度', mapConfidenceLevel(confidenceValue))}
      ${renderNutritionMetric('来源', userSource)}
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
  if (!Number.isFinite(num)) return '低';
  if (num >= 0.8) return '高';
  if (num >= 0.55) return '中';
  return '低';
}

function mapEstimateSource(result, explainability, feedback) {
  const method = String(result.estimation_method || explainability.method || '').toLowerCase();
  const source = String(result.data_source || '').toLowerCase();
  if (feedback?.corrected || method.includes('feedback') || source.includes('user')) return '用户修正';
  if (explainability.used_knowledge_match || result.matched_knowledge_id || source.includes('knowledge')) return '知识库匹配';
  if (explainability.used_composition || result.composition || method.includes('composition')) return '成分估算';
  return '兜底估算';
}

function getEstimateExplanation(source, explainability, result) {
  if (source === '用户修正') {
    return '这个结果包含你为本条记录保存的人工修正。';
  }
  if (source === '知识库匹配') {
    return '这个结果来自已审核的饮品知识库匹配，并按容量和糖度做了换算。';
  }
  if (source === '成分估算') {
    return '没有找到足够可信的产品匹配，所以后端根据可能的成分组成进行了估算。';
  }
  if (result.feedback_notice) {
    return result.feedback_notice;
  }
  if (explainability.warnings?.length) {
    return '这是兜底估算；如果你有包装营养表或官方数据，可以在下方修正。';
  }
  return '这是基于当前饮品信息得到的兜底估算。';
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
      <summary>技术详情</summary>
      <div class="nutrition-technical-stack">
        <div class="nutrition-explain-section">
          <div class="nutrition-explain-title">估算方法</div>
          <div class="explain-chips">
            <span class="explain-chip">方法: ${escapeHtml(result.estimation_method || explainability.method || '未知')}</span>
            <span class="explain-chip">原始来源: ${escapeHtml(result.data_source || '未知')}</span>
          </div>
        </div>

        <div class="nutrition-explain-section">
          <div class="nutrition-explain-title">知识库匹配</div>
          <div class="explain-chips">
            <span class="explain-chip">是否使用: ${usedKnowledge ? '是' : '否'}</span>
            ${matchedId ? `<span class="explain-chip">匹配 ID: ${escapeHtml(matchedId)}</span>` : ''}
            ${retrievalScore !== null && retrievalScore !== undefined ? `<span class="explain-chip">检索分数: ${escapeHtml(Number(retrievalScore).toFixed(3))}</span>` : ''}
          </div>
        </div>

        ${renderLangGraphWorkflow(graphTrace, verification)}

        <div class="nutrition-explain-section">
          <div class="nutrition-explain-title">成分拆解</div>
          ${usedComposition
            ? renderComponentsTable(components)
            : '<div class="nutrition-empty-note">未使用成分拆解，因为已有可信知识库匹配。</div>'}
        </div>

        ${renderTextList('推理说明', reasoning)}
        ${renderTextList('估算假设', assumptions)}
        ${renderTextList('提醒', warnings, 'warning')}
        ${renderFeedbackMetadata(feedback, result.feedback_notice)}
      </div>
    </details>
  `;
}

function renderLangGraphWorkflow(graphTrace, verification) {
  const events = normalizeAgentTraceEvents(graphTrace);
  if (events.length === 0) {
    return '';
  }

  const warnings = normalizeTextList(verification?.warnings || []);
  const issues = normalizeTextList(verification?.issues || []);
  const passed = verification?.passed;
  const completedCount = events.filter(event => event.status !== 'error').length;
  const errorCount = events.filter(event => event.status === 'error').length;

  return `
    <div class="nutrition-explain-section langgraph-workflow-section">
      <div class="nutrition-workflow-header">
        <div>
          <div class="nutrition-explain-title">Agent Trace 工作流</div>
          <div class="nutrition-workflow-subtitle">从输入、检索、路由到估算与校验的流程级可视化</div>
        </div>
        <div class="nutrition-workflow-stats">
          <span>${events.length} 步</span>
          <span>${completedCount} 完成</span>
          ${errorCount ? `<span class="tone-error">${errorCount} 异常</span>` : ''}
        </div>
      </div>
      <ol class="agent-trace-timeline">
        ${events.map((event, index) => `
          <li class="agent-trace-event tone-${escapeAttr(event.status)}">
            <span class="agent-trace-index">${index + 1}</span>
            <div class="agent-trace-card">
              <div class="agent-trace-card-head">
                <div>
                  <strong>${escapeHtml(event.label)}</strong>
                  <span>${escapeHtml(event.agent)}</span>
                </div>
                <div class="agent-trace-badges">
                  <span>${escapeHtml(event.phase)}</span>
                  <span>${escapeHtml(formatTraceStatus(event.status))}</span>
                  ${event.confidence !== null && event.confidence !== undefined ? `<span>${formatConfidence(event.confidence)}</span>` : ''}
                </div>
              </div>
              ${event.summary ? `<p>${escapeHtml(event.summary)}</p>` : ''}
              ${event.decision ? `<div class="agent-trace-decision">${escapeHtml(event.decision)}</div>` : ''}
              <div class="agent-trace-data-grid">
                ${renderTraceDataList('输入', event.input)}
                ${renderTraceDataList('输出', event.output)}
              </div>
            </div>
          </li>
        `).join('')}
      </ol>
      ${verification ? `
        <div class="langgraph-verification">
          <div class="explain-chips">
            <span class="explain-chip">验证通过: ${formatVerificationPassed(passed)}</span>
          </div>
          ${warnings.length ? renderInlineTextList('警告', warnings, 'warning') : ''}
          ${issues.length ? renderInlineTextList('问题', issues, 'issue') : ''}
        </div>
      ` : ''}
    </div>
  `;
}

function normalizeAgentTraceEvents(graphTrace) {
  return (Array.isArray(graphTrace) ? graphTrace : []).map((event) => {
    if (typeof event === 'string') {
      return {
        id: event,
        label: getLegacyTraceLabel(event),
        phase: '流程',
        agent: 'Nutrition Agent',
        status: 'completed',
        summary: '',
        input: null,
        output: null,
        decision: null,
        confidence: null
      };
    }
    if (!event || typeof event !== 'object') {
      return {
        id: '',
        label: '未知步骤',
        phase: '流程',
        agent: 'Nutrition Agent',
        status: 'completed',
        summary: '',
        input: null,
        output: null,
        decision: null,
        confidence: null
      };
    }
    return {
      id: event.id || event.node || '',
      label: event.label || getLegacyTraceLabel(event.id || event.node || ''),
      phase: event.phase || '流程',
      agent: event.agent || 'Nutrition Agent',
      status: event.status || 'completed',
      summary: event.summary || '',
      input: event.input || null,
      output: event.output || null,
      decision: event.decision || null,
      confidence: event.confidence
    };
  });
}

function getLegacyTraceLabel(id) {
  const labels = {
    normalize_input: '标准化输入',
    lookup_knowledge: '知识库检索',
    route_estimation: '路由决策',
    use_knowledge_result: '采用知识结果',
    composition_decompose: '成分拆解',
    composition_estimate: '成分估算',
    composition_error: '成分估算异常',
    verify_result: '结果校验',
    build_explainability: '生成解释'
  };
  return labels[id] || id || '未知步骤';
}

function renderTraceDataList(title, data) {
  if (!data || Object.keys(data).length === 0) return '';
  return `
    <div class="agent-trace-data">
      <span>${escapeHtml(title)}</span>
      <dl>
        ${Object.entries(data).map(([key, value]) => `
          <div>
            <dt>${escapeHtml(formatTraceKey(key))}</dt>
            <dd>${escapeHtml(formatTraceValue(value))}</dd>
          </div>
        `).join('')}
      </dl>
    </div>
  `;
}

function formatTraceKey(key) {
  const labels = {
    brand: '品牌',
    name: '名称',
    type: '类型',
    volume_ml: '容量',
    sugar: '甜度',
    method: '方法',
    source: '来源',
    caffeine_mg: '咖啡因',
    sugar_g: '糖分',
    confidence: '置信度',
    matched_knowledge_id: '知识 ID',
    retrieval_score: '检索分',
    components: '成分数',
    route: '路由',
    drink_type: '饮品类型',
    espresso_shots: '浓缩份数',
    tea_base_volume_ml: '茶底',
    milk_volume_ml: '奶基底',
    fruit_base_volume_ml: '果汁/饮品基底',
    syrup_pumps: '糖浆泵数',
    sweetness_level: '甜度级别',
    assumptions: '假设',
    warnings: '提醒',
    passed: '通过',
    issues: '问题',
    error: '错误'
  };
  return labels[key] || key;
}

function formatTraceValue(value) {
  if (Array.isArray(value)) return value.map(formatTraceValue).join('；');
  if (value && typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
  if (typeof value === 'boolean') return value ? '是' : '否';
  return translateNutritionText(value);
}

function formatTraceStatus(status) {
  if (status === 'error') return '异常';
  if (status === 'warning') return '有提醒';
  if (status === 'skipped') return '跳过';
  return '完成';
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
        ${values.map(item => `<li>${escapeHtml(translateNutritionText(item))}</li>`).join('')}
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
      estimation_method: log.estimation_method || '未知',
      data_source: log.data_source || '未知',
      matched_knowledge_id: log.matched_knowledge_id || null,
      retrieval_score: log.retrieval_score ?? null,
      reasoning: ['这条记录没有保存可解释性详情'],
      composition: null,
      explainability: {
        method: log.estimation_method || '未知',
        used_composition: false,
        used_knowledge_match: Boolean(log.matched_knowledge_id),
        matched_knowledge_id: log.matched_knowledge_id || null,
        retrieval_score: log.retrieval_score ?? null,
        confidence: log.confidence ?? 0,
        reasoning: ['这条记录没有保存可解释性详情'],
        components: [],
        assumptions: [],
        warnings: ['这条记录没有保存可解释性详情']
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
    return '<div class="nutrition-empty-note">后端没有返回成分明细。</div>';
  }
  return `
    <div class="nutrition-component-list">
      ${components.map(component => `
        <div class="nutrition-component-row">
          <div>
            <strong>${escapeHtml(translateNutritionTerm(component.name || '成分'))}</strong>
            <span>${escapeHtml(translateNutritionTerm(component.category || '未知类别'))}</span>
          </div>
          <div>${escapeHtml(formatAmount(component.amount, component.unit))}</div>
          <div>${formatNumber(component.caffeine_mg)}mg</div>
          <div>${formatNumber(component.sugar_g)}g</div>
          <div>${formatConfidence(component.confidence ?? 0)}</div>
          <small>${escapeHtml(translateNutritionText(component.basis || ''))}</small>
        </div>
      `).join('')}
    </div>
  `;
}

function renderFeedbackMetadata(feedback, notice = '') {
  if (!feedback && !notice) return '';
  return `
    <div class="nutrition-explain-section feedback-summary">
      <div class="nutrition-explain-title">修正记录</div>
      ${notice ? `<div class="feedback-notice">${escapeHtml(notice)}</div>` : ''}
      ${feedback ? `
        <div class="explain-chips">
          <span class="explain-chip">来源: ${escapeHtml(feedback.source_type || 'user_feedback')}</span>
          <span class="explain-chip">差异较大: ${feedback.high_delta ? '是' : '否'}</span>
        </div>
        ${feedback.source_note ? `<div class="nutrition-empty-note">${escapeHtml(feedback.source_note)}</div>` : ''}
      ` : ''}
    </div>
  `;
}

function renderNutritionFeedbackForm(result) {
  const logId = result?.log_id;
  if (!logId) {
    return `
      <div class="nutrition-feedback-form nutrition-feedback-disabled">
        <div class="nutrition-explain-title">人工修正估算</div>
        <div class="nutrition-empty-note">保存为饮品记录后，可以在这里修正咖啡因和糖分。</div>
      </div>
    `;
  }
  const corrected = result.explainability?.feedback?.corrected || result.feedback?.corrected || {};
  const brand = corrected.brand ?? result.brand ?? '';
  const name = corrected.name ?? result.name ?? '';
  const type = corrected.type ?? result.type ?? 'coffee';
  const volume = corrected.volume ?? result.volume ?? 500;
  const caffeine = corrected.caffeine ?? result.caffeine ?? 0;
  const sugarContent = corrected.sugarContent ?? result.sugarContent ?? 0;

  return `
    <form id="nutrition-feedback-form" class="nutrition-feedback-form" data-log-id="${escapeAttr(logId)}">
      <div class="nutrition-explain-title">人工修正估算</div>
      <div class="feedback-form-grid feedback-form-grid-simple">
        <label>咖啡因 mg<input name="caffeine" type="number" min="0" max="800" step="0.1" value="${escapeAttr(caffeine)}" required></label>
        <label>糖分 g<input name="sugarContent" type="number" min="0" max="150" step="0.1" value="${escapeAttr(sugarContent)}" required></label>
      </div>
      <label class="feedback-note-label">数据来源说明<textarea name="source_note" rows="2" placeholder="例如：包装营养表标注咖啡因 120mg，糖 18g"></textarea></label>
      <div class="feedback-options">
        <label><input type="checkbox" name="apply_to_log" checked> 更新这条记录</label>
      </div>
      <details class="feedback-advanced-details">
        <summary>高级修正字段</summary>
        <div class="feedback-form-grid">
          <label>品牌<input name="brand" value="${escapeAttr(brand)}"></label>
          <label>名称<input name="name" value="${escapeAttr(name)}" required></label>
          <label>类型<select name="type">${renderFeedbackTypeOptions(type)}</select></label>
          <label>容量 ml<input name="volume" type="number" min="10" max="2000" value="${escapeAttr(volume)}" required></label>
        </div>
        <div class="feedback-options">
          <label><input type="checkbox" name="submit_as_evidence"> 加入审核队列</label>
        </div>
      </details>
      <div class="feedback-actions">
        <button type="submit" class="btn btn-primary">保存修正</button>
        <span class="feedback-status" id="nutrition-feedback-status"></span>
      </div>
    </form>
  `;
}
function renderFeedbackTypeOptions(selected) {
  return Object.entries(TYPE_DEFINITIONS).map(([value, def]) => (
    `<option value="${escapeAttr(value)}" ${value === selected ? 'selected' : ''}>${escapeHtml(getTypeTextCN(value))}</option>`
  )).join('');
}

function renderTextList(title, items, tone = '') {
  const list = normalizeTextList(items);
  if (list.length === 0) return '';
  return `
    <div class="nutrition-explain-section ${tone ? `tone-${tone}` : ''}">
      <div class="nutrition-explain-title">${escapeHtml(title)}</div>
      <ul class="nutrition-text-list">
        ${list.map(item => `<li>${escapeHtml(translateNutritionText(item))}</li>`).join('')}
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
  return `${Number.isFinite(numeric) ? numeric.toFixed(numeric % 1 === 0 ? 0 : 1) : amount} ${translateNutritionTerm(unit || '')}`.trim();
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
      status.textContent = '加入审核队列时需要填写数据来源说明。';
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
    status.textContent = '提交中...';
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
    if (payload.apply_to_log) noticeParts.push('这条记录已更新。');
    if (data.evidence || payload.submit_as_evidence) noticeParts.push('修正已加入审核队列。');
    state.lastNutritionResult = buildNutritionResultFromLog(updatedLog, noticeParts.join(' ') || '修正已保存。');
    renderNutritionExplainabilityPanel();
  } catch (e) {
    if (status) {
      status.textContent = e.message || '修正提交失败';
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
    estimation_method: log.estimation_method || '未知',
    data_source: log.data_source || '未知',
    matched_knowledge_id: log.matched_knowledge_id || null,
    retrieval_score: log.retrieval_score ?? null,
    reasoning: normalizeTextList(log.reasoning),
    composition: log.composition || null,
    explainability: log.explainability || {
      method: log.estimation_method || '未知',
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
  
  // Backend nutrition pipeline will fill caffeine and sugar after the log is saved.
  let caffeine = 0;
  let baseSugarDensity = baseSugarOverride !== null ? baseSugarOverride : 0;
  const sugarContent = 0;

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
  const totalCaffeine = dateLogs.reduce((sum, l) => sum + Number(l.caffeine || 0), 0);
  const totalSugar = dateLogs.reduce((sum, l) => sum + Number(l.sugarContent || 0), 0);

  // Render Daily Gauges
  elements.caffeineTotal.textContent = formatNumber(totalCaffeine);
  elements.sugarTotal.textContent = formatNumber(totalSugar);

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
  renderDailyInsights(dateLogs, totalCaffeine, totalSugar);
  fetchDailyAgentInsights(state.selectedDate);
}

function formatConfidence(value) {
  const confidence = Number(value ?? 1);
  return `${Math.round(confidence * 100)}%`;
}

function translateExplainabilityLabel(label) {
  const labels = {
    source: '\u6765\u6e90',
    method: '\u65b9\u6cd5',
    knowledge: '\u77e5\u8bc6\u5e93',
    retrieval: '\u68c0\u7d22\u5206',
    trace: '\u8ffd\u8e2a',
  };
  return labels[label] || label;
}

function translateExplainabilityValue(value) {
  const text = String(value ?? '');
  const values = {
    'Composition Estimation Agent': '\u6210\u5206\u4f30\u7b97 Agent',
    COMPOSITION_ESTIMATION: '\u6210\u5206\u62c6\u89e3\u4f30\u7b97',
    HYBRID_SQL_EXACT_MATCH_LOCAL: '\u77e5\u8bc6\u5e93\u5339\u914d + \u672c\u5730\u52a8\u6001\u4f30\u7b97',
    LOCAL_ESTIMATION: '\u672c\u5730\u52a8\u6001\u4f30\u7b97',
    SQL_EXACT_MATCH: '\u77e5\u8bc6\u5e93\u7cbe\u786e\u5339\u914d',
  };
  return values[text] || text;
}

function translateNutritionTerm(value) {
  const text = String(value ?? '');
  const terms = {
    espresso: '浓缩咖啡',
    coconut_water_base: '椰子水基底',
    'coconut water or coconut beverage base': '椰子水或椰子饮品基底',
    coconut_milk: '厚椰乳',
    'coconut milk': '厚椰乳',
    milk: '牛奶',
    oat_milk: '燕麦奶',
    black_or_oolong_tea: '红茶/乌龙茶底',
    jasmine_tea: '茉莉花茶底',
    'tea base': '茶底',
    light_tea: '轻茶底',
    fruit_or_juice_base: '果汁/水果基底',
    'fruit or juice base': '果汁/水果基底',
    fruit_juice_and_puree: '果汁/果泥基底',
    mango_pomelo_puree: '芒果西柚果泥',
    generic_beverage_base: '通用饮品基底',
    added_syrup: '额外糖浆',
    pump_equivalent: '泵等效',
    coffee_base: '咖啡基底',
    fruit_base: '水果/饮品基底',
    milk_base: '奶基底',
    tea_base: '茶基底',
    sweetener: '甜味来源',
    coconut_latte: '生椰拿铁',
    coconut_americano: '生椰美式',
    americano: '美式咖啡',
    latte: '拿铁',
    oat_latte: '燕麦拿铁',
    milk_tea: '奶茶',
    fruit_tea: '水果茶',
    unknown: '未知',
    none: '无糖',
    three: '三分糖',
    half: '半糖',
    seven: '七分糖',
    full: '全糖',
    COMPOSITION_ESTIMATION: '成分拆解估算',
    SQL_EXACT_MATCH: '知识库精确匹配',
    RAG_MATCH: '知识库语义匹配',
    LOCAL_ESTIMATOR: '本地规则估算',
    LLM_ESTIMATION: '模型估算',
    'Composition Estimation Agent': '成分估算 Agent',
    'Knowledge Lookup Agent': '知识库检索 Agent',
    'Input Normalizer': '输入标准化',
    'Estimation Router': '估算路由器',
    'Result Verifier': '结果校验器',
    'Explainability Builder': '解释生成器'
  };
  return terms[text] || text;
}

function translateNutritionText(value) {
  const text = String(value ?? '');
  if (!text) return '';

  const direct = {
    'Functional or energy-style naming detected; extra caffeine sources are not modeled without product evidence.':
      '检测到功能型或能量风格命名；在没有可信产品证据时，不额外估算其他咖啡因来源。',
    'Warning: Functional or energy-style naming detected; extra caffeine sources are not modeled without product evidence.':
      '提醒：检测到功能型或能量风格命名；在没有可信产品证据时，不额外估算其他咖啡因来源。',
    'Coconut americano is modeled as espresso plus coconut water or coconut beverage base.':
      '生椰美式按“浓缩咖啡 + 椰子水或椰子饮品基底”建模。',
    'No added syrup sugar because sweetness level is none.':
      '甜度为无糖，因此没有计入额外糖浆糖分。',
    'Sweetness level is unknown; using half-sugar added sweetener assumption.':
      '甜度未知，因此按半糖估算额外甜味来源。',
    'Functional drink naming may imply extra active ingredients, but no verified product evidence was available.':
      '功能型命名可能暗示额外活性成分，但当前没有可信产品证据。',
    'Espresso caffeine varies by shot size and extraction.':
      '浓缩咖啡因会随 shot 大小和萃取方式变化。',
    'Coconut beverage sugar varies by brand recipe and base volume.':
      '椰子饮品糖分会随品牌配方和基底用量变化。',
    'Coconut milk sugar varies by brand recipe and milk volume.':
      '厚椰乳糖分会随品牌配方和用量变化。',
    'Oat milk sugar varies by product formula and milk volume.':
      '燕麦奶糖分会随产品配方和用量变化。',
    'Milk volume is inferred from cup size, so natural milk sugar is a range.':
      '奶量是根据杯型推断的，因此天然乳糖用范围表示。',
    'Tea caffeine and milk ratio vary across milk tea recipes.':
      '不同奶茶配方中的茶底咖啡因和奶量比例会有差异。',
    'Sweetness labels map to brand-specific standard syrup amounts.':
      '甜度标签会对应不同品牌自己的标准糖浆用量。',
    'Fruit or juice base sugar varies by fruit type, puree concentration, and brand recipe.':
      '水果或果汁基底糖分会随水果类型、果泥浓度和品牌配方变化。',
    'Fruit or juice base sugar varies by fruit mix and recipe concentration.':
      '水果/果汁基底糖分会随水果组合和配方浓度变化。',
    'Tea caffeine is estimated from a light tea base range.':
      '茶底咖啡因按轻茶底范围估算。',
    'Unknown drink style; using conservative generic beverage assumptions.':
      '饮品类型不明确，因此使用保守的通用饮品假设。',
    'Drink style is unknown, so both composition and sugar density use broad generic assumptions.':
      '饮品类型未知，因此组成和糖密度都使用较宽的通用假设。',
    'Coconut latte is modeled as espresso plus sweetened coconut milk base.':
      '生椰拿铁按“浓缩咖啡 + 含糖厚椰乳基底”建模。',
    'Oat latte is modeled as espresso plus oat milk.':
      '燕麦拿铁按“浓缩咖啡 + 燕麦奶”建模。',
    'Latte is modeled as espresso plus milk.':
      '拿铁按“浓缩咖啡 + 牛奶”建模。',
    'Americano is modeled as espresso diluted with water.':
      '美式按“浓缩咖啡 + 水”建模。',
    'Milk tea is modeled as tea base, milk, and adjustable added syrup.':
      '奶茶按“茶底 + 奶基底 + 可调额外糖浆”建模。',
    'Fruit tea is modeled as tea plus fruit or juice base.':
      '水果茶按“茶底 + 水果或果汁基底”建模。',
    'Fruit americano is modeled as espresso plus a fruit or juice base.':
      '水果美式按“浓缩咖啡 + 水果或果汁基底”建模。',
    'Fallback composition uses a small generic sugar-containing base plus optional sweetener.':
      '兜底组成使用少量通用含糖饮品基底，并按甜度估算可选甜味来源。',
    'Natural sugars from fresh mango and pomelo heavily influence total sweetness independent of added syrup.':
      '鲜芒果和西柚带来的天然糖会明显影响总甜度，不完全取决于额外糖浆。',
    'Coconut milk base concentration and fruit puree ratios are subject to seasonal and regional recipe updates.':
      '椰乳基底浓度和果泥比例可能会随季节、地区或配方调整而变化。',
    "Luckin Coffee's Yangzhi Ganlu is formulated as a fruit milk tea combining jasmine tea, coconut milk, and mango-pomelo puree.":
      '瑞幸杨枝甘露按“茉莉茶底 + 椰乳 + 芒果西柚果泥”的水果奶茶结构理解。',
    "The 'three' sugar level corresponds to 3 standard syrup pumps.":
      '三分糖按约 3 泵标准糖浆理解。',
    'Sago and ice occupy the remaining volume fraction.':
      '西米和冰块会占据剩余容量比例。',
    'brand and specific recipe unknown':
      '品牌和具体配方不明确。',
    'sugar content not specified':
      '糖分含量未明确标注。',
    'compositional ratios are industry estimates':
      '成分比例属于行业常见估算。',
    'composition route produced no components':
      '成分估算路径没有生成成分明细。',
    'composition route selected a non-composition method':
      '成分估算路径选择了非成分估算方法。',
    'knowledge route selected a composition method':
      '知识库路径选择了成分估算方法。',
    'knowledge result should not include composition details':
      '知识库匹配结果不应包含成分拆解详情。',
    'composition result should not include matched knowledge id':
      '成分估算结果不应包含知识库匹配 ID。',
    'caffeine is negative': '咖啡因数值为负数。',
    'sugarContent is negative': '糖分数值为负数。',
    'caffeine exceeds 500mg': '咖啡因超过 500mg。',
    'sugarContent exceeds 100g': '糖分超过 100g。'
  };
  if (direct[text]) return direct[text];
  if (text.startsWith('Warning: ')) {
    const translated = translateNutritionText(text.slice(9));
    return translated === text.slice(9) ? `提醒：${text.slice(9)}` : `提醒：${translated}`;
  }

  let match = text.match(/^([\d.]+)-([\d.]+)mg caffeine per espresso shot, best ([\d.]+)mg$/);
  if (match) {
    return `每份浓缩咖啡按 ${match[1]}-${match[2]}mg 咖啡因估算，取 ${match[3]}mg。`;
  }

  match = text.match(/^([\d.]+)-([\d.]+)g sugar per 100ml coconut water or coconut beverage base, best ([\d.]+)g$/);
  if (match) {
    return `椰子水或椰子饮品基底按每 100ml ${match[1]}-${match[2]}g 糖估算，取 ${match[3]}g。`;
  }

  match = text.match(/^([\d.]+)-([\d.]+)g sugar per 100ml (.+), best ([\d.]+)g$/);
  if (match) {
    return `${translateNutritionTerm(match[3])} 按每 100ml ${match[1]}-${match[2]}g 糖估算，取 ${match[4]}g。`;
  }

  match = text.match(/^([\d.]+)-([\d.]+)mg caffeine per 100ml (.+), best ([\d.]+)mg$/);
  if (match) {
    return `${translateNutritionTerm(match[3])} 按每 100ml ${match[1]}-${match[2]}mg 咖啡因估算，取 ${match[4]}mg。`;
  }

  match = text.match(/^Estimated espresso caffeine range from ([\d.]+) shot\(s\): ([\d.]+)-([\d.]+)mg, best ([\d.]+)mg\.$/);
  if (match) {
    return `按 ${match[1]} 份浓缩咖啡估算咖啡因范围：${match[2]}-${match[3]}mg，取估算值 ${match[4]}mg。`;
  }

  match = text.match(/^Included natural sugar range from fruit or beverage base: ([\d.]+)-([\d.]+)g\.$/);
  if (match) {
    return `已计入水果或饮品基底的天然糖范围：${match[1]}-${match[2]}g。`;
  }

  match = text.match(/^Included natural sugar range from ([^:]+): ([\d.]+)-([\d.]+)g\.$/);
  if (match) {
    return `已计入 ${translateNutritionTerm(match[1])} 的天然糖范围：${match[2]}-${match[3]}g。`;
  }

  match = text.match(/^Estimated tea caffeine range from tea base volume: ([\d.]+)-([\d.]+)mg\.$/);
  if (match) {
    return `根据茶底用量估算咖啡因范围：${match[1]}-${match[2]}mg。`;
  }

  match = text.match(/^Added sugar range adjusted by sweetness level '([^']+)': ([\d.]+)-([\d.]+)g\.$/);
  if (match) {
    return `按甜度档位“${getSugarTextCN(match[1])}”估算额外加糖范围：${match[2]}-${match[3]}g。`;
  }

  match = text.match(/^([\d.]+)-([\d.]+)g sugar per syrup pump adjusted by sweetness level ([^,]+), best ([\d.]+)g$/);
  if (match) {
    return `每泵糖浆按 ${match[1]}-${match[2]}g 糖估算，并按甜度“${getSugarTextCN(match[3])}”调整，取 ${match[4]}g。`;
  }

  const translatedTerm = translateNutritionTerm(text);
  return translatedTerm !== text ? translatedTerm : text;
}

function formatOptionalMeta(label, value) {
  if (value === undefined || value === null || value === '') return '';
  return `<span class="explain-chip">${translateExplainabilityLabel(label)}: ${escapeHtml(translateExplainabilityValue(value))}</span>`;
}

function translateReasoning(reason) {
  const text = String(reason ?? '');
  let match = text.match(/^Estimated espresso caffeine range from ([\d.]+) shot\(s\): ([\d.]+)-([\d.]+)mg, best ([\d.]+)mg\.$/);
  if (match) {
    return `\u6309 ${match[1]} \u4efd\u6d53\u7f29\u5496\u5561\u4f30\u7b97\u5496\u5561\u56e0\u8303\u56f4\uff1a${match[2]}-${match[3]} mg\uff0c\u53d6\u4f30\u7b97\u503c ${match[4]} mg\u3002`;
  }

  match = text.match(/^Included natural sugar range from fruit or beverage base: ([\d.]+)-([\d.]+)g\.$/);
  if (match) {
    return `\u5df2\u8ba1\u5165\u679c\u6c41\u6216\u996e\u54c1\u57fa\u5e95\u7684\u5929\u7136\u7cd6\u8303\u56f4\uff1a${match[1]}-${match[2]} g\u3002`;
  }

  match = text.match(/^Included natural sugar range from ([^:]+): ([\d.]+)-([\d.]+)g\.$/);
  if (match) {
    return `\u5df2\u8ba1\u5165 ${translateExplainabilityValue(match[1])} \u7684\u5929\u7136\u7cd6\u8303\u56f4\uff1a${match[2]}-${match[3]} g\u3002`;
  }

  match = text.match(/^Estimated tea caffeine range from tea base volume: ([\d.]+)-([\d.]+)mg\.$/);
  if (match) {
    return `\u6839\u636e\u8336\u5e95\u7528\u91cf\u4f30\u7b97\u5496\u5561\u56e0\u8303\u56f4\uff1a${match[1]}-${match[2]} mg\u3002`;
  }

  match = text.match(/^Added sugar range adjusted by sweetness level '([^']+)': ([\d.]+)-([\d.]+)g\.$/);
  if (match) {
    return `\u6309\u751c\u5ea6\u6863\u4f4d\u201c${getSugarTextCN(match[1])}\u201d\u4f30\u7b97\u989d\u5916\u52a0\u7cd6\u8303\u56f4\uff1a${match[2]}-${match[3]} g\u3002`;
  }

  if (text === 'Warning: Functional or energy-style naming detected; extra caffeine sources are not modeled without product evidence.') {
    return '\u63d0\u9192\uff1a\u996e\u54c1\u540d\u79f0\u542b\u529f\u80fd\u6216\u80fd\u91cf\u98ce\u683c\u8868\u8ff0\uff0c\u4f46\u6ca1\u6709\u53ef\u4fe1\u4ea7\u54c1\u8bc1\u636e\u65f6\uff0c\u4e0d\u989d\u5916\u4f30\u7b97\u5176\u4ed6\u5496\u5561\u56e0\u6765\u6e90\u3002';
  }

  if (text === 'Estimated tea caffeine from tea base volume.') {
    return '\u6839\u636e\u8336\u5e95\u7528\u91cf\u4f30\u7b97\u5496\u5561\u56e0\u3002';
  }

  if (text === 'Included natural sugar from fruit or beverage base.') {
    return '\u5df2\u8ba1\u5165\u679c\u6c41\u6216\u996e\u54c1\u57fa\u5e95\u7684\u5929\u7136\u7cd6\u3002';
  }

  return text;
}

function renderReasoningItems(reasoning) {
  if (!reasoning) return '';
  try {
    const reasons = typeof reasoning === 'string' ? JSON.parse(reasoning) : reasoning;
    const list = Array.isArray(reasons) ? reasons : [String(reasons)];
    return list.map(r => `<li>${escapeHtml(translateReasoning(r))}</li>`).join('');
  } catch(e) {
    return `<li>${escapeHtml(translateReasoning(reasoning))}</li>`;
  }
}

function renderExplainability(log) {
  const hasExplainability = log.data_source || log.estimation_method || log.reasoning || log.explainability;
  if (!hasExplainability) return '';

  const retrievalScore = log.retrieval_score !== undefined && log.retrieval_score !== null
    ? Number(log.retrieval_score).toFixed(3)
    : null;
  return `
    <div class="log-explainability">
      <div class="explain-header">
        <span>\u8425\u517b\u4f30\u7b97\u6d41\u7a0b</span>
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

      const explainabilityBadge = log.explainability
        ? '<span class="log-explainability-badge is-saved">\u53ef\u89e3\u91ca</span>'
        : '<span class="log-explainability-badge is-missing">\u6682\u65e0\u4f30\u7b97\u8bf4\u660e</span>';

      const logCard = document.createElement('div');
      logCard.className = `log-card type-${log.type}`;
      logCard.tabIndex = 0;
      logCard.title = '\u67e5\u770b\u5df2\u4fdd\u5b58\u7684\u8425\u517b\u4f30\u7b97\u8bf4\u660e';

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
        if (event.target.closest('.log-del-btn, .log-explainability')) return;
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
async function renderDailyInsights(dateLogs, totalCaffeine, totalSugar) {
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
      dailyInsights = buildDailyFallbackInsights(totalCaffeine, totalSugar);
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

function buildDailyFallbackInsights(totalCaffeine, totalSugar) {
  const insights = [];
  if (totalSugar > SUGAR_LIMIT) {
    insights.push({
      level: 'warning',
      title: '今日糖分已经超出预算',
      message: `今天糖分约 ${totalSugar.toFixed(1)}g，已经超过 ${SUGAR_LIMIT}g 的日建议限量。后续饮品建议优先选择无糖茶、无糖美式或白水。`,
      icon: '⚠️'
    });
  }
  if (totalCaffeine > CAFFEINE_LIMIT) {
    insights.push({
      level: 'warning',
      title: '今日咖啡因已经超出预算',
      message: `今天咖啡因约 ${totalCaffeine.toFixed(1)}mg，已经超过 ${CAFFEINE_LIMIT}mg 的日建议限量。后续建议避免继续摄入含咖啡因饮品。`,
      icon: '⚠️'
    });
  }
  if (insights.length > 0) return insights;
  if (totalSugar > SUGAR_LIMIT * 0.8 || totalCaffeine > CAFFEINE_LIMIT * 0.8) {
    return [{
      level: 'info',
      title: '今日摄入接近预算上限',
      message: `目前咖啡因约 ${totalCaffeine.toFixed(1)}mg，糖分约 ${totalSugar.toFixed(1)}g。接下来可以选择低糖或无咖啡因饮品，把余量留给晚些时候。`,
      icon: 'ℹ️'
    }];
  }
  return [{
    level: 'success',
    title: '今日饮品摄入控制良好',
    message: `目前咖啡因约 ${totalCaffeine.toFixed(1)}mg，糖分约 ${totalSugar.toFixed(1)}g，仍在日建议范围内。`,
    icon: '✅'
  }];
}

// Render WEEKLY trend tab
function renderWeeklyPanel() {
  const todayStr = getLocalDateString();
  const { weeklyLogs, weekDates } = getWeeklyLogs(state.logs, todayStr);

  // 1. Render Aggregates
  const totalCaffeine = weeklyLogs.reduce((sum, l) => sum + Number(l.caffeine || 0), 0);
  const totalSugar = weeklyLogs.reduce((sum, l) => sum + Number(l.sugarContent || 0), 0);

  // Calculate active tracking days
  const activeDays = new Set(weeklyLogs.map(l => l.date)).size;

  elements.weeklyCaffeineTotal.textContent = formatNumber(totalCaffeine);
  elements.weeklySugarTotal.textContent = formatNumber(totalSugar);
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
        default: return '🥤';
  }
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
          const tc = dateLogs.reduce((s, l) => s + Number(l.caffeine || 0), 0);
          const ts = dateLogs.reduce((s, l) => s + Number(l.sugarContent || 0), 0);
          
          const elCaf = document.getElementById('caffeine-total');
          const elSug = document.getElementById('sugar-total');
          if(elCaf) elCaf.textContent = formatNumber(tc);
          if(elSug) elSug.textContent = formatNumber(ts);
          
          const ur = (el, val, max) => {
            if(!el) return;
            const p = Math.min(val / max, 1);
            el.setAttribute('stroke-dashoffset', 377 - (p * 377));
          };
          ur(document.getElementById('caffeine-progress'), tc, CAFFEINE_LIMIT);
          ur(document.getElementById('sugar-progress'), ts, SUGAR_LIMIT);
          
          renderDailyLogs(dateLogs);
          
          // Refresh the daily insights report and weekly panel to reflect the new drink!
          renderDailyInsights(dateLogs, tc, ts);
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
          const tc = dateLogs.reduce((s, l) => s + Number(l.caffeine || 0), 0);
          const ts = dateLogs.reduce((s, l) => s + Number(l.sugarContent || 0), 0);
          const elCaf = document.getElementById('caffeine-total');
          const elSug = document.getElementById('sugar-total');
          if(elCaf) elCaf.textContent = formatNumber(tc);
          if(elSug) elSug.textContent = formatNumber(ts);
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


