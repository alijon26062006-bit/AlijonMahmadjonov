"""Запросы к базе. Единственное место, где живёт SQL."""
from __future__ import annotations

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
        self.conn.execute("INSERT OR IGNORE INTO stats(user_id) VALUES(?)", (user_id,))
        self.conn.commit()

    def get_user(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def is_banned(self, user_id: int) -> bool:
        row = self.get_user(user_id)
        return bool(row and row["is_banned"])

    def set_banned(self, user_id: int, banned: bool) -> None:
        self.conn.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(banned), user_id))
        self.conn.commit()

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

    def unassigned_players(self, battle_id: int) -> list[Player]:
        """Заявки, которым ещё не досталась пара в первом раунде."""
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

    def has_free_vote(self, match_id: int, voter_id: int) -> bool:
        row = self.conn.execute(
            """SELECT 1 FROM votes
               WHERE match_id = ? AND voter_id = ? AND source = ?""",
            (match_id, voter_id, VoteSource.FREE.value),
        ).fetchone()
        return row is not None

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
            return VoteResult.DUPLICATE

        if cursor.rowcount == 0:
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
        return [
            row[0]
            for row in self.conn.execute("SELECT user_id FROM users WHERE is_banned = 0")
        ]
