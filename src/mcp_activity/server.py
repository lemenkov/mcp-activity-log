"""MCP server for activity logging."""
import argparse
import asyncio
from fastmcp import FastMCP
from .database import ActivityDB
from datetime import date


# Initialize FastMCP server
mcp = FastMCP("Activity Log MCP Server")
db = ActivityDB()


@mcp.tool(tags={"write"}, annotations={"readOnlyHint": False, "openWorldHint": False,  "destructiveHint": True})
async def log_activity(
    message: str,
    source: str = "web",
    category: str | None = None,
    tags: str | None = None,
) -> str:
    """
    Log an activity entry.

    Args:
        message: Activity description
        source: Source (cli, web) - defaults to web
        category: Category (task, bug, decision, learning, todo, etc.)
        tags: Comma-separated tags (e.g., "bugzilla,mcp,pr")
    """
    entry_id = await db.add_activity(message, source, category, tags)
    return f"Activity logged successfully (ID: {entry_id})"


@mcp.tool(tags={"read"}, annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
async def get_activities(
    date_filter: str | None = None,
    category: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> str:
    """
    Get activity entries with optional filters.

    Args:
        date_filter: Filter by date (YYYY-MM-DD format, or 'today')
        category: Filter by category
        source: Filter by source (cli/web)
        limit: Maximum number of results (default: 50)
    """
    # Handle 'today' shortcut
    if date_filter == "today":
        date_filter = date.today().isoformat()

    activities = await db.get_activities(date_filter, category, source, limit)

    if not activities:
        return "No activities found matching the filters."

    response = f"Found {len(activities)} activities:\n\n"

    for activity in activities:
        response += f"**[{activity['timestamp'][:19]}]** ({activity['source']})\n"
        if activity['category']:
            response += f"Category: {activity['category']}\n"
        response += f"{activity['message']}\n"
        if activity['tags']:
            response += f"Tags: {activity['tags']}\n"
        response += "\n"

    return response


@mcp.tool(tags={"read"}, annotations={"readOnlyHint": True, "openWorldHint": False, "destructiveHint": False})
async def generate_report(
    date_filter: str = "today",
    format: str = "summary",
) -> str:
    """
    Generate a report of activities.

    Args:
        date_filter: Date to report on (YYYY-MM-DD or 'today')
        format: Report format ('summary', 'detailed', 'changelog')
    """
    if date_filter == "today":
        date_filter = date.today().isoformat()

    activities = await db.get_activities(date=date_filter)

    if not activities:
        return f"No activities logged for {date_filter}"

    if format == "changelog":
        response = f"# Changelog for {date_filter}\n\n"

        # Group by category
        by_category = {}
        for activity in activities:
            cat = activity.get('category', 'Other')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(activity['message'])

        for category, messages in by_category.items():
            response += f"## {category}\n"
            for msg in messages:
                response += f"- {msg}\n"
            response += "\n"

    elif format == "summary":
        response = f"# Activity Summary for {date_filter}\n\n"
        response += f"Total activities: {len(activities)}\n\n"

        categories = {}
        for activity in activities:
            cat = activity.get('category', 'Other')
            categories[cat] = categories.get(cat, 0) + 1

        response += "By category:\n"
        for cat, count in categories.items():
            response += f"- {cat}: {count}\n"

    else:  # detailed
        response = f"# Detailed Report for {date_filter}\n\n"
        for activity in activities:
            response += f"**{activity['timestamp'][:19]}** - {activity.get('category', 'N/A')}\n"
            response += f"{activity['message']}\n\n"

    return response


async def init():
    """Initialize the database."""
    await db.init_db()


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="Activity Log MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to listen on")
    parser.add_argument("--port", type=int, default=8802, help="Port to listen on")
    parser.add_argument("--db-path", default="/var/lib/mcp-activity/activity.db",
                       help="Path to SQLite database")
    args = parser.parse_args()

    # Set database path
    global db
    db = ActivityDB(db_path=args.db_path)

    # Initialize database
    asyncio.run(init())

    # Run the server
    mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
