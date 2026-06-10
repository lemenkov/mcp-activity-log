"""SQLite database for activity logs."""
import aiosqlite
from datetime import datetime
from typing import List, Dict, Any, Optional


class ActivityDB:
    """Activity log database."""

    def __init__(self, db_path: str = "/var/lib/mcp-activity/activity.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initialize the database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    category TEXT,
                    message TEXT NOT NULL,
                    tags TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bus_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'approved',
                    rejection_reason TEXT,
                    approved_at TEXT
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_bus_topic ON bus_messages(topic)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_bus_status ON bus_messages(status)")
            await db.commit()

    async def add_activity(
        self,
        message: str,
        source: str = "web",
        category: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> int:
        """
        Add an activity entry.

        Args:
            message: Activity description
            source: Source (cli, web, etc.)
            category: Category (task, bug, decision, learning, etc.)
            tags: Comma-separated tags

        Returns:
            ID of the created entry
        """
        timestamp = datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO activities (timestamp, source, category, message, tags)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, source, category, message, tags)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_activities(
        self,
        date: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get activity entries with optional filters.

        Args:
            date: Filter by date (YYYY-MM-DD)
            category: Filter by category
            source: Filter by source (cli/web)
            limit: Maximum number of results

        Returns:
            List of activity entries
        """
        query = "SELECT * FROM activities WHERE 1=1"
        params = []

        if date:
            query += " AND DATE(timestamp) = ?"
            params.append(date)

        if category:
            query += " AND category = ?"
            params.append(category)

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def bus_publish(
        self,
        topic: str,
        sender: str,
        body: str,
        requires_approval: bool = False,
    ) -> int:
        """Publish a message to a topic."""
        status = "pending" if requires_approval else "approved"
        created_at = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO bus_messages (created_at, topic, sender, body, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (created_at, topic, sender, body, status)
            )
            await db.commit()
            return cursor.lastrowid

    async def bus_poll(
        self,
        topic: str,
        since_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """Poll approved messages from a topic."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM bus_messages
                WHERE topic = ? AND status = 'approved' AND id > ?
                ORDER BY id ASC
                """,
                (topic, since_id)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def bus_pending(self) -> List[Dict[str, Any]]:
        """Get all pending messages awaiting approval."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM bus_messages
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def bus_approve(self, message_id: int) -> bool:
        """Approve a pending message."""
        approved_at = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE bus_messages
                SET status = 'approved', approved_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (approved_at, message_id)
            )
            await db.commit()
            return db.total_changes > 0

    async def bus_reject(self, message_id: int, reason: str = "") -> bool:
        """Reject a pending message."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE bus_messages
                SET status = 'rejected', rejection_reason = ?
                WHERE id = ? AND status = 'pending'
                """,
                (reason, message_id)
            )
            await db.commit()
            return db.total_changes > 0
