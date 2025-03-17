from typing import ClassVar, Any, Callable, Self
from hashlib import md5
import pydantic
from . import utils
from . import report


def hash_md5_hex(value: bytes) -> str:
    return md5(value).hexdigest()


class BaseIdentityModel(pydantic.BaseModel):
    """
    A BaseModel with the ability to hash its schema. Useful if storing densely nested
    data in a database, and later want to know whether two instances had the same model
    structure, validation rules, or documentation/descriptions, when they were created.

    This base model, by itself, doesn't change any behavior from Pydantic's BaseModel.

    The hash captures schema information for all nested models recursively. So, if you
    have a complex model, you only need to subclass this once, in your root/top-level
    model, to capture the full schema identity.

    Performance: This is generally efficient, because the hash is only computed once per
    model class (not instance), when the class's hash is first accessed.

    CONFIGURABLE BEHAVIOR
    =====================
    The following are configured with class-level variables. Read their docstrings to
    understand how they work, and notice their default values.

    - Whether to track descriptions (class docstrings/field descriptions) in the hash.
    - Whether to track the order of model fields in the hash.
    - Whether to track the order of type unions or any list-like structures in types.
    - Any additional, arbitrary data to track in the hash.
    - Truncated length of the hash
    - How many path parts from the tail of your model's filename to track.
    - Hashing function
    - Whether to track the validation mode of the JSON schema
    """

    # CLASS CONFIG ======================================================================

    model_schema_hash_track_descriptions: ClassVar[bool] = False
    """
    Class config: Whether to track class docstrings and field docstrings/descriptions in
    the schema hash. Disable if you only care about tracking changes to runtime behavior
    of the model. Enable if you care to track if the model's documentation has changed.
    """

    model_schema_hash_track_field_order: ClassVar[bool] = False
    """
    Class config: Whether the hash should track the order of fields in the schema.
    """

    model_schema_hash_track_type_order: ClassVar[bool] = False
    """
    Class config: Whether the schema hash should track the order of type union arguments,
    arguments to `Literal[...]`, Enums, and any other lists found in type annotations.
    """

    model_schema_hash_tracked_extra_data: ClassVar[Any] = None
    """
    Class config: Any additional data the hash should track. This might include configs,
    env variables, prompts, or other static data that's known when your program starts.
    Can be any json-serializable data.
    WARNING: The hash is only computed once, and cached. Never mutate this setting after
    class creation.
    """

    model_schema_hash_limit_length: ClassVar[int | None] = 12
    """
    Class config: Number of characters to keep from the start of the hash. If None, the
    full hash is kept. 10-14 characters offers plenty of collision resistance.
    """

    model_schema_hash_tracked_filepath_parts: ClassVar[int] = 2
    """
    Class config: Tracked number of path parts from the end of the filename that the
    model was defined in. For example, if your model is defined in `/a/b/c/d.py`, then
    tracking `2` path parts means the hash will change when `c/` or `d.py` is renamed.
    NOTE: Pydantic might already be including path information in the hash, because, if
    any models in your schema have duplicate names, it will use as many path parts as
    needed to disambiguate them.
    """

    model_schema_hash_function: ClassVar[Callable[[bytes], str]] = hash_md5_hex
    """
    Class config: The hashing function to use for the schema hash. By default, MD5 is
    used. It's plenty fast and collision-resistant for this use case.
    """

    model_schema_hash_track_validation_mode: ClassVar[bool] = True
    """
    Class config: Whether to track the "validation" mode of the JSON schema, in addition
    to the "serialization" mode. The serialization mode is always tracked, because it's
    faster to generate, and we need to track one mode twice to capture both
    'by_alias=True' and 'by_alias=False' field names. So, the serialization schema is
    used for that step.
    Tracking validation mode is optional, only for performance reasons, as disabling it
    will make the hash faster to generate. Unless you are running into performance
    issues, do not disable this.
    """

    # INSTANCE METHODS ==================================================================

    @property
    def model_schema_hash(self) -> str:
        """
        Returns the cached schema hash for the class, creating it if it doesn't exist.
        """
        return self.model_schema_hash_get()

    # CLASS METHODS =====================================================================

    @classmethod
    def model_schema_hash_get(cls) -> str:
        """
        Returns the cached schema hash for the class, creating it if it doesn't exist.
        """
        return cls._schema_hash_registry.get(
            cls
        ) or cls._schema_hash_registry.setdefault(
            cls, cls.model_schema_hash_create_new()
        )

    @classmethod
    def model_schema_hash_create_new(cls) -> str:
        """Creates a new schema hash for the class."""
        hash_input_data = cls.model_schema_hash_get_input_data()
        id_hash = cls.model_schema_hash_function(hash_input_data)
        id_hash = id_hash[: cls.model_schema_hash_limit_length or 1000]
        return id_hash

    @classmethod
    def model_schema_get_fullname(cls) -> str:
        """
        Returns the full name of the model, including the module path, using the number
        of parts specified in the class configuration.
        """
        path_parts = cls.model_schema_hash_tracked_filepath_parts
        name = utils.get_class_fullname(cls, path_parts=path_parts)
        return name

    @classmethod
    def model_schema_hash_get_input_data(cls) -> bytes:
        """
        Returns the exact value that was passed to the hashing function when creating the
        schema hash. Useful for debugging. Returns a new JSON object as bytes. To inspect
        the data, just `data.decode("utf-8")` and pass it to `json.loads()`.
        """
        cls._validate_no_json_schema_mode_override()

        track_validation_mode = cls.model_schema_hash_track_validation_mode
        track_descriptions = cls.model_schema_hash_track_descriptions
        tracked_extra_data = cls.model_schema_hash_tracked_extra_data
        track_field_order = cls.model_schema_hash_track_field_order
        track_type_order = cls.model_schema_hash_track_type_order

        json_schemas = {
            "ser_by_alias": cls.model_json_schema(mode="serialization", by_alias=True),
            "ser_by_name": cls.model_json_schema(mode="serialization", by_alias=False),
        }
        if track_validation_mode:
            json_schemas["val_by_alias"] = cls.model_json_schema(
                mode="validation", by_alias=True
            )

        cls._preprocess_schemas(
            json_schemas,
            sort_required=not track_field_order,
            del_descriptions=not track_descriptions,
            sort_lists=not track_type_order,
        )

        name = cls.model_schema_get_fullname()
        data = {"name": name, "schemas": json_schemas, "extra_data": tracked_extra_data}
        try:
            return utils.json_dumps(data, sort_keys=not track_field_order)
        except Exception as e:
            raise ValueError(
                f"The schema data for `{cls.__name__}` failed JSON serialization, so "
                "the schema hash can't be computed. "
                f"Error: {type(e).__name__}: {e}"
            )

    @classmethod
    def model_schema_hash_rebuild(cls) -> str:
        """
        Deletes and regenerates the schema hash for the class. This is only useful if you
        forcibly mutated the class in some way at runtime, that would change its schema.
        """
        cls._schema_hash_registry.pop(cls, None)
        cls._schema_identity_report_registry.pop(cls, None)
        return cls.model_schema_hash_get()

    @classmethod
    def model_schema_identity_report(cls) -> report.SchemaIdentityInfo:
        """
        Returns identifying information about the model schema, its hash, class settings,
        datetime of the start of this process, etc.
        """
        return cls._schema_identity_report_registry.get(
            cls
        ) or cls._schema_identity_report_registry.setdefault(
            cls,
            report.SchemaIdentityInfo(
                fullname=cls.model_schema_get_fullname(),
                hash=cls.model_schema_hash_get(),
                hash_settings=report.SchemaIdentityInfoHashSettings(
                    track_descriptions=cls.model_schema_hash_track_descriptions,
                    track_field_order=cls.model_schema_hash_track_field_order,
                    track_type_order=cls.model_schema_hash_track_type_order,
                    tracked_filepath_parts=cls.model_schema_hash_tracked_filepath_parts,
                    track_validation_mode=cls.model_schema_hash_track_validation_mode,
                ),
            ),
        )

    # HELPERS ===========================================================================

    @classmethod
    def _validate_no_json_schema_mode_override(cls) -> None:
        """
        Ensures the model's Pydantic json schema mode override setting is compatible with
        the desired tracked modes.
        Since schemas are generated using Pydantic's default json schema generator, it's
        impossible to respect the tracked modes when the override is set and doesn't
        match.
        """
        override_key = "json_schema_mode_override"

        if override_val := cls.model_config.get(override_key):
            raise ValueError(
                f"Model '{cls.__name__}' set {override_key}='{override_val}' in its "
                "config dict, but generating model schema hashes requires all modes to "
                "be available. Either remove the override (recommended), or do not "
                "generate model schema hashes for this model."
            )

    @classmethod
    def _preprocess_schemas(
        cls, data: Any, sort_required: bool, del_descriptions: bool, sort_lists: bool
    ):
        if isinstance(data, dict):
            for k, v in list(data.items()):

                if (
                    del_descriptions is True
                    and k == "description"
                    and isinstance(v, str)
                ):
                    del data[k]
                    continue

                if isinstance(v, list) and len(v) > 0:
                    if (
                        sort_required is True
                        and k == "required"
                        and isinstance(v[0], str)
                    ):
                        data[k] = list(sorted(v))
                    elif sort_lists is True and k != "default":
                        [
                            cls._preprocess_schemas(x, sort_required, False, sort_lists)
                            for x in v
                        ]
                        data[k] = list(sorted([str(x) for x in v]))

                cls._preprocess_schemas(v, sort_required, del_descriptions, sort_lists)

    # CLASS-LEVEL CACHE REGISTRIES ======================================================
    # Always store class-level cached values in mappings keyed by class identity, instead
    # of standalone class variables, to prevent incorrect cache lookups when multiple
    # inheritance is used.

    _schema_hash_registry: ClassVar[dict[type[Self], str]] = {}
    """
    Cached schema hashes for subclasses.
    """

    _schema_identity_report_registry: ClassVar[
        dict[type[Self], report.SchemaIdentityInfo]
    ] = {}
    """
    Cached schema identity reports for subclasses.
    """


# Class for most common usage:


class BaseModelWithSchemaHash(BaseIdentityModel):
    """Just like its parent class, but each instance stores the cached schema hash."""

    schema_hash: str = ""
    """The class's schema hash. Will be set automatically, if left unset."""

    def model_post_init(self, _):
        """Called automatically after an instance is created."""
        if not self.schema_hash:
            self.schema_hash = self.model_schema_hash_get()
