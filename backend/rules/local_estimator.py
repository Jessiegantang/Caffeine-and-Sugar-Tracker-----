import re
from db.database import SessionLocal, DrinkKnowledge
from sqlalchemy import func

SWEETNESS_MULTIPLIERS = {
    'none': 0.0,
    'three': 0.3,
    'half': 0.5,
    'seven': 0.7,
    'full': 1.0
}

def estimate_nutrition(brand: str, name: str, drink_type: str, volume: int, sugar_level: str) -> dict:
    """
    Estimates nutrition based on dynamic averages from the SQLite knowledge base.
    """
    db = SessionLocal()
    reasoning = []
    lower_name = name.lower() if name else ""

    caffeine_density = 0.0  # mg per 100ml
    sugar_density = 0.0     # g per 100ml

    try:
        # 1. Try to find average for this brand and type
        if brand:
            brand_records = db.query(DrinkKnowledge).filter(
                DrinkKnowledge.brand.ilike(f"%{brand}%"),
                DrinkKnowledge.type == drink_type
            ).all()
            
            if brand_records:
                avg_caf = sum((r.caffeine / r.volume * 100) for r in brand_records if r.volume) / len(brand_records)
                avg_sug = sum((r.baseSugar / r.volume * 100) for r in brand_records if r.volume) / len(brand_records)
                caffeine_density = avg_caf
                sugar_density = avg_sug
                reasoning.append(f"基于知识库中 {brand} {drink_type} 的 {len(brand_records)} 条数据动态计算平均密度: 咖啡因 {avg_caf:.1f}mg/100ml, 糖分 {avg_sug:.1f}g/100ml")

        # 2. Fallback to general type average if no brand data
        if caffeine_density == 0.0 and sugar_density == 0.0:
            type_records = db.query(DrinkKnowledge).filter(DrinkKnowledge.type == drink_type).all()
            if type_records:
                avg_caf = sum((r.caffeine / r.volume * 100) for r in type_records if r.volume) / len(type_records)
                avg_sug = sum((r.baseSugar / r.volume * 100) for r in type_records if r.volume) / len(type_records)
                caffeine_density = avg_caf
                sugar_density = avg_sug
                reasoning.append(f"未找到该品牌数据，基于知识库中 {drink_type} 类型的 {len(type_records)} 条数据动态计算平均密度: 咖啡因 {avg_caf:.1f}mg/100ml, 糖分 {avg_sug:.1f}g/100ml")

        # 3. Ultimate Fallback to basic heuristics if DB is empty for this type
        if caffeine_density == 0.0:
            if drink_type == 'coffee':
                caffeine_density = 50.0
                sugar_density = 2.0
            elif drink_type == 'milktea':
                caffeine_density = 16.0
                sugar_density = 5.0
            elif drink_type == 'tea':
                caffeine_density = 10.0
            else:
                caffeine_density = 0.0
                sugar_density = 4.0
            reasoning.append("知识库样本不足，使用系统基础保底密度估算。")

        # Adjust sugar based on user selection
        multiplier = SWEETNESS_MULTIPLIERS.get(sugar_level, 0.5)  # default half if unknown
        # Assume base sugar density is for full sugar
        estimated_sugar = (volume * sugar_density / 100.0) * multiplier
        estimated_caffeine = (volume * caffeine_density / 100.0)

        reasoning.append(f"应用甜度系数 {multiplier} ({sugar_level})")
        reasoning.append(f"最终测算: 容量 {volume}ml -> 咖啡因 {estimated_caffeine:.1f}mg, 糖分 {estimated_sugar:.1f}g")

        return {
            "caffeine": round(estimated_caffeine, 1),
            "sugar": round(estimated_sugar, 1),
            "source": "Local Estimator (Dynamic DB)",
            "confidence": 0.65,
            "reasoning": reasoning
        }
    finally:
        db.close()
