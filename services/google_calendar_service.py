"""Google Calendar integration service."""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config import Config
from database.models import Task

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_DIR = Config.BASE_DIR / "credentials"
CLIENT_SECRETS_FILE = CREDENTIALS_DIR / "client_secret.json"


def _get_user_token_path(user_id: int) -> Path:
    """Path to store user's OAuth token."""
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    return CREDENTIALS_DIR / f"token_{user_id}.json"


def is_configured() -> bool:
    """Check if Google Calendar client secrets are configured."""
    return CLIENT_SECRETS_FILE.exists()


def get_auth_url(user_id: int) -> str | None:
    """Generate OAuth2 authorization URL for the user."""
    if not is_configured():
        return None

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=str(user_id),
    )
    return auth_url


def complete_auth(user_id: int, auth_code: str) -> bool:
    """Complete OAuth2 flow with the authorization code."""
    if not is_configured():
        return False

    try:
        flow = Flow.from_client_secrets_file(
            str(CLIENT_SECRETS_FILE),
            scopes=SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        flow.fetch_token(code=auth_code)
        creds = flow.credentials

        token_path = _get_user_token_path(user_id)
        token_path.write_text(creds.to_json())
        logger.info("Google Calendar authorized for user %d", user_id)
        return True
    except Exception as e:
        logger.error("Google Calendar auth failed for user %d: %s", user_id, e)
        return False


def _get_credentials(user_id: int) -> Credentials | None:
    """Load user credentials from file."""
    token_path = _get_user_token_path(user_id)
    if not token_path.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        return creds
    except Exception as e:
        logger.error("Failed to load Google credentials for user %d: %s", user_id, e)
        return None


def is_user_connected(user_id: int) -> bool:
    """Check if user has valid Google Calendar credentials."""
    return _get_credentials(user_id) is not None


def sync_task_to_calendar(user_id: int, task: Task) -> str | None:
    """Create or update a Google Calendar event from a task. Returns event ID."""
    creds = _get_credentials(user_id)
    if creds is None:
        return None

    try:
        service = build("calendar", "v3", credentials=creds)

        start_time = task.due_date if task.due_date else datetime.utcnow() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)

        event = {
            "summary": task.title,
            "description": task.description or "",
            "start": {
                "dateTime": start_time.isoformat() + "Z",
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat() + "Z",
                "timeZone": "UTC",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                ],
            },
        }

        result = service.events().insert(calendarId="primary", body=event).execute()
        logger.info("Event created in Google Calendar: %s", result.get("id"))
        return result.get("id")

    except Exception as e:
        logger.error("Failed to sync task to Google Calendar: %s", e)
        return None


def delete_calendar_event(user_id: int, event_id: str) -> bool:
    """Delete a Google Calendar event."""
    creds = _get_credentials(user_id)
    if creds is None:
        return False

    try:
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return True
    except Exception as e:
        logger.error("Failed to delete calendar event: %s", e)
        return False


def get_upcoming_events(user_id: int, max_results: int = 10) -> list[dict] | None:
    """Get upcoming events from Google Calendar."""
    creds = _get_credentials(user_id)
    if creds is None:
        return None

    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.utcnow().isoformat() + "Z"

        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = result.get("items", [])
        return [
            {
                "summary": e.get("summary", "Без названия"),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date", "")),
                "id": e.get("id"),
            }
            for e in events
        ]

    except Exception as e:
        logger.error("Failed to get calendar events: %s", e)
        return None
