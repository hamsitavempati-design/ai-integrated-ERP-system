
from pathlib import Path
import pandas as pd


# ============================================================
# ERP UPLOAD VALIDATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent / "data"

EXPECTED_COLUMNS = {
    "Products.csv": [
        "Product ID", "Product Name", "Category", "Subcategory",
        "Brand", "Unit", "Pack Size", "MRP", "Selling Price",
        "Supplier Name", "TaxRate", "Status",
    ],
    "Inventory.csv": [
        "Product ID", "Warehouse", "Opening Stock", "Current Stock",
        "Reorder Level", "Maximum Stock", "Last Updated",
        "Stock Status", "Batch", "Expiry Date", "Reserved Stock",
        "Remarks",
    ],
    "Sales.csv": [
        "Order ID", "Product ID", "Quantity Sold", "Selling Price",
        "Sale Date", "Customer Type", "Region", "Sales Channel",
        "Discount", "Remarks",
    ],
    "Purchases.csv": [
        "PO Number", "Product ID", "Supplier", "Ordered Quantity",
        "Unit Cost", "Order Date", "Expected Delivery",
        "Received Quantity", "Delivery Status", "Remarks",
    ],
    "Suppliers.csv": [
        "Supplier Name", "Country", "On-Time Delivery %",
        "Quality Rating", "Average Delay (Days)", "Contact Email",
        "Status", "Contract Start", "Payment Terms", "Remarks",
    ],
    "Forecast.csv": [
        "Date", "Product ID", "Product Name", "Actual Sales",
        "Forecast Sales", "Forecast Accuracy", "Season", "Trend",
        "Model Used", "Confidence", "Remarks",
    ],
    "Seasonality.csv": [
        "Event Name", "Event Date", "Product ID", "Product Name",
        "Expected Impact", "Region", "Historical Lift", "Confidence",
        "Event Type", "Source", "Remarks",
    ],
    "Pricing History.csv": [
        "Product ID", "Product Name", "Old Price", "New Price",
        "Change Date", "Reason", "Approved By", "Expected Impact",
        "Status", "Review Date", "Remarks",
    ],
    "Competitor Prices.csv": [
        "Competitor Name", "Product ID", "Product Name",
        "Their Price", "Our Price", "Price Difference", "Platform",
        "Region", "Availability", "Rating", "Remarks",
    ],
    "RCA Insights.csv": [
        "Issue Type", "Product ID", "Product Name", "Detected Date",
        "Main Reason", "Supporting Reason", "Business Impact",
        "Suggested Action", "Priority", "Status", "Remarks",
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


def validate_upload_schema(
    df: pd.DataFrame,
    target_filename: str,
) -> dict:
    """Validate an uploaded DataFrame's required column structure."""

    if target_filename not in EXPECTED_COLUMNS:
        return {
            "valid": False,
            "errors": [f"Unsupported ERP dataset: {target_filename}"],
            "missing_columns": [],
            "extra_columns": [],
        }

    if df is None or df.empty:
        return {
            "valid": False,
            "errors": ["The uploaded dataset is empty."],
            "missing_columns": [],
            "extra_columns": [],
        }

    columns = [str(column).strip() for column in df.columns]

    if len(columns) != len(set(columns)):
        return {
            "valid": False,
            "errors": ["The uploaded file contains duplicate column names."],
            "missing_columns": [],
            "extra_columns": [],
        }

    expected = EXPECTED_COLUMNS[target_filename]
    missing = [column for column in expected if column not in columns]
    extra = [column for column in columns if column not in expected]

    errors = []

    if missing:
        errors.append(f"Missing required columns: {missing}")

    if extra:
        errors.append(f"Unexpected columns: {extra}")

    return {
        "valid": not errors,
        "errors": errors,
        "missing_columns": missing,
        "extra_columns": extra,
    }
