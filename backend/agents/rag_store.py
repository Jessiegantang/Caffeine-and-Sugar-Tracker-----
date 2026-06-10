import os

from langchain_chroma import Chroma
from langchain_core.documents import Document

from .llm_config import embeddings, env_truthy


default_chroma_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
chroma_path = os.getenv("CHROMA_PERSIST_DIR", default_chroma_path)
use_chroma = os.getenv("CHROMA_PERSIST_DIR") is not None or not env_truthy("DRINKMIND_OFFLINE")

if use_chroma and os.path.exists(chroma_path):
    vectorstore = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
else:
    vectorstore = None
    retriever = None


def sync_chroma_document(kb_id, data: dict):
    if not vectorstore:
        return
    delete_chroma_document(kb_id)
    content = (
        f"鍝佺墝: {data.get('brand', '')}\n"
        f"鍚嶇О: {data.get('name', '')}\n"
        f"鏉瀷: {data.get('volume', 500)}ml\n"
        f"鍜栧暋鍥犲惈閲? {data.get('caffeine', 0)}mg\n"
        f"绯栧垎鍚噺: {data.get('baseSugar', 0)}g"
    )
    doc = Document(
        page_content=content,
        metadata={
            "id": kb_id,
            "brand": data.get("brand", ""),
            "name": data.get("name", ""),
            "caffeine": data.get("caffeine", 0),
            "sugar": data.get("baseSugar", 0),
            "source": data.get("source", "鐭ヨ瘑搴?"),
            "confidence": data.get("confidence", 0.9),
        },
    )
    vectorstore.add_documents([doc], ids=[kb_id])
    print(f"[Chroma Sync] Synced {kb_id} to ChromaDB")


def delete_chroma_document(kb_id):
    if not vectorstore:
        return
    try:
        vectorstore.delete(ids=[kb_id])
        print(f"[Chroma Sync] Deleted {kb_id} from ChromaDB")
    except Exception:
        pass
