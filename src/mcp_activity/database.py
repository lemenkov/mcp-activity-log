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
