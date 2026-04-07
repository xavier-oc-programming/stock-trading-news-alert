import json
from datetime import date
from pathlib import Path

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


class SmsSender:
    """
    Sends SMS messages via Twilio with a local daily quota guard.

    The quota file persists the count of messages sent today so the
    script never exceeds the Twilio trial account cap across multiple
    invocations on the same day.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str,
        quota_file: Path,
        max_per_day: int,
    ):
        self._from      = from_number
        self._to        = to_number
        self._quota     = quota_file
        self._max       = max_per_day
        self._client    = Client(account_sid, auth_token)

    def verify_auth(self) -> None:
        """Raise TwilioRestException immediately if credentials are wrong."""
        self._client.api.accounts(self._client.username).fetch()
        print(f"[SmsSender] Auth OK — from {self._from} to {self._to}")

    # ------------------------------------------------------------------
    # Quota helpers
    # ------------------------------------------------------------------

    def _load_quota(self) -> dict:
        if self._quota.exists():
            try:
                return json.loads(self._quota.read_text() or "{}")
            except Exception:
                return {}
        return {}

    def _save_quota(self, data: dict) -> None:
        self._quota.parent.mkdir(parents=True, exist_ok=True)
        self._quota.write_text(json.dumps(data))

    def can_send(self) -> bool:
        """Return True if daily quota has not been reached."""
        today = date.today().isoformat()
        data  = self._load_quota()
        if data.get("date") != today:
            data = {"date": today, "count": 0}
            self._save_quota(data)
        return data["count"] < self._max

    def _record_send(self) -> None:
        today = date.today().isoformat()
        data  = self._load_quota()
        if data.get("date") != today:
            data = {"date": today, "count": 0}
        data["count"] = data.get("count", 0) + 1
        data["date"]  = today
        self._save_quota(data)

    # ------------------------------------------------------------------
    # Public send
    # ------------------------------------------------------------------

    def send(self, body: str) -> str | None:
        """
        Send `body` as an SMS.

        Returns the Twilio message SID on success, None if quota is
        exhausted. Raises TwilioRestException on send failure.
        """
        if not self.can_send():
            print("[SmsSender] Daily quota reached — message skipped.")
            return None

        try:
            sms = self._client.messages.create(
                body=body, from_=self._from, to=self._to
            )
            self._record_send()
            print(f"[SmsSender] Sent SID: {sms.sid}")
            return sms.sid
        except TwilioRestException as e:
            print(f"[SmsSender] Twilio error {getattr(e, 'code', '?')}: {e.msg}")
            raise

    # ------------------------------------------------------------------
    # SMS body helpers (static — no I/O)
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize(text: str) -> str:
        return (text or "").replace("\n", " ").strip()

    @staticmethod
    def clamp_ucs2(text: str, limit: int = 65) -> str:
        """Truncate to fit in one UCS-2 SMS segment (~70 chars safe)."""
        t = SmsSender.sanitize(text)
        return (t[: max(0, limit - 1)] + "…") if len(t) > limit else t

    @classmethod
    def build_body(
        cls,
        stock: str,
        emoji: str,
        perc: float,
        title: str,
        brief: str,
        limit: int = 65,
    ) -> str:
        header = f"{stock}: {emoji}{abs(perc)}% | "
        combo  = f"{cls.sanitize(title)} - {cls.sanitize(brief) or '(No description)'}"
        return cls.clamp_ucs2(header + combo, limit=limit)
