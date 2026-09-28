import getpass
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from cleaner import find_cleanable_links

HERE = Path(__file__).parent
ENV_FILE = HERE / ".env"
ENV_EXAMPLE = HERE / ".env.example"
TOKEN_PLACEHOLDER = "your-bot-token-here"

load_dotenv(ENV_FILE)

TOKEN = os.environ.get("DISCORD_TOKEN")
FIX_X = os.environ.get("FIX_X_LINKS", "true").lower() == "true"
SUPPRESS_ORIGINAL_EMBEDS = os.environ.get("SUPPRESS_ORIGINAL_EMBEDS", "true").lower() == "true"

log = logging.getLogger("linx")

intents = discord.Intents.default()
intents.message_content = True


class LinxBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()


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

    links = find_cleanable_links(message.content, fix_x=FIX_X)
    if not links:
        return

    await message.reply("\n".join(links), mention_author=False)

    # Hide the original embeds so the chat isn't doubled up. Needs Manage Messages.
    if SUPPRESS_ORIGINAL_EMBEDS and message.guild is not None:
        try:
            await message.edit(suppress=True)
        except discord.Forbidden:
            pass


@client.tree.command(name="clean", description="Remove tracking from a link (and convert X links to fixvx)")
@app_commands.describe(link="The link or text containing links to clean")
async def clean(interaction: discord.Interaction, link: str) -> None:
    links = find_cleanable_links(link, fix_x=FIX_X)
    if links:
        await interaction.response.send_message("\n".join(links))
    else:
        await interaction.response.send_message("Nothing to clean in that link.", ephemeral=True)


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
