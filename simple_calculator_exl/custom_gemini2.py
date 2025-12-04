from functools import cached_property
from typing import Optional

import google.auth
from google.auth.credentials import Credentials
from google.genai import types

# Import the original Gemini class from your module
from .gemini import Gemini  # adjust path if needed


class CustomGemini(Gemini):
  # MUST be Pydantic fields because base is a pydantic model.
  vertexai: Optional[bool] = None
  project_id: Optional[str] = None
  location: Optional[str] = None
  credentials: Optional[Credentials] = None

  def __init__(
      self,
      model: Optional[str] = None,
      *,
      vertexai: Optional[bool] = None,
      project_id: Optional[str] = None,
      location: Optional[str] = None,
      credentials: Optional[Credentials] = None,
      **kwargs,
  ):
    # Optional explicit model param (keeps signature explicit)
    if model is not None:
      kwargs["model"] = model

    # Let the base class (Pydantic) initialize its fields.
    super().__init__(**kwargs)

    # Assign our fields (allowed because we declared them above).
    self.vertexai = vertexai
    self.project_id = project_id
    self.location = location
    self.credentials = credentials

  @cached_property
  def api_client(self):
    """Construct google.genai.Client using provided overrides when present."""
    from google.genai import Client

    client_kwargs = {}
    if self.vertexai is not None:
      client_kwargs["vertexai"] = self.vertexai
    # map project_id -> project expected by Client
    if self.project_id is not None:
      client_kwargs["project"] = self.project_id
    if self.location is not None:
      client_kwargs["location"] = self.location
    if self.credentials is not None:
      client_kwargs["credentials"] = self.credentials

    # preserve the http_options behavior from original Gemini.api_client
    return Client(
        **client_kwargs,
        http_options=types.HttpOptions(
            headers=self._tracking_headers(),
            retry_options=self.retry_options,
        ),
    )

  @cached_property
  def _live_api_client(self):
    """Live client that respects provided args and live api version."""
    from google.genai import Client

    client_kwargs = {}
    if self.vertexai is not None:
      client_kwargs["vertexai"] = self.vertexai
    if self.project_id is not None:
      client_kwargs["project"] = self.project_id
    if self.location is not None:
      client_kwargs["location"] = self.location
    if self.credentials is not None:
      client_kwargs["credentials"] = self.credentials

    return Client(
        **client_kwargs,
        http_options=types.HttpOptions(
            headers=self._tracking_headers(), api_version=self._live_api_version
        ),
    )
