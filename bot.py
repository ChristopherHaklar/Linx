import getpass
import logging
import os
from collections import OrderedDict
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from cleaner import extract_urls, find_cleanable_links_async
from notify import (
    MAX_BUNDLE_SECONDS, Reaction, ReactionBundler, SettingsStore,
    format_reactions, format_reply, format_settings,
)
from shortlinks import ShortLinkExpander, short_link_target

HERE = Path(__file__).parent
ENV_FILE = HERE / ".env"
ENV_EXAMPLE = HERE / ".env.example"
TOKEN_PLACEHOLDER = "your-bot-token-here"

load_dotenv(ENV_FILE)

TOKEN = os.environ.get("DISCORD_TOKEN")
FIX_X = os.environ.get("FIX_X_LINKS", "true").lower() == "true"
SUPPRESS_ORIGINAL_EMBEDS = os.environ.get("SUPPRESS_ORIGINAL_EMBEDS", "true").lower() == "true"
EXPAND_SHORT_LINKS = os.environ.get("EXPAND_SHORT_LINKS", "true").lower() == "true"
DATA_DIR = Path(os.environ.get("LINX_DATA_DIR", HERE / "data"))

log = logging.getLogger("linx")

intents = discord.Intents.default()
intents.message_content = True


class LinxBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.expander = ShortLinkExpander() if EXPAND_SHORT_LINKS else None
        self.settings = SettingsStore(DATA_DIR / "linx.db")
        self.bundler = ReactionBundler(self.send_reaction_bundle)
        # message id -> id of the person a Linx post was made for (None: not one of Linx's link posts)
        self._owners: OrderedDict[int, int | None] = OrderedDict()

    async def setup_hook(self) -> None:
        await self.tree.sync()

    async def close(self) -> None:
        if self.expander:
            await self.expander.close()
        self.bundler.cancel_all()
        self.settings.close()
        await super().close()

    async def clean_links(self, text: str) -> list[str]:
        return await find_cleanable_links_async(text, fix_x=FIX_X, expand=self.expander)

    async def owner_of(self, channel_id: int, message_id: int, message: discord.Message | None = None) -> int | None:
        """The person a Linx link post was made for: whoever ran /clean, or whoever posted the link
        Linx replied to. None if the message isn't one of Linx's link posts."""
        if message_id in self._owners:
            return self._owners[message_id]
        channel = None
        if message is None:
            message = discord.utils.get(self.cached_messages, id=message_id)
        if message is None:
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)

        owner = None
        if message.author.id == self.user.id:
            if message.interaction_metadata is not None:
                owner = message.interaction_metadata.user.id
            elif message.reference is not None and message.reference.message_id is not None:
                original = message.reference.resolved
                if not isinstance(original, discord.Message):
                    # Not included (e.g. we were given a reply-to-a-reply); look it up.
                    try:
                        channel = channel or self.get_channel(channel_id) or await self.fetch_channel(channel_id)
                        original = await channel.fetch_message(message.reference.message_id)
                    except discord.NotFound:
                        original = None
                if isinstance(original, discord.Message) and not original.author.bot:
                    owner = original.author.id

        self._owners[message_id] = owner
        if len(self._owners) > 2000:
            self._owners.popitem(last=False)
        return owner

    async def dm(self, user_id: int, text: str) -> None:
        try:
            user = self.get_user(user_id) or await self.fetch_user(user_id)
            await user.send(text, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.info("Could not DM %s: %s", user_id, exc)

    async def send_reaction_bundle(self, user_id: int, context: tuple[str, str], reactions: list[Reaction]) -> None:
        where, jump_url = context
        await self.dm(user_id, format_reactions(reactions, where, jump_url))


client = LinxBot()


@client.event
async def on_ready() -> None:
    log.info("Logged in as %s (fix_x=%s)", client.user, FIX_X)
    permissions = discord.Permissions(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        embed_links=True,
        manage_messages=True,
    )
    invite = discord.utils.oauth_url(
        client.application_id, permissions=permissions, scopes=("bot", "applications.commands")
    )
    print(f"\nLinx is running! To add it to a server, open this link:\n{invite}\n", flush=True)


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    await relay_reply(message)

    links = await client.clean_links(message.content)
    if not links:
        return

    await message.reply("\n".join(links), mention_author=False)

    # Hide the original embeds so the chat isn't doubled up. Needs Manage Messages.
    if SUPPRESS_ORIGINAL_EMBEDS and message.guild is not None:
        try:
            await message.edit(suppress=True)
        except discord.Forbidden:
            pass


async def relay_reply(message: discord.Message) -> None:
    """DM the person a Linx link post was made for when someone replies to it."""
    ref = message.reference
    if ref is None or ref.message_id is None or message.guild is None:
        return
    try:
        resolved = ref.resolved if isinstance(ref.resolved, discord.Message) else None
        if resolved is not None and resolved.author.id != client.user.id:
            return
        owner = await client.owner_of(ref.channel_id, ref.message_id, resolved)
    except discord.HTTPException:
        return
    if owner is None or owner == message.author.id or not client.settings.get(owner).replies:
        return
    await client.dm(owner, format_reply(message.author.display_name, message.content, message.channel.mention, message.jump_url))


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    """Bundle reactions on Linx's link posts and DM them to the person the post was made for."""
    if payload.guild_id is None or payload.message_author_id != client.user.id:
        return
    if payload.member is not None and payload.member.bot:
        return
    try:
        owner = await client.owner_of(payload.channel_id, payload.message_id)
    except discord.HTTPException:
        return
    if owner is None or owner == payload.user_id:
        return
    settings = client.settings.get(owner)
    if not settings.reactions:
        return
    who = payload.member.display_name if payload.member else f"<@{payload.user_id}>"
    jump_url = f"https://discord.com/channels/{payload.guild_id}/{payload.channel_id}/{payload.message_id}"
    client.bundler.add(
        payload.message_id, owner, Reaction(str(payload.emoji), who), settings.bundle_seconds,
        context=(f"<#{payload.channel_id}>", jump_url),
    )


@client.tree.command(name="clean", description="Remove tracking from a link (and convert X links to fixvx)")
@app_commands.describe(link="The link or text containing links to clean")
async def clean(interaction: discord.Interaction, link: str) -> None:
    # Expanding short links can outlast Discord's 3-second reply window, so defer for those.
    if client.expander and any(short_link_target(url) for url in extract_urls(link)):
        await interaction.response.defer()
        links = await client.clean_links(link)
        await interaction.followup.send("\n".join(links) if links else "Couldn't expand or clean that link.")
        return

    links = await client.clean_links(link)
    if links:
        await interaction.response.send_message("\n".join(links))
    else:
        await interaction.response.send_message("Nothing to clean in that link.", ephemeral=True)


@client.tree.command(name="notifications", description="Choose which DMs you get about links Linx posts for you")
@app_commands.describe(
    replies="DM me when someone replies to a link Linx posted for me",
    reactions="DM me when someone reacts to a link Linx posted for me",
    bundle_seconds="After the first reaction, wait this long and send all reactions in one DM (0 = send each right away)",
)
async def notifications(
    interaction: discord.Interaction,
    replies: bool | None = None,
    reactions: bool | None = None,
    bundle_seconds: app_commands.Range[int, 0, MAX_BUNDLE_SECONDS] | None = None,
) -> None:
    changes = {k: v for k, v in
               {"replies": replies, "reactions": reactions, "bundle_seconds": bundle_seconds}.items() if v is not None}
    user_id = interaction.user.id
    settings = client.settings.update(user_id, **changes) if changes else client.settings.get(user_id)
    await interaction.response.send_message(format_settings(settings), ephemeral=True)


def save_token(token: str) -> None:
    """Write DISCORD_TOKEN into .env, creating it from .env.example if needed."""
    source = ENV_FILE if ENV_FILE.exists() else ENV_EXAMPLE
    lines = source.read_text().splitlines() if source.exists() else []
    lines = [line for line in lines if not line.startswith("DISCORD_TOKEN=")]
    lines.insert(0, f"DISCORD_TOKEN={token}")
    ENV_FILE.write_text("\n".join(lines) + "\n")


def ask_for_token() -> str:
    print(
        "Linx needs a bot token (first-time setup).\n"
        "Get one at https://discord.com/developers/applications -> your app -> Bot -> Reset Token.\n"
        "Paste it below (it won't be shown as you type) and press Enter."
    )
    token = getpass.getpass("Bot token: ").strip()
    if not token:
        raise SystemExit("No token entered.")
    save_token(token)
    print("Saved to .env.\n")
    return token


def main() -> None:
    token = TOKEN if TOKEN and TOKEN != TOKEN_PLACEHOLDER else ask_for_token()
    try:
        client.run(token, root_logger=True)
    except discord.LoginFailure:
        save_token(TOKEN_PLACEHOLDER)
        raise SystemExit("\nThat token was rejected by Discord. Run Linx again to enter a new one.")
    except discord.PrivilegedIntentsRequired:
        raise SystemExit(
            "\nLinx needs the Message Content Intent to read links.\n"
            f"Turn it on here: https://discord.com/developers/applications/{client.application_id}/bot\n"
            "(scroll to 'Privileged Gateway Intents', enable 'Message Content Intent', save), "
            "then run Linx again."
        )


if __name__ == "__main__":
    main()
