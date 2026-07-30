"""DuckDB In-Memory SQL Execution Engine for ADA.

Provides relational SQL query execution, table registration for single or multiple
CSVs, and SQL code formatting.
"""

from typing import Dict, Any, Optional, Tuple
import duckdb
import pandas as pd


class SQLEngine:
    """In-memory DuckDB query engine for multi-table analysis."""

    def __init__(self):
        self.conn = duckdb.connect(database=":memory:")
        self._registered_tables: Dict[str, pd.DataFrame] = {}

    def register_tables(self, tables: Dict[str, pd.DataFrame]) -> None:
        """Register a dictionary of DataFrames as SQL tables in DuckDB.
        
        Table names will be sanitized (e.g. 'sales.csv' -> 'sales').
        """
        for raw_name, df in tables.items():
            sanitized_name = self._sanitize_table_name(raw_name)
            self._registered_tables[sanitized_name] = df
            self.conn.register(sanitized_name, df)

    def _sanitize_table_name(self, name: str) -> str:
        clean = name.lower().replace(".csv", "").replace(".xlsx", "").replace(".xlsm", "")
        clean = "".join(c if c.isalnum() else "_" for c in clean).strip("_")
        return clean or "table_data"

    def execute_query(self, query: str) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
        """Execute a SQL query against registered tables.
        
        Returns:
            (result_df, error_message)
        """
        if not self._registered_tables:
            return None, "No tables registered in SQL Engine."

        try:
            rel = self.conn.sql(query)
            if rel is not None:
                return rel.df(), None
            return pd.DataFrame(), None
        except Exception as e:
            return None, str(e)

    def list_tables(self) -> Dict[str, Tuple[int, int]]:
        """Return table metadata: name -> (row_count, col_count)."""
        info = {}
        for name, df in self._registered_tables.items():
            info[name] = (len(df), len(df.columns))
        return info

    def get_table_schema(self, table_name: str) -> Optional[Dict[str, str]]:
        """Get column names and data types for a table."""
        if table_name not in self._registered_tables:
            return None
        df = self._registered_tables[table_name]
        return {col: str(dtype) for col, dtype in df.dtypes.items()}


def generate_sql_for_query_plan(
    table_name: str,
    metric_col: Optional[str] = None,
    segment_col: Optional[str] = None,
    date_col: Optional[str] = None,
    aggregation: str = "SUM",
    limit: Optional[int] = 10,
    ascending: bool = False,
) -> str:
    """Generate ANSI standard SQL corresponding to a QueryPlan."""
    agg_op = aggregation.upper() if aggregation else "SUM"
    select_clause = []
    group_clause = []

    if segment_col:
        select_clause.append(f'"{segment_col}"')
        group_clause.append(f'"{segment_col}"')

    if date_col:
        select_clause.append(f'DATE_TRUNC(\'month\', "{date_col}") AS period')
        group_clause.append(f'DATE_TRUNC(\'month\', "{date_col}")')

    if metric_col:
        select_clause.append(f'{agg_op}("{metric_col}") AS "{metric_col.lower()}_{agg_op.lower()}"')
    else:
        select_clause.append("COUNT(*) AS row_count")

    sql = f"SELECT {', '.join(select_clause)}\nFROM \"{table_name}\""
    
    if group_clause:
        sql += f"\nGROUP BY {', '.join(group_clause)}"

    order_dir = "ASC" if ascending else "DESC"
    if metric_col:
        sql += f'\nORDER BY "{metric_col.lower()}_{agg_op.lower()}" {order_dir}'
    elif group_clause:
        sql += f"\nORDER BY 1 {order_dir}"

    if limit and limit > 0:
        sql += f"\nLIMIT {limit}"

    sql += ";"
    return sql
