import pandas as pd
from pathlib import Path


# ============================================================
# ERP CSV VALIDATION SCRIPT
# Read-only: DOES NOT MODIFY ANY CSV FILES
# ============================================================

DATA_DIR = Path(__file__).resolve().parent


# ------------------------------------------------------------
# Expected files
# ------------------------------------------------------------

EXPECTED_FILES = [
    "Products.csv",
    "Inventory.csv",
    "Sales.csv",
    "Purchases.csv",
    "Suppliers.csv",
    "Forecast.csv",
    "Seasonality.csv",
    "Pricing History.csv",
    "Competitor Prices.csv",
    "RCA Insights.csv",
    "Customers.csv",
    "Warehouses.csv",
]


# ------------------------------------------------------------
# Expected schemas
# ------------------------------------------------------------

EXPECTED_COLUMNS = {

    "Products.csv": [
        "Product ID",
        "Product Name",
        "Category",
        "Subcategory",
        "Brand",
        "Unit",
        "Pack Size",
        "MRP",
        "Selling Price",
        "Supplier Name",
        "Tax Rate",
        "Status",
    ],

    "Inventory.csv": [
        "Product ID",
        "Warehouse",
        "Opening Stock",
        "Current Stock",
        "Reorder Level",
        "Maximum Stock",
        "Last Updated",
        "Stock Status",
        "Batch",
        "Expiry Date",
        "Reserved Stock",
        "Remarks",
    ],

    "Sales.csv": [
        "Order ID",
        "Product ID",
        "Quantity Sold",
        "Selling Price",
        "Sale Date",
        "Customer Type",
        "Region",
        "Sales Channel",
        "Discount",
        "Remarks",
    ],

    "Purchases.csv": [
        "PO Number",
        "Product ID",
        "Supplier",
        "Ordered Quantity",
        "Unit Cost",
        "Order Date",
        "Expected Delivery",
        "Received Quantity",
        "Delivery Status",
        "Remarks",
    ],

    "Suppliers.csv": [
        "Supplier Name",
        "Country",
        "On-Time Delivery %",
        "Quality Rating",
        "Average Delay (Days)",
        "Contact Email",
        "Status",
        "Contract Start",
        "Payment Terms",
        "Remarks",
    ],

    "Forecast.csv": [
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
    ],

    "Seasonality.csv": [
        "Event Name",
        "Event Date",
        "Product ID",
        "Product Name",
        "Expected Impact",
        "Region",
        "Historical Lift",
        "Confidence",
        "Event Type",
        "Source",
        "Remarks",
    ],

    "Pricing History.csv": [
        "Product ID",
        "Product Name",
        "Old Price",
        "New Price",
        "Change Date",
        "Reason",
        "Approved By",
        "Expected Impact",
        "Status",
        "Review Date",
        "Remarks",
    ],

    "Competitor Prices.csv": [
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
    ],

    "RCA Insights.csv": [
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
    ],

    "Customers.csv": [
        "Customer ID",
        "Customer Type",
        "Region",
        "City",
        "Membership Tier",
        "Registration Date",
        "Preferred Channel",
        "Status",
    ],

    "Warehouses.csv": [
        "Warehouse ID",
        "Warehouse Name",
        "Warehouse Type",
        "City",
        "State",
        "Capacity",
        "Manager",
        "Status",
    ],
}


# ------------------------------------------------------------
# Counters
# ------------------------------------------------------------

errors = []
warnings = []


def error(message):
    errors.append(message)


def warning(message):
    warnings.append(message)


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# 1. CHECK FILES
# ============================================================

section("1. FILE CHECK")

dataframes = {}

for filename in EXPECTED_FILES:

    path = DATA_DIR / filename

    if not path.exists():
        error(f"MISSING FILE: {filename}")
        continue

    try:
        df = pd.read_csv(path)
        dataframes[filename] = df

        print(f"OK   {filename:<28} {len(df):>4} rows")

    except Exception as e:
        error(f"FAILED TO READ {filename}: {e}")


# ============================================================
# 2. CHECK COLUMN NAMES
# ============================================================

section("2. SCHEMA / COLUMN CHECK")

for filename, expected in EXPECTED_COLUMNS.items():

    if filename not in dataframes:
        continue

    df = dataframes[filename]

    actual = list(df.columns)

    missing = [col for col in expected if col not in actual]
    extra = [col for col in actual if col not in expected]

    if missing:
        error(
            f"{filename}: missing columns -> {missing}"
        )

    if extra:
        warning(
            f"{filename}: unexpected columns -> {extra}"
        )

    if not missing and not extra:
        print(f"OK   {filename}: schema matches")


# ============================================================
# 3. PRODUCTS MASTER CHECK
# ============================================================

section("3. PRODUCT MASTER CHECK")

products = dataframes.get("Products.csv")

if products is not None:

    product_ids = products["Product ID"].astype(str).str.strip()

    # Empty IDs
    empty_ids = products[
        product_ids.eq("") | products["Product ID"].isna()
    ]

    if len(empty_ids):
        error(
            f"Products.csv: {len(empty_ids)} products have missing Product ID"
        )

    # Duplicate IDs
    duplicates = product_ids[product_ids.duplicated()].unique()

    if len(duplicates):
        error(
            f"Products.csv: duplicate Product IDs -> {list(duplicates)}"
        )
    else:
        print("OK   Product IDs are unique")

    # Product names
    if products["Product Name"].isna().any():
        error("Products.csv: missing Product Name values")

    # Prices
    for column in ["MRP", "Selling Price"]:

        values = pd.to_numeric(
            products[column],
            errors="coerce"
        )

        if values.isna().any():
            error(
                f"Products.csv: non-numeric values in {column}"
            )

        if (values < 0).any():
            error(
                f"Products.csv: negative values in {column}"
            )

    # Selling price should normally not exceed MRP
    invalid_price = products[
        pd.to_numeric(products["Selling Price"], errors="coerce")
        > pd.to_numeric(products["MRP"], errors="coerce")
    ]

    if len(invalid_price):
        warning(
            f"Products.csv: {len(invalid_price)} products have Selling Price > MRP"
        )

    print(f"Products found: {len(products)}")


# ============================================================
# 4. PRODUCT ID RELATIONSHIP CHECK
# ============================================================

section("4. PRODUCT ID RELATIONSHIP CHECK")

if products is not None:

    master_ids = set(
        products["Product ID"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    files_using_product_id = [
        "Inventory.csv",
        "Sales.csv",
        "Purchases.csv",
        "Forecast.csv",
        "Seasonality.csv",
        "Pricing History.csv",
        "Competitor Prices.csv",
        "RCA Insights.csv",
    ]

    for filename in files_using_product_id:

        df = dataframes.get(filename)

        if df is None or "Product ID" not in df.columns:
            continue

        ids = set(
            df["Product ID"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        unknown = ids - master_ids

        if unknown:
            error(
                f"{filename}: unknown Product IDs -> {sorted(unknown)}"
            )
        else:
            print(f"OK   {filename}: all Product IDs exist in Products.csv")


# ============================================================
# 5. PRODUCT NAME CONSISTENCY
# ============================================================

section("5. PRODUCT NAME CONSISTENCY")

if products is not None:

    product_name_map = dict(
        zip(
            products["Product ID"].astype(str).str.strip(),
            products["Product Name"].astype(str).str.strip()
        )
    )

    files_to_check = [
        "Forecast.csv",
        "Seasonality.csv",
        "Pricing History.csv",
        "Competitor Prices.csv",
        "RCA Insights.csv",
    ]

    for filename in files_to_check:

        df = dataframes.get(filename)

        if df is None:
            continue

        for index, row in df.iterrows():

            pid = str(row["Product ID"]).strip()

            if pid not in product_name_map:
                continue

            expected_name = product_name_map[pid]
            actual_name = str(row["Product Name"]).strip()

            if actual_name != expected_name:

                error(
                    f"{filename}, row {index + 2}: "
                    f"{pid} should be '{expected_name}' "
                    f"but is '{actual_name}'"
                )

        print(f"Checked product names: {filename}")


# ============================================================
# 6. INVENTORY LOGIC
# ============================================================

section("6. INVENTORY LOGIC CHECK")

inventory = dataframes.get("Inventory.csv")

if inventory is not None:

    numeric_columns = [
        "Opening Stock",
        "Current Stock",
        "Reorder Level",
        "Maximum Stock",
        "Reserved Stock",
    ]

    for column in numeric_columns:

        inventory[column] = pd.to_numeric(
            inventory[column],
            errors="coerce"
        )

        if inventory[column].isna().any():

            error(
                f"Inventory.csv: invalid numeric values in {column}"
            )

    # Negative stock
    for column in numeric_columns:

        if (inventory[column] < 0).any():

            error(
                f"Inventory.csv: negative values found in {column}"
            )

    # Current stock > maximum
    invalid_max = inventory[
        inventory["Current Stock"]
        > inventory["Maximum Stock"]
    ]

    if len(invalid_max):

        warning(
            f"Inventory.csv: {len(invalid_max)} rows have "
            f"Current Stock > Maximum Stock"
        )

    # Reserved > current
    invalid_reserved = inventory[
        inventory["Reserved Stock"]
        > inventory["Current Stock"]
    ]

    if len(invalid_reserved):

        error(
            f"Inventory.csv: {len(invalid_reserved)} rows have "
            f"Reserved Stock > Current Stock"
        )

    # Calculate expected status
    def expected_status(row):

        current = row["Current Stock"]
        reorder = row["Reorder Level"]

        if current <= reorder * 0.5:
            return "Critical"

        if current <= reorder:
            return "Low Stock"

        return "Healthy"

    inventory["Calculated Status"] = inventory.apply(
        expected_status,
        axis=1
    )

    mismatches = inventory[
        inventory["Stock Status"].astype(str).str.strip()
        != inventory["Calculated Status"]
    ]

    if len(mismatches):

        warning(
            f"Inventory.csv: {len(mismatches)} stock-status values "
            f"do not match the calculated rule"
        )

        print("\nStatus mismatches:")

        for _, row in mismatches.iterrows():

            print(
                f"  {row['Product ID']}: "
                f"CSV={row['Stock Status']} | "
                f"Calculated={row['Calculated Status']}"
            )

    else:

        print("OK   Inventory stock statuses match business rule")


# ============================================================
# 7. INVENTORY DATE CHECK
# ============================================================

section("7. INVENTORY DATE CHECK")

if inventory is not None:

    for column in ["Last Updated", "Expiry Date"]:

        dates = pd.to_datetime(
            inventory[column],
            errors="coerce"
        )

        invalid = dates.isna()

        if invalid.any():

            error(
                f"Inventory.csv: invalid dates in {column}: "
                f"{invalid.sum()} rows"
            )
        else:
            print(f"OK   {column} dates valid")

    today = pd.Timestamp.today().normalize()

    expired = inventory[
        pd.to_datetime(
            inventory["Expiry Date"],
            errors="coerce"
        ) < today
    ]

    if len(expired):

        warning(
            f"Inventory.csv: {len(expired)} products have expired stock"
        )


# ============================================================
# 8. SALES CHECK
# ============================================================

section("8. SALES CHECK")

sales = dataframes.get("Sales.csv")

if sales is not None:

    numeric_columns = [
        "Quantity Sold",
        "Selling Price",
        "Discount",
    ]

    for column in numeric_columns:

        sales[column] = pd.to_numeric(
            sales[column],
            errors="coerce"
        )

        if sales[column].isna().any():

            error(
                f"Sales.csv: invalid numeric values in {column}"
            )

        if (sales[column] < 0).any():

            error(
                f"Sales.csv: negative values in {column}"
            )

    # Duplicate Order IDs
    duplicate_orders = sales[
        sales["Order ID"].astype(str).duplicated()
    ]

    if len(duplicate_orders):

        error(
            f"Sales.csv: duplicate Order IDs found"
        )
    else:

        print("OK   Order IDs are unique")

    # Dates
    dates = pd.to_datetime(
        sales["Sale Date"],
        errors="coerce"
    )

    if dates.isna().any():

        error("Sales.csv: invalid Sale Date values")
    else:

        print("OK   Sale dates valid")


# ============================================================
# 9. PURCHASE CHECK
# ============================================================

section("9. PURCHASE CHECK")

purchases = dataframes.get("Purchases.csv")

if purchases is not None:

    numeric_columns = [
        "Ordered Quantity",
        "Unit Cost",
        "Received Quantity",
    ]

    for column in numeric_columns:

        purchases[column] = pd.to_numeric(
            purchases[column],
            errors="coerce"
        )

        if purchases[column].isna().any():

            error(
                f"Purchases.csv: invalid numeric values in {column}"
            )

        if (purchases[column] < 0).any():

            error(
                f"Purchases.csv: negative values in {column}"
            )

    # Received should normally not exceed ordered
    invalid_received = purchases[
        purchases["Received Quantity"]
        > purchases["Ordered Quantity"]
    ]

    if len(invalid_received):

        warning(
            f"Purchases.csv: {len(invalid_received)} rows have "
            f"Received Quantity > Ordered Quantity"
        )

        for _, row in invalid_received.iterrows():

            print(
                f"  WARNING {row['PO Number']}: "
                f"ordered={row['Ordered Quantity']} "
                f"received={row['Received Quantity']}"
            )

    # Date validation
    for column in [
        "Order Date",
        "Expected Delivery",
    ]:

        dates = pd.to_datetime(
            purchases[column],
            errors="coerce"
        )

        if dates.isna().any():

            error(
                f"Purchases.csv: invalid dates in {column}"
            )

    print("Purchase validation completed")


# ============================================================
# 10. SUPPLIER CHECK
# ============================================================

section("10. SUPPLIER CHECK")

suppliers = dataframes.get("Suppliers.csv")

if suppliers is not None:

    supplier_names = (
        suppliers["Supplier Name"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    duplicates = supplier_names[
        supplier_names.duplicated()
    ].unique()

    if len(duplicates):

        error(
            f"Suppliers.csv: duplicate Supplier Names -> "
            f"{list(duplicates)}"
        )

    else:

        print("OK   Supplier names are unique")

    # Delivery %
    delivery = pd.to_numeric(
        suppliers["On-Time Delivery %"],
        errors="coerce"
    )

    invalid_delivery = (
        delivery.isna()
        | (delivery < 0)
        | (delivery > 100)
    )

    if invalid_delivery.any():

        error(
            "Suppliers.csv: invalid On-Time Delivery % values"
        )

    # Quality rating
    quality = pd.to_numeric(
        suppliers["Quality Rating"],
        errors="coerce"
    )

    invalid_quality = (
        quality.isna()
        | (quality < 0)
        | (quality > 5)
    )

    if invalid_quality.any():

        error(
            "Suppliers.csv: Quality Rating must be between 0 and 5"
        )


# ============================================================
# 11. PURCHASE → SUPPLIER CHECK
# ============================================================

section("11. PURCHASE → SUPPLIER CHECK")

if purchases is not None and suppliers is not None:

    known_suppliers = set(
        suppliers["Supplier Name"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    purchase_suppliers = set(
        purchases["Supplier"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    unknown_suppliers = purchase_suppliers - known_suppliers

    if unknown_suppliers:

        error(
            f"Purchases.csv: suppliers not found in Suppliers.csv -> "
            f"{sorted(unknown_suppliers)}"
        )
    else:

        print(
            "OK   All purchase suppliers exist in Suppliers.csv"
        )


# ============================================================
# 12. FORECAST CHECK
# ============================================================

section("12. FORECAST CHECK")

forecast = dataframes.get("Forecast.csv")

if forecast is not None:

    numeric_columns = [
        "Actual Sales",
        "Forecast Sales",
        "Forecast Accuracy",
    ]

    for column in numeric_columns:

        forecast[column] = pd.to_numeric(
            forecast[column],
            errors="coerce"
        )

        if forecast[column].isna().any():

            error(
                f"Forecast.csv: invalid numeric values in {column}"
            )

    invalid_accuracy = forecast[
        (forecast["Forecast Accuracy"] < 0)
        | (forecast["Forecast Accuracy"] > 100)
    ]

    if len(invalid_accuracy):

        error(
            f"Forecast.csv: Forecast Accuracy must be 0–100"
        )

    dates = pd.to_datetime(
        forecast["Date"],
        errors="coerce"
    )

    if dates.isna().any():

        error("Forecast.csv: invalid Date values")

    print("Forecast validation completed")


# ============================================================
# 13. COMPETITOR PRICE CHECK
# ============================================================

section("13. COMPETITOR PRICE CHECK")

competitors = dataframes.get("Competitor Prices.csv")

if competitors is not None:

    numeric_columns = [
        "Their Price",
        "Our Price",
        "Price Difference",
        "Rating",
    ]

    for column in numeric_columns:

        competitors[column] = pd.to_numeric(
            competitors[column],
            errors="coerce"
        )

        if competitors[column].isna().any():

            error(
                f"Competitor Prices.csv: invalid values in {column}"
            )

    # Check calculated price difference
    calculated_difference = (
        competitors["Our Price"]
        - competitors["Their Price"]
    )

    mismatch = (
        calculated_difference.round(2)
        != competitors["Price Difference"].round(2)
    )

    if mismatch.any():

        warning(
            f"Competitor Prices.csv: "
            f"{mismatch.sum()} Price Difference values "
            f"do not match Our Price - Their Price"
        )

        for index in competitors.index[mismatch]:

            row = competitors.loc[index]

            print(
                f"  {row['Product ID']}: "
                f"CSV={row['Price Difference']} | "
                f"Calculated={calculated_difference.loc[index]}"
            )

    else:

        print(
            "OK   Competitor Price Difference calculations match"
        )


# ============================================================
# 14. PRICING HISTORY CHECK
# ============================================================

section("14. PRICING HISTORY CHECK")

pricing = dataframes.get("Pricing History.csv")

if pricing is not None:

    for column in ["Old Price", "New Price"]:

        values = pd.to_numeric(
            pricing[column],
            errors="coerce"
        )

        if values.isna().any():

            error(
                f"Pricing History.csv: invalid values in {column}"
            )

        if (values < 0).any():

            error(
                f"Pricing History.csv: negative prices in {column}"
            )

    for column in ["Change Date", "Review Date"]:

        dates = pd.to_datetime(
            pricing[column],
            errors="coerce"
        )

        if dates.isna().any():

            error(
                f"Pricing History.csv: invalid dates in {column}"
            )

    print("Pricing history validation completed")


# ============================================================
# 15. SEASONALITY CHECK
# ============================================================

section("15. SEASONALITY CHECK")

seasonality = dataframes.get("Seasonality.csv")

if seasonality is not None:

    dates = pd.to_datetime(
        seasonality["Event Date"],
        errors="coerce"
    )

    if dates.isna().any():

        error(
            "Seasonality.csv: invalid Event Date values"
        )

    lift = pd.to_numeric(
        seasonality["Historical Lift"],
        errors="coerce"
    )

    if lift.isna().any():

        error(
            "Seasonality.csv: invalid Historical Lift values"
        )

    print("Seasonality validation completed")


# ============================================================
# 16. RCA CHECK
# ============================================================

section("16. RCA CHECK")

rca = dataframes.get("RCA Insights.csv")

if rca is not None:

    valid_priorities = {
        "Low",
        "Medium",
        "High",
        "Critical",
    }

    priorities = set(
        rca["Priority"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    invalid_priorities = priorities - valid_priorities

    if invalid_priorities:

        warning(
            f"RCA Insights.csv: unexpected priorities -> "
            f"{sorted(invalid_priorities)}"
        )
    else:

        print("OK   RCA priorities are consistent")

    dates = pd.to_datetime(
        rca["Detected Date"],
        errors="coerce"
    )

    if dates.isna().any():

        error(
            "RCA Insights.csv: invalid Detected Date values"
        )


# ============================================================
# 17. CUSTOMER CHECK
# ============================================================

section("17. CUSTOMER CHECK")

customers = dataframes.get("Customers.csv")

if customers is not None:

    customer_ids = (
        customers["Customer ID"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    duplicates = customer_ids[
        customer_ids.duplicated()
    ].unique()

    if len(duplicates):

        error(
            f"Customers.csv: duplicate Customer IDs -> "
            f"{list(duplicates)}"
        )
    else:

        print("OK   Customer IDs are unique")

    dates = pd.to_datetime(
        customers["Registration Date"],
        errors="coerce"
    )

    if dates.isna().any():

        error(
            "Customers.csv: invalid Registration Date values"
        )


# ============================================================
# 18. WAREHOUSE CHECK
# ============================================================

section("18. WAREHOUSE CHECK")

warehouses = dataframes.get("Warehouses.csv")

if warehouses is not None:

    warehouse_ids = (
        warehouses["Warehouse ID"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    duplicates = warehouse_ids[
        warehouse_ids.duplicated()
    ].unique()

    if len(duplicates):

        error(
            f"Warehouses.csv: duplicate Warehouse IDs -> "
            f"{list(duplicates)}"
        )
    else:

        print("OK   Warehouse IDs are unique")

    capacity = pd.to_numeric(
        warehouses["Capacity"],
        errors="coerce"
    )

    if capacity.isna().any() or (capacity <= 0).any():

        error(
            "Warehouses.csv: invalid Capacity values"
        )


# ============================================================
# 19. MISSING VALUE CHECK
# ============================================================

section("19. MISSING VALUE CHECK")

for filename, df in dataframes.items():

    missing_count = int(df.isna().sum().sum())

    if missing_count:

        warning(
            f"{filename}: {missing_count} missing values"
        )

        missing_columns = df.isna().sum()

        for column, count in missing_columns.items():

            if count:

                print(
                    f"  {column}: {count} missing"
                )

    else:

        print(f"OK   {filename}: no missing values")


# ============================================================
# 20. DUPLICATE ROW CHECK
# ============================================================

section("20. DUPLICATE ROW CHECK")

for filename, df in dataframes.items():

    duplicates = int(df.duplicated().sum())

    if duplicates:

        warning(
            f"{filename}: {duplicates} completely duplicate rows"
        )
    else:

        print(
            f"OK   {filename}: no duplicate rows"
        )


# ============================================================
# FINAL REPORT
# ============================================================

section("FINAL VALIDATION REPORT")

print(f"Files successfully loaded : {len(dataframes)}")
print(f"Errors                    : {len(errors)}")
print(f"Warnings                  : {len(warnings)}")


if errors:

    print("\n❌ ERRORS")
    print("-" * 70)

    for number, message in enumerate(errors, 1):

        print(f"{number}. {message}")


if warnings:

    print("\n⚠️ WARNINGS")
    print("-" * 70)

    for number, message in enumerate(warnings, 1):

        print(f"{number}. {message}")


if not errors and not warnings:

    print("\n🎉 DATASET PASSED ALL CHECKS")
    print("Your ERP CSV structure is ready to freeze.")


elif not errors:

    print("\n✅ NO BLOCKING ERRORS")
    print("Only warnings remain. Review them before freezing the dataset.")


else:

    print("\n❌ DATASET NEEDS CLEANUP")
    print("Fix the errors above before freezing the CSV structure.")


print("\nValidation complete.")