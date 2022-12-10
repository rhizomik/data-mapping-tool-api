from pydantic import BaseModel


class KeyModel(BaseModel):
    filename: str = None
    key: str or None = None
