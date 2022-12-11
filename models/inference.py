from typing import List, Dict

from pydantic import BaseModel


class FieldInfo(BaseModel):
    name: str
    type: str
    subtype: str | None = None
    format: str
    annotation: str | None = None


class InferenceModel(BaseModel):
    filename: str = None
    inferences: List[FieldInfo]
