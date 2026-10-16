from fastapi import APIRouter, Depends, Header, Request, Response

from forge_rag.security.dependencies import reader, writer
from forge_rag.shared.models import DocumentInput

router = APIRouter(prefix="/v1", tags=["Documents"])


@router.post("/documents", status_code=202)
def enqueue(
    payload: DocumentInput,
    request: Request,
    idempotency_key: str = Header(...),
    account=Depends(writer),
):
    return request.app.state.rag.ingestion.enqueue(account, payload, idempotency_key)


@router.get("/documents/{document_id}")
def document(document_id: str, request: Request, account=Depends(reader)):
    return request.app.state.rag.repository.document(account, document_id)


@router.delete("/documents/{document_id}", status_code=204)
def remove(document_id: str, request: Request, account=Depends(writer)):
    request.app.state.rag.repository.delete(account, document_id)
    return Response(status_code=204)


@router.get("/jobs/{job_id}")
def job(job_id: str, request: Request, account=Depends(writer)):
    return request.app.state.rag.repository.job(account, job_id)
