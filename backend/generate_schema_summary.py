"""
Generate a text summary of all tables, columns, and data types in supportdb.
The output is written to backend/support_schema.txt and is formatted for LLM consumption.
"""

import os
import psycopg

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "support_schema.txt")


def main():
    conn = psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5431"),
        dbname=os.getenv("DB_NAME", "supportdb"),
        user=os.getenv("DB_USER", "support_ro"),
        password=os.getenv("DB_PASSWORD", "support_ro"),
    )

    query = """
    SELECT
        table_schema,
        table_name,
        column_name,
        data_type,
        is_nullable,
        ordinal_position
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """

    with conn, conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    # Group columns by table
    tables = {}
    for schema, table, col, dtype, nullable, pos in rows:
        tables.setdefault(table, []).append(
            {"name": col, "type": dtype, "nullable": nullable}
        )

    lines = []
    lines.append("Database: supportdb")
    lines.append("Schema: public")
    lines.append("Tables:")

    for table_name, cols in tables.items():
        lines.append(f"- {table_name}")
        for col in cols:
            nullable_flag = "nullable" if col["nullable"] == "YES" else "not null"
            lines.append(f"  - {col['name']}: {col['type']} ({nullable_flag})")

    output = "\n".join(lines)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Schema summary written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

