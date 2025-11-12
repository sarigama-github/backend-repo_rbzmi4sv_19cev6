import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Task

app = FastAPI(title="Todo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers to serialize ObjectId
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def serialize_task(doc: dict) -> dict:
    doc = doc.copy()
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.get("/")
def read_root():
    return {"message": "Todo API is running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

# CRUD Endpoints for tasks

class TaskCreate(BaseModel):
    title: str
    notes: Optional[str] = None
    completed: bool = False
    priority: Optional[int] = 2
    due_date: Optional[str] = None  # ISO string

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[int] = None
    due_date: Optional[str] = None

@app.get("/api/tasks")
async def list_tasks() -> List[dict]:
    docs = get_documents("task", {}, limit=None)
    return [serialize_task(d) for d in docs]

@app.post("/api/tasks", status_code=201)
async def create_task(payload: TaskCreate):
    # Validate against schema
    task = Task(
        title=payload.title,
        notes=payload.notes,
        completed=payload.completed,
        priority=payload.priority,
        # due_date will be parsed by schema if provided; keep None or parse in frontend
    )
    inserted_id = create_document("task", task)
    doc = db["task"].find_one({"_id": ObjectId(inserted_id)})
    return serialize_task(doc)

@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskUpdate):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    update_fields = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = db["task"].update_one({"_id": ObjectId(task_id)}, {"$set": update_fields})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    doc = db["task"].find_one({"_id": ObjectId(task_id)})
    return serialize_task(doc)

@app.delete("/api/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    res = db["task"].delete_one({"_id": ObjectId(task_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
