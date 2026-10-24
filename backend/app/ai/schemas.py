from pydantic import BaseModel, Field, field_validator

from app.models.enums import TicketCategory, TicketPriority


def _match_enum(enum_cls, value):
    """Tolerate case/whitespace differences; anything else still fails validation."""
    if isinstance(value, str):
        key = " ".join(value.split()).casefold()
        for member in enum_cls:
            if member.value.casefold() == key:
                return member
    return value


class TriageResult(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=400)

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v):
        return _match_enum(TicketCategory, v)

    @field_validator("priority", mode="before")
    @classmethod
    def _pri(cls, v):
        return _match_enum(TicketPriority, v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        if isinstance(v, str):
            try:
                v = float(v.strip().rstrip("%"))
            except ValueError:
                return v
        if isinstance(v, (int, float)) and 1 < v <= 100:  # model answered in percent
            return v / 100
        return v

    @field_validator("rationale", mode="before")
    @classmethod
    def _rat(cls, v):
        return v.strip()[:400] if isinstance(v, str) else v


class DraftResult(BaseModel):
    draft: str = Field(min_length=40, max_length=4000)
    verify_before_sending: list[str] = Field(default_factory=list)

    @field_validator("draft", mode="before")
    @classmethod
    def _draft(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("verify_before_sending", mode="before")
    @classmethod
    def _verify(cls, v):
        if not isinstance(v, list):
            return []
        return [str(x).strip()[:200] for x in v[:5] if str(x).strip()]