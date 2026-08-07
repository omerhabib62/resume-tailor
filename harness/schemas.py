import json
from pydantic import BaseModel, Field, model_validator, field_validator, ConfigDict


def _as_str(v):
    return v if isinstance(v, str) else ("" if v is None else json.dumps(v))

class Task(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)   # int id -> "1"
    id: str
    description: str
    files: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    acceptance: str = ""

    @field_validator("id", "description", "acceptance", mode="before")
    @classmethod
    def _str(cls, v): return _as_str(v)

    @field_validator("files", "depends_on", mode="before")
    @classmethod
    def _list_str(cls, v): return [str(x) for x in (v or [])]

class Plan(BaseModel):
    tasks: list[Task]


class FileEdit(BaseModel):
    path: str
    content: str
    @model_validator(mode="before")
    @classmethod
    def _key(cls, v):
        if isinstance(v, dict) and "path" not in v and "file" in v:
            return {"path": v["file"], "content": v.get("content", "")}
        return v

class EngineerOutput(BaseModel):
    files: list[FileEdit]
    notes: str = ""
    @model_validator(mode="before")
    @classmethod
    def _wrap(cls, v):
        # handle a flat single-file object: {"file"/"path", "content"}
        if isinstance(v, dict) and "files" not in v:
            path = v.get("path") or v.get("file")
            if path and "content" in v:
                return {"files": [{"path": path, "content": v["content"]}], "notes": v.get("notes", "")}
        return v
    @field_validator("notes", mode="before")
    @classmethod
    def _n(cls, v): return _as_str(v)

class ReviewResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    fix_instructions: str = ""
    @field_validator("issues", mode="before")
    @classmethod
    def _iss(cls, v): return [_as_str(x) for x in (v or [])]
    @field_validator("fix_instructions", mode="before")
    @classmethod
    def _fx(cls, v): return _as_str(v)