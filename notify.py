"""DM people about replies and reactions on the links Linx posted for them."""

import asyncio
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BUNDLE_SECONDS = 30
MAX_BUNDLE_SECONDS = 3600


@dataclass(frozen=True)
class NotifySettings:
    replies: bool = True
    reactions: bool = True
    bundle_seconds: int = DEFAULT_BUNDLE_SECONDS


class SettingsStore:
    """Per-user notification settings in a small SQLite file."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS notify_settings ("
            " user_id INTEGER PRIMARY KEY, replies INTEGER NOT NULL,"
            " reactions INTEGER NOT NULL, bundle_seconds INTEGER NOT NULL)"
        )
        self._db.commit()

    def get(self, user_id: int) -> NotifySettings:
        row = self._db.execute(
            "SELECT replies, reactions, bundle_seconds FROM notify_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return NotifySettings()
        return NotifySettings(bool(row[0]), bool(row[1]), row[2])

    def update(self, user_id: int, **changes) -> NotifySettings:
        current = self.get(user_id)
        new = NotifySettings(
            replies=changes.get("replies", current.replies),
            reactions=changes.get("reactions", current.reactions),
            bundle_seconds=changes.get("bundle_seconds", current.bundle_seconds),
        )
        self._db.execute(
            "INSERT OR REPLACE INTO notify_settings VALUES (?, ?, ?, ?)",
            (user_id, int(new.replies), int(new.reactions), new.bundle_seconds),
        )
        self._db.commit()
        return new

    def close(self) -> None:
        self._db.close()


@dataclass(frozen=True)
class Reaction:
    emoji: str
    who: str


@dataclass
class _Bundle:
    recipient_id: int
    context: object
    reactions: list[Reaction] = field(default_factory=list)


Deliver = Callable[[int, object, list[Reaction]], Awaitable[None]]


class ReactionBundler:
    """Collects reactions on a message for a window after the first one, then delivers them together.

    A reaction that arrives after a bundle was delivered starts a new bundle.
    """

    def __init__(self, deliver: Deliver) -> None:
        self._deliver = deliver
        self._pending: dict[int, _Bundle] = {}
        self._tasks: set[asyncio.Task] = set()

    def add(self, message_id: int, recipient_id: int, reaction: Reaction, window: float, context: object) -> None:
        bundle = self._pending.get(message_id)
        if bundle is not None:
            bundle.reactions.append(reaction)
            return
        self._pending[message_id] = _Bundle(recipient_id, context, [reaction])
        task = asyncio.create_task(self._flush_after(message_id, window))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _flush_after(self, message_id: int, window: float) -> None:
        await asyncio.sleep(window)
        bundle = self._pending.pop(message_id)
        await self._deliver(bundle.recipient_id, bundle.context, bundle.reactions)

    def cancel_all(self) -> None:
        for task in self._tasks:
            task.cancel()


def format_reactions(reactions: list[Reaction], where: str, jump_url: str) -> str:
    if len(reactions) == 1:
        r = reactions[0]
        return f"**{r.who}** reacted {r.emoji} to your link in {where}\n{jump_url}"
    by_emoji: dict[str, list[str]] = {}
    for r in reactions:
        by_emoji.setdefault(r.emoji, []).append(r.who)
    lines = [f"{emoji} {', '.join(names)}" for emoji, names in by_emoji.items()]
    return f"**{len(reactions)} reactions** on your link in {where}:\n" + "\n".join(lines) + f"\n{jump_url}"


def format_reply(who: str, content: str, where: str, jump_url: str) -> str:
    snippet = " ".join(content.split())
    if len(snippet) > 300:
        snippet = snippet[:297] + "..."
    quoted = f"\n> {snippet}" if snippet else ""
    return f"**{who}** replied to your link in {where}:{quoted}\n{jump_url}"


def format_settings(s: NotifySettings) -> str:
    on_off = {True: "on", False: "off"}
    window = "sent right away" if s.bundle_seconds == 0 else f"bundled for {s.bundle_seconds}s after the first one"
    return (
        "**Notifications for links Linx posts for you**\n"
        f"Replies: {on_off[s.replies]}\n"
        f"Reactions: {on_off[s.reactions]}" + (f" ({window})" if s.reactions else "") + "\n"
        "Change with `/notifications replies:` `reactions:` `bundle_seconds:`"
    )
