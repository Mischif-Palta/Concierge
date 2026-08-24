from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

@app.get("/")
def root():
    return {"message" : "concierge api"}

@app.get("/health")
def health_check():
    return {"status" : "ok", "message" : "concierge backend is running"}