from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "https://concierge-commerce.vercel.app"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"message" : "concierge api"}

@app.get("/health")
def health_check():
    return {"status" : "ok", "message" : "concierge backend is running"}
