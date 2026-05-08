from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import pdf_router
from routers.similarity_router import router as similarity_router
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pdf_router.router, prefix="/pdf", tags=["PDF"])
app.include_router(similarity_router, prefix="/similarity", tags=["Similarity"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)