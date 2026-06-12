import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers.agent import router as agent_router
from api.routers.health import router as health_router
from api.routers.knowledge import router as knowledge_router
from api.routers.logs import router as logs_router
from database import init_db


app = FastAPI(title="DrinkMind Agent API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB
init_db()

app.include_router(logs_router)
app.include_router(agent_router)
app.include_router(knowledge_router)
app.include_router(health_router)

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), ".."), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
