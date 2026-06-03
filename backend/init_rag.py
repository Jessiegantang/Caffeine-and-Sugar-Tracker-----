import os
import sys
import json
import uuid
from database import SessionLocal, DrinkKnowledge, init_db
from agent import vectorstore, embeddings, sync_chroma_document, chroma_path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8')

def init_knowledge_base():
    # Ensure DB tables exist
    init_db()
    db = SessionLocal()
    
    try:
        count = db.query(DrinkKnowledge).count()
        if count > 0:
            print(f"✅ SQLite 知识库已有 {count} 条数据，将全量同步到 ChromaDB。")
            # Sync existing data
            items = db.query(DrinkKnowledge).all()
            for db_kb in items:
                sync_chroma_document(db_kb.id, {
                    "brand": db_kb.brand,
                    "name": db_kb.name,
                    "volume": db_kb.volume,
                    "caffeine": db_kb.caffeine,
                    "baseSugar": db_kb.baseSugar,
                    "source": db_kb.source,
                    "confidence": db_kb.confidence
                })
            print(f"✅ 成功同步 {count} 条记录到 ChromaDB。")
            return
            
        print("🚀 开始初始化饮品知识库...")
        
        # Load from JSON
        json_path = os.path.join(os.path.dirname(__file__), 'knowledge_base.json')
        if not os.path.exists(json_path):
            print("⚠️ 未找到 knowledge_base.json，跳过初始化。")
            return
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        added_count = 0
        if isinstance(data, list):
            items = data
        else:
            # Fallback if it's the frontend dict format
            items = []
            for category, details in data.items():
                for item in details.get('items', []):
                    item['type'] = category
                    items.append(item)
                    
        for item in items:
            # Ensure unique ID
            kb_id = item.get('id', f"kb_{uuid.uuid4().hex[:8]}")
            
            db_kb = DrinkKnowledge(
                id=kb_id,
                brand=item.get('brand', ''),
                name=item.get('name', ''),
                type=item.get('type', '未知'),
                volume=item.get('volume', item.get('defaultVolume', 500)),
                caffeine=item.get('caffeine_mg', item.get('caffeine', 0.0)),
                baseSugar=item.get('sugar_g', item.get('baseSugar', 0.0)),
                abv=item.get('abv', 0.0),
                source=item.get('source', "系统预设权威数据"),
                confidence=item.get('confidence', 0.95)
            )
            db.add(db_kb)
            
            # 同步到 ChromaDB
            sync_chroma_document(kb_id, {
                "brand": db_kb.brand,
                "name": db_kb.name,
                "volume": db_kb.volume,
                "caffeine": db_kb.caffeine,
                "baseSugar": db_kb.baseSugar,
                "source": db_kb.source,
                "confidence": db_kb.confidence
            })
            
            added_count += 1
                
        db.commit()
        print(f"🎉 初始化完成！成功将 {added_count} 条饮品数据录入 SQLite 并建立 Chroma 向量索引。")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 初始化失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_knowledge_base()
