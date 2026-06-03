import { elements } from '../state.js';
import { TYPE_DEFINITIONS, getDrinkById, getAllDrinks, addDrink, updateDrink, deleteDrink, resetDatabase } from '../drinks-database.js';

let _onDatabaseChanged = null;

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
  const abv = parseFloat(document.getElementById('new-drink-abv').value) || 0;
  
  // Input validation
  const errors = [];
  
  if (!name || name.length < 2) {
    errors.push('饮品名称至少需要2个字符');
  }
  
  if (isNaN(caffeine) || caffeine < 0 || caffeine > 500) {
    errors.push('咖啡因含量必须是0-500之间的数值');
  }
  
  if (isNaN(baseSugar) || baseSugar < 0 || baseSugar > 100) {
    errors.push('糖分含量必须是0-100之间的数值');
  }
  
  if (isNaN(defaultVolume) || defaultVolume < 10 || defaultVolume > 2000) {
    errors.push('容量必须是10-2000ml之间的数值');
  }
  
  if (abv < 0 || abv > 95) {
    errors.push('酒精度必须是0-95之间的数值');
  }
  
  if (errors.length > 0) {
    alert('输入验证失败：\n' + errors.join('\n'));
    return;
  }
  
  addDrink(type, { brand, name, caffeine, baseSugar, defaultVolume, abv });
  
  elements.addDrinkForm.reset();
  document.getElementById('new-drink-caffeine').value = 100;
  document.getElementById('new-drink-sugar').value = 10;
  document.getElementById('new-drink-volume').value = 500;
  document.getElementById('new-drink-abv').value = 0;
  
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
  document.getElementById('edit-drink-abv').value = drink.abv || 0;
  
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
  const abv = parseFloat(document.getElementById('edit-drink-abv').value) || 0;
  
  // Input validation
  const errors = [];
  
  if (!name || name.length < 2) {
    errors.push('饮品名称至少需要2个字符');
  }
  
  if (isNaN(caffeine) || caffeine < 0 || caffeine > 500) {
    errors.push('咖啡因含量必须是0-500之间的数值');
  }
  
  if (isNaN(baseSugar) || baseSugar < 0 || baseSugar > 100) {
    errors.push('糖分含量必须是0-100之间的数值');
  }
  
  if (isNaN(defaultVolume) || defaultVolume < 10 || defaultVolume > 2000) {
    errors.push('容量必须是10-2000ml之间的数值');
  }
  
  if (abv < 0 || abv > 95) {
    errors.push('酒精度必须是0-95之间的数值');
  }
  
  if (errors.length > 0) {
    alert('输入验证失败：\n' + errors.join('\n'));
    return;
  }
  
  updateDrink(drinkId, { brand, name, caffeine, baseSugar, defaultVolume, abv });
  
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

  const validTypes = ['coffee', 'teacoffee', 'tea', 'milktea', 'fruittea', 'soda', 'alcohol'];
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

    const [type, brand, name, caffeineStr, sugarStr, volumeStr, abvStr] = parts;

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

    const abv = abvStr ? parseFloat(abvStr) : 0;

    addDrink(type, {
      brand: brand || '',
      name: name.trim(),
      caffeine,
      baseSugar: sugar,
      defaultVolume: volume,
      abv: isNaN(abv) ? 0 : abv
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
