
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent / "data"

files = {
    "Products": "Products.csv",
    "Inventory": "Inventory.csv",
    "Sales": "Sales.csv",
    "Forecast": "Forecast.csv",
}

# Load the product master
products_path = BASE_DIR / files["Products"]
products = pd.read_csv(products_path)

product_ids = set(products["Product ID"].astype(str).str.strip())

print("\n===== ERP DATA VALIDATION =====")
print(f"Products loaded: {len(products)}")
print(f"Unique product IDs: {len(product_ids)}")

# Check the other CSV files
for name, filename in list(files.items())[1:]:
    path = BASE_DIR / filename

    print(f"\n--- {name} ---")

    if not path.exists():
        print(f"FILE NOT FOUND: {filename}")
        continue

    df = pd.read_csv(path)
    print(f"Rows: {len(df)}")

    if "Product ID" not in df.columns:
        print("Product ID column not found.")
        print("Available columns:", list(df.columns))
        continue

    ids = set(df["Product ID"].dropna().astype(str).str.strip())
    missing = sorted(ids - product_ids)

    if missing:
        print("Product IDs missing from Products.csv:", missing)
    else:
        print("All product IDs match Products.csv.")

print("\n===== VALIDATION COMPLETE =====")
# Check forecast coverage
forecast = pd.read_csv(BASE_DIR / "Forecast.csv")

forecast_ids = set(
    forecast["Product ID"].dropna().astype(str).str.strip()
)

all_product_ids = set(
    products["Product ID"].dropna().astype(str).str.strip()
)

not_forecasted = sorted(all_product_ids - forecast_ids)

print("\n--- Forecast Coverage ---")
print("Products with forecasts:", len(forecast_ids))
print("Products without forecasts:", len(not_forecasted))
print("Products without forecasts:", not_forecasted)