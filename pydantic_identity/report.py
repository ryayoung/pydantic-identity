from datetime import datetime
from .utils import process_start_datetime
import pydantic


class SchemaIdentityInfoHashSettings(pydantic.BaseModel):
    track_descriptions: bool
    track_field_order: bool
    track_type_order: bool
    tracked_filepath_parts: int
    track_validation_mode: bool


class SchemaIdentityInfo(pydantic.BaseModel):
    fullname: str
    date: datetime = process_start_datetime
    hash: str
    hash_settings: SchemaIdentityInfoHashSettings
