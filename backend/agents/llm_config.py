import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


load_dotenv()

base_url = os.getenv("BASE_URL")
api_key = os.getenv("OPENAI_API_KEY", "dummy_key_if_none")
model_name = os.getenv("MODEL_NAME", "gpt-3.5-turbo")


def env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"true", "1", "yes"}


def llm_enabled() -> bool:
    if env_truthy("DRINKMIND_OFFLINE"):
        return False
    current_api_key = os.getenv("OPENAI_API_KEY", "")
    if not current_api_key or current_api_key.startswith("dummy_"):
        return False
    return env_truthy("ENABLE_LLM")


if base_url:
    llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)
    embeddings = OpenAIEmbeddings(
        model="text-embedding-v3",
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False,
    )
else:
    llm = ChatOpenAI(model=model_name, api_key=api_key)
    embeddings = OpenAIEmbeddings(
        model="text-embedding-v3",
        api_key=api_key,
        check_embedding_ctx_length=False,
    )


def get_llm():
    return llm
