from fastapi import APIRouter, File, HTTPException, UploadFile

from ..db import get_runtime_config, update_runtime_config
from ..evaluation import run_evaluation
from ..rag import answer_question, ingest_upload, reindex_document
from ..repositories import create_feedback, list_documents as list_documents_repository, list_message_logs
from ..schemas import ChatRequest, ConfigUpdate, FeedbackRequest


router = APIRouter(prefix="/api")


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        return await ingest_upload(file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents")
def list_documents():
    return list_documents_repository()


@router.post("/documents/{document_id}/reindex")
def reindex(document_id: int):
    try:
        return reindex_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat")
async def chat(payload: ChatRequest):
    return await answer_question(payload.question, payload.conversation_id, payload.top_k, payload.rerank, payload.min_score)


@router.post("/feedback")
def feedback(payload: FeedbackRequest):
    create_feedback(payload.message_id, payload.rating, payload.comment)
    return {"ok": True}


@router.get("/config")
def config():
    return get_runtime_config()


@router.post("/config")
def save_config(payload: ConfigUpdate):
    data = payload.clean()
    if "chunk_overlap" in data and "chunk_size" in data and data["chunk_overlap"] >= data["chunk_size"]:
        raise HTTPException(status_code=400, detail="片段重叠长度必须小于片段长度")
    return update_runtime_config(data)


@router.get("/logs")
def logs(limit: int = 50):
    return list_message_logs(limit)


@router.post("/evaluate")
async def evaluate():
    try:
        return await run_evaluation()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
