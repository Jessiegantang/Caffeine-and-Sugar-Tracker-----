// ==========================================
// Caffeine and Sugar Tracker - Configuration & Presets
// ==========================================

// Preset Templates
// Caffeine and sugar are intentionally not stored here. The backend nutrition
// pipeline is the single source of truth for those estimates.
export const PRESET_TEMPLATES = {
  'luckin-americano': { brand: '瑞幸咖啡', name: '冰美式', type: 'coffee', sugar: 'none', volume: 650 },
  'luckin-coconut-americano': { brand: '瑞幸咖啡', name: '椰青美式', type: 'coffee', sugar: 'none', volume: 500, baseSugarOverride: 2.2 },
  'luckin-latte': { brand: '瑞幸咖啡', name: '生椰拿铁', type: 'coffee', sugar: 'half', volume: 500 },
  'cotti-coco': { brand: '库迪咖啡', name: '生椰拿铁', type: 'coffee', sugar: 'half', volume: 600 },
  'milktea-standard': { brand: '通用', name: '珍珠奶茶', type: 'milktea', sugar: 'full', volume: 500 },
  'fruittea-standard': { brand: '通用', name: '柠檬果茶', type: 'fruittea', sugar: 'half', volume: 500 },
  'tea-green': { brand: '通用', name: '绿茶', type: 'tea', sugar: 'none', volume: 350 },
  'soda-cola': { brand: '可口可乐', name: '经典可乐', type: 'soda', sugar: 'full', volume: 330 }
};

// Health Limits
export const CAFFEINE_LIMIT = 400; // mg
export const SUGAR_LIMIT = 50; // g
