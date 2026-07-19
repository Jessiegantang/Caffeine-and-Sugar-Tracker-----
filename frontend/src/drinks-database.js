const API_BASE = 'http://127.0.0.1:8000';

let database = null;

export const TYPE_DEFINITIONS = {
  coffee: { label: '☕ 咖啡', description: '纯咖啡或含奶咖啡饮品。美式咖啡本身无糖，拿铁/摩卡等含奶饮品含有少量乳糖。' },
  teacoffee: { label: '🥥 茶咖', description: '茶与咖啡混合饮品。结合了茶的清香和咖啡的醇厚，通常含有牛奶或植物奶。' },
  tea: { label: '🍵 原叶茶', description: '纯茶类饮品，不含奶和糖。包括绿茶、红茶、乌龙茶等。' },
  milktea: { label: '🧋 奶茶', description: '茶与牛奶/奶精混合饮品。通常含有较多糖分。' },
  fruittea: { label: '🍋 果茶', description: '水果与茶混合饮品。含有水果本身的糖分。' },
  soda: { label: '🥤 汽水', description: '碳酸饮料。通常含有大量添加糖。' },
  other: { label: '其他', description: '无法明确归入咖啡、茶、奶茶、果茶或汽水的饮品。类型不参与营养推断。' },
};

// Map backend DB structure to frontend Category structure
function convertListToDict(dbLogs) {
  const newDb = {
    coffee: { category: '咖啡', items: [] },
    teacoffee: { category: '茶咖', items: [] },
    tea: { category: '原叶茶', items: [] },
    milktea: { category: '奶茶', items: [] },
    fruittea: { category: '果茶', items: [] },
    soda: { category: '汽水', items: [] },
    other: { category: '其他', items: [] },
  };
  
  for (const log of dbLogs) {
    const typeKey = log.type || 'coffee';
    if (!newDb[typeKey]) newDb[typeKey] = { category: '其他', items: [] };
    
    newDb[typeKey].items.push({
      id: log.id,
      brand: log.brand || '',
      name: log.name,
      caffeine: log.caffeine,
      baseSugar: log.baseSugar,
      defaultVolume: log.volume,
      source: log.source,
    });
  }
  return newDb;
}

export async function loadDatabaseAsync() {
  try {
    const response = await fetch(`${API_BASE}/api/knowledge_base`);
    if (response.ok) {
      const dbLogs = await response.json();
      database = convertListToDict(dbLogs);
      console.log('Loaded knowledge base from Backend API');
    }
  } catch (e) {
    console.error('Failed to load DB from API:', e);
    // Fallback to empty if server down
    database = convertListToDict([]);
  }
  return database;
}

export function getDatabase() {
  return database;
}

export function getDrinkById(drinkId) {
  if (!database) return null;
  for (const [type, category] of Object.entries(database)) {
    const drink = category.items.find(item => item.id === drinkId);
    if (drink) return { ...drink, type };
  }
  return null;
}

export function searchDrinks(keyword) {
  if (!database) return [];
  const results = [];
  const lowerKeyword = keyword.toLowerCase();
  
  for (const [type, category] of Object.entries(database)) {
    const matches = category.items.filter(item => 
      item.name.toLowerCase().includes(lowerKeyword) ||
      (item.brand && item.brand.toLowerCase().includes(lowerKeyword))
    );
    results.push(...matches.map(item => ({ ...item, type })));
  }
  
  return results;
}

export function getDrinksByType(type) {
  if (!database) return [];
  return database[type]?.items || [];
}

export async function addDrink(type, drinkData) {
  const newId = `kb_${Date.now()}`;
  const payload = {
    id: newId,
    brand: drinkData.brand || '',
    name: drinkData.name || '',
    type: type,
    volume: drinkData.defaultVolume || 500,
    caffeine: drinkData.caffeine || 0,
    baseSugar: drinkData.baseSugar || 0,
    source: "用户自建知识库",
  };

  // Optimistic update
  if (!database[type]) database[type] = { category: '未知', items: [] };
  database[type].items.push({
    id: newId,
    brand: payload.brand,
    name: payload.name,
    caffeine: payload.caffeine,
    baseSugar: payload.baseSugar,
    defaultVolume: payload.volume,
  });

  try {
    await fetch(`${API_BASE}/api/knowledge_base`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    console.error('Failed to sync new drink to backend API:', e);
  }
  
  return payload;
}

export async function updateDrink(drinkId, drinkData) {
  let foundType = null;
  let foundDrink = null;
  let foundIndex = -1;
  for (const [type, category] of Object.entries(database)) {
    const index = category.items.findIndex(item => item.id === drinkId);
    if (index !== -1) {
      foundDrink = category.items[index];
      foundIndex = index;
      foundType = type;
      break;
    }
  }

  if (foundType && foundDrink) {
    const nextType = drinkData.type || foundType;
    const updatedDrink = {
      ...foundDrink,
      brand: drinkData.brand || '',
      name: drinkData.name || '',
      caffeine: drinkData.caffeine || 0,
      baseSugar: drinkData.baseSugar || 0,
      defaultVolume: drinkData.defaultVolume || 500,
    };

    if (nextType !== foundType) {
      database[foundType].items.splice(foundIndex, 1);
      if (!database[nextType]) database[nextType] = { category: '其他', items: [] };
      database[nextType].items.push(updatedDrink);
    } else {
      Object.assign(foundDrink, updatedDrink);
    }

    const payload = {
      id: drinkId,
      brand: drinkData.brand || '',
      name: drinkData.name || '',
      type: nextType,
      volume: drinkData.defaultVolume || 500,
      caffeine: drinkData.caffeine || 0,
      baseSugar: drinkData.baseSugar || 0,
      source: "用户自建知识库",
    };
    try {
      await fetch(`${API_BASE}/api/knowledge_base/${drinkId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch (e) {
      console.error('Failed to update drink in backend API:', e);
    }
    return true;
  }
  return false;
}

export async function deleteDrink(drinkId) {
  for (const category of Object.values(database)) {
    const index = category.items.findIndex(item => item.id === drinkId);
    if (index !== -1) {
      category.items.splice(index, 1);
      try {
        await fetch(`${API_BASE}/api/knowledge_base/${drinkId}`, {
          method: 'DELETE'
        });
      } catch (e) {
        console.error('Failed to delete drink in backend API:', e);
      }
      return true;
    }
  }
  return false;
}

export function getAllDrinks() {
  if (!database) return [];
  const allDrinks = [];
  for (const [type, category] of Object.entries(database)) {
    allDrinks.push(...category.items.map(item => ({ ...item, type, category: category.category })));
  }
  return allDrinks;
}

export async function resetDatabase() {
  // We don't implement full reset over API for safety, just ignore or implement later.
  console.log("Reset database is disabled in API mode to prevent accidental data loss.");
  return database;
}
