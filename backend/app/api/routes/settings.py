"""Settings API — manage app configuration including API keys.

Secrets are encrypted at rest using the encryption service.
On read, secret values are masked (only last 4 chars visible).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.db.postgres import get_db_session
from app.models.app_setting import AppSetting
from app.services.encryption_service import decrypt_tokens, encrypt_tokens

router = APIRouter()

KNOWN_SETTINGS = {
    "openai_api_key": {"label": "OpenAI API Key", "is_secret": True},
    "openai_model": {
        "label": "OpenAI Model",
        "is_secret": False,
        "help_url": "https://developers.openai.com/api/docs/models",
        "placeholder": "e.g. gpt-4o, gpt-5-mini",
    },
    "primary_user_email": {
        "label": "Primary User Email",
        "is_secret": False,
        "readonly": True,
        "placeholder": "Detected automatically from Granola login",
    },
    "primary_user_name": {
        "label": "Primary User Name",
        "is_secret": False,
        "readonly": True,
        "placeholder": "Detected automatically from Granola login",
    },
}


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "••••"
    return "••••••••" + value[-4:]


class SettingUpdate(BaseModel):
    value: str


@router.get("/")
async def list_settings(session: AsyncSession = Depends(get_db_session)):
    """Return all known settings with their current values (secrets masked)."""
    stmt = select(AppSetting)
    result = await session.execute(stmt)
    db_settings = {s.key: s for s in result.scalars().all()}

    items = []
    for key, meta in KNOWN_SETTINGS.items():
        db_row = db_settings.get(key)
        if db_row and db_row.value:
            raw = (
                decrypt_tokens(db_row.value).get("v", "")
                if db_row.is_secret
                else db_row.value
            )
            display = _mask(raw) if meta["is_secret"] else raw
            is_set = True
        else:
            env_val = getattr(app_settings, key, "")
            if env_val and env_val != "sk-your-key-here":
                display = _mask(env_val) if meta["is_secret"] else env_val
                is_set = True
            else:
                display = ""
                is_set = False

        item: dict = {
            "key": key,
            "label": meta["label"],
            "value": display,
            "is_secret": meta["is_secret"],
            "is_set": is_set,
            "source": "database" if (db_row and db_row.value) else ("env" if is_set else "not_set"),
        }
        if meta.get("help_url"):
            item["help_url"] = meta["help_url"]
        if meta.get("placeholder"):
            item["placeholder"] = meta["placeholder"]
        if meta.get("readonly"):
            item["readonly"] = True
        items.append(item)

    return {"items": items}


@router.put("/{key}")
async def update_setting(
    key: str,
    body: SettingUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """Create or update a setting. Secrets are encrypted before storage."""
    meta = KNOWN_SETTINGS.get(key)
    if not meta:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    stmt = select(AppSetting).where(AppSetting.key == key)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    stored_value = (
        encrypt_tokens({"v": body.value}) if meta["is_secret"] else body.value
    )

    if row:
        row.value = stored_value
        row.is_secret = meta["is_secret"]
        row.updated_at = datetime.utcnow()
    else:
        row = AppSetting(
            key=key,
            value=stored_value,
            is_secret=meta["is_secret"],
        )
        session.add(row)

    await session.commit()

    _apply_setting_to_runtime(key, body.value)

    return {
        "key": key,
        "is_set": True,
        "source": "database",
        "message": f"{meta['label']} updated",
    }


@router.delete("/{key}")
async def delete_setting(
    key: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Remove a setting from the database (falls back to .env value)."""
    from sqlalchemy import delete as sql_delete

    meta = KNOWN_SETTINGS.get(key)
    if not meta:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    await session.execute(
        sql_delete(AppSetting).where(AppSetting.key == key)
    )
    await session.commit()

    _apply_setting_to_runtime(key, getattr(app_settings, key, ""))

    return {"key": key, "message": f"{meta['label']} removed from database, using .env fallback"}


def _apply_setting_to_runtime(key: str, value: str) -> None:
    """Hot-apply a setting change to the running app without restart."""
    if key == "openai_api_key":
        app_settings.openai_api_key = value
    elif key == "openai_model":
        app_settings.openai_model = value
    elif key == "primary_user_email":
        app_settings.primary_user_email = value
    elif key == "primary_user_name":
        app_settings.primary_user_name = value


async def load_settings_from_db() -> None:
    """Called on startup to load DB settings into the runtime config.

    DB values take priority over .env values.
    If primary_user_email is still empty, fall back to the self-profile.
    """
    from app.db.postgres import async_session_factory
    from app.models.profile import Profile

    try:
        async with async_session_factory() as session:
            stmt = select(AppSetting).where(AppSetting.value != "")
            result = await session.execute(stmt)
            for row in result.scalars().all():
                if row.is_secret:
                    try:
                        value = decrypt_tokens(row.value).get("v", "")
                    except Exception:
                        continue
                else:
                    value = row.value
                if value:
                    _apply_setting_to_runtime(row.key, value)

            if not app_settings.primary_user_email:
                self_stmt = select(Profile).where(Profile.type == "self")
                self_result = await session.execute(self_stmt)
                self_profile = self_result.scalar_one_or_none()
                if self_profile and self_profile.email:
                    email = self_profile.email.lower()
                    name = self_profile.name if self_profile.name != "Me" else ""

                    for key, value in [("primary_user_email", email), ("primary_user_name", name)]:
                        if not value:
                            continue
                        existing = await session.execute(
                            select(AppSetting).where(AppSetting.key == key)
                        )
                        row = existing.scalar_one_or_none()
                        if row:
                            row.value = value
                        else:
                            session.add(AppSetting(key=key, value=value, is_secret=False))
                        _apply_setting_to_runtime(key, value)

                    await session.commit()
                    import logging
                    logging.getLogger(__name__).info(
                        "Populated primary user from self-profile: %s (%s)", email, name
                    )
    except Exception:
        pass
