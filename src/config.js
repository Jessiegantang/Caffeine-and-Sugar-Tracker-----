// ==========================================
// Caffeine and Sugar Tracker - Configuration & Presets V3
// ==========================================

// Caffeine Density (mg per 100ml)
export const CAFFEINE_DENSITIES = {
  coffee: 30,     // e.g., 500ml Coffee = 150mg
  teacoffee: 35,  // e.g., 500ml Tea-Coffee = 175mg (concentrated espresso + tea)
  tea: 10,        // e.g., 500ml Tea = 50mg
  milktea: 16,    // e.g., 500ml Milk Tea = 80mg
  fruittea: 6,    // e.g., 500ml Fruit Tea = 30mg
  soda: 9,        // e.g., 330ml Coke = 30mg caffeine
  alcohol: 0      // Alcohol drinks contain no caffeine (unless mixed like Jägerbombs)
};

// Base Sugar Density (g per 100ml)
// Inherent sugars from ingredients like milk (lactose), fruit juices/jams, maltose
export const BASE_SUGAR_DENSITIES = {
  coffee: 0,
  teacoffee: 0,
  tea: 0,
  milktea: 1.8,   // e.g., 500ml Milk Tea = 9g natural base sugar
  fruittea: 2.2,  // e.g., 500ml Fruit Tea = 11g base sugar from fruits
  soda: 0,
  alcohol: 0      // Beer usually has negligible sugar; custom drinks override this
};

// Added Sweetener Sugar Density (g per 100ml)
// Added sugar syrups at full sweetness (100%)
export const SWEETENER_SUGAR_DENSITIES = {
  coffee: 2.0,
  teacoffee: 2.0,
  tea: 2.0,
  milktea: 7.2,
  fruittea: 7.8,
  soda: 10.6,     // e.g., 330ml Regular Coke = 35g added sugar
  alcohol: 4.0    // Used if sweet liqueurs/syrups are added; beer standard is none
};

// Sweetness multiplier mapping
export const SWEETNESS_MULTIPLIERS = {
  none: 0,    // 不另外加糖 (0%)
  three: 0.3, // 三分糖 (30%)
  half: 0.5,  // 半糖 (50%)
  seven: 0.7, // 七分糖 (70%)
  full: 1.0   // 全糖 (100%)
};

// Preset Templates
export const PRESET_TEMPLATES = {
  'luckin-americano': { brand: '瑞幸咖啡', name: '冰美式', type: 'coffee', sugar: 'none', volume: 650 },
  'luckin-coconut-americano': { brand: '瑞幸咖啡', name: '椰青美式', type: 'coffee', sugar: 'none', volume: 500, baseSugarOverride: 2.2 },
  'luckin-latte': { brand: '瑞幸咖啡', name: '生椰拿铁', type: 'coffee', sugar: 'half', volume: 500 },
  'cotti-coco': { brand: '库迪咖啡', name: '生椰拿铁', type: 'coffee', sugar: 'half', volume: 600 },
  'milktea-standard': { brand: '通用', name: '珍珠奶茶', type: 'milktea', sugar: 'full', volume: 500 },
  'fruittea-standard': { brand: '通用', name: '柠檬果茶', type: 'fruittea', sugar: 'half', volume: 500 },
  'tea-green': { brand: '通用', name: '绿茶', type: 'tea', sugar: 'none', volume: 350 },
  'soda-cola': { brand: '可口可乐', name: '经典可乐', type: 'soda', sugar: 'full', volume: 330 },
  'beer-standard': { brand: '青岛啤酒', name: '经典啤酒', type: 'alcohol', sugar: 'none', volume: 500, abv: 4.0 },
  'cocktail-standard': { brand: '自调', name: '莫吉托鸡尾酒', type: 'alcohol', sugar: 'half', volume: 250, abv: 12.0, baseSugarOverride: 5.0 }
};

// Health Limits
export const CAFFEINE_LIMIT = 400; // mg
export const SUGAR_LIMIT = 50;     // g
export const ALCOHOL_LIMIT = 20;   // g (approx. 1 standard drink)
export const ALCOHOL_DENSITY = 0.8; // g/ml
