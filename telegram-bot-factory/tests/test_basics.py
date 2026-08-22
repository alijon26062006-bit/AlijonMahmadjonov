"""Проверки, которые работают без сети и без токенов."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from botfactory.childbot import ChildBotEngine, _chunks, _menu_keyboard
from botfactory.crypto import TokenCipher, generate_key
from botfactory.spec import BotSpec, lint, normalize, strict_json_schema, summary
from botfactory.storage import STATUS_RUNNING, Storage, token_fingerprint

RAW_SPEC = {
    "name": "Пиццерия",
    "description": "Бот пиццерии: меню, заказы, доставка",
    "welcome_text": "Привет! Это бот пиццерии.",
    "menu_buttons": ["Меню", "Меню", "Доставка", ""],
    "commands": [
        {
            "command": "/Menu ",
            "description": "Меню",
            "reply_text": "Маргарита 45, Пепперони 55",
            "buttons": [
                {"text": "Заказать", "action": "message", "value": "Напишите, что хотите"},
                {"text": "Сайт", "action": "url", "value": "не ссылка"},
                {"text": "", "action": "message", "value": "пусто"},
            ],
        },
        {"command": "start", "description": "старт", "reply_text": "дубль", "buttons": []},
        {"command": "menu", "description": "повтор", "reply_text": "дубль", "buttons": []},
    ],
    "triggers": [
        {"keywords": ["Доставка", "везёте"], "reply_text": "Доставка бесплатно от 100"},
        {"keywords": [], "reply_text": "пустой триггер"},
    ],
    "ai": {"enabled": True, "persona": "дружелюбный", "system_prompt": "Ты бот пиццерии"},
    "fallback_text": "Уточню у владельца",
}


def make_spec() -> BotSpec:
    return normalize(BotSpec.model_validate(RAW_SPEC))


class SpecTests(unittest.TestCase):
    def test_normalize_cleans_input(self) -> None:
        spec = make_spec()
        self.assertEqual([c.command for c in spec.commands], ["menu"])
        self.assertEqual(spec.menu_buttons, ["Меню", "Доставка"])
        self.assertEqual(len(spec.triggers), 1)

    def test_url_button_without_link_becomes_text(self) -> None:
        button = make_spec().commands[0].buttons[1]
        self.assertEqual(button.action, "message")

    def test_empty_button_dropped(self) -> None:
        self.assertEqual(len(make_spec().commands[0].buttons), 2)

    def test_summary_escapes_html(self) -> None:
        raw = dict(RAW_SPEC, name="<script>Пицца</script>")
        spec = normalize(BotSpec.model_validate(raw))
        self.assertIn("&lt;script&gt;", summary(spec))

    def test_lint_finds_orphan_button_when_ai_off(self) -> None:
        raw = dict(
            RAW_SPEC,
            menu_buttons=["Меню", "Доставка", "Акции"],
            ai={"enabled": False, "persona": "деловой", "system_prompt": "x"},
        )
        problems = lint(normalize(BotSpec.model_validate(raw)))
        self.assertTrue(any("Акции" in p for p in problems))
        self.assertFalse(any("Доставка" in p for p in problems))

    def test_lint_silent_when_ai_answers_everything(self) -> None:
        raw = dict(RAW_SPEC, menu_buttons=["Меню", "Акции"])
        self.assertEqual(lint(normalize(BotSpec.model_validate(raw))), [])

    def test_schema_is_strict(self) -> None:
        schema = strict_json_schema()
        self.assertFalse(schema["additionalProperties"])
        for definition in schema.get("$defs", {}).values():
            if definition.get("type") == "object":
                self.assertFalse(definition["additionalProperties"])


class RoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ChildBotEngine(
            bot_id=1,
            spec=make_spec(),
            generator=None,  # type: ignore[arg-type]
            take_quota=lambda: asyncio.sleep(0, result=True),
            history_limit=5,
        )

    def test_command_lookup(self) -> None:
        self.assertIsNotNone(self.engine._find_command("menu"))
        self.assertIsNone(self.engine._find_command("nope"))

    def test_menu_button_opens_command(self) -> None:
        found = self.engine._command_by_label("меню")
        self.assertIsNotNone(found)
        self.assertEqual(found.command, "menu")

    def test_trigger_matches_inside_sentence(self) -> None:
        reply = self.engine._match_trigger("А доставка у вас есть?")
        self.assertEqual(reply, "Доставка бесплатно от 100")

    def test_trigger_misses_unrelated_text(self) -> None:
        self.assertIsNone(self.engine._match_trigger("сколько сейчас времени"))

    def test_long_text_is_split(self) -> None:
        parts = _chunks("а" * 9000)
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(len(p) <= 4096 for p in parts))

    def test_menu_keyboard_two_per_row(self) -> None:
        keyboard = _menu_keyboard(make_spec())
        self.assertEqual(len(keyboard.keyboard), 1)
        self.assertEqual(len(keyboard.keyboard[0]), 2)


class CryptoTests(unittest.TestCase):
    def test_roundtrip(self) -> None:
        cipher = TokenCipher(generate_key())
        token = "123456:AAFakeTokenForTests-0123456789abcdef"
        self.assertEqual(cipher.decrypt(cipher.encrypt(token)), token)

    def test_ciphertext_differs_from_plaintext(self) -> None:
        cipher = TokenCipher(generate_key())
        token = "123456:AAFakeTokenForTests-0123456789abcdef"
        self.assertNotIn(token, cipher.encrypt(token))


class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.storage = Storage(str(Path(self._dir.name) / "test.db"))
        await self.storage.open()
        self.spec = make_spec()
        self.record = await self.storage.create_bot(
            owner_id=42,
            token_enc="enc",
            token_hash=token_fingerprint("123:abc"),
            tg_bot_id=7,
            username="pizza_bot",
            prompt="бот пиццерии",
            spec=self.spec,
        )

    async def asyncTearDown(self) -> None:
        await self.storage.close()
        self._dir.cleanup()

    async def test_created_and_listed(self) -> None:
        bots = await self.storage.list_bots(42)
        self.assertEqual(len(bots), 1)
        self.assertEqual(bots[0].spec.name, "Пиццерия")
        self.assertEqual(bots[0].handle, "@pizza_bot")

    async def test_duplicate_token_detected(self) -> None:
        self.assertTrue(await self.storage.token_taken("123:abc"))
        self.assertFalse(await self.storage.token_taken("999:zzz"))

    async def test_update_and_rollback(self) -> None:
        changed = self.spec.model_copy(update={"name": "Новое имя"})
        await self.storage.update_spec(self.record.id, changed, "переименовал")

        updated = await self.storage.get_bot(self.record.id)
        self.assertEqual(updated.spec.name, "Новое имя")

        previous = await self.storage.previous_version(self.record.id)
        self.assertEqual(previous.name, "Пиццерия")

    async def test_no_rollback_for_fresh_bot(self) -> None:
        self.assertIsNone(await self.storage.previous_version(self.record.id))

    async def test_ai_quota_runs_out(self) -> None:
        self.assertTrue(await self.storage.take_ai_quota(self.record.id, 2))
        self.assertTrue(await self.storage.take_ai_quota(self.record.id, 2))
        self.assertFalse(await self.storage.take_ai_quota(self.record.id, 2))
        self.assertEqual(await self.storage.ai_used(self.record.id), 2)

    async def test_zero_limit_means_unlimited(self) -> None:
        for _ in range(5):
            self.assertTrue(await self.storage.take_ai_quota(self.record.id, 0))

    async def test_status_and_delete(self) -> None:
        await self.storage.set_status(self.record.id, STATUS_RUNNING)
        self.assertEqual(len(await self.storage.list_by_status(STATUS_RUNNING)), 1)
        await self.storage.delete_bot(self.record.id)
        self.assertEqual(await self.storage.count_bots(42), 0)


if __name__ == "__main__":
    unittest.main()
