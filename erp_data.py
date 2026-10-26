from pathlib import Path
import pandas as pd


# ---------------------------------------------------------
# ERP DATA DIRECTORY
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------
# CSV FILES
# ---------------------------------------------------------

DATA_FILES = {
    "products": "Products.csv",
    "inventory": "Inventory.csv",
    "sales": "Sales.csv",
    "purchases": "Purchases.csv",
    "suppliers": "Suppliers.csv",
    "forecast": "Forecast.csv",
    "seasonality": "Seasonality.csv",
    "pricing_history": "Pricing History.csv",
    "competitor_prices": "Competitor Prices.csv",
    "rca_insights": "RCA Insights.csv",
    "customers": "Customers.csv",
    "warehouses": "Warehouses.csv",
}


# ---------------------------------------------------------
# LOAD ONE CSV
# ---------------------------------------------------------

def load_csv(filename: str) -> pd.DataFrame:
    """
    Load one ERP CSV file.
    """

    file_path = BASE_DIR / filename

    if not file_path.exists():
        raise FileNotFoundError(
            f"ERP data file not found: {file_path}"
        )

    return pd.read_csv(file_path)


# ---------------------------------------------------------
# LOAD ALL ERP DATA
# ---------------------------------------------------------

def load_erp_data() -> dict[str, pd.DataFrame]:
    """
    Load all ERP CSV files into a dictionary.
    """

    data = {}

    for name, filename in DATA_FILES.items():
        data[name] = load_csv(filename)

    return data


# ---------------------------------------------------------
# TEST
# ---------------------------------------------------------

if __name__ == "__main__":

    erp = load_erp_data()

    print("\nERP DATA LOADED")
    print("=" * 60)

    for name, df in erp.items():
        print(f"{name:20} {len(df):>5} rows")

    print("=" * 60)