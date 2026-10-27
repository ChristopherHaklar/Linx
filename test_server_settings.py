import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from server_settings import ServerSettings, ServerSettingsStore, format_server_settings


class ServerSettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sub" / "linx.db"
        self.store = ServerSettingsStore(self.path, ServerSettings(fix_x_links=False))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_defaults(self):
        self.assertEqual(self.store.get(1), ServerSettings(fix_x_links=False))
        self.assertEqual(self.store.get(None), ServerSettings(fix_x_links=False))

    def test_update_keeps_other_settings_and_servers(self):
        self.store.update(1, auto_clean=False)
        self.store.update(1, delete_reaction=False)
        self.assertEqual(self.store.get(1), ServerSettings(auto_clean=False, fix_x_links=False, delete_reaction=False))
        self.assertEqual(self.store.get(2), ServerSettings(fix_x_links=False))

    def test_unchanged_settings_follow_new_defaults(self):
        self.store.update(1, auto_clean=False)
        self.store.close()
        self.store = ServerSettingsStore(self.path, ServerSettings(fix_x_links=True))
        self.assertEqual(self.store.get(1), ServerSettings(auto_clean=False, fix_x_links=True))

    def test_explicit_setting_beats_default(self):
        self.store.update(1, fix_x_links=True)
        self.assertTrue(self.store.get(1).fix_x_links)

    def test_unknown_setting_rejected(self):
        with self.assertRaises(ValueError):
            self.store.update(1, ignored_channels=True)

    def test_ignored_channels(self):
        self.store.set_ignored(1, 10, True)
        self.store.set_ignored(1, 11, True)
        self.store.set_ignored(1, 10, True)
        self.store.set_ignored(2, 12, True)
        self.assertEqual(self.store.get(1).ignored_channels, {10, 11})
        self.store.set_ignored(1, 10, False)
        self.assertEqual(self.store.get(1).ignored_channels, {11})

    def test_survives_reopen(self):
        self.store.update(1, hide_original_embeds=False)
        self.store.set_ignored(1, 10, True)
        self.store.close()
        self.store = ServerSettingsStore(self.path)
        self.assertEqual(self.store.get(1), ServerSettings(hide_original_embeds=False, ignored_channels=frozenset({10})))

    def test_adds_toggles_missing_from_older_table(self):
        self.store.close()
        db = sqlite3.connect(self.path)
        db.execute("DROP TABLE server_settings")
        db.execute("CREATE TABLE server_settings (guild_id INTEGER PRIMARY KEY, auto_clean INTEGER)")
        db.execute("INSERT INTO server_settings VALUES (1, 0)")
        db.commit()
        db.close()
        self.store = ServerSettingsStore(self.path)
        self.assertEqual(self.store.get(1), ServerSettings(auto_clean=False))
        self.assertEqual(self.store.update(1, fix_instagram_links=False), ServerSettings(auto_clean=False, fix_instagram_links=False))


class IgnoresTests(unittest.TestCase):
    settings = ServerSettings(ignored_channels=frozenset({10, 20}))

    def test_channel(self):
        self.assertTrue(self.settings.ignores(SimpleNamespace(id=10, category_id=None)))
        self.assertFalse(self.settings.ignores(SimpleNamespace(id=11, category_id=None)))

    def test_channel_in_ignored_category(self):
        self.assertTrue(self.settings.ignores(SimpleNamespace(id=11, category_id=20)))

    def test_thread_in_ignored_channel_or_category(self):
        self.assertTrue(self.settings.ignores(SimpleNamespace(id=30, parent=SimpleNamespace(id=10, category_id=None))))
        self.assertTrue(self.settings.ignores(SimpleNamespace(id=30, parent=SimpleNamespace(id=11, category_id=20))))
        self.assertFalse(self.settings.ignores(SimpleNamespace(id=30, parent=SimpleNamespace(id=11, category_id=21))))

    def test_dm_channel(self):
        self.assertFalse(self.settings.ignores(SimpleNamespace(id=5)))


class FormatTests(unittest.TestCase):
    def test_lists_settings_and_channels(self):
        text = format_server_settings(ServerSettings(auto_clean=False, ignored_channels=frozenset({20, 10})))
        self.assertIn("Clean links automatically: off", text)
        self.assertIn("Rewrite X links to fixvx: on", text)
        self.assertIn("Ignored channels: <#10>, <#20>", text)
        self.assertIn("Ignored channels: none", format_server_settings(ServerSettings()))


if __name__ == "__main__":
    unittest.main()
