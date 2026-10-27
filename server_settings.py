"""Per-server settings that people with Manage Server change with /server."""

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path

# Settings a server can switch on or off, with the wording /server shows for each.
TOGGLES = {
    "auto_clean": "Clean links automatically",
    "fix_x_links": "Rewrite X links to fixvx",
    "fix_instagram_links": "Rewrite Instagram links so they embed",
    "expand_short_links": "Expand short links",
    "hide_original_embeds": "Hide the original message's embed",
    "delete_reaction": "❌ reaction to delete Linx's reply",
}


@dataclass(frozen=True)
class ServerSettings:
    auto_clean: bool = True
    fix_x_links: bool = True
    fix_instagram_links: bool = True
    expand_short_links: bool = True
    hide_original_embeds: bool = True
    delete_reaction: bool = True
    # Channels and categories Linx doesn't clean automatically in (/clean still works there).
    ignored_channels: frozenset[int] = frozenset()

    def ignores(self, channel: object) -> bool:
        """Whether automatic cleaning is off in `channel`: it, its parent (for threads)
        or its category is ignored."""
        parent = getattr(channel, "parent", None)
        ids = {getattr(channel, "id", None), getattr(parent, "id", None),
               getattr(parent or channel, "category_id", None)}
        return bool(ids & self.ignored_channels)


class ServerSettingsStore:
    """Per-server settings in the same SQLite file as notification settings.

    Only settings a server changed are stored, so a server that never touched one follows
    `defaults` (which come from the environment).
    """

    def __init__(self, path: Path, defaults: ServerSettings = ServerSettings()) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.defaults = defaults
        self._db = sqlite3.connect(path)
        columns = ", ".join(f"{name} INTEGER" for name in TOGGLES)
        self._db.execute(f"CREATE TABLE IF NOT EXISTS server_settings (guild_id INTEGER PRIMARY KEY, {columns})")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS ignored_channels ("
            " guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, PRIMARY KEY (guild_id, channel_id))"
        )
        self._db.commit()

    def get(self, guild_id: int | None) -> ServerSettings:
        if guild_id is None:
            return self.defaults
        row = self._db.execute(
            f"SELECT {', '.join(TOGGLES)} FROM server_settings WHERE guild_id = ?", (guild_id,)
        ).fetchone()
        changed = {name: bool(value) for name, value in zip(TOGGLES, row or ()) if value is not None}
        ignored = frozenset(channel_id for (channel_id,) in self._db.execute(
            "SELECT channel_id FROM ignored_channels WHERE guild_id = ?", (guild_id,)
        ))
        return replace(self.defaults, **changed, ignored_channels=ignored)

    def update(self, guild_id: int, **changes: bool) -> ServerSettings:
        for name, value in changes.items():
            if name not in TOGGLES:
                raise ValueError(f"Unknown setting: {name}")
            self._db.execute("INSERT OR IGNORE INTO server_settings (guild_id) VALUES (?)", (guild_id,))
            self._db.execute(f"UPDATE server_settings SET {name} = ? WHERE guild_id = ?", (int(value), guild_id))
        self._db.commit()
        return self.get(guild_id)

    def set_ignored(self, guild_id: int, channel_id: int, ignored: bool) -> ServerSettings:
        if ignored:
            self._db.execute("INSERT OR IGNORE INTO ignored_channels VALUES (?, ?)", (guild_id, channel_id))
        else:
            self._db.execute(
                "DELETE FROM ignored_channels WHERE guild_id = ? AND channel_id = ?", (guild_id, channel_id)
            )
        self._db.commit()
        return self.get(guild_id)

    def close(self) -> None:
        self._db.close()


def format_server_settings(s: ServerSettings) -> str:
    on_off = {True: "on", False: "off"}
    lines = [f"{label}: {on_off[getattr(s, name)]}" for name, label in TOGGLES.items()]
    ignored = ", ".join(f"<#{cid}>" for cid in sorted(s.ignored_channels)) or "none"
    return (
        "**Linx settings for this server**\n" + "\n".join(lines) + f"\nIgnored channels: {ignored}\n"
        "Change with `/server settings`, `/server ignore-channel` and `/server watch-channel`"
    )
