"""
Pydantic models para request/response.
Compatíveis com o formato do frontend.
"""

from typing import Optional, List, Any, Literal
from pydantic import BaseModel


# ── Chat ──────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system" | "tool"
    content: Any
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list] = None


class ChatRequest(BaseModel):
    """Formato que o frontend envia para /api/agent/chat."""
    messages: List[ChatMessage]
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    session_id: Optional[str] = None
    mode: Optional[str] = "agent"


class ChatSSEEvent(BaseModel):
    type: str  # "steps" | "chunk" | "error"
    content: str


# ── Route ─────────────────────────────────────────────

class RouteRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None


class RouteResponse(BaseModel):
    type: str  # "action" | "reasoning" | "error"
    intent: Optional[str] = None
    confidence: Optional[float] = None
    payload: Optional[dict] = None
    error: Optional[str] = None


# ── Search ────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    search_depth: Optional[str] = "basic"
    max_results: Optional[int] = 5


class SearchResponse(BaseModel):
    answer: Optional[str] = None
    results: Optional[list] = None
    query: Optional[str] = None


# ── Files ─────────────────────────────────────────────

class FileGenerateRequest(BaseModel):
    type: str  # "pdf" | "pptx" | "docx" | "excel" | "xlsx"
    title: str
    content: str


class FileGenerateResponse(BaseModel):
    url: str
    message: str


class SessionFileUploadResponse(BaseModel):
    session_id: str
    file_id: str
    original_name: str
    size_bytes: int
    status: Literal["uploaded", "processing", "ready", "failed"]
    message: str


class SessionFileItem(BaseModel):
    file_id: str
    original_name: str
    stored_path: str
    extracted_text_path: Optional[str] = None
    mime_type: str
    size_bytes: int
    status: Literal["uploaded", "processing", "ready", "failed"]
    created_at: str
    processed_at: Optional[str] = None
    error: Optional[str] = None


class SessionFileListResponse(BaseModel):
    session_id: str
    files: List[SessionFileItem]


class SessionFilesDeleteResponse(BaseModel):
    session_id: str
    deleted: bool
    message: str


# ── OCR ───────────────────────────────────────────────

class OCRRequest(BaseModel):
    image_url: str


class OCRResponse(BaseModel):
    text: str
    confidence: float


# ── Health ────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    model: str
    uptime_seconds: int
    sessions_active: int
    tools_available: int
