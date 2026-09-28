import asyncio
import tempfile
import unittest
from pathlib import Path

from notify import (
    NotifySettings, Reaction, ReactionBundler, SettingsStore,
    format_reactions, format_reply, format_settings,
)


class SettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "linx.db"
        self.store = SettingsStore(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_defaults(self):
        self.assertEqual(self.store.get(1), NotifySettings(replies=True, reactions=True, bundle_seconds=30))

    def test_partial_update_keeps_other_fields(self):
        self.store.update(1, reactions=False)
        self.store.update(1, bundle_seconds=90)
        self.assertEqual(self.store.get(1), NotifySettings(replies=True, reactions=False, bundle_seconds=90))
        self.assertEqual(self.store.get(2), NotifySettings())

    def test_persists_across_reopen(self):
        self.store.update(1, replies=False, bundle_seconds=0)
        self.store.close()
        self.store = SettingsStore(self.path)
        self.assertEqual(self.store.get(1), NotifySettings(replies=False, reactions=True, bundle_seconds=0))


class ReactionBundlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.delivered = []

        async def deliver(user_id, context, reactions):
            self.delivered.append((user_id, context, [r.emoji for r in reactions]))

        self.bundler = ReactionBundler(deliver)

    async def test_reactions_in_window_are_bundled(self):
        self.bundler.add(10, 1, Reaction("👍", "a"), window=0.1, context="ctx")
        self.bundler.add(10, 1, Reaction("😂", "b"), window=0.1, context="ctx")
        await asyncio.sleep(0.02)
        self.bundler.add(10, 1, Reaction("🔥", "c"), window=0.1, context="ctx")
        self.assertEqual(self.delivered, [])
        await asyncio.sleep(0.15)
        self.assertEqual(self.delivered, [(1, "ctx", ["👍", "😂", "🔥"])])

    async def test_reaction_after_window_starts_new_bundle(self):
        self.bundler.add(10, 1, Reaction("👍", "a"), window=0.05, context="ctx")
        await asyncio.sleep(0.1)
        self.bundler.add(10, 1, Reaction("😂", "b"), window=0.05, context="ctx")
        await asyncio.sleep(0.1)
        self.assertEqual(self.delivered, [(1, "ctx", ["👍"]), (1, "ctx", ["😂"])])

    async def test_messages_bundle_separately(self):
        self.bundler.add(10, 1, Reaction("👍", "a"), window=0.05, context="m10")
        self.bundler.add(11, 2, Reaction("😂", "b"), window=0.05, context="m11")
        await asyncio.sleep(0.1)
        self.assertCountEqual(self.delivered, [(1, "m10", ["👍"]), (2, "m11", ["😂"])])

    async def test_zero_window_sends_right_away(self):
        self.bundler.add(10, 1, Reaction("👍", "a"), window=0, context="ctx")
        await asyncio.sleep(0.01)
        self.assertEqual(self.delivered, [(1, "ctx", ["👍"])])


class FormatTests(unittest.TestCase):
    def test_single_reaction(self):
        text = format_reactions([Reaction("👍", "alice")], "<#5>", "https://discord.com/channels/1/5/9")
        self.assertEqual(text, "**alice** reacted 👍 to your link in <#5>\nhttps://discord.com/channels/1/5/9")

    def test_bundled_reactions_grouped_by_emoji(self):
        text = format_reactions(
            [Reaction("😂", "alice"), Reaction("👍", "bob"), Reaction("😂", "carol")], "<#5>", "URL"
        )
        self.assertEqual(text, "**3 reactions** on your link in <#5>:\n😂 alice, carol\n👍 bob\nURL")

    def test_reply_snippet_collapsed_and_truncated(self):
        text = format_reply("bob", "nice\n\nfind   " + "x" * 400, "<#5>", "URL")
        quote = text.split("\n")[1]
        self.assertTrue(quote.startswith("> nice find xxx"))
        self.assertTrue(quote.endswith("..."))
        self.assertEqual(len(quote), 2 + 300)

    def test_reply_without_text(self):
        self.assertEqual(format_reply("bob", "", "<#5>", "URL"), "**bob** replied to your link in <#5>:\nURL")

    def test_settings_text(self):
        self.assertIn("Reactions: off", format_settings(NotifySettings(reactions=False)))
        self.assertIn("sent right away", format_settings(NotifySettings(bundle_seconds=0)))
        self.assertIn("bundled for 30s", format_settings(NotifySettings()))
