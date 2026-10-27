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
from server_settings import ServerSettings, ServerSettingsStore, format_server_settings
from shortlinks import ShortLinkExpander, short_link_target

HERE = Path(__file__).parent
ENV_FILE = HERE / ".env"
ENV_EXAMPLE = HERE / ".env.example"
TOKEN_PLACEHOLDER = "your-bot-token-here"

load_dotenv(ENV_FILE)

TOKEN = os.environ.get("DISCORD_TOKEN")
FIX_X = os.environ.get("FIX_X_LINKS", "true").lower() == "true"
FIX_INSTAGRAM = os.environ.get("FIX_INSTAGRAM_LINKS", "true").lower() == "true"
# Instagram embed fixers shut down often. Change this when the current one stops working.
INSTAGRAM_FIX_HOST = os.environ.get("INSTAGRAM_FIX_HOST", "vxinstagram.com").strip() or "vxinstagram.com"
SUPPRESS_ORIGINAL_EMBEDS = os.environ.get("SUPPRESS_ORIGINAL_EMBEDS", "true").lower() == "true"
EXPAND_SHORT_LINKS = os.environ.get("EXPAND_SHORT_LINKS", "true").lower() == "true"
DATA_DIR = Path(os.environ.get("LINX_DATA_DIR", HERE / "data"))
# The environment sets each server's defaults; /server settings overrides them per server.
DEFAULT_SERVER_SETTINGS = ServerSettings(
    fix_x_links=FIX_X, fix_instagram_links=FIX_INSTAGRAM, expand_short_links=EXPAND_SHORT_LINKS, hide_original_embeds=SUPPRESS_ORIGINAL_EMBEDS,
)
DELETE_EMOJI = "❌"

log = logging.getLogger("linx")

intents = discord.Intents.default()
intents.message_content = True


class LinxBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.expander = ShortLinkExpander() if EXPAND_SHORT_LINKS else None
        self.settings = SettingsStore(DATA_DIR / "linx.db")
        self.server_settings = ServerSettingsStore(DATA_DIR / "linx.db", DEFAULT_SERVER_SETTINGS)
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
        self.server_settings.close()
        await super().close()

    async def clean_links(self, text: str, settings: ServerSettings) -> list[str]:
        expand = self.expander if settings.expand_short_links else None
        instagram_host = INSTAGRAM_FIX_HOST if settings.fix_instagram_links else None
        return await find_cleanable_links_async(
            text, fix_x=settings.fix_x_links, expand=expand, instagram_host=instagram_host
        )

    def remember_owner(self, message_id: int, owner_id: int) -> None:
        self._owners[message_id] = owner_id
        if len(self._owners) > 2000:
            self._owners.popitem(last=False)

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

        self.remember_owner(message_id, owner)
        return owner

    async def delete_post(self, channel_id: int, message_id: int) -> None:
        """Delete one of Linx's link posts. For an automatic reply, bring back the original
        message's embed, since Linx hid it."""
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        post = await channel.fetch_message(message_id)
        ref = post.reference
        if post.interaction_metadata is None and ref is not None and ref.message_id is not None:
            try:
                original = await channel.fetch_message(ref.message_id)
                if original.flags.suppress_embeds:
                    await original.edit(suppress=False)
            except discord.HTTPException:
                pass
        await post.delete()
        self._owners.pop(message_id, None)

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
    log.info("Logged in as %s (defaults: %s)", client.user, DEFAULT_SERVER_SETTINGS)
    permissions = discord.Permissions(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        embed_links=True,
        manage_messages=True,
        add_reactions=True,
    )
    invite = discord.utils.oauth_url(
        client.application_id, permissions=permissions, scopes=("bot", "applications.commands")
    )
    user_install = (
        f"https://discord.com/oauth2/authorize?client_id={client.application_id}"
        "&integration_type=1&scope=applications.commands"
    )
    print(
        f"\nLinx is running! To add it to a server, open this link:\n{invite}\n"
        f"To add it to your own account (use /clean anywhere), open this one:\n{user_install}\n",
        flush=True,
    )


async def add_delete_reaction(message: discord.Message) -> None:
    try:
        await message.add_reaction(DELETE_EMOJI)
    except discord.HTTPException:
        pass  # No Add Reactions permission there


@client.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    await relay_reply(message)

    settings = client.server_settings.get(message.guild.id if message.guild else None)
    if not settings.auto_clean or settings.ignores(message.channel):
        return

    links = await client.clean_links(message.content, settings)
    if not links:
        return

    reply = await message.reply("\n".join(links), mention_author=False)
    client.remember_owner(reply.id, message.author.id)
    if settings.delete_reaction and message.guild is not None:
        await add_delete_reaction(reply)

    # Hide the original embeds so the chat isn't doubled up. Needs Manage Messages.
    if settings.hide_original_embeds and message.guild is not None:
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
    """Delete a Linx link post when the person it was made for (or a moderator) reacts ❌.
    Otherwise bundle reactions on it and DM them to that person."""
    if payload.guild_id is None or payload.message_author_id != client.user.id:
        return
    if payload.member is not None and payload.member.bot:
        return
    try:
        owner = await client.owner_of(payload.channel_id, payload.message_id)
    except discord.HTTPException:
        return
    if owner is None:
        return
    if str(payload.emoji) == DELETE_EMOJI and client.server_settings.get(payload.guild_id).delete_reaction:
        if payload.user_id == owner or can_manage_messages(payload):
            try:
                await client.delete_post(payload.channel_id, payload.message_id)
            except discord.HTTPException as exc:
                log.info("Could not delete %s: %s", payload.message_id, exc)
            return
    if owner == payload.user_id:
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


def can_manage_messages(payload: discord.RawReactionActionEvent) -> bool:
    channel = client.get_channel(payload.channel_id)
    if channel is None or payload.member is None:
        return False
    return channel.permissions_for(payload.member).manage_messages


async def post_cleaned(interaction: discord.Interaction, text: str, nothing_to_clean: str) -> None:
    """Answer a /clean or "Clean links" with the cleaned links. Also works where Linx is only
    installed on someone's account, not in the server."""
    settings = client.server_settings.get(interaction.guild_id)
    # Expanding short links can outlast Discord's 3-second reply window, so defer for those.
    if client.expander and settings.expand_short_links and any(short_link_target(url) for url in extract_urls(text)):
        await interaction.response.defer()
        links = await client.clean_links(text, settings)
        if not links:
            await interaction.followup.send("Couldn't expand or clean that link.")
            return
        post = await interaction.followup.send("\n".join(links), wait=True)
    else:
        links = await client.clean_links(text, settings)
        if not links:
            await interaction.response.send_message(nothing_to_clean, ephemeral=True)
            return
        await interaction.response.send_message("\n".join(links))
        post = await interaction.original_response()

    # Reactions only reach Linx in servers it's a member of.
    if settings.delete_reaction and interaction.guild_id and client.get_guild(interaction.guild_id):
        await add_delete_reaction(post)


ANYWHERE = dict(guilds=True, dms=True, private_channels=True)


@client.tree.command(name="clean", description="Remove tracking from a link, and fix X and Instagram links so they embed")
@app_commands.describe(link="The link or text containing links to clean")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(**ANYWHERE)
async def clean(interaction: discord.Interaction, link: str) -> None:
    await post_cleaned(interaction, link, "Nothing to clean in that link.")


@client.tree.context_menu(name="Clean links")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(**ANYWHERE)
async def clean_message(interaction: discord.Interaction, message: discord.Message) -> None:
    await post_cleaned(interaction, message.content, "No links to clean in that message.")


server = app_commands.Group(
    name="server", description="Linx settings for this server",
    allowed_installs=app_commands.AppInstallationType(guild=True, user=False),
    allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False),
    default_permissions=discord.Permissions(manage_guild=True),
)
client.tree.add_command(server)


@server.command(name="settings", description="Show or change how Linx behaves in this server")
@app_commands.describe(
    auto_clean="Reply to links people post with a cleaned version (/clean always works)",
    fix_x_links="Rewrite x.com and twitter.com links to fixvx.com so they embed",
    fix_instagram_links="Rewrite Instagram post and reel links to an embed-fixer site so they embed",
    expand_short_links="Follow short links like bit.ly and amzn.to so the real link can be cleaned",
    hide_original_embeds="Hide the embed on the original message after replying",
    delete_reaction="Add a ❌ the poster (or a moderator) can click to delete Linx's reply",
)
async def server_settings_command(
    interaction: discord.Interaction,
    auto_clean: bool | None = None,
    fix_x_links: bool | None = None,
    fix_instagram_links: bool | None = None,
    expand_short_links: bool | None = None,
    hide_original_embeds: bool | None = None,
    delete_reaction: bool | None = None,
) -> None:
    changes = {k: v for k, v in {
        "auto_clean": auto_clean, "fix_x_links": fix_x_links, "fix_instagram_links": fix_instagram_links,
        "expand_short_links": expand_short_links,
        "hide_original_embeds": hide_original_embeds, "delete_reaction": delete_reaction,
    }.items() if v is not None}
    store = client.server_settings
    settings = store.update(interaction.guild_id, **changes) if changes else store.get(interaction.guild_id)
    await interaction.response.send_message(format_server_settings(settings), ephemeral=True)


@server.command(name="ignore-channel", description="Stop cleaning links automatically in a channel or category")
@app_commands.describe(channel="Channel or category (threads in it are ignored too)")
async def ignore_channel(interaction: discord.Interaction, channel: discord.abc.GuildChannel) -> None:
    settings = client.server_settings.set_ignored(interaction.guild_id, channel.id, True)
    await interaction.response.send_message(format_server_settings(settings), ephemeral=True)


@server.command(name="watch-channel", description="Clean links automatically in an ignored channel again")
@app_commands.describe(channel="Channel or category to stop ignoring")
async def watch_channel(interaction: discord.Interaction, channel: discord.abc.GuildChannel) -> None:
    settings = client.server_settings.set_ignored(interaction.guild_id, channel.id, False)
    await interaction.response.send_message(format_server_settings(settings), ephemeral=True)


@client.tree.command(name="notifications", description="Choose which DMs you get about links Linx posts for you")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(**ANYWHERE)
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
