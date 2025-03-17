# pyright: reportRedeclaration=false
# pyright: reportInvalidTypeForm=false
from typing import Literal
from pydantic import ConfigDict, Field
from pydantic_identity import BaseIdentityModel


class BaseModel(BaseIdentityModel):
    """
    Used as base class for tests, with sensible Pydantic model config defaults to make
    testing easier, and also sets its own class configurations, so tests won't break
    as a result of changes to the actual defaults of these configurations.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_attribute_docstrings=True,
        from_attributes=True,
    )
    model_schema_hash_track_descriptions = True
    model_schema_hash_track_field_order = True
    model_schema_hash_track_type_order = True
    model_schema_hash_tracked_extra_data = None
    model_schema_hash_limit_length = 12
    model_schema_hash_tracked_filepath_parts = 2
    model_schema_hash_track_validation_mode = True


def test_multi_inheritance():
    """
    Schema hashes are cached in the class. Registries should be implemented properly, to
    prevent incorrect cache lookups when multiple inheritance is used, and the parent
    sets its cache before the child.
    """

    class Foo(BaseModel):
        a: int = 1

    class Bar(Foo):
        b: int = 2

    # Get Foo's hash first, since it's the parent. If the cache is not implemented
    # correctly, this will cause Bar's cache lookup to pull from Foo's cache instead
    # of making its own.
    foo_hash = Foo.model_schema_hash_get()
    bar_hash = Bar.model_schema_hash_get()

    assert foo_hash != bar_hash


def test_track_descriptions():
    """
    When descriptions are tracked, changing a description should cause the hash to
    change. Otherwise, it should not.
    """

    class Tracked(BaseModel):
        model_schema_hash_track_descriptions = True

    class Untracked(BaseModel):
        model_schema_hash_track_descriptions = False

    def test(base: type) -> tuple[str, str]:

        class Foo(base):
            a: int = Field(..., description="RED")

        class Bar(base):
            a: int = Field(..., description="YELLOW")

        Bar.__name__ = Foo.__name__
        return Foo.model_schema_hash_get(), Bar.model_schema_hash_get()

    tracked1, tracked2 = test(Tracked)
    untracked1, untracked2 = test(Untracked)

    assert tracked1 != tracked2
    assert untracked1 == untracked2


def test_track_field_order():
    """
    When field order is tracked, changing the order of fields should cause the hash to
    change. Otherwise, it should not.
    """

    class Tracked(BaseModel):
        model_schema_hash_track_field_order = True

    class Untracked(BaseModel):
        model_schema_hash_track_field_order = False

    def test(base: type) -> tuple[str, str]:

        class Foo(base):
            a: int
            b: int

        class Bar(base):
            b: int
            a: int

        Bar.__name__ = Foo.__name__
        return Foo.model_schema_hash_get(), Bar.model_schema_hash_get()

    tracked1, tracked2 = test(Tracked)
    untracked1, untracked2 = test(Untracked)

    assert tracked1 != tracked2
    assert untracked1 == untracked2


def test_track_type_order_unions():
    """
    When type order is tracked, changing the order of any 'list'-like structures in the
    type annotations should cause the hash to change. Otherwise, it should not.
    """

    class Tracked(BaseModel):
        model_schema_hash_track_type_order = True

    class Untracked(BaseModel):
        model_schema_hash_track_type_order = False

    def test(base: type) -> tuple[str, str]:

        class Foo(base):
            a: int | None | Literal["5"] | float = None

        class Bar(base):
            a: float | None | int | Literal["5"] = None

        Bar.__name__ = Foo.__name__
        return Foo.model_schema_hash_get(), Bar.model_schema_hash_get()

    tracked1, tracked2 = test(Tracked)
    untracked1, untracked2 = test(Untracked)

    assert tracked1 != tracked2
    assert untracked1 == untracked2


def test_track_type_order_arbitrary_nested_lists():
    """
    When type order is tracked, changing the order of any 'list'-like structures nested
    deep in the type annotations should cause the hash to change.
    """

    class Tracked(BaseModel):
        model_schema_hash_track_type_order = True

    class Untracked(BaseModel):
        model_schema_hash_track_type_order = False

    def test(base: type) -> tuple[str, str]:

        class Foo(base):
            a: Literal[{"a": [{"b": [2, 1]}, 1]}] | int | None = None

        class Bar(base):
            a: Literal[{"a": [{"b": [1, 2]}, 1]}] | int | None = None

        Bar.__name__ = Foo.__name__
        return Foo.model_schema_hash_get(), Bar.model_schema_hash_get()

    tracked1, tracked2 = test(Tracked)
    untracked1, untracked2 = test(Untracked)

    assert tracked1 != tracked2
    assert untracked1 == untracked2


def test_tracked_validation_json_schema_mode():
    """
    The main difference between schema modes is whether validation field names are used,
    or serialization field names are used. So the focus is on field aliasing behavior.
    """
    from decimal import Decimal

    class Tracked(BaseModel):
        model_schema_hash_track_validation_mode = True

    class Untracked(BaseModel):
        model_schema_hash_track_validation_mode = False

    def test(base: type) -> tuple[str, str]:

        class Foo(base):
            a: Decimal

        class Bar(base):
            a: str

        Bar.__name__ = Foo.__name__
        return Foo.model_schema_hash_get(), Bar.model_schema_hash_get()

    tracked1, tracked2 = test(Tracked)
    untracked1, untracked2 = test(Untracked)

    assert tracked1 != tracked2
    assert untracked1 == untracked2


def test_track_type_order_ignore_defaults():
    """
    When type order is untracked - causing us to sort values in type arguments - we
    want to make sure we don't accidentally touch field default values during this
    sorting process.
    """

    class Untracked(BaseModel):
        model_schema_hash_track_type_order = False

    def test(base: type) -> tuple[str, str]:

        class Foo(base):
            a: list | None = [1, 2, 3]

        class Bar(base):
            a: list | None = [3, 2, 1]

        Bar.__name__ = Foo.__name__
        return Foo.model_schema_hash_get(), Bar.model_schema_hash_get()

    untracked1, untracked2 = test(Untracked)

    assert untracked1 != untracked2


def test_track_extra_data():
    class M1(BaseModel):
        model_schema_hash_tracked_extra_data = ["a", "b"]
        x: int

    class M2(BaseModel):
        model_schema_hash_tracked_extra_data = ["foo", "bar"]
        x: int

    class M3(BaseModel):
        model_schema_hash_tracked_extra_data = None
        x: int

    assert (
        M1.model_schema_hash_get()
        != M2.model_schema_hash_get()
        != M3.model_schema_hash_get()
    )


def test_track_limit_length():
    from hashlib import md5

    class Base(BaseModel):
        model_schema_hash_function = lambda x: md5(x).hexdigest()

    class M0(Base):
        model_schema_hash_limit_length = 5
        a: int

    class M1(Base):
        model_schema_hash_limit_length = None
        b: int

    class M2(Base):
        model_schema_hash_limit_length = 0
        c: int

    class M3(Base):
        model_schema_hash_limit_length = 1000
        d: int

    hashes = [
        M0.model_schema_hash_get(),
        M1.model_schema_hash_get(),
        M2.model_schema_hash_get(),
        M3.model_schema_hash_get(),
    ]

    assert (
        len(set(hashes)) == 4
        and len(hashes[0]) == 5
        and all([len(h) == 32 for h in hashes[1:]])
    )


def test_tracked_filepath_parts():
    class M0(BaseModel):
        model_schema_hash_tracked_filepath_parts = 0
        x: int

    class M1(BaseModel):
        model_schema_hash_tracked_filepath_parts = 1
        x: int

    class M2(BaseModel):
        model_schema_hash_tracked_filepath_parts = 2
        x: int

    class M3(BaseModel):
        model_schema_hash_tracked_filepath_parts = 1000
        x: int

    names = [
        M0.model_schema_get_fullname(),
        M1.model_schema_get_fullname(),
        M2.model_schema_get_fullname(),
        M3.model_schema_get_fullname(),
    ]
    assert names[0] == "M0"
    assert len(names[1].split(".")) == 2
    assert len(names[2].split(".")) == 3
    assert len(names[3].split(".")) > len(names[2].split("."))
