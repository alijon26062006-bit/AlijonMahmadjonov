"""Запросы к базе. Единственное место, где живёт SQL."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from config import MSK
from core.models import (
    BattleStatus,
    MatchStatus,
    ParticipantStatus,
    Player,
    Slot,
    VoteResult,
    VoteSource,
)

log = logging.getLogger(__name__)


class Repo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ------------------------------------------------------------------ users

    def upsert_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        self.conn.execute(
            """INSERT INTO users(user_id, username, first_name) VALUES(?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET username = excluded.username,
                                                  first_name = excluded.first_name""",
            (user_id, username, first_name),
        )
        # человек написал — значит бот не заблокирован
        self.conn.execute(
            "UPDATE users SET is_blocked = 0 WHERE user_id = ? AND is_blocked = 1", (user_id,)
        )
        self.conn.execute("INSERT OR IGNORE INTO stats(user_id) VALUES(?)", (user_id,))
        self.conn.commit()

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def is_banned(self, user_id: int) -> bool:
        row = self.get_user(user_id)
        return bool(row and row["is_banned"])

    def mark_blocked(self, user_id: int, blocked: bool = True) -> None:
        """Отметить, что человек заблокировал бота.

        Без этого на тысячах пользователей рассылка каждый раз ломилась бы
        в тех, кто давно ушёл, — впустую тратя лимиты Telegram.
        """
        self.conn.execute(
            "UPDATE users SET is_blocked = ? WHERE user_id = ?", (int(blocked), user_id)
        )
        self.conn.commit()

    def blocked_count(self) -> int:
        return int(
            self.conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1").fetchone()[0]
        )

    def set_banned(self, user_id: int, banned: bool) -> None:
        self.conn.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(banned), user_id))
        self.conn.commit()

    # ----------------------------------------------------------- очередь

    def enqueue(self, user_id: int, nickname: str) -> bool:
        """Записать в очередь на следующий батл. False — если уже записан."""
        try:
            self.conn.execute(
                "INSERT INTO queue(user_id, nickname) VALUES(?, ?)", (user_id, nickname)
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()  # иначе неудачная запись держит транзакцию открытой
            return False
        self.conn.commit()
        return True

    def in_queue(self, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM queue WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row is not None

    def queue_size(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0])

    def queue_players(self, limit: int | None = None) -> list[Player]:
        query = "SELECT user_id, nickname FROM queue ORDER BY joined_at, user_id"
        if limit:
            query += f" LIMIT {int(limit)}"
        return [Player(row["user_id"], row["nickname"]) for row in self.conn.execute(query)]

    def leave_queue(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM queue WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def take_from_queue(self, user_ids: list[int]) -> None:
        """Убрать из очереди тех, кто попал в созданный батл."""
        if not user_ids:
            return
        placeholders = ",".join("?" * len(user_ids))
        self.conn.execute(f"DELETE FROM queue WHERE user_id IN ({placeholders})", user_ids)
        self.conn.commit()

    def clear_queue(self) -> int:
        cursor = self.conn.execute("DELETE FROM queue")
        self.conn.commit()
        return cursor.rowcount

    # ---------------------------------------------------------------- battles

    def current_battle(self) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT * FROM battles WHERE status IN (?, ?) ORDER BY id DESC LIMIT 1""",
            (BattleStatus.REGISTRATION.value, BattleStatus.RUNNING.value),
        ).fetchone()

    def create_battle(self, deadline: datetime) -> int:
        cur = self.conn.execute(
            "INSERT INTO battles(status, round_no, deadline) VALUES(?, 1, ?)",
            (BattleStatus.REGISTRATION.value, deadline.isoformat()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def close_battle(self, battle_id: int, status: BattleStatus) -> int:
        """Завершить или отменить батл, закрыв все его открытые матчи.

        Без закрытия матчей голосование по ним продолжалось бы: у голоса своя
        проверка, и она смотрит в том числе на статус матча.
        """
        cursor = self.conn.execute(
            """UPDATE matches SET status = ?, closed_at = datetime('now')
               WHERE battle_id = ? AND status = ?""",
            (MatchStatus.CLOSED.value, battle_id, MatchStatus.VOTING.value),
        )
        closed = cursor.rowcount
        self.set_battle_status(battle_id, status)
        return closed

    def set_battle_status(self, battle_id: int, status: BattleStatus) -> None:
        finished = status in (BattleStatus.FINISHED, BattleStatus.CANCELLED)
        self.conn.execute(
            """UPDATE battles SET status = ?,
                   finished_at = CASE WHEN ? THEN datetime('now') ELSE finished_at END
               WHERE id = ?""",
            (status.value, int(finished), battle_id),
        )
        self.conn.commit()

    def extend_deadlines(self, battle_id: int, deadline: datetime) -> None:
        """Сдвинуть дедлайн батла и всех ещё открытых матчей."""
        self.conn.execute(
            "UPDATE battles SET deadline = ? WHERE id = ?", (deadline.isoformat(), battle_id)
        )
        self.conn.execute(
            "UPDATE matches SET deadline = ? WHERE battle_id = ? AND status = ?",
            (deadline.isoformat(), battle_id, MatchStatus.VOTING.value),
        )
        self.conn.commit()

    def set_round(self, battle_id: int, round_no: int, deadline: datetime) -> None:
        self.conn.execute(
            "UPDATE battles SET round_no = ?, deadline = ? WHERE id = ?",
            (round_no, deadline.isoformat(), battle_id),
        )
        self.conn.commit()

    # ----------------------------------------------------------- participants

    def add_participant(self, battle_id: int, user_id: int, nickname: str) -> bool:
        """Записать заявку. False — если участник уже в этом батле."""
        try:
            self.conn.execute(
                "INSERT INTO participants(battle_id, user_id, nickname) VALUES(?, ?, ?)",
                (battle_id, user_id, nickname),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()  # иначе неудачная запись держит транзакцию открытой
            return False
        self.conn.execute("UPDATE stats SET battles = battles + 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return True

    def is_participant(self, battle_id: int, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM participants WHERE battle_id = ? AND user_id = ?",
            (battle_id, user_id),
        ).fetchone()
        return row is not None

    def alive_players(self, battle_id: int) -> list[Player]:
        rows = self.conn.execute(
            """SELECT user_id, nickname FROM participants
               WHERE battle_id = ? AND status = ? ORDER BY joined_at, user_id""",
            (battle_id, ParticipantStatus.ALIVE.value),
        ).fetchall()
        return [Player(row["user_id"], row["nickname"]) for row in rows]

    def participant_count(self, battle_id: int) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM participants WHERE battle_id = ?", (battle_id,)
            ).fetchone()[0]
        )

    def match_count(self, battle_id: int, round_no: int) -> int:
        """Сколько матчей уже заведено в этом раунде — для нумерации пар."""
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM matches WHERE battle_id = ? AND round_no = ?",
                (battle_id, round_no),
            ).fetchone()[0]
        )

    def unassigned_players(self, battle_id: int) -> list[Player]:
        """Заявки, которым ещё не досталась пара.

        Это либо новички, подсевшие в идущий батл и ждущие соперника, либо
        нечётный участник первого раунда. Порядок — по времени заявки: кто
        ждёт дольше, тот и получает соперника первым.
        """
        rows = self.conn.execute(
            """SELECT p.user_id, p.nickname FROM participants p
               WHERE p.battle_id = ? AND p.status = ?
                 AND p.user_id NOT IN (
                     SELECT s.user_id FROM match_slots s
                     JOIN matches m ON m.id = s.match_id
                     WHERE m.battle_id = ?
                 )
               ORDER BY p.joined_at, p.user_id""",
            (battle_id, ParticipantStatus.ALIVE.value, battle_id),
        ).fetchall()
        return [Player(row["user_id"], row["nickname"]) for row in rows]

    def eliminate(self, battle_id: int, user_ids: list[int]) -> None:
        if not user_ids:
            return
        placeholders = ",".join("?" * len(user_ids))
        self.conn.execute(
            f"""UPDATE participants SET status = ?
                WHERE battle_id = ? AND user_id IN ({placeholders})""",
            (ParticipantStatus.OUT.value, battle_id, *user_ids),
        )
        self.conn.commit()

    def set_place(self, battle_id: int, user_id: int, place: int) -> None:
        self.conn.execute(
            "UPDATE participants SET place = ? WHERE battle_id = ? AND user_id = ?",
            (place, battle_id, user_id),
        )
        self.conn.commit()

    # ---------------------------------------------------------------- matches

    def create_match(
        self,
        battle_id: int,
        round_no: int,
        number: int,
        players: list[Player],
        advance: int,
        is_final: bool,
        deadline: datetime,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO matches(battle_id, round_no, number, advance, is_final, deadline)
               VALUES(?, ?, ?, ?, ?, ?)""",
            (battle_id, round_no, number, advance, int(is_final), deadline.isoformat()),
        )
        match_id = int(cur.lastrowid)
        self.conn.executemany(
            "INSERT INTO match_slots(match_id, user_id, nickname, slot_no) VALUES(?, ?, ?, ?)",
            [(match_id, p.user_id, p.nickname, i) for i, p in enumerate(players, start=1)],
        )
        self.conn.commit()
        return match_id

    def set_match_message(self, match_id: int, message_id: int) -> None:
        self.conn.execute("UPDATE matches SET message_id = ? WHERE id = ?", (message_id, match_id))
        self.conn.commit()

    def get_match(self, match_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()

    def match_slots(self, match_id: int) -> list[Slot]:
        rows = self.conn.execute(
            """SELECT user_id, nickname, votes, position, slot_no FROM match_slots
               WHERE match_id = ? ORDER BY slot_no""",
            (match_id,),
        ).fetchall()
        return [
            Slot(row["user_id"], row["nickname"], row["votes"], row["position"] or 0)
            for row in rows
        ]

    def open_matches(self, battle_id: int, round_no: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT * FROM matches
               WHERE battle_id = ? AND round_no = ? AND status = ?
               ORDER BY number""",
            (battle_id, round_no, MatchStatus.VOTING.value),
        ).fetchall()

    def active_match_for(self, user_id: int) -> sqlite3.Row | None:
        """Матч, в котором участник голосуется прямо сейчас."""
        return self.conn.execute(
            """SELECT m.* FROM matches m
               JOIN match_slots s ON s.match_id = m.id
               WHERE s.user_id = ? AND m.status = ?
               ORDER BY m.id DESC LIMIT 1""",
            (user_id, MatchStatus.VOTING.value),
        ).fetchone()

    def latest_open_match(self, battle_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """SELECT * FROM matches WHERE battle_id = ? AND status = ?
               ORDER BY id DESC LIMIT 1""",
            (battle_id, MatchStatus.VOTING.value),
        ).fetchone()

    def close_match(self, match_id: int, ranking: list[Slot]) -> None:
        self.conn.executemany(
            "UPDATE match_slots SET position = ? WHERE match_id = ? AND user_id = ?",
            [(slot.position, match_id, slot.user_id) for slot in ranking],
        )
        self.conn.execute(
            "UPDATE matches SET status = ?, closed_at = datetime('now') WHERE id = ?",
            (MatchStatus.CLOSED.value, match_id),
        )
        self.conn.commit()

    # ------------------------------------------------------------------ votes

    # насколько широко действует бесплатный голос
    FREE_SCOPES = ("battle", "round", "match")

    def free_vote_used(self, match_id: int, voter_id: int, scope: str = "battle") -> bool:
        """Потрачен ли уже бесплатный голос.

        ``battle`` — один бесплатный голос на весь батл: поддержал одну пару,
        за остальные голосуй купленными. ``round`` — один на раунд,
        ``match`` — один на каждую пару (как было раньше).
        """
        if scope == "match":
            row = self.conn.execute(
                """SELECT 1 FROM votes
                   WHERE match_id = ? AND voter_id = ? AND source = ?""",
                (match_id, voter_id, VoteSource.FREE.value),
            ).fetchone()
            return row is not None

        same_round = " AND m.round_no = here.round_no" if scope == "round" else ""
        row = self.conn.execute(
            f"""SELECT 1 FROM votes v
                JOIN matches m ON m.id = v.match_id
                JOIN matches here ON here.id = ?
                WHERE v.voter_id = ? AND v.source = ?
                  AND m.battle_id = here.battle_id{same_round}""",
            (match_id, voter_id, VoteSource.FREE.value),
        ).fetchone()
        return row is not None

    def has_free_vote(self, match_id: int, voter_id: int) -> bool:
        """Оставлено для совместимости: бесплатный голос в этом матче."""
        return self.free_vote_used(match_id, voter_id, scope="match")

    def add_vote(
        self,
        match_id: int,
        voter_id: int,
        target_id: int,
        source: VoteSource,
        now: datetime | None = None,
    ) -> VoteResult:
        """Записать голос.

        Все условия проверяются внутри одного INSERT: матч ещё идёт, дедлайн не
        прошёл, участник действительно в этом матче. Проверять их заранее в
        Python нельзя — между проверкой и записью стоит сетевой вызов (подписка
        на канал), за время которого раунд успевает закрыться.

        Проверяется и статус батла: отменённый или завершённый батл закрывает
        голосование целиком, даже если отдельный матч почему-то остался открыт.

        Время сравнивается через datetime() самой SQLite: она приводит смещение
        часового пояса к UTC, поэтому сравнение верно и для «наивных» дат.
        """
        moment = (now or datetime.now(MSK)).isoformat()
        try:
            cursor = self.conn.execute(
                """INSERT INTO votes(match_id, voter_id, target_id, source)
                   SELECT ?, ?, ?, ?
                   WHERE EXISTS (
                       SELECT 1 FROM matches m
                       JOIN match_slots s ON s.match_id = m.id AND s.user_id = ?
                       JOIN battles b ON b.id = m.battle_id
                       WHERE m.id = ?
                         AND m.status = ?
                         AND b.status IN ('registration', 'running')
                         AND (m.deadline IS NULL
                              OR datetime(m.deadline) > datetime(?))
                   )""",
                (
                    match_id, voter_id, target_id, source.value,
                    target_id, match_id, MatchStatus.VOTING.value, moment,
                ),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return VoteResult.DUPLICATE

        if cursor.rowcount == 0:
            # голос не подошёл по условиям — записи нет, но транзакция открыта
            self.conn.rollback()
            return self._why_refused(match_id, target_id, moment)

        self.conn.execute(
            "UPDATE match_slots SET votes = votes + 1 WHERE match_id = ? AND user_id = ?",
            (match_id, target_id),
        )
        self.conn.commit()
        return VoteResult.ACCEPTED

    def _why_refused(self, match_id: int, target_id: int, moment: str) -> VoteResult:
        """Голос не записался — объяснить человеку, почему именно."""
        row = self.conn.execute(
            """SELECT 1 FROM match_slots WHERE match_id = ? AND user_id = ?""",
            (match_id, target_id),
        ).fetchone()
        return VoteResult.CLOSED if row else VoteResult.UNKNOWN_TARGET

    def can_nudge(self, match_id: int, user_id: int, cooldown_minutes: int = 10) -> bool:
        """Можно ли сейчас сказать участнику, что его обошли.

        Проверка и отметка — один запрос, поэтому при перестрелке за первое
        место человек не получит десяток сообщений подряд.
        """
        cursor = self.conn.execute(
            """INSERT INTO nudges(match_id, user_id) VALUES(?, ?)
               ON CONFLICT(match_id, user_id) DO UPDATE SET sent_at = datetime('now')
               WHERE datetime(sent_at) <= datetime('now', ?)""",
            (match_id, user_id, f"-{cooldown_minutes} minutes"),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def vote_log(self, match_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM votes WHERE match_id = ? ORDER BY id", (match_id,)
        ).fetchall()

    # --------------------------------------------------------------- payments

    def vote_balance(self, user_id: int) -> int:
        row = self.get_user(user_id)
        return int(row["vote_balance"]) if row else 0

    def add_votes(self, user_id: int, amount: int) -> None:
        self.conn.execute(
            "UPDATE users SET vote_balance = vote_balance + ? WHERE user_id = ?",
            (amount, user_id),
        )
        self.conn.commit()

    def spend_vote(self, user_id: int) -> bool:
        """Списать один купленный голос. False — если баланс пуст."""
        cur = self.conn.execute(
            "UPDATE users SET vote_balance = vote_balance - 1 WHERE user_id = ? AND vote_balance > 0",
            (user_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def record_payment(self, user_id: int, charge_id: str, stars: int, votes: int) -> bool:
        """Записать оплату. False — если этот платёж уже проведён."""
        try:
            self.conn.execute(
                "INSERT INTO payments(user_id, charge_id, stars, votes) VALUES(?, ?, ?, ?)",
                (user_id, charge_id, stars, votes),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()  # иначе неудачная запись держит транзакцию открытой
            return False
        self.conn.commit()
        return True

    def payment_history(self, user_id: int, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()

    def payment_by_charge(self, charge_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM payments WHERE charge_id = ?", (charge_id,)
        ).fetchone()

    def mark_refunded(self, charge_id: str) -> bool:
        """Пометить платёж возвращённым и снять начисленные голоса.

        Баланс не уходит в минус: если голоса уже потрачены, списываем сколько есть.
        """
        payment = self.payment_by_charge(charge_id)
        if payment is None or payment["status"] == "refunded":
            return False
        self.conn.execute(
            """UPDATE users SET vote_balance = MAX(0, vote_balance - ?) WHERE user_id = ?""",
            (payment["votes"], payment["user_id"]),
        )
        self.conn.execute(
            "UPDATE payments SET status = 'refunded' WHERE charge_id = ?", (charge_id,)
        )
        self.conn.commit()
        return True

    # ------------------------------------------------- проверка накрутки

    def self_referral_votes(self, limit: int = 10) -> list[sqlite3.Row]:
        """Голоса от людей, которых сам участник и пригласил.

        Самый весомый признак: человек нагнал знакомых по своей ссылке и они
        голосуют только за него.
        """
        return self.conn.execute(
            """SELECT s.user_id, u.username, COUNT(*) AS own_votes,
                      (SELECT COUNT(*) FROM votes v2
                       WHERE v2.match_id = v.match_id AND v2.target_id = s.user_id)
                      AS all_votes
               FROM votes v
               JOIN referrals r ON r.invited_id = v.voter_id
                                AND r.inviter_id = v.target_id
               JOIN match_slots s ON s.match_id = v.match_id AND s.user_id = v.target_id
               LEFT JOIN users u ON u.user_id = s.user_id
               GROUP BY s.user_id
               HAVING own_votes >= 3
               ORDER BY own_votes DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def vote_bursts(self, within_seconds: int = 60, threshold: int = 8,
                    limit: int = 10) -> list[sqlite3.Row]:
        """Всплески: много голосов за одного участника за короткое время."""
        return self.conn.execute(
            """SELECT v.match_id, v.target_id, u.username, COUNT(*) AS burst,
                      MIN(v.created_at) AS started
               FROM votes v
               LEFT JOIN users u ON u.user_id = v.target_id
               GROUP BY v.match_id, v.target_id,
                        CAST(strftime('%s', v.created_at) / ? AS INTEGER)
               HAVING burst >= ?
               ORDER BY burst DESC LIMIT ?""",
            (within_seconds, threshold, limit),
        ).fetchall()

    def loyal_voters(self, min_votes: int = 4, limit: int = 10) -> list[sqlite3.Row]:
        """Люди, которые голосуют всегда за одного и того же.

        Может быть настоящей дружбой, а может — фермой аккаунтов. Решает админ.
        """
        return self.conn.execute(
            """SELECT voter_id, COUNT(*) AS votes,
                      COUNT(DISTINCT target_id) AS targets,
                      MIN(target_id) AS target
               FROM votes
               GROUP BY voter_id
               HAVING targets = 1 AND votes >= ?
               ORDER BY votes DESC LIMIT ?""",
            (min_votes, limit),
        ).fetchall()

    def fresh_account_votes(self, minutes: int = 10, limit: int = 10) -> list[sqlite3.Row]:
        """Голоса от аккаунтов, заведённых прямо перед голосованием."""
        return self.conn.execute(
            """SELECT v.target_id, u2.username, COUNT(*) AS votes
               FROM votes v
               JOIN users u ON u.user_id = v.voter_id
               LEFT JOIN users u2 ON u2.user_id = v.target_id
               WHERE datetime(v.created_at) <= datetime(u.created_at, ?)
               GROUP BY v.target_id
               HAVING votes >= 3
               ORDER BY votes DESC LIMIT ?""",
            (f"+{minutes} minutes", limit),
        ).fetchall()

    # --------------------------------------------------------- автопилот

    def mark_done(self, kind: str, key: str) -> bool:
        """Отметить разовое действие автопилота. False — если уже было.

        Проверка и отметка — один запрос, поэтому повтор невозможен даже при
        двух тиках подряд.
        """
        try:
            self.conn.execute(
                "INSERT INTO auto_log(kind, key) VALUES(?, ?)", (kind, key)
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()  # иначе неудачная запись держит транзакцию открытой
            return False
        self.conn.commit()
        return True

    def add_promo(self, text: str, label: str | None, url: str | None) -> int:
        cursor = self.conn.execute(
            "INSERT INTO promos(text, button_label, button_url) VALUES(?, ?, ?)",
            (text, label, url),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def promos(self, only_enabled: bool = False) -> list[sqlite3.Row]:
        query = "SELECT * FROM promos"
        if only_enabled:
            query += " WHERE enabled = 1"
        return self.conn.execute(query + " ORDER BY id").fetchall()

    def next_promo(self) -> sqlite3.Row | None:
        """Наименее показанный пост — так очередь идёт по кругу честно."""
        return self.conn.execute(
            """SELECT * FROM promos WHERE enabled = 1
               ORDER BY sent_count, COALESCE(last_sent, ''), id LIMIT 1"""
        ).fetchone()

    def mark_promo_sent(self, promo_id: int) -> None:
        self.conn.execute(
            """UPDATE promos SET sent_count = sent_count + 1,
                                 last_sent = datetime('now')
               WHERE id = ?""",
            (promo_id,),
        )
        self.conn.commit()

    def toggle_promo(self, promo_id: int) -> None:
        self.conn.execute(
            "UPDATE promos SET enabled = 1 - enabled WHERE id = ?", (promo_id,)
        )
        self.conn.commit()

    def delete_promo(self, promo_id: int) -> None:
        self.conn.execute("DELETE FROM promos WHERE id = ?", (promo_id,))
        self.conn.commit()

    # ------------------------------------------------------- приглашения

    def record_referral(self, invited_id: int, inviter_id: int) -> bool:
        """Запомнить, кто кого привёл. False — если приглашённый уже учтён.

        Первичный ключ по invited_id гарантирует, что один и тот же человек не
        принесёт награду дважды, даже если откроет десяток разных ссылок.
        """
        if invited_id == inviter_id:
            return False
        try:
            self.conn.execute(
                "INSERT INTO referrals(invited_id, inviter_id) VALUES(?, ?)",
                (invited_id, inviter_id),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()  # иначе неудачная запись держит транзакцию открытой
            return False
        self.conn.commit()
        return True

    def pending_referral(self, invited_id: int) -> sqlite3.Row | None:
        """Приглашение, за которое ещё не выдана награда."""
        return self.conn.execute(
            "SELECT * FROM referrals WHERE invited_id = ? AND rewarded = 0",
            (invited_id,),
        ).fetchone()

    def reward_referral(self, invited_id: int, votes: int) -> int | None:
        """Выдать награду пригласившему. Возвращает его id или None.

        Отметка о награде ставится тем же запросом, что и её проверка, поэтому
        повторный вызов ничего не начислит.
        """
        cursor = self.conn.execute(
            """UPDATE referrals SET rewarded = 1, rewarded_at = datetime('now')
               WHERE invited_id = ? AND rewarded = 0""",
            (invited_id,),
        )
        if cursor.rowcount == 0:
            self.conn.commit()
            return None

        row = self.conn.execute(
            "SELECT inviter_id FROM referrals WHERE invited_id = ?", (invited_id,)
        ).fetchone()
        inviter_id = int(row["inviter_id"])
        self.conn.execute(
            "UPDATE users SET vote_balance = vote_balance + ? WHERE user_id = ?",
            (votes, inviter_id),
        )
        self.conn.commit()
        return inviter_id

    def referral_stats(self, inviter_id: int) -> tuple[int, int]:
        """Сколько человек привёл и за скольких получил награду."""
        row = self.conn.execute(
            """SELECT COUNT(*), COALESCE(SUM(rewarded), 0)
               FROM referrals WHERE inviter_id = ?""",
            (inviter_id,),
        ).fetchone()
        return int(row[0]), int(row[1])

    def referral_totals(self) -> tuple[int, int]:
        row = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(rewarded), 0) FROM referrals"
        ).fetchone()
        return int(row[0]), int(row[1])

    def referral_report(self) -> dict:
        """Полная картина по приглашениям — для панели."""
        total, rewarded = self.referral_totals()

        def since(days: int) -> int:
            return int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM referrals WHERE created_at >= datetime('now', ?)",
                    (f"-{days} day",),
                ).fetchone()[0]
            )

        inviters = int(
            self.conn.execute(
                "SELECT COUNT(DISTINCT inviter_id) FROM referrals"
            ).fetchone()[0]
        )
        return {
            "total": total,
            "rewarded": rewarded,
            "pending": total - rewarded,
            "today": since(1),
            "week": since(7),
            "inviters": inviters,
            # обычное округление, а не «к чётному»: 62.5% должно стать 63%
            "share": int(rewarded / total * 100 + 0.5) if total else 0,
        }

    def top_inviters(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT r.inviter_id, u.username, COUNT(*) AS invited,
                      COALESCE(SUM(r.rewarded), 0) AS rewarded
               FROM referrals r LEFT JOIN users u ON u.user_id = r.inviter_id
               GROUP BY r.inviter_id ORDER BY rewarded DESC, invited DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    # ------------------------------------------------- опубликованные посты

    def record_post(self, chat_id: int, message_id: int, battle_id: int | None,
                    kind: str = "match") -> None:
        self.conn.execute(
            """INSERT OR IGNORE INTO channel_posts(battle_id, chat_id, message_id, kind)
               VALUES(?, ?, ?, ?)""",
            (battle_id, chat_id, message_id, kind),
        )
        self.conn.commit()

    def posts(self, chat_id: int | None = None, kind: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM channel_posts WHERE 1=1"
        params: list = []
        if chat_id is not None:
            query += " AND chat_id = ?"
            params.append(chat_id)
        if kind is not None:
            query += " AND kind = ?"
            params.append(kind)
        return self.conn.execute(query + " ORDER BY id", params).fetchall()

    def forget_post(self, chat_id: int, message_id: int) -> None:
        self.conn.execute(
            "DELETE FROM channel_posts WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id),
        )
        self.conn.commit()

    # ------------------------------------------------- личные каналы участников

    def link_channel(
        self, user_id: int, chat_id: int, title: str | None, username: str | None
    ) -> bool:
        """Привязать канал к участнику.

        Один канал — один владелец: если его уже занял другой человек, отказываем.
        Свой же канал можно привязывать сколько угодно раз, это просто обновление.
        """
        owner = self.conn.execute(
            "SELECT user_id FROM member_channels WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        if owner is not None and int(owner["user_id"]) != user_id:
            return False

        self.conn.execute(
            """INSERT INTO member_channels(user_id, chat_id, title, username, active)
               VALUES(?, ?, ?, ?, 1)
               ON CONFLICT(user_id) DO UPDATE SET
                   chat_id = excluded.chat_id,
                   title = excluded.title,
                   username = excluded.username,
                   active = 1""",
            (user_id, chat_id, title, username),
        )
        self.conn.commit()
        return True

    def member_channel(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM member_channels WHERE user_id = ?", (user_id,)
        ).fetchone()

    def unlink_channel(self, user_id: int) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM member_channels WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def disable_channel(self, user_id: int) -> None:
        """Публиковать больше не можем: бота выгнали или лишили прав."""
        self.conn.execute(
            "UPDATE member_channels SET active = 0 WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()

    def bump_channel_posts(self, user_id: int) -> None:
        self.conn.execute(
            "UPDATE member_channels SET posts = posts + 1 WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()

    def member_channels(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT c.*, u.username AS owner_username, u.first_name AS owner_name
               FROM member_channels c LEFT JOIN users u ON u.user_id = c.user_id
               ORDER BY c.active DESC, c.posts DESC, c.linked_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def member_channel_stats(self) -> tuple[int, int, int]:
        """Сколько каналов привязано, сколько живых и сколько постов ушло."""
        row = self.conn.execute(
            """SELECT COUNT(*) AS total,
                      COALESCE(SUM(active), 0) AS live,
                      COALESCE(SUM(posts), 0) AS posts
               FROM member_channels"""
        ).fetchone()
        return int(row["total"]), int(row["live"]), int(row["posts"])

    # ------------------------------------------------------ группы и спам

    def add_group(self, chat_id: int, title: str | None, added_by: int | None = None) -> None:
        """Запомнить группу. Кто добавил — не перетираем, если уже знаем."""
        self.conn.execute(
            """INSERT INTO groups(chat_id, title, added_by) VALUES(?, ?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET
                   title = excluded.title,
                   added_by = COALESCE(groups.added_by, excluded.added_by)""",
            (chat_id, title, added_by),
        )
        self.conn.commit()

    def group(self, chat_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM groups WHERE chat_id = ?", (chat_id,)
        ).fetchone()

    def groups(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM groups ORDER BY added_at"
        ).fetchall()

    def toggle_group(self, chat_id: int) -> bool:
        """Включить или выключить чистку в группе. Возвращает новое состояние."""
        self.conn.execute(
            "UPDATE groups SET moderation = 1 - moderation WHERE chat_id = ?", (chat_id,)
        )
        self.conn.commit()
        row = self.group(chat_id)
        return bool(row and row["moderation"])

    def forget_group(self, chat_id: int) -> None:
        self.conn.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
        self.conn.execute("DELETE FROM strikes WHERE chat_id = ?", (chat_id,))
        self.conn.commit()

    def count_deleted(self, chat_id: int) -> None:
        self.conn.execute(
            "UPDATE groups SET deleted = deleted + 1 WHERE chat_id = ?", (chat_id,)
        )
        self.conn.commit()

    def add_strike(self, chat_id: int, user_id: int) -> int:
        """Записать нарушение. Возвращает, какое оно по счёту."""
        self.conn.execute(
            """INSERT INTO strikes(chat_id, user_id, count) VALUES(?, ?, 1)
               ON CONFLICT(chat_id, user_id) DO UPDATE SET
                   count = strikes.count + 1,
                   last_at = datetime('now')""",
            (chat_id, user_id),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT count FROM strikes WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ).fetchone()
        return int(row["count"]) if row else 1

    def clear_strikes(self, chat_id: int, user_id: int) -> None:
        self.conn.execute(
            "DELETE FROM strikes WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)
        )
        self.conn.commit()

    # ------------------------------------------------- вышедшие из канала

    def mark_left(self, user_id: int, chat_id: int) -> int:
        """Запомнить выход из канала. Возвращает, какой это раз по счёту."""
        self.conn.execute(
            """INSERT INTO leavers(user_id, chat_id) VALUES(?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   chat_id = excluded.chat_id,
                   times = leavers.times + 1,
                   left_at = datetime('now')""",
            (user_id, chat_id),
        )
        # в очереди ему делать нечего, пока не вернётся честно
        self.conn.execute("DELETE FROM queue WHERE user_id = ?", (user_id,))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT times FROM leavers WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(row["times"]) if row else 1

    def known_subscribers(self, limit: int = 2000) -> list[int]:
        """Кто **точно** был подписан на канал.

        Список подписчиков Telegram не отдаёт, но это и не нужно: подписку
        проверяет сам бот при каждой заявке и при каждом голосе. Значит все,
        кто хоть раз участвовал или голосовал, гейт проходили — а больше
        никто и не может подавать заявку.

        Тех, кто просто нажал /start и не подписывался, сюда не берём: они
        не выходили, им просто нечего было покидать.
        """
        rows = self.conn.execute(
            """SELECT user_id FROM (
                   SELECT user_id FROM participants
                   UNION
                   SELECT voter_id AS user_id FROM votes
               )
               WHERE user_id NOT IN (SELECT user_id FROM leavers)
               ORDER BY user_id LIMIT ?""",
            (limit,),
        ).fetchall()
        return [int(row["user_id"]) for row in rows]

    def leaver(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM leavers WHERE user_id = ?", (user_id,)
        ).fetchone()

    def forgive_leaver(self, user_id: int) -> bool:
        cursor = self.conn.execute("DELETE FROM leavers WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def leavers(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT l.*, u.username, u.first_name
               FROM leavers l LEFT JOIN users u ON u.user_id = l.user_id
               ORDER BY l.left_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    def leaver_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM leavers").fetchone()[0])

    # ------------------------------------------------------- сила участника

    def player_strength(self, battle_id: int) -> dict[int, float]:
        """Насколько уверенно человек проходил прошлые раунды.

        Считаем **долю** голосов в своём матче, а не их количество. Так честнее:
        победа 3:0 — это полное превосходство, а 20:19 — почти ничья, хотя
        голосов там втрое больше. Количество голосов говорит о популярности
        пары, доля — о самом участнике.

        Итог — средняя доля по сыгранным матчам. Прошедшему без боя ставим
        нейтральные 0.5: он ничего не доказал, но и не проиграл.
        """
        rows = self.conn.execute(
            """SELECT s.user_id,
                      s.votes AS mine,
                      (SELECT SUM(s2.votes) FROM match_slots s2
                       WHERE s2.match_id = s.match_id) AS total
               FROM match_slots s
               JOIN matches m ON m.id = s.match_id
               WHERE m.battle_id = ? AND m.status = ?""",
            (battle_id, MatchStatus.CLOSED.value),
        ).fetchall()

        played: dict[int, list[float]] = {}
        for row in rows:
            total = int(row["total"] or 0)
            # матч без единого голоса ничего о силе не говорит
            share = (int(row["mine"]) / total) if total else 0.5
            played.setdefault(int(row["user_id"]), []).append(share)

        strength = {uid: sum(shares) / len(shares) for uid, shares in played.items()}
        for player in self.alive_players(battle_id):
            strength.setdefault(player.user_id, 0.5)  # прошёл без боя
        return strength

    # ---------------------------------------------------- пауза призёрам

    def set_cooldown(self, user_id: int, place: int, battle_id: int | None,
                     until: datetime) -> None:
        """Поставить паузу. Новая победа перекрывает старую паузу."""
        self.conn.execute(
            """INSERT INTO cooldowns(user_id, place, battle_id, until)
               VALUES(?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   place = excluded.place,
                   battle_id = excluded.battle_id,
                   until = excluded.until,
                   created_at = datetime('now')""",
            (user_id, place, battle_id, until.isoformat()),
        )
        # в очереди на следующий батл ему теперь не место
        self.conn.execute("DELETE FROM queue WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def cooldown_for(self, user_id: int, now: datetime | None = None) -> sqlite3.Row | None:
        """Действующая пауза или None. Истёкшая считается снятой."""
        moment = (now or datetime.now(MSK)).isoformat()
        return self.conn.execute(
            """SELECT * FROM cooldowns
               WHERE user_id = ? AND datetime(until) > datetime(?)""",
            (user_id, moment),
        ).fetchone()

    def clear_cooldown(self, user_id: int) -> bool:
        cursor = self.conn.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def active_cooldowns(self, limit: int = 20, now: datetime | None = None) -> list[sqlite3.Row]:
        moment = (now or datetime.now(MSK)).isoformat()
        return self.conn.execute(
            """SELECT c.*, u.username, u.first_name
               FROM cooldowns c LEFT JOIN users u ON u.user_id = c.user_id
               WHERE datetime(c.until) > datetime(?)
               ORDER BY c.until LIMIT ?""",
            (moment, limit),
        ).fetchall()

    def cooldown_count(self, now: datetime | None = None) -> int:
        moment = (now or datetime.now(MSK)).isoformat()
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM cooldowns WHERE datetime(until) > datetime(?)",
                (moment,),
            ).fetchone()[0]
        )

    # ------------------------------------------------------- журнал сбоев

    KEEP_ERRORS = 200  # хранить только последние: журнал не должен расти вечно

    def record_error(
        self, kind: str, message: str, action: str | None = None,
        user_id: int | None = None,
    ) -> None:
        """Записать сбой. Сама запись не должна ронять обработчик ошибок."""
        try:
            self.conn.execute(
                "INSERT INTO errors(kind, message, action, user_id) VALUES(?, ?, ?, ?)",
                (kind[:64], message[:500], (action or "")[:120] or None, user_id),
            )
            self.conn.execute(
                """DELETE FROM errors WHERE id NOT IN (
                       SELECT id FROM errors ORDER BY id DESC LIMIT ?
                   )""",
                (self.KEEP_ERRORS,),
            )
            self.conn.commit()
        except sqlite3.Error as failure:  # журнал важен, но не важнее бота
            log.warning("Не удалось записать сбой в журнал: %s", failure)

    def recent_errors(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def error_summary(self, hours: int = 24) -> list[sqlite3.Row]:
        """Что и сколько раз ломалось за последнее время."""
        return self.conn.execute(
            """SELECT kind, COUNT(*) AS times, MAX(created_at) AS last_at
               FROM errors
               WHERE datetime(created_at) > datetime('now', ?)
               GROUP BY kind ORDER BY times DESC""",
            (f"-{int(hours)} hours",),
        ).fetchall()

    def clear_errors(self) -> int:
        cursor = self.conn.execute("DELETE FROM errors")
        self.conn.commit()
        return cursor.rowcount

    # ---------------------------------------------------- сводка для панели

    def user_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def new_users(self, days: int = 1) -> int:
        return int(
            self.conn.execute(
                "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?)",
                (f"-{days} day",),
            ).fetchone()[0]
        )

    def banned_count(self) -> int:
        return int(
            self.conn.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        )

    def sold_votes(self) -> tuple[int, int]:
        """Сколько голосов продано и на сколько звёзд."""
        row = self.conn.execute(
            """SELECT COALESCE(SUM(votes), 0), COALESCE(SUM(stars), 0)
               FROM payments WHERE status = 'paid'"""
        ).fetchone()
        return int(row[0]), int(row[1])

    def total_votes_cast(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0])

    def find_users(self, needle: str, limit: int = 10) -> list[sqlite3.Row]:
        """Поиск по нику или ID — для карточки участника в панели."""
        if needle.isdigit():
            rows = self.conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(needle),)
            ).fetchall()
            if rows:
                return rows
        return self.conn.execute(
            "SELECT * FROM users WHERE username LIKE ? COLLATE NOCASE ORDER BY user_id LIMIT ?",
            (f"%{needle.lstrip('@')}%", limit),
        ).fetchall()

    # ------------------------------------------------------------------ stats

    def bump_wins(self, user_ids: list[int]) -> None:
        if not user_ids:
            return
        self.conn.executemany(
            "UPDATE stats SET wins = wins + 1 WHERE user_id = ?",
            [(uid,) for uid in user_ids],
        )
        self.conn.commit()

    def record_place(self, user_id: int, place: int) -> None:
        self.conn.execute(
            """UPDATE stats
               SET titles = titles + CASE WHEN ? = 1 THEN 1 ELSE 0 END,
                   best_place = CASE
                       WHEN best_place IS NULL OR best_place > ? THEN ?
                       ELSE best_place END
               WHERE user_id = ?""",
            (place, place, place, user_id),
        )
        self.conn.commit()

    def stats_for(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM stats WHERE user_id = ?", (user_id,)).fetchone()

    def leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT u.user_id, u.username, s.battles, s.wins, s.titles, s.best_place
               FROM stats s JOIN users u ON u.user_id = s.user_id
               WHERE s.battles > 0
               ORDER BY s.titles DESC, s.wins DESC, s.battles ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    def all_user_ids(self) -> list[int]:
        """Кому вообще имеет смысл писать: без забаненных и заблокировавших бота."""
        return [
            row[0]
            for row in self.conn.execute(
                "SELECT user_id FROM users WHERE is_banned = 0 AND is_blocked = 0"
            )
        ]
