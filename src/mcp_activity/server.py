# SPDX-FileCopyrightText: 2026 Peter Lemenkov <lemenkov@gmail.com>
# SPDX-License-Identifier: Apache-2.0

"""MCP server for activity logging."""

import argparse
import asyncio
from datetime import date

from fastmcp import FastMCP

from .database import ActivityDB

# Initialize FastMCP server
mcp = FastMCP("Activity Log MCP Server")
db = ActivityDB()


@mcp.tool(
    tags={"write"},
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    },
)
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


@mcp.tool(
    tags={"read"},
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
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
        if activity["category"]:
            response += f"Category: {activity['category']}\n"
        response += f"{activity['message']}\n"
        if activity["tags"]:
            response += f"Tags: {activity['tags']}\n"
        response += "\n"

    return response


@mcp.tool(
    tags={"read"},
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
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
            cat = activity.get("category", "Other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(activity["message"])

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
            cat = activity.get("category", "Other")
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


@mcp.tool(
    tags={"write"},
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
async def bus_publish(
    topic: str,
    sender: str,
    body: str,
    requires_approval: bool = False,
) -> str:
    """Publish a message to a topic on the agent bus.

    Args:
        topic: Topic name (e.g. 'research', 'implementation', 'review')
        sender: Agent identity (e.g. 'researcher', 'implementer')
        body: Message content
        requires_approval: If True, message waits for human approval before delivery
    """
    message_id = await db.bus_publish(topic, sender, body, requires_approval)
    status = "pending approval" if requires_approval else "delivered"
    return f"Message published (ID: {message_id}, status: {status})"


@mcp.tool(
    tags={"read"},
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
async def bus_poll(
    topic: str,
    since_id: int = 0,
) -> str:
    """Poll approved messages from a topic on the agent bus.

    Args:
        topic: Topic name to poll
        since_id: Only return messages with ID greater than this (for pagination)
    """
    messages = await db.bus_poll(topic, since_id)
    if not messages:
        return f"No new messages on topic '{topic}' since ID {since_id}"

    response = f"Found {len(messages)} message(s) on topic '{topic}':\n\n"
    for msg in messages:
        response += (
            f"**[ID:{msg['id']}]** from {msg['sender']} at {msg['created_at'][:19]}\n"
        )
        response += f"{msg['body']}\n\n"
    return response


@mcp.tool(
    tags={"read"},
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
async def bus_pending() -> str:
    """List all messages pending human approval on the agent bus."""
    messages = await db.bus_pending()
    if not messages:
        return "No messages pending approval."

    response = f"Found {len(messages)} message(s) pending approval:\n\n"
    for msg in messages:
        response += f"**[ID:{msg['id']}]** topic={msg['topic']} from={msg['sender']} at {msg['created_at'][:19]}\n"
        response += f"{msg['body']}\n\n"
    return response


@mcp.tool(
    tags={"write"},
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
async def bus_approve(message_id: int) -> str:
    """Approve a pending message on the agent bus, making it visible to subscribers.

    Args:
        message_id: ID of the message to approve
    """
    success = await db.bus_approve(message_id)
    if success:
        return f"Message {message_id} approved and delivered."
    return f"Message {message_id} not found or not in pending state."


@mcp.tool(
    tags={"write"},
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
async def bus_reject(message_id: int, reason: str = "") -> str:
    """Reject a pending message on the agent bus.

    Args:
        message_id: ID of the message to reject
        reason: Optional reason for rejection
    """
    success = await db.bus_reject(message_id, reason)
    if success:
        return f"Message {message_id} rejected."
    return f"Message {message_id} not found or not in pending state."


async def init():
    """Initialize the database."""
    await db.init_db()


def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="Activity Log MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to listen on")
    parser.add_argument("--port", type=int, default=8802, help="Port to listen on")
    parser.add_argument(
        "--db-path",
        default="/var/lib/mcp-activity/activity.db",
        help="Path to SQLite database",
    )
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
