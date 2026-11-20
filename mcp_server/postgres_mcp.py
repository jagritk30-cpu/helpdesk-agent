"""
MCP Server for HR/IT Helpdesk — Postgres Employee Data
Uses MCP v2 (MCPServer) with @tool decorators for stdio transport.

Exposes tools:
  get_leave_balance, get_employee_info, get_it_assets,
  get_it_tickets, list_employees

The underlying handler functions are plain Python and can be
imported directly by the agent without spinning up the MCP server.
"""
import os
import sys
from typing import Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

# ── DB connection ────────────────────────────────────────────────────────────

def _get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "helpdesk"),
        user=os.getenv("POSTGRES_USER", "jagritpandit"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def _query(sql: str, params: tuple = ()) -> list[dict]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _resolve_employee_id(employee_id: Optional[str], employee_name: Optional[str]) -> Optional[str]:
    if employee_id:
        return employee_id.strip().upper()
    if employee_name:
        rows = _query(
            "SELECT employee_id FROM employees WHERE full_name ILIKE %s LIMIT 1",
            (f"%{employee_name}%",),
        )
        if rows:
            return rows[0]["employee_id"]
    return None


# ── Tool handler functions (importable directly) ──────────────────────────────

def get_leave_balance(
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
    year: int = 2026,
) -> str:
    """
    Get the leave balance for an employee.
    Provide either employee_id (e.g. 'E102') or employee_name.
    Returns remaining days per leave type for the given year.
    """
    eid = _resolve_employee_id(employee_id, employee_name)
    if not eid:
        return "Could not find employee. Please provide a valid employee_id or name."
    rows = _query(
        """
        SELECT lb.leave_type,
               lb.total_days,
               lb.used_days,
               lb.total_days - lb.used_days AS remaining_days,
               e.full_name
        FROM leave_balances lb
        JOIN employees e ON e.employee_id = lb.employee_id
        WHERE lb.employee_id = %s AND lb.year = %s
        ORDER BY lb.leave_type
        """,
        (eid, year),
    )
    if not rows:
        return f"No leave balance data found for employee {eid} in year {year}."
    name = rows[0]["full_name"]
    result = [f"Leave balances for {name} ({eid}) — {year}:"]
    for r in rows:
        result.append(
            f"  • {r['leave_type'].title()} Leave: {r['remaining_days']} days remaining "
            f"(used {r['used_days']} of {r['total_days']})"
        )
    return "\n".join(result)


def get_employee_info(
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
) -> str:
    """
    Look up employee details: name, department, designation, join date, manager.
    """
    eid = _resolve_employee_id(employee_id, employee_name)
    if not eid:
        return "Could not find employee."
    rows = _query(
        """
        SELECT e.employee_id, e.full_name, e.email, e.department,
               e.designation, e.date_joined, e.is_active,
               m.full_name AS manager_name
        FROM employees e
        LEFT JOIN employees m ON m.employee_id = e.manager_id
        WHERE e.employee_id = %s
        """,
        (eid,),
    )
    if not rows:
        return f"No employee found with ID {eid}."
    r = rows[0]
    return (
        f"Employee: {r['full_name']} ({r['employee_id']})\n"
        f"  Department   : {r['department']}\n"
        f"  Designation  : {r['designation']}\n"
        f"  Email        : {r['email']}\n"
        f"  Date Joined  : {r['date_joined']}\n"
        f"  Manager      : {r['manager_name'] or 'N/A'}\n"
        f"  Status       : {'Active' if r['is_active'] else 'Inactive'}"
    )


def get_it_assets(
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
) -> str:
    """List IT assets (laptop, monitor, phone) assigned to an employee."""
    eid = _resolve_employee_id(employee_id, employee_name)
    if not eid:
        return "Could not find employee."
    rows = _query(
        """
        SELECT a.asset_tag, a.asset_type, a.brand, a.model,
               a.serial_number, a.assigned_date, a.status,
               e.full_name
        FROM it_assets a
        JOIN employees e ON e.employee_id = a.assigned_to
        WHERE a.assigned_to = %s
        ORDER BY a.asset_type
        """,
        (eid,),
    )
    if not rows:
        return f"No IT assets assigned to employee {eid}."
    name = rows[0]["full_name"]
    result = [f"IT assets assigned to {name} ({eid}):"]
    for r in rows:
        result.append(
            f"  • [{r['asset_tag']}] {r['brand']} {r['model']} ({r['asset_type']}) "
            f"— assigned {r['assigned_date']}"
        )
    return "\n".join(result)


def get_it_tickets(
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
    status: Optional[str] = None,
) -> str:
    """
    Retrieve IT helpdesk tickets for an employee.
    Optionally filter by status: 'open', 'in_progress', 'resolved', 'closed'.
    """
    eid = _resolve_employee_id(employee_id, employee_name)
    if not eid:
        return "Could not find employee."
    if status:
        rows = _query(
            """
            SELECT t.ticket_id, t.category, t.subject, t.priority,
                   t.status, t.created_at, t.resolved_at, e.full_name
            FROM it_tickets t
            JOIN employees e ON e.employee_id = t.employee_id
            WHERE t.employee_id = %s AND t.status = %s
            ORDER BY t.created_at DESC
            """,
            (eid, status),
        )
    else:
        rows = _query(
            """
            SELECT t.ticket_id, t.category, t.subject, t.priority,
                   t.status, t.created_at, t.resolved_at, e.full_name
            FROM it_tickets t
            JOIN employees e ON e.employee_id = t.employee_id
            WHERE t.employee_id = %s
            ORDER BY t.created_at DESC
            """,
            (eid,),
        )
    if not rows:
        return f"No IT tickets found for employee {eid}."
    name = rows[0]["full_name"]
    result = [f"IT tickets for {name} ({eid}):"]
    for r in rows:
        result.append(
            f"  • [{r['ticket_id']}] [{r['priority'].upper()}] {r['subject']} "
            f"— Status: {r['status']}"
        )
    return "\n".join(result)


def list_employees() -> str:
    """List all active employees with their IDs, names, and departments."""
    rows = _query(
        "SELECT employee_id, full_name, department, designation "
        "FROM employees WHERE is_active = TRUE ORDER BY employee_id"
    )
    if not rows:
        return "No active employees found."
    result = ["Active Employees:"]
    for r in rows:
        result.append(
            f"  {r['employee_id']} — {r['full_name']} ({r['department']}, {r['designation']})"
        )
    return "\n".join(result)


# ── MCP Server entry point ────────────────────────────────────────────────────
# Only runs when executed directly (not when imported as a module).

if __name__ == "__main__":
    from mcp.server.mcpserver import MCPServer

    mcp_server = MCPServer("helpdesk-postgres-mcp")

    # Register tools
    mcp_server.add_tool(get_leave_balance)
    mcp_server.add_tool(get_employee_info)
    mcp_server.add_tool(get_it_assets)
    mcp_server.add_tool(get_it_tickets)
    mcp_server.add_tool(list_employees)

    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    mcp_server.run(transport=transport)
