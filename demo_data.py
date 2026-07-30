"""Deterministic demo datasets for single and multi-table analysis in ADA."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_demo_data(seed: int = 17, rows: int = 1_800) -> pd.DataFrame:
    """Default single-table E-commerce sales dataset."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    products = np.array(["Core", "Growth", "Enterprise", "Starter"])
    product_prices = {"Core": 129.0, "Growth": 229.0, "Enterprise": 799.0, "Starter": 49.0}
    regions = np.array(["West", "Northeast", "South", "Midwest"])
    channels = np.array(["Direct", "Partner", "Self-serve"])

    order_date = rng.choice(dates, size=rows)
    product = rng.choice(products, size=rows, p=[0.40, 0.27, 0.11, 0.22])
    region = rng.choice(regions, size=rows, p=[0.31, 0.27, 0.25, 0.17])
    channel = rng.choice(channels, size=rows, p=[0.45, 0.22, 0.33])
    units = rng.integers(1, 6, size=rows)

    day_index = (pd.Series(order_date) - pd.Timestamp("2024-01-01")).dt.days.to_numpy()
    growth = 1 + day_index / day_index.max() * 0.28
    seasonal = 1 + 0.13 * np.sin(2 * np.pi * day_index / 365)
    west_lift = np.where(region == "West", 1.10, 1.0)
    enterprise_lift = np.where(product == "Enterprise", 1.18, 1.0)
    base_price = np.array([product_prices[item] for item in product])
    revenue = base_price * units * growth * seasonal * west_lift * enterprise_lift
    revenue *= rng.normal(1.0, 0.09, size=rows)
    cost_ratio = np.where(product == "Enterprise", 0.58, 0.67)
    profit = revenue * (1 - cost_ratio) - rng.uniform(4, 18, size=rows)

    return pd.DataFrame(
        {
            "Order ID": [f"ORD-{100_000 + index}" for index in range(rows)],
            "Order Date": pd.to_datetime(order_date),
            "Product": product,
            "Region": region,
            "Channel": channel,
            "Units": units,
            "Revenue": revenue.round(2),
            "Profit": profit.round(2),
        }
    ).sort_values("Order Date", ignore_index=True)


def make_saas_metrics_data(seed: int = 42, rows: int = 1_200) -> pd.DataFrame:
    """SaaS subscription & churn dataset."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    plans = np.array(["Basic", "Pro", "Enterprise"])
    plan_prices = {"Basic": 29.0, "Pro": 99.0, "Enterprise": 499.0}
    statuses = np.array(["Active", "Churned", "Upgraded"])
    countries = np.array(["United States", "United Kingdom", "Germany", "Canada", "Australia"])

    sub_date = rng.choice(dates, size=rows)
    plan = rng.choice(plans, size=rows, p=[0.50, 0.35, 0.15])
    status = rng.choice(statuses, size=rows, p=[0.75, 0.15, 0.10])
    country = rng.choice(countries, size=rows, p=[0.40, 0.20, 0.15, 0.15, 0.10])
    mrr = np.array([plan_prices[p] for p in plan]) * rng.uniform(0.9, 1.2, size=rows)
    ltv = mrr * rng.integers(6, 36, size=rows)

    return pd.DataFrame(
        {
            "Subscription ID": [f"SUB-{50_000 + i}" for i in range(rows)],
            "Signup Date": pd.to_datetime(sub_date),
            "Plan": plan,
            "Status": status,
            "Country": country,
            "MRR": mrr.round(2),
            "LTV": ltv.round(2),
        }
    ).sort_values("Signup Date", ignore_index=True)


def make_hr_analytics_data(seed: int = 99, rows: int = 800) -> pd.DataFrame:
    """HR Employee performance & salary dataset."""
    rng = np.random.default_rng(seed)
    departments = np.array(["Engineering", "Sales", "Marketing", "HR", "Product"])
    roles = np.array(["Junior", "Mid", "Senior", "Lead"])
    gender = np.array(["Female", "Male", "Non-binary"])
    
    dept = rng.choice(departments, size=rows, p=[0.35, 0.30, 0.15, 0.08, 0.12])
    role = rng.choice(roles, size=rows, p=[0.30, 0.40, 0.20, 0.10])
    gen = rng.choice(gender, size=rows, p=[0.48, 0.48, 0.04])
    base_salary = np.where(role == "Junior", 65000, np.where(role == "Mid", 95000, np.where(role == "Senior", 140000, 185000)))
    dept_mult = np.where(dept == "Engineering", 1.2, np.where(dept == "Sales", 1.1, 1.0))
    salary = base_salary * dept_mult * rng.uniform(0.92, 1.15, size=rows)
    perf_rating = rng.integers(1, 6, size=rows)
    satisfaction = rng.uniform(2.5, 5.0, size=rows).round(1)

    return pd.DataFrame(
        {
            "Employee ID": [f"EMP-{1000 + i}" for i in range(rows)],
            "Department": dept,
            "Role": role,
            "Gender": gen,
            "Salary": salary.round(2),
            "Performance Rating": perf_rating,
            "Satisfaction Score": satisfaction,
        }
    )


def make_multi_table_ecommerce() -> dict[str, pd.DataFrame]:
    """Multi-table dataset: sales and customers for relational joins."""
    sales_df = make_demo_data()
    
    # Generate customer lookup table
    customer_ids = [f"CUST-{1000 + i}" for i in range(300)]
    tiers = np.random.choice(["Standard", "VIP", "Premium"], size=300, p=[0.6, 0.3, 0.1])
    segment = np.random.choice(["B2B", "B2C", "Enterprise"], size=300, p=[0.2, 0.7, 0.1])
    
    customers_df = pd.DataFrame({
        "Customer ID": customer_ids,
        "Tier": tiers,
        "Segment Type": segment,
    })
    
    # Assign Customer ID to sales
    sales_df["Customer ID"] = np.random.choice(customer_ids, size=len(sales_df))
    
    return {
        "sales": sales_df,
        "customers": customers_df,
    }
