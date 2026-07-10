"""Shared base class for typed configuration contracts."""

from pydantic import BaseModel, ConfigDict


class ConfigModel(BaseModel):
    """Base model for all configuration contracts."""

    model_config = ConfigDict(extra="forbid")
