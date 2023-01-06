from pydantic import BaseModel, EmailStr, Field, conlist


class PrefixModel(BaseModel):
    prefix: str
    url: str
