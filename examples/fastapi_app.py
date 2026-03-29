"""
FastAPI example application for Omnicorn.

Run with:
    omnicorn examples.fastapi_app:app --config .omnicorn.dev.yaml
"""

from fastapi import FastAPI

app = FastAPI(title="Omnicorn Example")


@app.get("/")
async def root():
    return {"message": "Hello from Omnicorn!", "server": "omnicorn"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
