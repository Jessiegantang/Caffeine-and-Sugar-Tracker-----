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
  renderHotDrinks();
  renderApp();
});

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

}

// Helper to get HH:MM of now
function getCurrentTimeString() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
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

      const logCard = document.createElement('div');
      logCard.className = `log-card type-${log.type}`;

      logCard.innerHTML = `
        <div class="log-card-left">
          <div class="log-type-icon">${typeIcon}</div>
          <div class="log-info-meta">
            <div class="log-title-row">
              ${log.brand ? `<span class="log-brand">${log.brand}</span>` : ''}
              <span class="log-name">${log.name}</span>
              <span class="log-type-badge">${getTypeTextCN(log.type)}</span>
            </div>
            <div class="log-time-range">
              ⏰ 饮用时间：${log.startTime} - ${log.endTime} (${log.volume}ml | ${sugarText})
            </div>
            ${log.data_source ? `<div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">来源: ${log.data_source} (可信度 ${log.confidence || 1.0})</div>` : ''}
            ${log.reasoning ? `
              <div class="log-reasoning" style="margin-top: 8px; font-size: 0.7rem; color: #8b5cf6; background: #f3f4f6; padding: 6px; border-radius: 4px; border-left: 2px solid #8b5cf6;">
                <div style="font-weight: 600; margin-bottom: 3px;">🧠 后端 AI 推断链路:</div>
                <ul style="margin: 0; padding-left: 14px;">
                  ${(() => {
                    try {
                      const reasons = typeof log.reasoning === 'string' ? JSON.parse(log.reasoning) : log.reasoning;
                      return reasons.map(r => `<li>${r}</li>`).join('');
                    } catch(e) { return `<li>${log.reasoning}</li>`; }
                  })()}
                </ul>
              </div>
            ` : ''}
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


