from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.twilio import router as twilio_router

app = FastAPI()
app.include_router(twilio_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
