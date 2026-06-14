from services.memory_service import clear_user_memory, read_user_memory


def get_user_preferences(db) -> dict:
    return {"status": "success", "preferences": read_user_memory(db)}


def delete_user_preferences(db) -> dict:
    deleted = clear_user_memory(db)
    return {"status": "success", "deleted": deleted}
