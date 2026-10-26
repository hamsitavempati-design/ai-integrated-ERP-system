import pandas as pd
from erp_data import load_erp_data


# ============================================================
# COMMON HELPERS
# ============================================================

def _data():
    """
    Load the latest ERP data every time a tool is called.

    This is intentional:
    if the CSV data changes while the application is running,
    the chatbot sees the latest data on the next request.
    """
    return load_erp_data()


def _json_records(df):
    """
    Convert a DataFrame into JSON text safely.

    Using pandas' JSON conversion avoids problems with
    numpy integers/floats and timestamps.
    """
    if df is None or df.empty:
        return "[]"

    return df.to_json(
        orient="records",
        date_format="iso"
    )


def _find_column(df, candidates):
    """
    Find a column while supporting small schema naming variations.

    Example:
        Forecast Sales
        ForecastSales

    Both can be recognized.
    """
    normalized = {
        str(col).strip().lower().replace(" ", "").replace("_", ""): col
        for col in df.columns
    }

    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "").replace("_", "")

        if key in normalized:
            return normalized[key]

    return None


def _find_product(products, value):
    """
    Find a product by Product ID, Product Name or partial name.
    """
    if not value:
        return products.iloc[0:0]

    value = str(value).strip().lower()

    product_id_col = _find_column(
        products,
        ["Product ID"]
    )

    product_name_col = _find_column(
        products,
        ["Product Name"]
    )

    result = products[
        products[product_id_col]
        .astype(str)
        .str.lower()
        .eq(value)
    ]

    if not result.empty:
        return result

    result = products[
        products[product_name_col]
        .astype(str)
        .str.lower()
        .str.contains(value, na=False)
    ]

    return result


# ============================================================
# 1. LOW INVENTORY
# ============================================================


def get_low_inventory():
    """
    Return products whose current stock is at or below
    the reorder level, including their product names.
    """

    data = _data()
    inventory = data["inventory"].copy()
    products = data["products"].copy()

    # Find columns safely despite naming variations.
    inventory_id = _find_column(inventory, ["Product ID"])
    products_id = _find_column(products, ["Product ID"])
    products_name = _find_column(products, ["Product Name"])

    if not all([inventory_id, products_id, products_name]):
        raise ValueError(
            "Required product ID or product name column is missing."
        )

    # Identify products at or below their reorder levels.
    current_stock = _find_column(inventory, ["Current Stock"])
    reorder_level = _find_column(inventory, ["Reorder Level"])

    if not current_stock or not reorder_level:
        raise ValueError(
            "Current Stock or Reorder Level column is missing."
        )

    low_stock = inventory[
        inventory[current_stock] <= inventory[reorder_level]
    ].copy()

    if low_stock.empty:
        return low_stock

    # Add product names by matching Product ID.
    product_lookup = products[[products_id, products_name]].copy()
    product_lookup = product_lookup.drop_duplicates(subset=[products_id])

    product_lookup = product_lookup.rename(
        columns={
            products_id: inventory_id,
            products_name: "Product Name",
        }
    )

    low_stock = low_stock.merge(
        product_lookup,
        on=inventory_id,
        how="left",
    )

    low_stock["Stock Ratio"] = (
        low_stock[current_stock] / low_stock[reorder_level]
    )

    low_stock["Severity"] = low_stock["Stock Ratio"].apply(
        lambda ratio: "Critical" if ratio <= 0.5 else "Low Stock"
    )

    low_stock = low_stock.sort_values(
        by="Stock Ratio",
        ascending=True,
    )

    # Return the existing fields plus Product Name.
    output_columns = [
        inventory_id,
        "Product Name",
        "Warehouse",
        current_stock,
        reorder_level,
        "Maximum Stock",
        "Severity",
        "Remarks",
    ]

    return low_stock[
        [column for column in output_columns if column in low_stock.columns]
    ]

# ============================================================
# 2. CRITICAL INVENTORY
# ============================================================

def get_critical_inventory():
    """
    Critical inventory means current stock is <= 50%
    of the reorder level.
    """

    data = _data()
    inventory = data["inventory"]

    critical = inventory[
        inventory["Current Stock"]
        <= inventory["Reorder Level"] * 0.5
    ].copy()

    if critical.empty:
        return critical

    critical["Severity"] = "Critical"

    critical = critical.sort_values(
        by="Current Stock",
        ascending=True
    )

    return critical[
        [
            "Product ID",
            "Warehouse",
            "Current Stock",
            "Reorder Level",
            "Maximum Stock",
            "Severity",
            "Remarks",
        ]
    ]


# ============================================================
# 3. RESTOCK RECOMMENDATIONS
# ============================================================


def get_restock_recommendations():
    """
    Find products requiring replenishment.

    Eligibility:
        Current Stock <= Reorder Level

    Demand-based policy:
        Safety Stock = ceil(Forecast Sales * 20%)
        Target Stock = Forecast Sales + Safety Stock
        Suggested Order Qty = max(Target Stock - Current Stock, 0)

    Products without forecasts require manual review.
    """

    import math

    data = _data()

    inventory = data["inventory"].copy()
    forecast = data["forecast"].copy()
    products = data["products"].copy()

    # Validate required inventory columns.
    inventory_columns = [
        "Product ID",
        "Warehouse",
        "Current Stock",
        "Reorder Level",
        "Maximum Stock",
        "Remarks",
    ]

    missing_inventory_columns = [
        column
        for column in inventory_columns
        if column not in inventory.columns
    ]

    if missing_inventory_columns:
        raise ValueError(
            "Inventory data is missing required columns: "
            + ", ".join(missing_inventory_columns)
        )

    # Find the forecast sales column.
    forecast_column = _find_column(
        forecast,
        ["Forecast Sales", "ForecastSales"]
    )

    if forecast_column is None:
        raise ValueError(
            "Forecast data is missing the Forecast Sales column."
        )

    if "Product ID" not in forecast.columns:
        raise ValueError(
            "Forecast data is missing the Product ID column."
        )

    # Select products that need replenishment.
    restock = inventory[
        inventory["Current Stock"]
        <= inventory["Reorder Level"]
    ].copy()

    if restock.empty:
        return restock

    # Keep one forecast record per product.
    forecast_data = forecast[
        ["Product ID", forecast_column]
    ].copy()

    forecast_data = forecast_data.rename(
        columns={
            forecast_column: "Forecast Sales"
        }
    )

    forecast_data["Product ID"] = (
        forecast_data["Product ID"].astype(str).str.strip()
    )

    restock["Product ID"] = (
        restock["Product ID"].astype(str).str.strip()
    )

    # Avoid multiplying inventory rows if forecasts are duplicated.
    duplicate_forecasts = forecast_data[
        forecast_data["Product ID"].duplicated(keep=False)
    ]

    if not duplicate_forecasts.empty:
        raise ValueError(
            "Forecast data contains multiple records for the same "
            "product. Resolve duplicate forecasts before calculating "
            "restock recommendations."
        )

    restock = restock.merge(
        forecast_data,
        on="Product ID",
        how="left",
        validate="many_to_one"
    )

    # Add product names from the product master.
    products.columns = products.columns.str.strip()

    product_id_col = _find_column(products, ["Product ID"])
    product_name_col = _find_column(products, ["Product Name"])

    if product_id_col is None or product_name_col is None:
        raise ValueError(
            "Products data is missing Product ID or Product Name."
        )

    product_lookup = products[
        [product_id_col, product_name_col]
    ].copy()

    product_lookup = product_lookup.rename(
        columns={
            product_id_col: "Product ID",
            product_name_col: "Product Name",
        }
    )

    product_lookup["Product ID"] = (
        product_lookup["Product ID"].astype(str).str.strip()
    )

    product_lookup = product_lookup.drop_duplicates(
        subset=["Product ID"]
    )

    restock = restock.merge(
        product_lookup,
        on="Product ID",
        how="left",
        validate="many_to_one"
    )

    # Mark products without forecast data for manual review.
    has_forecast = restock["Forecast Sales"].notna()

    restock["Safety Stock"] = restock["Forecast Sales"].apply(
        lambda value: (
            math.ceil(value * 0.20)
            if pd.notna(value) else None
        )
    )

    
    restock["Target Stock"] = restock.apply(
        lambda row: (
            max(
                row["Forecast Sales"] + row["Safety Stock"],
                row["Reorder Level"]
            )
            if pd.notna(row["Forecast Sales"]) else None
        ),
        axis=1
    )


    restock["Suggested Order Qty"] = restock.apply(
        lambda row: (
            max(
                math.ceil(
                    row["Target Stock"] - row["Current Stock"]
                ),
                0
            )
            if pd.notna(row["Target Stock"]) else None
        ),
        axis=1
    )

    restock["Recommendation Status"] = has_forecast.map(
        {
            True: "Recommended",
            False: "Manual review - forecast unavailable"
        }
    )

    # Preserve urgency classification.
    restock["Stock Ratio"] = (
        restock["Current Stock"]
        / restock["Reorder Level"]
    )

    restock["Urgency"] = restock["Stock Ratio"].apply(
        lambda ratio: (
            "Critical" if ratio <= 0.5 else "High"
        )
    )

    restock = restock.sort_values(
        by="Stock Ratio",
        ascending=True
    )

    return restock[
        [
            "Product ID",
            "Product Name",
            "Warehouse",
            "Current Stock",
            "Reorder Level",
            "Maximum Stock",
            "Forecast Sales",
            "Safety Stock",
            "Target Stock",
            "Suggested Order Qty",
            "Urgency",
            "Recommendation Status",
            "Remarks",
        ]
    ]


# ============================================================
# 4. TOP SELLING PRODUCTS
# ============================================================

def get_top_selling_products(top_n: int = 5):
    """Return products with the highest total quantity sold."""
    data = _data()
    sales = data["sales"].copy()
    products = data["products"].copy()
    top_n = max(1, min(int(top_n), 50))

    sales_product_id = _find_column(sales, ["Product ID", "ProductID"])
    quantity_col = _find_column(sales, ["Quantity Sold", "QuantitySold"])
    product_id_col = _find_column(products, ["Product ID", "ProductID"])
    product_name_col = _find_column(products, ["Product Name", "ProductName"])
    category_col = _find_column(products, ["Category", "Category Name", "Product Category"])

    if not sales_product_id or not quantity_col:
        raise ValueError("Sales data is missing Product ID or Quantity Sold.")
    if not product_id_col or not product_name_col:
        raise ValueError("Products data is missing Product ID or Product Name.")

    top_products = (
        sales.groupby(sales_product_id, as_index=False)[quantity_col]
        .sum()
        .sort_values(by=quantity_col, ascending=False)
        .head(top_n)
        .rename(columns={sales_product_id: "Product ID", quantity_col: "Quantity Sold"})
    )

    lookup_cols = [product_id_col, product_name_col]
    if category_col:
        lookup_cols.append(category_col)
    lookup = products[lookup_cols].copy()
    rename_map = {product_id_col: "Product ID", product_name_col: "Product Name"}
    if category_col:
        rename_map[category_col] = "Category"
    lookup = lookup.rename(columns=rename_map)
    lookup = lookup.drop_duplicates(subset=["Product ID"], keep="first")
    if "Category" not in lookup.columns:
        lookup["Category"] = "Not available"

    result = top_products.merge(lookup, on="Product ID", how="left")
    return result[["Product ID", "Product Name", "Category", "Quantity Sold"]]


def get_total_sales_revenue():
    """
    Calculate total revenue from Sales.csv.

    Revenue = Quantity Sold * Selling Price
    """

    data = _data()

    sales = data["sales"].copy()

    sales["Revenue"] = (
        sales["Quantity Sold"]
        * sales["Selling Price"]
    )

    return float(sales["Revenue"].sum())


# ============================================================
# 6. SALES BY PRODUCT
# ============================================================

def get_sales_by_product(product: str = ""):
    """Return sales information for a specific product."""
    data = _data()
    sales = data["sales"].copy()
    products = data["products"].copy()

    sales_product_id = _find_column(sales, ["Product ID", "ProductID"])
    quantity_col = _find_column(sales, ["Quantity Sold", "QuantitySold"])
    selling_price_col = _find_column(sales, ["Selling Price", "SellingPrice"])
    product_id_col = _find_column(products, ["Product ID", "ProductID"])
    product_name_col = _find_column(products, ["Product Name", "ProductName"])
    category_col = _find_column(products, ["Category", "Category Name", "Product Category"])

    if not sales_product_id or not quantity_col or not selling_price_col:
        raise ValueError("Sales data is missing required sales columns.")
    if not product_id_col or not product_name_col:
        raise ValueError("Products data is missing Product ID or Product Name.")

    matched = _find_product(products, product)
    if matched.empty:
        return pd.DataFrame(columns=["Product ID", "Product Name", "Category", "Quantity Sold", "Revenue"])

    # Product master data should have one authoritative row per Product ID.
    matched = matched.drop_duplicates(subset=[product_id_col], keep="first")
    product_ids = matched[product_id_col].astype(str).str.strip().tolist()

    filtered = sales[
        sales[sales_product_id].astype(str).str.strip().isin(product_ids)
    ].copy()

    if filtered.empty:
        rows = []
        for _, row in matched.iterrows():
            rows.append({
                "Product ID": row[product_id_col],
                "Product Name": row[product_name_col],
                "Category": row[category_col] if category_col else "Not available",
                "Quantity Sold": 0,
                "Revenue": 0,
            })
        return pd.DataFrame(rows)

    filtered["Revenue"] = filtered[quantity_col] * filtered[selling_price_col]
    result = (
        filtered.groupby(sales_product_id, as_index=False)
        .agg({quantity_col: "sum", "Revenue": "sum"})
        .rename(columns={sales_product_id: "Product ID", quantity_col: "Quantity Sold"})
    )

    lookup_cols = [product_id_col, product_name_col]
    if category_col:
        lookup_cols.append(category_col)
    lookup = products[lookup_cols].drop_duplicates(subset=[product_id_col], keep="first").copy()
    rename_map = {product_id_col: "Product ID", product_name_col: "Product Name"}
    if category_col:
        rename_map[category_col] = "Category"
    lookup = lookup.rename(columns=rename_map)
    if "Category" not in lookup.columns:
        lookup["Category"] = "Not available"

    result = result.merge(lookup, on="Product ID", how="left")
    return result[["Product ID", "Product Name", "Category", "Quantity Sold", "Revenue"]]


def get_sales_by_category():
    """Aggregate quantity and revenue by category."""
    data = _data()
    sales = data["sales"].copy()
    products = data["products"].copy()

    sales_product_id = _find_column(sales, ["Product ID", "ProductID"])
    quantity_col = _find_column(sales, ["Quantity Sold", "QuantitySold"])
    selling_price_col = _find_column(sales, ["Selling Price", "SellingPrice"])
    product_id_col = _find_column(products, ["Product ID", "ProductID"])
    category_col = _find_column(products, ["Category", "Category Name", "Product Category"])

    if not sales_product_id or not quantity_col or not selling_price_col:
        raise ValueError("Sales data is missing required sales columns.")
    if not product_id_col or not category_col:
        raise ValueError("Products data is missing Product ID or Category information.")

    lookup = products[[product_id_col, category_col]].copy()
    lookup = lookup.rename(columns={product_id_col: "Product ID", category_col: "Category"})
    lookup = lookup.drop_duplicates(subset=["Product ID"], keep="first")

    sales_normalized = sales.rename(columns={
        sales_product_id: "Product ID",
        quantity_col: "Quantity Sold",
        selling_price_col: "Selling Price",
    })
    merged = sales_normalized.merge(lookup, on="Product ID", how="left")
    merged["Revenue"] = merged["Quantity Sold"] * merged["Selling Price"]

    return (
        merged.groupby("Category", as_index=False)
        .agg({"Quantity Sold": "sum", "Revenue": "sum"})
        .sort_values(by="Revenue", ascending=False)
    )


def get_product_sales_performance(product: str = ""):
    """Combine sales, inventory and forecast information for a specific product."""
    data = _data()
    products = data["products"].copy()
    sales = data["sales"].copy()
    inventory = data["inventory"].copy()
    forecast = data["forecast"].copy()

    matched = _find_product(products, product)
    if matched.empty:
        return pd.DataFrame()
    matched = matched.drop_duplicates(subset=[_find_column(products, ["Product ID", "ProductID"])], keep="first")
    product_info = matched.iloc[0]

    product_id_col = _find_column(products, ["Product ID", "ProductID"])
    product_name_col = _find_column(products, ["Product Name", "ProductName"])
    category_col = _find_column(products, ["Category", "Category Name", "Product Category"])
    brand_col = _find_column(products, ["Brand"])
    selling_price_col = _find_column(products, ["Selling Price", "SellingPrice"])
    sales_product_id = _find_column(sales, ["Product ID", "ProductID"])
    quantity_col = _find_column(sales, ["Quantity Sold", "QuantitySold"])
    sales_price_col = _find_column(sales, ["Selling Price", "SellingPrice"])

    if not product_id_col or not product_name_col:
        raise ValueError("Products data is missing Product ID or Product Name.")
    if not sales_product_id or not quantity_col or not sales_price_col:
        raise ValueError("Sales data is missing required sales columns.")

    product_id = product_info[product_id_col]
    product_sales = sales[
        sales[sales_product_id].astype(str).str.strip() == str(product_id).strip()
    ].copy()
    quantity_sold = product_sales[quantity_col].sum() if not product_sales.empty else 0
    revenue = (product_sales[quantity_col] * product_sales[sales_price_col]).sum() if not product_sales.empty else 0

    result = {
        "Product ID": product_id,
        "Product Name": product_info[product_name_col],
        "Category": product_info[category_col] if category_col else "Not available",
        "Brand": product_info[brand_col] if brand_col else "Not available",
        "Selling Price": product_info[selling_price_col] if selling_price_col else None,
        "Quantity Sold": quantity_sold,
        "Revenue": revenue,
    }

    inventory_product_id = _find_column(inventory, ["Product ID", "ProductID"])
    if inventory_product_id:
        inventory_match = inventory[
            inventory[inventory_product_id].astype(str).str.strip() == str(product_id).strip()
        ]
        if not inventory_match.empty:
            inv = inventory_match.iloc[0]
            for key in ["Current Stock", "Reorder Level", "Maximum Stock", "Stock Status", "Remarks"]:
                if key in inv.index:
                    result["Inventory Remarks" if key == "Remarks" else key] = inv[key]

    forecast_product_id = _find_column(forecast, ["Product ID", "ProductID"])
    forecast_column = _find_column(forecast, ["Forecast Sales", "ForecastSales"])
    if forecast_product_id and forecast_column:
        forecast_match = forecast[
            forecast[forecast_product_id].astype(str).str.strip() == str(product_id).strip()
        ]
        if not forecast_match.empty:
            fc = forecast_match.iloc[-1]
            result["Forecast Sales"] = fc[forecast_column]
            for key in ["Forecast Accuracy", "Trend", "Confidence", "Remarks"]:
                if key in fc.index:
                    result["Forecast Remarks" if key == "Remarks" else key] = fc[key]

    return pd.DataFrame([result])


def get_supplier_performance():
    """
    Return supplier delivery and quality performance.

    Supplier risk:
        On-Time Delivery < 90
        OR
        Average Delay > 3 days
    """

    data = _data()

    suppliers = data["suppliers"].copy()

    suppliers["Risk Status"] = suppliers.apply(
        lambda row:
        "At Risk"
        if (
            row["On-Time Delivery %"] < 90
            or row["Average Delay (Days)"] > 3
        )
        else "Healthy",
        axis=1
    )

    suppliers = suppliers.sort_values(
        by="On-Time Delivery %",
        ascending=True
    )

    return suppliers[
        [
            "Supplier Name",
            "Country",
            "On-Time Delivery %",
            "Quality Rating",
            "Average Delay (Days)",
            "Status",
            "Risk Status",
            "Remarks",
        ]
    ]


# ============================================================
# 10. PURCHASE SUMMARY
# ============================================================

def get_purchase_summary():
    """
    Summarize purchase orders by status.
    """

    data = _data()

    purchases = data["purchases"].copy()

    purchases["Pending Quantity"] = (
        purchases["Ordered Quantity"]
        - purchases["Received Quantity"]
    )

    purchases["Purchase Value"] = (
        purchases["Ordered Quantity"]
        * purchases["Unit Cost"]
    )

    return purchases[
        [
            "PO Number",
            "Product ID",
            "Supplier",
            "Ordered Quantity",
            "Received Quantity",
            "Pending Quantity",
            "Unit Cost",
            "Purchase Value",
            "Order Date",
            "Expected Delivery",
            "Delivery Status",
            "Remarks",
        ]
    ]


# ============================================================
# 11. PENDING PURCHASES
# ============================================================


def get_pending_purchases():
    """
    Return purchase orders that are not fully received,
    including whether each order is overdue.
    """

    data = _data()

    purchases = data["purchases"].copy()

    pending = purchases[
        purchases["Delivery Status"] != "Received"
    ].copy()

    pending["Pending Quantity"] = (
        pending["Ordered Quantity"]
        - pending["Received Quantity"]
    )

    pending["Purchase Value"] = (
        pending["Ordered Quantity"]
        * pending["Unit Cost"]
    )

    # Determine whether an order is overdue.
    today = pd.Timestamp.today().normalize()

    expected_delivery = pd.to_datetime(
        pending["Expected Delivery"],
        errors="coerce"
    )

    pending["Overdue"] = (
        (expected_delivery < today)
        & (pending["Pending Quantity"] > 0)
    ).map({True: "Yes", False: "No"})

    return pending[
        [
            "PO Number",
            "Product ID",
            "Supplier",
            "Ordered Quantity",
            "Received Quantity",
            "Pending Quantity",
            "Expected Delivery",
            "Delivery Status",
            "Overdue",
            "Remarks",
        ]
    ]

# ============================================================
# 12. FORECAST / DEMAND
# ============================================================


def get_demand_forecast(product: str = ""):
    """
    Return demand forecast information.

    If product is empty, return all forecast records.
    If a product has no forecast, return an empty result.
    """

    data = _data()
    forecast = data["forecast"].copy()
    products = data["products"].copy()

    # Find the forecast sales column safely.
    forecast_column = _find_column(
        forecast,
        ["Forecast Sales", "ForecastSales"]
    )

    if forecast_column is None:
        raise ValueError(
            "Forecast.csv is missing the Forecast Sales column."
        )

    forecast = forecast.rename(
        columns={forecast_column: "Forecast Sales"}
    )

    # Filter by product if requested.
    if product and product.strip():
        matched = _find_product(products, product.strip())

        if matched.empty:
            return forecast.iloc[0:0].copy()

        product_ids = (
            matched["Product ID"]
            .astype(str)
            .str.strip()
            .tolist()
        )

        forecast = forecast[
            forecast["Product ID"]
            .astype(str)
            .str.strip()
            .isin(product_ids)
        ]

    required_columns = [
        "Date",
        "Product ID",
        "Product Name",
        "Actual Sales",
        "Forecast Sales",
        "Forecast Accuracy",
        "Season",
        "Trend",
        "Model Used",
        "Confidence",
        "Remarks",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in forecast.columns
    ]

    if missing_columns:
        raise ValueError(
            "Forecast.csv is missing required columns: "
            + ", ".join(missing_columns)
        )

    return forecast[required_columns].copy()

# ============================================================
# 13. SEASONAL OPPORTUNITIES
# ============================================================

def get_seasonal_opportunities():
    """Return products affected by seasonal/festival demand."""
    data = _data()
    seasonality = data["seasonality"].copy()

    required = [
        "Event Name", "Event Date", "Product ID", "Product Name",
        "Expected Impact", "Region", "Historical Lift", "Confidence",
        "Source", "Remarks"
    ]
    resolved = {}
    for name in required:
        col = _find_column(seasonality, [name])
        if col:
            resolved[name] = col
    missing = [name for name in required if name not in resolved]
    if missing:
        raise ValueError(f"Seasonality data is missing columns: {missing}")

    result = seasonality[[resolved[name] for name in required]].copy()
    result.columns = required
    event_type_col = _find_column(seasonality, ["EventType", "Event Type", "Event_Type"])
    result["EventType"] = seasonality[event_type_col].values if event_type_col else "Not specified"

    return result[
        ["Event Name", "Event Date", "Product ID", "Product Name", "Expected Impact",
         "Region", "Historical Lift", "Confidence", "EventType", "Source", "Remarks"]
    ].sort_values(by="Historical Lift", ascending=False)


def get_competitor_price_analysis(
    product: str = ""
):
    """
    Compare our price against competitors.

    Positive/negative price difference is taken directly
    from the ERP competitor dataset.
    """

    data = _data()

    competitor = data["competitor_prices"].copy()

    if product:
        products = data["products"]

        matched = _find_product(
            products,
            product
        )

        if matched.empty:
            return competitor.iloc[0:0]

        product_ids = matched["Product ID"].tolist()

        competitor = competitor[
            competitor["Product ID"].isin(product_ids)
        ]

    return competitor[
        [
            "Competitor Name",
            "Product ID",
            "Product Name",
            "Their Price",
            "Our Price",
            "Price Difference",
            "Platform",
            "Region",
            "Availability",
            "Rating",
            "Remarks",
        ]
    ]


# ============================================================
# 15. PRICING HISTORY
# ============================================================

def get_pricing_history(product: str = ""):
    """
    Return pricing history records.

    If product is provided, it can be:
        P001
        Amul Taaza Milk
        milk
    """

    data = _data()
    pricing = data["pricing_history"].copy()

    product_id_col = _find_column(
        pricing,
        ["Product ID"]
    )

    product_name_col = _find_column(
        pricing,
        ["Product Name"]
    )

    change_date_col = _find_column(
        pricing,
        ["ChangeDate", "Change Date", "Change_Date"]
    )

    required_columns = {
        "Product ID": product_id_col,
        "Product Name": product_name_col,
        "ChangeDate": change_date_col,
    }

    missing = [
        name
        for name, column in required_columns.items()
        if column is None
    ]

    if missing:
        raise ValueError(
            f"Pricing History data is missing required columns: {missing}"
        )

    # Normalize the important column names.
    pricing = pricing.rename(
        columns={
            product_id_col: "Product ID",
            product_name_col: "Product Name",
            change_date_col: "ChangeDate",
        }
    )

    if product:
        value = str(product).strip().lower()

        matched = pricing[
            pricing["Product ID"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq(value)
        ]

        if matched.empty:
            matched = pricing[
                pricing["Product Name"]
                .astype(str)
                .str.strip()
                .str.lower()
                .str.contains(value, na=False)
            ]

        pricing = matched

    output_columns = [
        "Product ID",
        "Product Name",
        "Old Price",
        "New Price",
        "ChangeDate",
        "Reason",
        "Approved By",
        "Expected Impact",
        "Status",
        "Review Date",
        "Remarks",
    ]

    # Return only columns that actually exist.
    available_columns = [
        column
        for column in output_columns
        if column in pricing.columns
    ]

    return pricing[available_columns]

# ============================================================
# 16. RCA / BUSINESS ISSUES
# ============================================================

def get_business_issues():
    """
    Return current root-cause-analysis insights.
    """

    data = _data()

    rca = data["rca_insights"].copy()

    return rca[
        [
            "Issue Type",
            "Product ID",
            "Product Name",
            "Detected Date",
            "Main Reason",
            "Supporting Reason",
            "Business Impact",
            "Suggested Action",
            "Priority",
            "Status",
            "Remarks",
        ]
    ]


# ============================================================
# 17. CUSTOMER SUMMARY
# ============================================================

def get_customer_summary():
    """
    Summarize customer base.
    """

    data = _data()

    customers = data["customers"].copy()

    result = (
        customers
        .groupby(
            [
                "Customer Type",
                "Membership Tier",
                "Preferred Channel",
                "Status",
            ],
            as_index=False
        )
        .size()
        .rename(columns={"size": "Customer Count"})
        .sort_values(
            by="Customer Count",
            ascending=False
        )
    )

    return result


# ============================================================
# 18. WAREHOUSE OVERVIEW
# ============================================================

def get_warehouse_overview():
    """
    Return warehouse information.
    """

    data = _data()

    warehouses = data["warehouses"].copy()

    inventory = data["inventory"]

    inventory_summary = (
        inventory
        .groupby("Warehouse", as_index=False)
        .agg(
            {
                "Product ID": "count",
                "Current Stock": "sum",
            }
        )
        .rename(
            columns={
                "Product ID": "Inventory Product Count",
                "Current Stock": "Total Current Stock",
            }
        )
    )

    result = warehouses.merge(
        inventory_summary,
        left_on="Warehouse Name",
        right_on="Warehouse",
        how="left"
    )

    if "Warehouse" in result.columns:
        result = result.drop(
            columns=["Warehouse"]
        )

    return result


# ============================================================
# 19. BUSINESS OVERVIEW
# ============================================================

def get_business_overview():
    """Return a deterministic high-level ERP snapshot."""
    data = _data()
    sales = data["sales"]
    products = data["products"]
    inventory = data["inventory"]
    purchases = data["purchases"]
    suppliers = data["suppliers"]

    total_quantity = float(sales["Quantity Sold"].sum())
    total_revenue = float((sales["Quantity Sold"] * sales["Selling Price"]).sum())
    average_selling_price = total_revenue / total_quantity if total_quantity > 0 else 0.0
    product_count = len(products)
    inventory_count = len(inventory)
    low_stock_count = int((inventory["Current Stock"] <= inventory["Reorder Level"]).sum())
    critical_count = int((inventory["Current Stock"] <= inventory["Reorder Level"] * 0.5).sum())
    pending_purchase_count = int((purchases["Delivery Status"] != "Received").sum())
    supplier_risk_count = int(((suppliers["On-Time Delivery %"] < 90) | (suppliers["Average Delay (Days)"] > 3)).sum())

    return pd.DataFrame([{
        "Currency": "INR",
        "Total Sales Quantity": total_quantity,
        "Total Sales Revenue": total_revenue,
        "Average Selling Price": average_selling_price,
        "Product Count": product_count,
        "Inventory Records": inventory_count,
        "Low Stock Products": low_stock_count,
        "Critical Stock Products": critical_count,
        "Pending Purchase Orders": pending_purchase_count,
        "Supplier Risk Count": supplier_risk_count,
    }])

def get_products_by_category(category: str) -> pd.DataFrame:
    """
    Return products in a category with their current inventory details.
    """
    data = load_erp_data()

    products = data["products"].copy()
    inventory = data["inventory"].copy()

    # Normalize column names to handle spaces and underscores.
    products.columns = products.columns.str.strip()
    inventory.columns = inventory.columns.str.strip()

    # Find the category column.
    category_col = next(
        (col for col in products.columns if col.lower().replace("_", " ") == "category"),
        None
    )

    if category_col is None:
        raise ValueError("Category column not found in Products.csv")

    # Identify product ID columns in both CSV files.
    product_id_col = next(
        (col for col in products.columns if col.lower().replace("_", " ") == "product id"),
        None
    )
    inventory_id_col = next(
        (col for col in inventory.columns if col.lower().replace("_", " ") == "product id"),
        None
    )

    if product_id_col is None or inventory_id_col is None:
        raise ValueError("Product ID column not found in one or both CSV files")

    # Match the requested category, ignoring capitalization and extra spaces.
    matching_products = products[
        products[category_col].astype(str).str.strip().str.casefold()
        == category.strip().casefold()
    ].copy()

    # Find the inventory stock column.
    stock_col = next(
        (col for col in inventory.columns if col.lower().replace("_", " ") == "current stock"),
        None
    )

    if stock_col is None:
        raise ValueError("Current Stock column not found in Inventory.csv")

    # Keep only the inventory columns needed for this answer.
    inventory_columns = [inventory_id_col, stock_col]
    reorder_col = next(
        (col for col in inventory.columns if col.lower().replace("_", " ") == "reorder level"),
        None
    )
    if reorder_col:
        inventory_columns.append(reorder_col)

    result = matching_products.merge(
        inventory[inventory_columns],
        left_on=product_id_col,
        right_on=inventory_id_col,
        how="left",
        validate="one_to_one"
    )

    # Return the most useful fields available.
    preferred_columns = [
        product_id_col, "Product Name", category_col,
        stock_col, reorder_col
    ]
    output_columns = [
        col for col in preferred_columns
        if col and col in result.columns
    ]

    return result[output_columns].rename(
        columns={product_id_col: "Product ID", stock_col: "Current Stock"}
    )


def get_product_inventory_by_id(product_id: str) -> pd.DataFrame:
    """
    Return product details and inventory for a specific Product ID.
    """
    data = load_erp_data()

    products = data["products"].copy()
    inventory = data["inventory"].copy()

    products.columns = products.columns.str.strip()
    inventory.columns = inventory.columns.str.strip()

    product_id_col = _find_column(products, ["Product ID"])
    product_name_col = _find_column(products, ["Product Name"])
    category_col = _find_column(products, ["Category"])
    inventory_id_col = _find_column(inventory, ["Product ID"])

    if not all([product_id_col, product_name_col, inventory_id_col]):
        raise ValueError("Required product or inventory columns are missing.")

    product_id = str(product_id).strip().upper()

    product = products[
        products[product_id_col].astype(str).str.strip().str.upper()
        == product_id
    ].copy()

    stock = inventory[
        inventory[inventory_id_col].astype(str).str.strip().str.upper()
        == product_id
    ].copy()

    if product.empty or stock.empty:
        return pd.DataFrame()

    # Standardize the inventory key before merging.
    product = product.rename(
        columns={
            product_id_col: "Product ID",
            product_name_col: "Product Name",
        }
    )
    stock = stock.rename(columns={inventory_id_col: "Product ID"})

    # Keep useful product details and inventory fields.
    product_columns = ["Product ID", "Product Name"]
    if category_col:
        product_columns.append(category_col)

    result = stock.merge(
        product[product_columns].drop_duplicates(subset=["Product ID"]),
        on="Product ID",
        how="left",
    )

    return result


# ============================================================
# LOCAL TESTING
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 90)
    print("ERP TOOLS TEST")
    print("=" * 90)

    result = get_low_inventory()
    print("\nLOW INVENTORY")
    print(result.to_string(index=False))

    result = get_critical_inventory()
    print("\nCRITICAL INVENTORY")
    if result.empty:
        print("No critically low products.")
    else:
        print(result.to_string(index=False))

    result = get_restock_recommendations()
    print("\nRESTOCK RECOMMENDATIONS")
    print(result.to_string(index=False))

    result = get_top_selling_products(5)
    print("\nTOP SELLING PRODUCTS")
    print(result.to_string(index=False))

    result = get_total_sales_revenue()
    print("\nTOTAL SALES REVENUE")
    print(f"₹{result:,.2f}")

    result = get_sales_by_product("Amul")
    print("\nSALES BY PRODUCT")
    print(result.to_string(index=False))

    result = get_sales_by_category()
    print("\nSALES BY CATEGORY")
    print(result.to_string(index=False))

    result = get_product_sales_performance("P001")
    print("\nPRODUCT PERFORMANCE")
    print(result.to_string(index=False))

    result = get_supplier_performance()
    print("\nSUPPLIER PERFORMANCE")
    print(result.to_string(index=False))

    result = get_purchase_summary()
    print("\nPURCHASE SUMMARY")
    print(result.to_string(index=False))

    result = get_pending_purchases()
    print("\nPENDING PURCHASES")
    print(result.to_string(index=False))

    result = get_demand_forecast()
    print("\nDEMAND FORECAST")
    print(result.to_string(index=False))

    result = get_seasonal_opportunities()
    print("\nSEASONAL OPPORTUNITIES")
    print(result.to_string(index=False))

    result = get_competitor_price_analysis()
    print("\nCOMPETITOR PRICE ANALYSIS")
    print(result.to_string(index=False))

    result = get_pricing_history()
    print("\nPRICING HISTORY")
    print(result.to_string(index=False))

    result = get_business_issues()
    print("\nBUSINESS ISSUES")
    print(result.to_string(index=False))

    result = get_customer_summary()
    print("\nCUSTOMER SUMMARY")
    print(result.to_string(index=False))

    result = get_warehouse_overview()
    print("\nWAREHOUSE OVERVIEW")
    print(result.to_string(index=False))

    result = get_business_overview()
    print("\nBUSINESS OVERVIEW")
    print(result.to_string(index=False))

    print("\n" + "=" * 90)
    print("ALL ERP TOOLS TESTED")
    print("=" * 90)
