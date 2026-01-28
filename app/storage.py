import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi.concurrency import run_in_threadpool

from .logging_utils import utc_now_iso

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  from_msisdn TEXT NOT NULL,
  to_msisdn TEXT NOT NULL,
  ts TEXT NOT NULL,
  text TEXT,
  created_at TEXT NOT NULL
);
"""


def _sqlite_path(database_url: str) -> str:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise ValueError("DATABASE_URL must be sqlite")
    if not parsed.path:
        raise ValueError("Invalid sqlite DATABASE_URL")
    return parsed.path


@dataclass(frozen=True)
class InsertResult:
    dup: bool


@dataclass(frozen=True)
class MessagesPage:
    rows: List[Dict[str, Any]]
    total: int


class Storage:
    def __init__(self, database_url: str):
        self.db_path = _sqlite_path(database_url)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema_sync(self) -> None:
        conn = self._connect()
        try:
            conn.execute(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    async def init_schema(self) -> None:
        await run_in_threadpool(self.init_schema_sync)

    def schema_exists_sync(self) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
            )
            return cur.fetchone() is not None
        finally:
            conn.close()

    async def schema_exists(self) -> bool:
        return await run_in_threadpool(self.schema_exists_sync)

    def insert_message_sync(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str],
    ) -> InsertResult:
        conn = self._connect()
        try:
            created_at = utc_now_iso()
            try:
                conn.execute(
                    "INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at),
                )
                conn.commit()
                return InsertResult(dup=False)
            except sqlite3.IntegrityError:
                return InsertResult(dup=True)
        finally:
            conn.close()

    async def insert_message(
        self, message_id: str, from_msisdn: str, to_msisdn: str, ts: str, text: Optional[str]
    ) -> InsertResult:
        return await run_in_threadpool(
            self.insert_message_sync, message_id, from_msisdn, to_msisdn, ts, text
        )

    def _build_filters(
        self,
        from_filter: Optional[str],
        since: Optional[str],
        q: Optional[str],
    ) -> Tuple[str, List[Any]]:
        where = []
        args: List[Any] = []
        if from_filter:
            where.append("from_msisdn = ?")
            args.append(from_filter)
        if since:
            where.append("ts >= ?")
            args.append(since)
        if q is not None:
            where.append("LOWER(COALESCE(text,'')) LIKE ?")
            args.append(f"%{q.lower()}%")
        sql = ""
        if where:
            sql = " WHERE " + " AND ".join(where)
        return sql, args

    def list_messages_sync(
        self,
        limit: int,
        offset: int,
        from_filter: Optional[str],
        since: Optional[str],
        q: Optional[str],
    ) -> MessagesPage:
        conn = self._connect()
        try:
            where_sql, args = self._build_filters(from_filter, since, q)
            total_cur = conn.execute("SELECT COUNT(*) AS c FROM messages" + where_sql, args)
            total = int(total_cur.fetchone()["c"])
            cur = conn.execute(
                "SELECT message_id, from_msisdn, to_msisdn, ts, text, created_at "
                "FROM messages" + where_sql +
                " ORDER BY ts ASC, message_id ASC LIMIT ? OFFSET ?",
                args + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]
            return MessagesPage(rows=rows, total=total)
        finally:
            conn.close()

    async def list_messages(
        self,
        limit: int,
        offset: int,
        from_filter: Optional[str],
        since: Optional[str],
        q: Optional[str],
    ) -> MessagesPage:
        return await run_in_threadpool(
            self.list_messages_sync, limit, offset, from_filter, since, q
        )

    def stats_sync(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            total = int(conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"])
            senders = int(
                conn.execute("SELECT COUNT(DISTINCT from_msisdn) AS c FROM messages").fetchone()["c"]
            )
            top_cur = conn.execute(
                "SELECT from_msisdn, COUNT(*) AS c FROM messages GROUP BY from_msisdn ORDER BY c DESC LIMIT 10"
            )
            per_sender = [
                {"from": r["from_msisdn"], "count": int(r["c"])}
                for r in top_cur.fetchall()
            ]
            minmax = conn.execute("SELECT MIN(ts) AS mn, MAX(ts) AS mx FROM messages").fetchone()
            first_ts = minmax["mn"]
            last_ts = minmax["mx"]
            return {
                "total_messages": total,
                "senders_count": senders,
                "messages_per_sender": per_sender,
                "first_message_ts": first_ts,
                "last_message_ts": last_ts,
            }
        finally:
            conn.close()

    async def stats(self) -> Dict[str, Any]:
        return await run_in_threadpool(self.stats_sync)
