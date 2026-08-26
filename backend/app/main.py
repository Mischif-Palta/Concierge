from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from app.catalog import router as catalog_router
from app.sessions import router as sessions_router
from app.cart import router as cart_router
from app.audit import router as audit_router

load_dotenv()
app = FastAPI(title="Concierge Commerce API", description="Agent-readable merchant catalog API for Concierge.", version="1.0.0",)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "https://concierge-commerce.vercel.app"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(catalog_router)
app.include_router(sessions_router)
app.include_router(cart_router)
app.include_router(audit_router)

@app.get("/")
def root():
    return {"message" : "concierge api"}

@app.get("/health")
def health_check():
    return {"status" : "ok", "message" : "concierge backend is running"}

