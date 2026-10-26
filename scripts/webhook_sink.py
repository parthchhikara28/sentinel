from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/hook")
async def hook(request: Request) -> dict:
    body = await request.json()
    print("RECEIVED:", body)
    return {"ok": True}
