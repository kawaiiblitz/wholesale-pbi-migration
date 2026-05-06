"""
Databricks Metrics View documentation reference - COMPLETE.
Fetched from official docs: https://docs.databricks.com/aws/en/metric-views/data-modeling/
Used as context for Claude when generating Metrics View YAMLs from DAX.
"""

METRICS_VIEW_DOCS = r"""
# Databricks Metrics View - Complete Official Reference

## 1. OVERVIEW & CORE COMPONENTS

Metric views create a semantic layer, transforming raw tables into standardized, business-friendly metrics.
They define what to measure, how to aggregate, and how to segment, ensuring a single source of truth.

| Component | Description | Example |
|-----------|-------------|---------|
| Source | Base table, view, or SQL query | samples.tpch.orders |
| Dimensions | Column attributes for segmenting metrics | Product category, Order month |
| Measures | Column aggregations (must use aggregate functions) | SUM(o_totalprice), COUNT(1) |
| Filters | Persistent WHERE conditions | status = 'completed' |

## 2. SOURCE DEFINITION

Table:
```yaml
source: samples.tpch.orders
```

SQL query:
```yaml
source: SELECT * FROM samples.tpch.orders o LEFT JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
```

Metric view as source:
```yaml
source: views.examples.source_metric_view
dimensions:
  - name: Order date
    expr: order_date_dim
measures:
  - name: Latest order month
    expr: MAX(order_date_dim_month)
  - name: Latest order year
    expr: DATE_TRUNC('year', MEASURE(max_order_date_measure))
```

## 3. DIMENSIONS

Columns used in SELECT, WHERE, GROUP BY. Each returns a scalar value.

```yaml
dimensions:
  - name: order_date
    expr: o_orderdate
    display_name: Order Date
    comment: Date when the order was placed
    format:
      type: date
      date_format: year_month_day
    synonyms:
      - order time
      - date of order
  - name: order_month
    expr: DATE_TRUNC('MONTH', o_orderdate)
  - name: order_status
    expr: |
      CASE
        WHEN o_orderstatus = 'O' THEN 'Open'
        WHEN o_orderstatus = 'P' THEN 'Processing'
        WHEN o_orderstatus = 'F' THEN 'Fulfilled'
      END
    display_name: Order Status
  - name: customer_segment
    expr: |
      CASE
        WHEN o_totalprice > 100000 THEN 'Enterprise'
        WHEN o_totalprice > 10000 THEN 'Mid-market'
        ELSE 'SMB'
      END
    display_name: Customer Segment
    synonyms:
      - segment
      - customer tier
```

## 4. MEASURES

Must use aggregate functions. Reference with MEASURE() in queries.

```yaml
measures:
  - name: order_count
    expr: COUNT(1)
    display_name: Order Count
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
  - name: total_revenue
    expr: SUM(o_totalprice)
    display_name: Total Revenue
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2
    synonyms:
      - revenue
      - total sales
  - name: unique_customers
    expr: COUNT(DISTINCT o_custkey)
  - name: avg_order_value
    expr: SUM(o_totalprice) / COUNT(DISTINCT o_orderkey)
  - name: high_priority_revenue
    expr: SUM(o_totalprice) FILTER (WHERE o_orderpriority = '1 - URGENT')
    comment: Revenue from urgent orders only
  - name: revenue_per_month
    expr: SUM(o_totalprice) / COUNT(DISTINCT DATE_TRUNC('MONTH', o_orderdate))
```

## 5. FILTERS

Persistent WHERE conditions applied to all queries:

```yaml
filter: o_orderdate > '2024-01-01'
filter: o_orderstatus IN ('F', 'P') AND o_orderdate >= '2024-01-01'
filter: o_comment LIKE '%express%' AND o_orderdate > '2024-01-01'
```

## 6. COMPOSABILITY (MEASURE() function)

Build complex metrics by reusing simpler measures. Use MEASURE() to reference.

```yaml
measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    comment: The gross total value of all orders.
    display_name: Total Revenue
  - name: order_count
    expr: COUNT(1)
    comment: The total number of orders.
    display_name: Order Count
  - name: avg_order_value
    expr: MEASURE(total_revenue) / MEASURE(order_count)
    comment: Total revenue divided by number of orders.
    display_name: Avg Order Value
  - name: fulfilled_orders
    expr: COUNT(1) FILTER (WHERE o_orderstatus = 'F')
    comment: Only includes orders marked as fulfilled.
  - name: fulfillment_rate
    expr: MEASURE(fulfilled_orders) / MEASURE(order_count)
    display_name: Order Fulfillment Rate
    format:
      type: percentage
```

Rules:
- Define atomic measures first, then composed ones
- Always use MEASURE() when referencing another measure
- expr should read like a mathematical formula
- If total_revenue changes, avg_order_value automatically inherits the change

## 7. JOINS

Star schema: source is fact table, LEFT OUTER JOIN to dimensions.
Join should follow many-to-one relationship.
IMPORTANT: Quote 'on' key to avoid YAML boolean parsing.

Star schema:
```yaml
source: catalog.schema.fact_table
joins:
  - name: dimension_table_1
    source: catalog.schema.dimension_table_1
    'on': source.dimension_table_1_fk = dimension_table_1.pk
  - name: dimension_table_2
    source: catalog.schema.dimension_table_2
    using:
      - dimension_table_2_key_a
      - dimension_table_2_key_b
dimensions:
  - name: dim1_key
    expr: dimension_table_1.pk
measures:
  - name: count_dim1
    expr: COUNT(dimension_table_1.pk)
```

Snowflake schema (Runtime 17.1+, nested joins):
```yaml
source: samples.tpch.orders
joins:
  - name: customer
    source: samples.tpch.customer
    'on': source.o_custkey = customer.c_custkey
    joins:
      - name: nation
        source: samples.tpch.nation
        'on': customer.c_nationkey = nation.n_nationkey
        joins:
          - name: region
            source: samples.tpch.region
            'on': nation.n_regionkey = region.r_regionkey
dimensions:
  - name: customer_name
    expr: customer.c_name
  - name: nation_name
    expr: customer.nation.n_name
```

Notes:
- Joined tables cannot include MAP type columns
- source namespace = metric view's source; join name = joined table columns
- For many-to-many, first matching row is selected

## 8. WINDOW MEASURES (Experimental)

Windowed, cumulative, or semiadditive aggregations.

Required fields:
- order: dimension for ordering
- range: current | cumulative | trailing <N> <unit> | leading <N> <unit> | all
- semiadditive: first | last

Trailing/moving window:
```yaml
measures:
  - name: t7d_customers
    expr: COUNT(DISTINCT o_custkey)
    window:
      - order: date
        range: trailing 7 day
        semiadditive: last
```

Period-over-period:
```yaml
measures:
  - name: previous_day_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: trailing 1 day
        semiadditive: last
  - name: current_day_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: current
        semiadditive: last
  - name: day_over_day_growth
    expr: (MEASURE(current_day_sales) - MEASURE(previous_day_sales)) / MEASURE(previous_day_sales) * 100
```

Cumulative (running total):
```yaml
measures:
  - name: running_total_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: cumulative
        semiadditive: last
```

Year-to-date:
```yaml
dimensions:
  - name: date
    expr: o_orderdate
  - name: year
    expr: DATE_TRUNC('year', o_orderdate)
measures:
  - name: ytd_sales
    expr: SUM(o_totalprice)
    window:
      - order: date
        range: cumulative
        semiadditive: last
      - order: year
        range: current
        semiadditive: last
```

Semiadditive (e.g., bank balance - don't sum over time):
```yaml
measures:
  - name: semiadditive_balance
    expr: SUM(balance)
    window:
      - order: date
        range: current
        semiadditive: last
```

## 9. LEVEL OF DETAIL (LOD) EXPRESSIONS

Control aggregation granularity independently of query dimensions.

Fixed LOD: use SQL window in source + expose as identity dimension:
```yaml
version: 1.1
source: |
  SELECT o_orderkey, o_orderpriority, o_totalprice, o_orderdate,
    SUM(o_totalprice) OVER (PARTITION BY o_orderpriority) AS priority_total_price
  FROM samples.tpch.orders
dimensions:
  - name: order_priority
    expr: o_orderpriority
  - name: priority_total_price
    expr: priority_total_price
measures:
  - name: total_sales
    expr: SUM(o_totalprice)
  - name: pct_of_priority_total
    expr: SUM(o_totalprice) / ANY_VALUE(priority_total_price)
```

Note: Wrap fixed LOD dimension in aggregate function (ANY_VALUE) when used in measure.
Fixed LOD is computed before query-time filters.

Coarser LOD: use window measures with range: all
```yaml
measures:
  - name: total_sales
    expr: SUM(o_totalprice)
  - name: all_priorities_sales
    expr: SUM(o_totalprice)
    window:
      - order: order_priority
        range: all
        semiadditive: last
  - name: pct_of_total_sales
    expr: SUM(o_totalprice) / MEASURE(all_priorities_sales)
    format:
      type: percentage
```

When to use:
- Fixed LOD: static partitioning, dataset-level aggregates, multi-level hierarchies
- Coarser LOD: dynamic groupings, filter-aware aggregations

## 10. SEMANTIC METADATA (version 1.1, Runtime 17.2+)

- display_name: human-readable label (max 255 chars)
- comment: description (YAML # comments are removed on save in 1.1)
- synonyms: up to 10 alternatives for LLM discovery (max 255 chars each)
- format: type-specific display formatting

Format types:
- number: decimal_places ({type: max|exact|all, places: 0-10}), hide_group_separator, abbreviation (none|compact|scientific)
- currency: currency_code (ISO-4217: USD, EUR, MXN, JPY), decimal_places, hide_group_separator, abbreviation
- percentage: decimal_places, hide_group_separator
- byte: decimal_places, hide_group_separator
- date: date_format (locale_short_month|locale_long_month|year_month_day|locale_number_month|year_week), leading_zeros
- date_time: date_format + time_format (no_time|locale_hour_minute|locale_hour_minute_second), leading_zeros

Complete example:
```yaml
version: 1.1
source: samples.tpch.orders
comment: Comprehensive sales metrics with enhanced semantic metadata
dimensions:
  - name: order_date
    expr: o_orderdate
    comment: Date when the order was placed
    display_name: Order Date
    format:
      type: date
      date_format: year_month_day
      leading_zeros: true
    synonyms:
      - order time
      - date of order
measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    comment: Total revenue from all orders
    display_name: Total Revenue
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2
      hide_group_separator: false
      abbreviation: compact
    synonyms:
      - revenue
      - total sales
      - sales amount
  - name: order_count
    expr: COUNT(1)
    comment: Total number of orders
    display_name: Order Count
    format:
      type: number
      decimal_places:
        type: all
      hide_group_separator: true
    synonyms:
      - count
      - number of orders
  - name: avg_order_value
    expr: SUM(o_totalprice) / COUNT(1)
    comment: Average revenue per order
    display_name: Average Order Value
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2
    synonyms:
      - aov
      - average revenue
```

## 11. YAML SYNTAX RULES

- Column names with spaces: backticks `First Name`
- Expression starting with backtick: wrap in double quotes: expr: "`First Name`"
- Expressions with colons: always wrap in double quotes
- Multi-line: use | block scalar, indent 2+ spaces
- Quote 'on' key in joins to avoid YAML boolean parsing
- version 1.1 requires Runtime 17.2+
- version 0.1 requires Runtime 16.4-17.1

## 12. CREATE SQL SYNTAX

```sql
CREATE OR REPLACE VIEW catalog.schema.view_name
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
comment: "Description"
source: catalog.schema.table
dimensions:
  - name: dim1
    expr: column1
measures:
  - name: measure1
    expr: COUNT(1)
$$
```

## 13. LIMITATIONS & UNSUPPORTED FEATURES

CRITICAL — these CANNOT be used in measure expr:
- SQL window functions: RANK(), ROW_NUMBER(), LAG(), LEAD(), NTILE(), DENSE_RANK() or any OVER() clause
- SELECT * is not supported in queries
- JOINs are not supported at query time (only in the YAML definition)
- Metric Views do not support Delta Sharing, Lineage, or Lakehouse Monitoring

ALTERNATIVES for unsupported patterns:
- For RANK/ROW_NUMBER: use Fixed LOD with RANK() OVER() in the SOURCE query (not in measures), expose as dimension
- For grand totals / percent of total: use Coarser LOD with window range: all
- For running totals: use window range: cumulative
- For period-over-period: use window range: trailing 1 month + range: current

## 13b. LEVEL OF DETAIL (LOD) EXPRESSIONS

### Fixed LOD — precompute in source query, expose as dimension
Use when you need RANK(), ROW_NUMBER(), or partitioned aggregates.
Put the window function in the SOURCE SQL, then reference it as a dimension.

```yaml
version: 1.1
source: |
  SELECT *,
    RANK() OVER (PARTITION BY category ORDER BY sales DESC) AS sales_rank,
    SUM(sales) OVER (PARTITION BY category) AS category_total
  FROM catalog.schema.table

dimensions:
  - name: category
    expr: category
  - name: sales_rank
    expr: sales_rank
  - name: category_total
    expr: category_total

measures:
  - name: total_sales
    expr: SUM(sales)
  - name: pct_of_category
    expr: SUM(sales) / ANY_VALUE(category_total)
```

Rules for Fixed LOD:
- The window function goes in the SOURCE query, NOT in measure expr
- Expose the result as a dimension (name = expr = column name)
- In measures, wrap fixed LOD dimensions in ANY_VALUE() since value is constant per group
- Filters must be in the source query (fixed LOD ignores query-time filters)

### Coarser LOD — dynamic subtotals with window range: all
Use for percent-of-total, subtotals, or ignoring specific dimensions.

```yaml
measures:
  - name: total_sales
    expr: SUM(sales)
  - name: grand_total
    expr: SUM(sales)
    window:
      - order: category
        range: all
        semiadditive: last
  - name: pct_of_total
    expr: SUM(sales) / MEASURE(grand_total)
    format:
      type: percentage
```

To exclude multiple dimensions from aggregation, add multiple window entries:
```yaml
  - name: subtotal
    expr: SUM(sales)
    window:
      - order: region
        range: all
        semiadditive: last
      - order: category
        range: all
        semiadditive: last
```

## 14. COMPOSABILITY RULES

- Dimensions can reference dimensions defined EARLIER in the YAML
- Measures can reference ALL dimensions
- Measures can reference measures defined EARLIER using MEASURE() — ORDER MATTERS
- Define atomic measures first (SUM, COUNT), then composed ones (DIVIDE, ratios)
- MEASURE() is required when referencing another measure — do NOT use the raw name

Example:
```yaml
measures:
  - name: revenue
    expr: SUM(sales_amount)
  - name: costs
    expr: SUM(item_cost)
  - name: profit
    expr: MEASURE(revenue) - MEASURE(costs)
```

## 15. FILTER SYNTAX IN MEASURES

filter(WHERE ...) must be specified for EACH aggregation function in a multi-agg expression:
```yaml
# WRONG — filter only applies to first agg
- name: bad
  expr: SUM(price) FILTER (WHERE status='O') / COUNT(DISTINCT custkey)

# RIGHT — filter on each agg
- name: good
  expr: SUM(price) FILTER (WHERE status='O') / COUNT(DISTINCT custkey) FILTER (WHERE status='O')
```

## 16. VALID FIELD REFERENCE

Dimension fields: name, expr, comment, display_name, format, synonyms
Measure fields: name, expr, comment, display_name, format, synonyms, window
Join fields: name, source, on, using, joins
Window fields: order, range, semiadditive (ALL three required)

NO other fields are valid. Do NOT add: type, is_dimension, table, or any custom field.

## 17. BEST PRACTICES

- Model atomic measures first (SUM, COUNT, AVG), then compose complex ones
- Standardize dimension values with CASE statements
- Define scope with persistent filters
- Use business-friendly naming
- Separate granular time dimensions (Order Date) and truncated (Order Month, Order Week)
- Use MEASURE() for consistency when referencing measures
- Combine composability with semantic metadata for formatting
- Combine composability with semantic metadata for formatting
"""
