from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field


class SiigoTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    issued: datetime = Field(default_factory=datetime.now)

    @property
    def expires_at(self) -> datetime:
        return self.issued + timedelta(seconds=self.expires_in)

    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at - timedelta(minutes=5) # Refresh 5 minutes before actual expiration
