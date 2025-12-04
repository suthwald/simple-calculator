from functools import cached_property
from typing import Optional

# credentials type
from google.auth.credentials import Credentials  # type: ignore

# reuse the original Gemini class from the module you showed
# assume it's in the same module or imported already:
# from .gemini import Gemini

class CustomGemini(Gemini):
  """Gemini subclass that accepts explicit vertex/vertexai args.

  Args:
    vertexai: if True use Vertex AI backend; otherwise use Gemini API.
    project_id: GCP project id (used when vertexai=True / Vertex client).
    location: GCP location/region (used when vertexai=True / Vertex client).
    credentials: google.auth.credentials.Credentials to pass to the client.
    **kwargs: forwarded to base Gemini constructor.
  """

  def __init__(
      self,
      *,
      vertexai: bool | None = None,
      project_id: Optional[str] = None,
      location: Optional[str] = None,
      credentials: Optional[Credentials] = None,
      **kwargs,
  ):
    # Let base Gemini handle anything else it expects
    super().__init__(**kwargs)

    # Store overrides (None means "use default behaviour from base client")
    self.vertexai: bool | None = vertexai
    self.project_id: Optional[str] = project_id
    self.location: Optional[str] = location
    self.credentials: Optional[Credentials] = credentials

  @cached_property
  def api_client(self):
    """Construct Client using provided args (falls back to base behaviour)."""
    from google.genai import Client

    # If caller didn't explicitly set vertexai on this subclass instance,
    # fall back to the base class's detection (via self.api_client in base).
    # But since we are overriding, prefer explicit flag if provided.
    client_args = {}
    if self.vertexai is not None:
      client_args['vertexai'] = self.vertexai
    if self.project_id is not None:
      client_args['project'] = self.project_id
    if self.location is not None:
      client_args['location'] = self.location
    if self.credentials is not None:
      client_args['credentials'] = self.credentials

    return Client(
        **client_args,
        http_options=types.HttpOptions(
            headers=self._tracking_headers(),
            retry_options=self.retry_options,
        ),
    )

  @cached_property
  def _live_api_client(self):
    """Live client that also respects the provided args and live api version."""
    from google.genai import Client

    client_args = {}
    if self.vertexai is not None:
      client_args['vertexai'] = self.vertexai
    if self.project_id is not None:
      client_args['project'] = self.project_id
    if self.location is not None:
      client_args['location'] = self.location
    if self.credentials is not None:
      client_args['credentials'] = self.credentials

    # include the api_version used by the live client (same as base Gemini logic)
    return Client(
        **client_args,
        http_options=types.HttpOptions(
            headers=self._tracking_headers(), api_version=self._live_api_version
        ),
    )
