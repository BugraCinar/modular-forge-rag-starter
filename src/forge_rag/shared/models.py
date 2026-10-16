from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

Identifier = str


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str
    tenant: str
    groups: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ("rag:read", "rag:write")

    @property
    def actor(self) -> str:
        return f"{self.issuer}:{self.subject}"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentInput(StrictModel):
    external_id: str = Field(min_length=1, max_length=128, pattern=r"^[\w.:-]+$")
    dataset: str = Field(
        default="default", min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1, max_length=1_400_000)
    media_type: str = Field(
        default="text/plain", pattern=r"^(text/plain|text/markdown|application/pdf)$"
    )
    read_subjects: list[str] = Field(default_factory=list, max_length=100)
    read_groups: list[str] = Field(default_factory=list, max_length=100)


class QueryInput(StrictModel):
    question: str = Field(min_length=1, max_length=2000)
    dataset: str = Field(
        default="default", min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    top_k: int = Field(default=5, ge=1, le=10)


@dataclass(frozen=True)
class Section:
    text: str
    page: int | None = None


@dataclass(frozen=True)
class Piece:
    text: str
    position: int
    start: int
    end: int
    page: int | None = None


@dataclass
class Hit:
    id: str
    document_id: str
    revision: int
    title: str
    text: str
    position: int
    page: int | None
    start: int
    end: int
    similarity: float = 0
    lexical: float = 0
    score: float = 0


class Statement(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    chunk_ids: list[str] = Field(min_length=1, max_length=10)


class Generation(StrictModel):
    statements: list[Statement] = Field(max_length=10)


@dataclass
class Generated:
    content: Generation
    usage: dict[str, int] = field(default_factory=dict)
