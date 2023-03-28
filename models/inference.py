from typing import List, Dict

from pydantic import BaseModel

class PrefixInfoModel(BaseModel):
    prefix: str
    uri: List[str] | str

class FieldInfo(BaseModel):
    name: str
    type: str
    subtype: str | None = None
    format: str
    annotation: str | List[str] | None = None
    prefix: PrefixInfoModel | None


class InferenceModel(BaseModel):
    filename: str = None
    inferences: List[FieldInfo]
