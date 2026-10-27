import os
import tempfile
import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

_tmp = tempfile.TemporaryDirectory()
os.environ["LINX_DATA_DIR"] = _tmp.name

from bot import LinxBot  # noqa: E402

LINX_ID, POSTER_ID, CLEANER_ID = 1, 2, 3


def fake_message(author_id, *, bot=False, interaction_user=None, reference_to=None, resolved=None, mid=100):
    message = MagicMock(spec=discord.Message)
    message.id = mid
    message.author = SimpleNamespace(id=author_id, bot=bot)
    message.interaction_metadata = SimpleNamespace(user=SimpleNamespace(id=interaction_user)) if interaction_user else None
    message.reference = SimpleNamespace(message_id=reference_to, resolved=resolved) if reference_to else None
    return message


def fake_bot(fetchable=()):
    def fetch(mid):
        found = next((m for m in fetchable if m.id == mid), None)
        if found is None:
            raise discord.NotFound(MagicMock(status=404), "Unknown Message")
        return found

    channel = SimpleNamespace(fetch_message=AsyncMock(side_effect=fetch))
    bot = SimpleNamespace(
        _owners=OrderedDict(), user=SimpleNamespace(id=LINX_ID), cached_messages=[],
        get_channel=lambda cid: channel, fetch_channel=AsyncMock(return_value=channel),
    )
    bot.remember_owner = lambda mid, owner: LinxBot.remember_owner(bot, mid, owner)
    return bot


class OwnerOfTests(unittest.IsolatedAsyncioTestCase):
    async def owner(self, message, fetchable=()):
        return await LinxBot.owner_of(fake_bot(fetchable), 10, message.id, message)

    async def test_clean_command_post(self):
        self.assertEqual(await self.owner(fake_message(LINX_ID, interaction_user=CLEANER_ID)), CLEANER_ID)

    async def test_automatic_reply_with_original_included(self):
        original = fake_message(POSTER_ID, mid=50)
        reply = fake_message(LINX_ID, reference_to=50, resolved=original)
        self.assertEqual(await self.owner(reply), POSTER_ID)

    async def test_automatic_reply_fetches_missing_original(self):
        original = fake_message(POSTER_ID, mid=50)
        reply = fake_message(LINX_ID, reference_to=50, resolved=None)
        self.assertEqual(await self.owner(reply, fetchable=[original]), POSTER_ID)

    async def test_other_peoples_messages_ignored(self):
        self.assertIsNone(await self.owner(fake_message(POSTER_ID)))
        self.assertIsNone(await self.owner(fake_message(POSTER_ID, reference_to=50, resolved=fake_message(4, mid=50))))

    async def test_linx_message_without_reply_or_command_ignored(self):
        self.assertIsNone(await self.owner(fake_message(LINX_ID)))

    async def test_remembered_owner_skips_lookup(self):
        bot = fake_bot()
        LinxBot.remember_owner(bot, 100, POSTER_ID)
        self.assertEqual(await LinxBot.owner_of(bot, 10, 100), POSTER_ID)

    async def test_reply_to_a_bot_ignored(self):
        original = fake_message(9, bot=True, mid=50)
        self.assertIsNone(await self.owner(fake_message(LINX_ID, reference_to=50, resolved=original)))


class DeletePostTests(unittest.IsolatedAsyncioTestCase):
    async def delete(self, post, original=None):
        messages = {m.id: m for m in (post, original) if m is not None}
        bot = fake_bot(fetchable=list(messages.values()))
        bot._owners[post.id] = POSTER_ID
        await LinxBot.delete_post(bot, 10, post.id)
        post.delete.assert_awaited_once()
        self.assertNotIn(post.id, bot._owners)

    def original(self, suppressed):
        original = fake_message(POSTER_ID, mid=50)
        original.flags = SimpleNamespace(suppress_embeds=suppressed)
        original.edit = AsyncMock()
        return original

    async def test_automatic_reply_brings_back_hidden_embed(self):
        original = self.original(suppressed=True)
        await self.delete(fake_message(LINX_ID, reference_to=50), original)
        original.edit.assert_awaited_once_with(suppress=False)

    async def test_embed_left_alone_when_not_hidden(self):
        original = self.original(suppressed=False)
        await self.delete(fake_message(LINX_ID, reference_to=50), original)
        original.edit.assert_not_awaited()

    async def test_clean_command_post_just_deleted(self):
        await self.delete(fake_message(LINX_ID, interaction_user=CLEANER_ID))

    async def test_missing_original_still_deletes(self):
        await self.delete(fake_message(LINX_ID, reference_to=50))
