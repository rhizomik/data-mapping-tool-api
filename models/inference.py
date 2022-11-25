from typing import List, Dict

from pydantic import BaseModel


class FieldInfo(BaseModel):
    name: str
    type: str
    format: str


class InferenceModel(BaseModel):
    filename: str = None
    inferences: List[FieldInfo]
