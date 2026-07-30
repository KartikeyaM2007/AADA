"""Unit tests for DuckDB SQL execution engine."""

import unittest
import pandas as pd
from sql_engine import SQLEngine, generate_sql_for_query_plan


class TestSQLEngine(unittest.TestCase):

    def setUp(self):
        self.engine = SQLEngine()
        self.df_sales = pd.DataFrame({
            "Order ID": ["ORD-1", "ORD-2", "ORD-3"],
            "Revenue": [100.0, 250.0, 150.0],
            "Customer ID": ["C-1", "C-2", "C-1"],
        })
        self.df_customers = pd.DataFrame({
            "Customer ID": ["C-1", "C-2"],
            "Tier": ["VIP", "Standard"],
        })

    def test_table_registration_and_query(self):
        self.engine.register_tables({
            "sales.csv": self.df_sales,
            "customers.csv": self.df_customers,
        })
        tables = self.engine.list_tables()
        self.assertIn("sales", tables)
        self.assertIn("customers", tables)

        df, err = self.engine.execute_query("SELECT SUM(Revenue) AS total FROM sales;")
        self.assertIsNone(err)
        self.assertIsNotNone(df)
        self.assertEqual(float(df["total"].iloc[0]), 500.0)

    def test_relational_join_query(self):
        self.engine.register_tables({
            "sales": self.df_sales,
            "customers": self.df_customers,
        })
        query = """
        SELECT c.Tier, SUM(s.Revenue) as tier_revenue
        FROM sales s
        JOIN customers c ON s."Customer ID" = c."Customer ID"
        GROUP BY c.Tier;
        """
        df, err = self.engine.execute_query(query)
        self.assertIsNone(err)
        self.assertEqual(len(df), 2)

    def test_generate_sql_for_query_plan(self):
        sql = generate_sql_for_query_plan(
            table_name="sales",
            metric_col="Revenue",
            segment_col="Region",
            aggregation="sum",
            limit=5,
        )
        self.assertIn('SELECT "Region"', sql)
        self.assertIn('SUM("Revenue")', sql)
        self.assertIn('FROM "sales"', sql)
        self.assertIn('LIMIT 5', sql)


if __name__ == "__main__":
    unittest.main()
