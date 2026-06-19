import { elements } from '../state.js';
import {
  addKnowledgeEvidenceApi,
  analyzeKnowledgeImageApi,
  approveKnowledgeEvidenceBulkApi,
  approveKnowledgeEvidenceApi,
  createKnowledgeCandidateApi,
  deleteKnowledgeCandidateApi,
  deleteKnowledgeCandidatesBulkApi,
  deleteKnowledgeEvidenceApi,
  deleteKnowledgeEvidenceBulkApi,
  fetchKnowledgeCandidatesApi,
  fetchKnowledgeEvidenceApi,
  importKnowledgeImageItemsApi
} from '../api.js';
import { TYPE_DEFINITIONS, getDrinkById, getAllDrinks, addDrink, updateDrink, deleteDrink, resetDatabase, loadDatabaseAsync } from '../drinks-database.js';

let _onDatabaseChanged = null;
let _imageAnalysisItems = [];

export function initDatabasePanel(onDatabaseChanged) {
  _onDatabaseChanged = onDatabaseChanged;

  elements.dbResetBtn.addEventListener('click', () => {
    if (confirm('确定要重置数据库吗？所有自定义数据将被清除！')) {
      resetDatabase();
      renderDatabasePanel();
      if (_onDatabaseChanged) _onDatabaseChanged();
    }
  });

  elements.dbImportBtn.addEventListener('click', () => {
    openImportModal();
  });

  elements.addDrinkForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleAddDrinkToDatabase();
  });

  elements.modalCloseBtn.addEventListener('click', () => {
    closeEditModal();
  });

  elements.editDrinkForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleUpdateDrink();
  });

  elements.editDeleteBtn.addEventListener('click', () => {
    handleDeleteDrink();
  });

  // Import Modal Events
  elements.importModalClose.addEventListener('click', () => {
    closeImportModal();
  });

  elements.importSelectBtn.addEventListener('click', () => {
    elements.importFile.click();
  });

  elements.importFile.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      elements.importFilename.textContent = file.name;
      elements.importExecuteBtn.disabled = false;
      elements.importResult.textContent = '';
    }
  });

  elements.importExecuteBtn.addEventListener('click', () => {
    handleImportFile();
  });

  document.getElementById('acquisition-image-file')?.addEventListener('change', handleImageFileSelected);

  document.getElementById('analyze-image-btn')?.addEventListener('click', () => {
    handleAnalyzeImage();
  });

  document.getElementById('stage-image-items-btn')?.addEventListener('click', () => {
    handleStageImageItems();
  });

  document.getElementById('acquisition-candidate-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    handleCreateCandidate();
  });

  document.getElementById('acquisition-evidence-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    handleCreateEvidence();
  });

  document.getElementById('bulk-approve-evidence-btn')?.addEventListener('click', () => {
    handleBulkApproveEvidence();
  });
  document.getElementById('bulk-delete-evidence-btn')?.addEventListener('click', () => {
    handleBulkDeleteEvidence();
  });
  document.getElementById('bulk-approve-source-groups-btn')?.addEventListener('click', () => {
    handleBulkApproveSourceGroups();
  });
  document.getElementById('bulk-delete-source-groups-btn')?.addEventListener('click', () => {
    handleBulkDeleteSourceGroups();
  });
  document.getElementById('bulk-delete-candidates-btn')?.addEventListener('click', () => {
    handleBulkDeleteCandidates();
  });
}

// Database Management Functions
// ==========================================

export function renderDatabasePanel() {
  const dbTotalCount = document.getElementById('db-total-count');
  const dbCustomCount = document.getElementById('db-custom-count');
  const drinksTableBody = document.getElementById('drinks-table-body');
  const tabDatabase = document.getElementById('tab-database');
  const tabContentWrapper = document.querySelector('.tab-content-wrapper');
  const mainContent = document.getElementById('main-content');
  
  if (tabDatabase && tabContentWrapper && mainContent) {
    const tabDatabaseParent = tabDatabase.parentElement;
    if (tabDatabaseParent !== tabContentWrapper) {
      tabContentWrapper.appendChild(tabDatabase);
    }
  }
  
  const allDrinks = getAllDrinks();
  const customCount = allDrinks.filter(d => d.id.startsWith('custom_')).length;
  
  if (dbTotalCount) {
    dbTotalCount.textContent = allDrinks.length;
  }
  if (dbCustomCount) {
    dbCustomCount.textContent = customCount;
  }
  
  if (drinksTableBody) {
    renderDrinksTableToElement(allDrinks, drinksTableBody);
  }

  renderKnowledgeAcquisitionPanel();
}

function renderDrinksTableToElement(drinks, container) {
  container.innerHTML = drinks.map(drink => `
    <tr>
      <td>${drink.brand || '-'}</td>
      <td>${drink.name}</td>
      <td>${TYPE_DEFINITIONS[drink.type]?.label || drink.type}</td>
      <td>${drink.caffeine}</td>
      <td>${drink.baseSugar}</td>
      <td>${drink.defaultVolume}</td>
      <td>
        <button class="table-edit-btn" data-drink-id="${drink.id}" title="编辑">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>
            <path d="m15 5 4 4"/>
          </svg>
        </button>
      </td>
    </tr>
  `).join('');
  
  document.querySelectorAll('.table-edit-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const drinkId = btn.dataset.drinkId;
      openEditModal(drinkId);
    });
  });
}

function handleAddDrinkToDatabase() {
  const type = document.querySelector('input[name="new-drink-type"]:checked').value;
  const brand = document.getElementById('new-drink-brand').value.trim();
  const name = document.getElementById('new-drink-name').value.trim();
  const caffeine = parseInt(document.getElementById('new-drink-caffeine').value, 10);
  const baseSugar = parseFloat(document.getElementById('new-drink-sugar').value);
  const defaultVolume = parseInt(document.getElementById('new-drink-volume').value, 10);

  const errors = [];
  if (!name || name.length < 2) errors.push('饮品名称至少需要2个字符');
  if (isNaN(caffeine) || caffeine < 0 || caffeine > 500) errors.push('咖啡因含量必须是0-500之间的数值');
  if (isNaN(baseSugar) || baseSugar < 0 || baseSugar > 100) errors.push('糖分含量必须是0-100之间的数值');
  if (isNaN(defaultVolume) || defaultVolume < 10 || defaultVolume > 2000) errors.push('容量必须是10-2000ml之间的数值');

  if (errors.length > 0) {
    alert('输入验证失败：\n' + errors.join('\n'));
    return;
  }

  addDrink(type, { brand, name, caffeine, baseSugar, defaultVolume });

  elements.addDrinkForm.reset();
  document.getElementById('new-drink-caffeine').value = 100;
  document.getElementById('new-drink-sugar').value = 10;
  document.getElementById('new-drink-volume').value = 500;

  renderDatabasePanel();
  if (_onDatabaseChanged) _onDatabaseChanged();
}
function openEditModal(drinkId) {
  const drink = getDrinkById(drinkId);
  if (!drink) return;
  
  document.getElementById('edit-drink-id').value = drinkId;
  document.getElementById('edit-drink-brand').value = drink.brand || '';
  document.getElementById('edit-drink-name').value = drink.name || '';
  document.getElementById('edit-drink-caffeine').value = drink.caffeine || 0;
  document.getElementById('edit-drink-sugar').value = drink.baseSugar || 0;
  document.getElementById('edit-drink-volume').value = drink.defaultVolume || 500;
  
  elements.editDrinkModal.style.display = 'flex';
}

function closeEditModal() {
  elements.editDrinkModal.style.display = 'none';
  elements.editDrinkForm.reset();
}

function handleUpdateDrink() {
  const drinkId = document.getElementById('edit-drink-id').value;
  const brand = document.getElementById('edit-drink-brand').value.trim();
  const name = document.getElementById('edit-drink-name').value.trim();
  const caffeine = parseInt(document.getElementById('edit-drink-caffeine').value, 10);
  const baseSugar = parseFloat(document.getElementById('edit-drink-sugar').value);
  const defaultVolume = parseInt(document.getElementById('edit-drink-volume').value, 10);

  const errors = [];
  if (!name || name.length < 2) errors.push('饮品名称至少需要2个字符');
  if (isNaN(caffeine) || caffeine < 0 || caffeine > 500) errors.push('咖啡因含量必须是0-500之间的数值');
  if (isNaN(baseSugar) || baseSugar < 0 || baseSugar > 100) errors.push('糖分含量必须是0-100之间的数值');
  if (isNaN(defaultVolume) || defaultVolume < 10 || defaultVolume > 2000) errors.push('容量必须是10-2000ml之间的数值');

  if (errors.length > 0) {
    alert('输入验证失败：\n' + errors.join('\n'));
    return;
  }

  updateDrink(drinkId, { brand, name, caffeine, baseSugar, defaultVolume });

  closeEditModal();
  renderDatabasePanel();
  if (_onDatabaseChanged) _onDatabaseChanged();
}
function handleDeleteDrink() {
  const drinkId = document.getElementById('edit-drink-id').value;
  
  if (confirm('确定要删除这个饮品吗？')) {
    deleteDrink(drinkId);
    closeEditModal();
    renderDatabasePanel();
    if (_onDatabaseChanged) _onDatabaseChanged();
  }
}

function openImportModal() {
  elements.importModal.style.display = 'flex';
  elements.importFilename.textContent = '';
  elements.importExecuteBtn.disabled = true;
  elements.importResult.textContent = '';
  elements.importFile.value = '';
}

function closeImportModal() {
  elements.importModal.style.display = 'none';
}

function handleImportFile() {
  const file = elements.importFile.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    const content = e.target.result;
    const result = parseAndImportCSV(content);
    
    if (result.success) {
      elements.importResult.innerHTML = `<span style="color: green;">✅ 成功导入 ${result.successCount} 条饮品数据</span>`;
      renderDatabasePanel();
      if (_onDatabaseChanged) _onDatabaseChanged();
    } else {
      elements.importResult.innerHTML = `<span style="color: red;">❌ 导入失败：${result.error}</span>`;
    }
  };
  reader.readAsText(file, 'UTF-8');
}

function parseAndImportCSV(content) {
  const lines = content.split('\n').filter(line => line.trim());
  if (lines.length < 2) {
    return { success: false, error: 'CSV 文件内容为空或只有表头' };
  }

  const validTypes = ['coffee', 'teacoffee', 'tea', 'milktea', 'fruittea', 'soda'];
  let successCount = 0;
  let errorMessages = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const parts = parseCSVLine(line);
    if (parts.length < 6) {
      errorMessages.push(`第 ${i + 1} 行：列数不足`);
      continue;
    }

    const [type, brand, name, caffeineStr, sugarStr, volumeStr] = parts;

    if (!validTypes.includes(type)) {
      errorMessages.push(`第 ${i + 1} 行：无效类型 "${type}"`);
      continue;
    }

    if (!name || !name.trim()) {
      errorMessages.push(`第 ${i + 1} 行：饮品名称为空`);
      continue;
    }

    const caffeine = parseFloat(caffeineStr);
    const sugar = parseFloat(sugarStr);
    const volume = parseInt(volumeStr, 10);

    if (isNaN(caffeine)) {
      errorMessages.push(`第 ${i + 1} 行：咖啡因值无效`);
      continue;
    }

    if (isNaN(sugar)) {
      errorMessages.push(`第 ${i + 1} 行：糖分值无效`);
      continue;
    }

    if (isNaN(volume) || volume <= 0) {
      errorMessages.push(`第 ${i + 1} 行：容量值必须大于0`);
      continue;
    }


    addDrink(type, {
      brand: brand || '',
      name: name.trim(),
      caffeine,
      baseSugar: sugar,
      defaultVolume: volume
    });

    successCount++;
  }

  if (errorMessages.length > 0) {
    return { 
      success: false, 
      error: errorMessages.slice(0, 5).join('；') + (errorMessages.length > 5 ? `（还有 ${errorMessages.length - 5} 条错误）` : '') 
    };
  }

  return { success: true, successCount };
}

function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  
  result.push(current);
  return result.map(item => item.trim());
}

async function renderKnowledgeAcquisitionPanel() {
  const candidateList = document.getElementById('acquisition-candidates-list');
  const evidenceList = document.getElementById('acquisition-evidence-list');
  const candidateSelect = document.getElementById('evidence-candidate-select');
  const countBadge = document.getElementById('acquisition-candidate-count');
  if (!candidateList || !evidenceList || !candidateSelect) return;

  try {
    const [candidateData, evidenceData] = await Promise.all([
      fetchKnowledgeCandidatesApi(),
      fetchKnowledgeEvidenceApi()
    ]);
    const candidates = candidateData.candidates || [];
    const evidenceRows = evidenceData.evidence || [];

    if (countBadge) countBadge.textContent = candidates.length;
    candidateSelect.innerHTML = candidates.length
      ? candidates.map(candidate => `<option value="${candidate.id}">${candidate.brand || '-'} ${candidate.name}</option>`).join('')
      : '<option value="">暂无候选</option>';

    candidateList.innerHTML = renderReviewQueue(candidates, evidenceRows);
    evidenceList.innerHTML = '';

    candidateList.querySelectorAll('.approve-evidence-btn').forEach(btn => {
      btn.addEventListener('click', () => handleApproveEvidence(btn.dataset.evidenceId));
    });
    candidateList.querySelectorAll('.delete-evidence-btn').forEach(btn => {
      btn.addEventListener('click', () => handleDeleteEvidence(btn.dataset.evidenceId));
    });
    candidateList.querySelectorAll('.delete-candidate-btn').forEach(btn => {
      btn.addEventListener('click', () => handleDeleteCandidate(btn.dataset.candidateId));
    });
    candidateList.querySelectorAll('.approve-evidence-group-btn').forEach(btn => {
      btn.addEventListener('click', () => handleApproveEvidenceGroup(btn.dataset.evidenceIds));
    });
    candidateList.querySelectorAll('.delete-evidence-group-btn').forEach(btn => {
      btn.addEventListener('click', () => handleDeleteEvidenceGroup(btn.dataset.evidenceIds));
    });
    bindSourceGroupSelection(candidateList);
  } catch (e) {
    candidateList.innerHTML = '<div class="acquisition-empty">无法连接后端采集接口</div>';
    evidenceList.innerHTML = '';
  }
}

function renderReviewQueue(candidates, evidenceRows) {
  if (!candidates.length && !evidenceRows.length) {
    return '<div class="acquisition-empty">暂无待审核内容</div>';
  }

  const sourceGroups = groupEvidenceBySource(evidenceRows);
  const evidenceByCandidate = new Map();
  evidenceRows.forEach(evidence => {
    const key = evidence.candidate_id || '';
    if (!evidenceByCandidate.has(key)) evidenceByCandidate.set(key, []);
    evidenceByCandidate.get(key).push(evidence);
  });

  const sourceGroupCards = sourceGroups.map(group => (
    renderSourceReviewGroup(group, candidates, evidenceByCandidate)
  ));

  const orphanEvidence = evidenceRows.filter(evidence => (
    !evidence.candidate_id || !candidates.some(candidate => candidate.id === evidence.candidate_id)
  ));
  const orphanBlock = orphanEvidence.length
    ? `
      <div class="acquisition-review-group">
        <div class="acquisition-review-head">
          <div>
            <div class="acquisition-title">未匹配证据</div>
            <div class="acquisition-meta">这些证据没有找到对应候选，可单独入库或删除。</div>
          </div>
        </div>
        <div class="acquisition-evidence-stack">
          ${orphanEvidence.map(evidence => renderEvidenceItem(evidence)).join('')}
        </div>
      </div>
    `
    : '';

  const candidateIdsInSourceGroups = new Set(evidenceRows.map(evidence => evidence.candidate_id).filter(Boolean));
  const candidateWithoutEvidence = candidates
    .filter(candidate => !candidateIdsInSourceGroups.has(candidate.id))
    .map(candidate => renderCandidateReviewItem(candidate, []));

  return [...sourceGroupCards, ...candidateWithoutEvidence, orphanBlock].join('');
}

function groupEvidenceBySource(evidenceRows) {
  const groups = new Map();
  evidenceRows.forEach(evidence => {
    if (!evidence.candidate_id) return;
    const key = [
      evidence.source_type || 'manual',
      evidence.source_url || '',
      evidence.raw_evidence || ''
    ].join('|');
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        source_type: evidence.source_type || 'manual',
        source_url: evidence.source_url || '',
        evidence: []
      });
    }
    groups.get(key).evidence.push(evidence);
  });
  return Array.from(groups.values());
}

function renderSourceReviewGroup(group, candidates, evidenceByCandidate) {
  const evidenceIds = group.evidence.map(evidence => evidence.id);
  const candidateIds = new Set(group.evidence.map(evidence => evidence.candidate_id).filter(Boolean));
  const groupCandidates = candidates.filter(candidate => candidateIds.has(candidate.id));
  const sourceLabel = formatSourceLabel(group);
  return `
    <div class="acquisition-source-group" data-source-group>
      <div class="acquisition-source-head">
        <input type="checkbox" class="source-group-select" value="${escapeAttr(evidenceIds.join(','))}" aria-label="选择来源组">
        <div>
          <div class="acquisition-title">${escapeHtml(sourceLabel)}</div>
          <div class="acquisition-meta">${groupCandidates.length} 个候选 · ${evidenceIds.length} 条证据</div>
        </div>
        <div class="acquisition-actions">
          <button type="button" class="btn btn-primary approve-evidence-group-btn" data-evidence-ids="${escapeAttr(evidenceIds.join(','))}">入库这一组</button>
          <button type="button" class="mini-danger-btn delete-evidence-group-btn" data-evidence-ids="${escapeAttr(evidenceIds.join(','))}">删除这一组证据</button>
        </div>
      </div>
      <div class="acquisition-source-body">
        ${groupCandidates.map(candidate => renderCandidateReviewItem(candidate, evidenceByCandidate.get(candidate.id) || [])).join('')}
      </div>
    </div>
  `;
}

function bindSourceGroupSelection(container) {
  const selectAll = document.getElementById('select-all-source-groups');
  const groupInputs = Array.from(container.querySelectorAll('.source-group-select'));
  const updateSelectAll = () => {
    if (!selectAll) return;
    const checkedCount = groupInputs.filter(input => input.checked).length;
    selectAll.checked = groupInputs.length > 0 && checkedCount === groupInputs.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < groupInputs.length;
  };

  groupInputs.forEach(input => {
    input.addEventListener('change', () => {
      const group = input.closest('[data-source-group]');
      setGroupChildrenChecked(group, input.checked);
      input.indeterminate = false;
      updateSelectAll();
    });
  });

  container.querySelectorAll('.candidate-select, .evidence-select').forEach(input => {
    input.addEventListener('change', () => {
      const group = input.closest('[data-source-group]');
      updateGroupSelectionState(group);
      updateSelectAll();
    });
  });

  if (selectAll) {
    selectAll.onchange = () => {
      groupInputs.forEach(input => {
        input.checked = selectAll.checked;
        input.indeterminate = false;
        setGroupChildrenChecked(input.closest('[data-source-group]'), selectAll.checked);
      });
      selectAll.indeterminate = false;
    };
  }

  groupInputs.forEach(input => updateGroupSelectionState(input.closest('[data-source-group]')));
  updateSelectAll();
}

function setGroupChildrenChecked(group, checked) {
  if (!group) return;
  group.querySelectorAll('.candidate-select, .evidence-select').forEach(input => {
    input.checked = checked;
  });
}

function updateGroupSelectionState(group) {
  if (!group) return;
  const groupInput = group.querySelector('.source-group-select');
  const childInputs = Array.from(group.querySelectorAll('.candidate-select, .evidence-select'));
  if (!groupInput || !childInputs.length) return;
  const checkedCount = childInputs.filter(input => input.checked).length;
  groupInput.checked = checkedCount === childInputs.length;
  groupInput.indeterminate = checkedCount > 0 && checkedCount < childInputs.length;
}

function renderCandidateReviewItem(candidate, evidenceRows = []) {
  const evidenceCountText = evidenceRows.length ? `${evidenceRows.length} 条证据` : '暂无证据';
  return `
    <div class="acquisition-review-group">
      <div class="acquisition-review-head">
        <input type="checkbox" class="candidate-select" value="${candidate.id}" aria-label="选择候选">
        <div>
          <div class="acquisition-title">${escapeHtml(candidate.brand || '-')} ${escapeHtml(candidate.name)}</div>
          <div class="acquisition-meta">${candidate.type || '-'} · ${candidate.status || '-'} · ${evidenceCountText} · 置信度 ${formatConfidence(candidate.confidence)}</div>
        </div>
        <div class="acquisition-actions">
          <span class="mini-badge">${candidate.discovery_method || 'manual'}</span>
          <button type="button" class="mini-danger-btn delete-candidate-btn" data-candidate-id="${candidate.id}">删除候选</button>
        </div>
      </div>
      <div class="acquisition-evidence-stack">
        ${evidenceRows.length
          ? evidenceRows.map(evidence => renderEvidenceItem(evidence)).join('')
          : '<div class="acquisition-empty inline-empty">还没有证据，可以在上方添加证据文本。</div>'}
      </div>
    </div>
  `;
}

function renderEvidenceItem(evidence) {
  const extracted = evidence.extracted || {};
  return `
    <div class="acquisition-item acquisition-evidence-item">
      <input type="checkbox" class="evidence-select" value="${evidence.id}" aria-label="选择证据">
      <div>
        <div class="acquisition-title">${evidence.source_type || 'manual'} · ${evidence.status || '-'}</div>
        <div class="acquisition-meta">
          ${extracted.volume || '-'}ml · 咖啡因 ${formatNutritionValue(extracted.caffeine, 'mg')} · 糖分 ${formatNutritionValue(extracted.sugar, 'g')} · ${formatNutritionScope(extracted)} · 置信度 ${formatConfidence(evidence.confidence)}
        </div>
      </div>
      <div class="acquisition-actions">
        <button type="button" class="btn btn-primary approve-evidence-btn" data-evidence-id="${evidence.id}">入库</button>
        <button type="button" class="mini-danger-btn delete-evidence-btn" data-evidence-id="${evidence.id}">删除</button>
      </div>
    </div>
  `;
}

function handleImageFileSelected(e) {
  const file = e.target.files?.[0];
  const preview = document.getElementById('acquisition-image-preview');
  const result = document.getElementById('image-analysis-result');
  _imageAnalysisItems = [];
  if (result) result.innerHTML = '';
  document.getElementById('stage-image-items-btn')?.setAttribute('disabled', 'true');
  if (!preview) return;

  if (!file) {
    preview.className = 'image-preview-empty';
    preview.textContent = '暂无图片';
    return;
  }

  const url = URL.createObjectURL(file);
  preview.className = 'image-preview-box';
  preview.innerHTML = `<img src="${url}" alt="上传图片预览">`;
}

async function handleAnalyzeImage() {
  const input = document.getElementById('acquisition-image-file');
  const file = input?.files?.[0];
  if (!file) {
    setAcquisitionResult('请先选择一张图片', false);
    return;
  }

  const button = document.getElementById('analyze-image-btn');
  if (button) {
    button.disabled = true;
    button.textContent = '识别中...';
  }

  try {
    const data = await analyzeKnowledgeImageApi(file);
    _imageAnalysisItems = data.items || [];
    renderImageAnalysisItems(_imageAnalysisItems, data);
    setAcquisitionResult(data.message || `识别完成：${_imageAnalysisItems.length} 条`, _imageAnalysisItems.length > 0);
  } catch (e) {
    _imageAnalysisItems = [];
    renderImageAnalysisItems([], { message: '图片识别失败，请确认后端已启动并配置视觉模型 API' });
    setAcquisitionResult('图片识别失败：后端未启动或视觉模型未配置', false);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = '识别图片';
    }
  }
}

function renderImageAnalysisItems(items, meta = {}) {
  const container = document.getElementById('image-analysis-result');
  const stageBtn = document.getElementById('stage-image-items-btn');
  if (!container) return;

  if (!items.length) {
    container.innerHTML = `<div class="acquisition-empty">${meta.message || '暂无识别结果'}</div>`;
    if (stageBtn) stageBtn.disabled = true;
    return;
  }

  container.innerHTML = `
    <div class="image-items-table-wrap">
      <table class="image-items-table">
        <thead>
          <tr>
            <th>选</th>
            <th>品牌</th>
            <th>饮品</th>
            <th>类型</th>
            <th>容量</th>
            <th>咖啡因</th>
            <th>糖分</th>
            <th>置信度</th>
          </tr>
        </thead>
        <tbody>
          ${items.map((item, index) => renderImageItemRow(item, index)).join('')}
        </tbody>
      </table>
    </div>
  `;
  if (stageBtn) stageBtn.disabled = false;
}

function renderImageItemRow(item, index) {
  return `
    <tr data-image-item-index="${index}">
      <td><input type="checkbox" class="image-item-selected" checked></td>
      <td><input class="image-item-brand" value="${escapeAttr(item.brand || '')}"></td>
      <td><input class="image-item-name" value="${escapeAttr(item.name || '')}"></td>
      <td>
        <select class="image-item-type">
          ${renderTypeOptions(item.type || 'coffee')}
        </select>
      </td>
      <td><input type="number" class="image-item-volume" value="${item.volume ?? ''}" placeholder="ml"></td>
      <td><input type="number" class="image-item-caffeine" value="${item.caffeine ?? ''}" placeholder="mg"></td>
      <td><input type="number" class="image-item-sugar" value="${item.sugar ?? ''}" placeholder="未知"></td>
      <td>${formatConfidence(item.confidence)}</td>
    </tr>
  `;
}

function renderTypeOptions(selected) {
  return Object.entries(TYPE_DEFINITIONS).map(([value, def]) => (
    `<option value="${value}" ${value === selected ? 'selected' : ''}>${def.label}</option>`
  )).join('');
}

async function handleStageImageItems() {
  const rows = document.querySelectorAll('[data-image-item-index]');
  const items = [];
  rows.forEach(row => {
    if (!row.querySelector('.image-item-selected')?.checked) return;
    const name = row.querySelector('.image-item-name')?.value.trim();
    if (!name) return;
    const original = _imageAnalysisItems[Number(row.dataset.imageItemIndex)] || {};
    items.push({
      brand: row.querySelector('.image-item-brand')?.value.trim() || null,
      name,
      type: row.querySelector('.image-item-type')?.value || 'coffee',
      volume: parseOptionalNumber(row.querySelector('.image-item-volume')?.value),
      caffeine: parseOptionalNumber(row.querySelector('.image-item-caffeine')?.value),
      sugar: parseOptionalNumber(row.querySelector('.image-item-sugar')?.value),
      volume_note: original.volume_note || null,
      raw_evidence: original.raw_evidence || name,
      confidence: original.confidence || 0.65
    });
  });

  if (!items.length) {
    setAcquisitionResult('请选择至少一条识别结果', false);
    return;
  }

  try {
    const sourceType = document.getElementById('image-source-type')?.value || 'image_upload';
    const data = await importKnowledgeImageItemsApi(items, sourceType);
    const skippedCount = data.skipped?.length || 0;
    const skippedText = skippedCount ? `，跳过 ${skippedCount} 条缺少营养数值的结果` : '';
    setAcquisitionResult(`已加入审核队列：${data.count} 条${skippedText}`, true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`批量加入审核失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleCreateCandidate() {
  const result = document.getElementById('acquisition-result');
  const payload = {
    brand: document.getElementById('acquisition-brand').value.trim(),
    name: document.getElementById('acquisition-name').value.trim(),
    type: document.getElementById('acquisition-type').value,
    source_url: document.getElementById('acquisition-source-url').value.trim() || null,
    discovery_method: 'manual',
    confidence: 0.6
  };

  if (!payload.name) {
    setAcquisitionResult('请输入候选饮品名称', false);
    return;
  }

  try {
    await createKnowledgeCandidateApi(payload);
    document.getElementById('acquisition-candidate-form').reset();
    setAcquisitionResult('候选已创建', true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult('候选创建失败：来源可能被策略拦截或后端未启动', false);
  }
}

async function handleCreateEvidence() {
  const candidateId = document.getElementById('evidence-candidate-select').value;
  const rawEvidence = document.getElementById('evidence-raw').value.trim();
  if (!candidateId || !rawEvidence) {
    setAcquisitionResult('请选择候选并填写证据文本', false);
    return;
  }

  try {
    await addKnowledgeEvidenceApi(candidateId, {
      source_type: document.getElementById('evidence-source-type').value,
      source_url: document.getElementById('evidence-source-url').value.trim() || null,
      raw_evidence: rawEvidence
    });
    document.getElementById('acquisition-evidence-form').reset();
    setAcquisitionResult('证据已抽取，等待审核入库', true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult('证据提交失败：来源可能被策略拦截或后端未启动', false);
  }
}

async function handleApproveEvidence(evidenceId) {
  if (!evidenceId) return;
  try {
    await approveKnowledgeEvidenceApi(evidenceId);
    await loadDatabaseAsync();
    setAcquisitionResult('证据已审核入库，并同步知识库', true);
    renderDatabasePanel();
    if (_onDatabaseChanged) _onDatabaseChanged();
  } catch (e) {
    setAcquisitionResult('入库失败：证据字段不足或后端未启动', false);
  }
}

async function handleBulkApproveEvidence() {
  const ids = getCheckedValues('.evidence-select');
  if (!ids.length) {
    setAcquisitionResult('请选择至少一条证据', false);
    return;
  }
  try {
    const data = await approveKnowledgeEvidenceBulkApi(ids);
    await loadDatabaseAsync();
    const errorText = data.errors?.length ? `，${data.errors.length} 条失败` : '';
    setAcquisitionResult(`已入库 ${data.approved?.length || 0} 条证据${errorText}`, true);
    renderDatabasePanel();
    if (_onDatabaseChanged) _onDatabaseChanged();
  } catch (e) {
    setAcquisitionResult(`批量入库失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleApproveEvidenceGroup(idsText) {
  const ids = parseEvidenceIds(idsText);
  if (!ids.length) return;
  try {
    const data = await approveKnowledgeEvidenceBulkApi(ids);
    await loadDatabaseAsync();
    const errorText = data.errors?.length ? `，${data.errors.length} 条失败` : '';
    setAcquisitionResult(`这一组已入库 ${data.approved?.length || 0} 条证据${errorText}`, true);
    renderDatabasePanel();
    if (_onDatabaseChanged) _onDatabaseChanged();
  } catch (e) {
    setAcquisitionResult(`这一组入库失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleBulkApproveSourceGroups() {
  const ids = getSelectedSourceGroupEvidenceIds();
  if (!ids.length) {
    setAcquisitionResult('请选择至少一个来源组', false);
    return;
  }
  try {
    const data = await approveKnowledgeEvidenceBulkApi(ids);
    await loadDatabaseAsync();
    const errorText = data.errors?.length ? `，${data.errors.length} 条失败` : '';
    setAcquisitionResult(`选中组已入库 ${data.approved?.length || 0} 条证据${errorText}`, true);
    renderDatabasePanel();
    if (_onDatabaseChanged) _onDatabaseChanged();
  } catch (e) {
    setAcquisitionResult(`选中组入库失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleDeleteEvidence(evidenceId) {
  if (!evidenceId) return;
  try {
    await deleteKnowledgeEvidenceApi(evidenceId);
    setAcquisitionResult('证据已删除', true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`删除证据失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleBulkDeleteEvidence() {
  const ids = getCheckedValues('.evidence-select');
  if (!ids.length) {
    setAcquisitionResult('请选择至少一条证据', false);
    return;
  }
  try {
    const data = await deleteKnowledgeEvidenceBulkApi(ids);
    setAcquisitionResult(`已删除证据 ${data.deleted || 0} 条`, true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`批量删除证据失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleDeleteEvidenceGroup(idsText) {
  const ids = parseEvidenceIds(idsText);
  if (!ids.length) return;
  try {
    const data = await deleteKnowledgeEvidenceBulkApi(ids);
    setAcquisitionResult(`这一组已删除证据 ${data.deleted || 0} 条`, true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`这一组删除失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleBulkDeleteSourceGroups() {
  const ids = getSelectedSourceGroupEvidenceIds();
  if (!ids.length) {
    setAcquisitionResult('请选择至少一个来源组', false);
    return;
  }
  try {
    const data = await deleteKnowledgeEvidenceBulkApi(ids);
    setAcquisitionResult(`选中组已删除证据 ${data.deleted || 0} 条`, true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`选中组删除失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleDeleteCandidate(candidateId) {
  if (!candidateId) return;
  try {
    await deleteKnowledgeCandidateApi(candidateId);
    setAcquisitionResult('候选已删除，关联证据也已隐藏', true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`删除候选失败：${e.message || '请确认后端已启动'}`, false);
  }
}

async function handleBulkDeleteCandidates() {
  const ids = getCheckedValues('.candidate-select');
  if (!ids.length) {
    setAcquisitionResult('请选择至少一个候选', false);
    return;
  }
  try {
    const data = await deleteKnowledgeCandidatesBulkApi(ids);
    setAcquisitionResult(`已删除候选 ${data.deleted || 0} 个，关联证据也已隐藏`, true);
    renderKnowledgeAcquisitionPanel();
  } catch (e) {
    setAcquisitionResult(`批量删除候选失败：${e.message || '请确认后端已启动'}`, false);
  }
}

function setAcquisitionResult(message, success) {
  const result = document.getElementById('acquisition-result');
  if (!result) return;
  result.textContent = message;
  result.className = `acquisition-result ${success ? 'success' : 'error'}`;
}

function formatConfidence(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return '-';
  return `${Math.round(num * 100)}%`;
}

function formatNutritionValue(value, unit) {
  return value === null || value === undefined ? '未知' : `${value}${unit}`;
}

function formatNutritionScope(extracted = {}) {
  const hasCaffeine = extracted.caffeine !== null && extracted.caffeine !== undefined;
  const hasSugar = extracted.sugar !== null && extracted.sugar !== undefined;
  if (hasCaffeine && !hasSugar) return '仅咖啡因';
  if (hasSugar && !hasCaffeine) return '仅糖分';
  if (hasCaffeine && hasSugar) return '咖啡因+糖分';
  return '部分数据';
}

function parseOptionalNumber(value) {
  if (value === '' || value === null || value === undefined) return null;
  const num = Number(value);
  return Number.isNaN(num) ? null : num;
}

function escapeAttr(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function formatSourceLabel(group) {
  const typeLabel = {
    image_upload: '图片识别来源',
    official: '官方来源',
    nutrition_label: '营养表来源',
    community_measurement: '实测来源',
    user_feedback: '用户反馈来源',
    manual: '手动证据来源'
  }[group.source_type] || group.source_type || '证据来源';
  return group.source_url ? `${typeLabel} · ${group.source_url}` : typeLabel;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function getCheckedValues(selector) {
  return Array.from(document.querySelectorAll(selector))
    .filter(input => input.checked)
    .map(input => input.value)
    .filter(Boolean);
}

function getSelectedSourceGroupEvidenceIds() {
  const ids = Array.from(document.querySelectorAll('.source-group-select'))
    .filter(input => input.checked)
    .flatMap(input => parseEvidenceIds(input.value));
  return Array.from(new Set(ids));
}

function parseEvidenceIds(idsText = '') {
  return String(idsText)
    .split(',')
    .map(id => id.trim())
    .filter(Boolean);
}
