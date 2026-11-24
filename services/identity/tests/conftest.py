"""Identity service tests never touch the legacy backend database."""
import os

os.environ.setdefault("IDENTITY_INTERNAL_TOKEN", "test-only-internal-service-token-0123456789")
