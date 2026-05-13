import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .db import db, get_runtime_config, init_db, row_to_dict, update_runtime_config, utc_now
from .evaluation import run_evaluation
from .rag import answer_question, ingest_upload, reindex_document
from .schemas import ChatRequest, ConfigUpdate, FeedbackRequest


app = FastAPI(title="企业知识库智能助手")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        return await ingest_upload(file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/documents")
def list_documents():
    with db() as conn:
        rows = conn.execute(text("select * from documents order by created_at desc")).fetchall()
    return [row_to_dict(row) for row in rows]


@app.post("/api/documents/{document_id}/reindex")
def reindex(document_id: int):
    try:
        return reindex_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
async def chat(payload: ChatRequest):
    return await answer_question(payload.question, payload.conversation_id, payload.top_k, payload.rerank, payload.min_score)


@app.post("/api/feedback")
def feedback(payload: FeedbackRequest):
    with db() as conn:
        conn.execute(
            text("insert into feedback(message_id, rating, comment, created_at) values(:message_id, :rating, :comment, :created_at)"),
            {
                "message_id": payload.message_id,
                "rating": payload.rating,
                "comment": payload.comment,
                "created_at": utc_now(),
            },
        )
    return {"ok": True}


@app.get("/api/config")
def config():
    return get_runtime_config()


@app.post("/api/config")
def save_config(payload: ConfigUpdate):
    data = payload.clean()
    if "chunk_overlap" in data and "chunk_size" in data and data["chunk_overlap"] >= data["chunk_size"]:
        raise HTTPException(status_code=400, detail="片段重叠长度必须小于片段长度")
    return update_runtime_config(data)


@app.get("/api/logs")
def logs(limit: int = 50):
    with db() as conn:
        rows = conn.execute(
            text("select * from messages order by created_at desc limit :limit"),
            {"limit": min(limit, 200)},
        ).fetchall()
    items = []
    for row in rows:
        item = row_to_dict(row)
        item["sources"] = json.loads(item.pop("sources_json"))
        items.append(item)
    return items


@app.post("/api/evaluate")
async def evaluate():
    try:
        return await run_evaluation()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
