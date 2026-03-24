from dotenv import load_dotenv

load_dotenv()  # load .env before anything else reads env vars

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.routes import claude, gemini, ollama

app = FastAPI(
    title="AI CLI Bridge",
    description="RESTful API wrapper for claude, gemini, and ollama CLI tools",
    version="1.0.0",
)

app.include_router(claude.router, prefix="/v1/claude")
app.include_router(gemini.router, prefix="/v1/gemini")
app.include_router(ollama.router, prefix="/v1/ollama")


@app.get("/health", tags=["health"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})
