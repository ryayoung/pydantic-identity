from typing import Any
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
import orjson


process_start_datetime = datetime.now(timezone.utc)


def get_class_fullname(cls: type, *, path_parts: int = 2) -> str:
    """Class name that includes N path parts. i.e., with 2 parts: `foo.bar.MyCls`."""
    path = get_filepath_cls_was_defined_in(cls) or ""
    path = truncate_path(path, parts_to_keep=path_parts)
    path = path.removesuffix(".py")
    parts = [*Path(path).parts, cls.__name__]
    return ".".join(parts)


def truncate_path(path: str, *, parts_to_keep: int) -> str:
    """Remove all but the last N parts of a path."""
    if not parts_to_keep:
        return ""
    parts = Path(path).parts[-parts_to_keep:]
    if len(parts) == 0:
        return ""
    return os.path.join(*parts)


def get_filepath_cls_was_defined_in(cls: type) -> str | None:
    """
    Returns None if the filepath can't be found, due to the object being created
    dynamically or for some other reason.
    """
    if not (module := sys.modules.get(cls.__module__)):
        return None
    if not (file := getattr(module, "__file__", None)):
        return None
    return file


def json_dumps(obj: Any, sort_keys: bool = False) -> bytes:
    """Better JSON serialization"""
    opts = 0
    if sort_keys:
        opts |= orjson.OPT_SORT_KEYS
    return orjson.dumps(obj, option=opts)


def json_loads(data: bytes) -> Any:
    """Better JSON deserialization"""
    return orjson.loads(data)
