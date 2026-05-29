from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {"msg": "Solinilla en Render - OK"}

@app.get("/api/test")
def test():
    return {"status": "online"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)