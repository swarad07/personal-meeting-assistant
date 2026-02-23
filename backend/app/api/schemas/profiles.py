from pydantic import BaseModel


class ProfileResponse(BaseModel):
    id: str
    type: str
    name: str
    email: str | None = None
    bio: str | None = None
    traits: dict | None = None
    meeting_count: int = 0


class ProfileDetailResponse(ProfileResponse):
    notes: str | None = None
    learning_log: list | None = None
    recent_meetings: list = []
    action_items: list = []
