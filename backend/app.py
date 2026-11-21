from fastapi import FastAPI, Request, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
from auth_routes import (
    router as auth_router,
      init_auth_db,
      current_user,
    )
import pandas as pd
import os
import io
import shutil
import tempfile
import threading
import math
from datetime import datetime, timezone
from erp_upload_validation import (
    EXPECTED_COLUMNS,
    validate_upload_schema,
)

app = FastAPI(title = "ERP System")

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
ERP_DIR = os.path.join(PROJECT_ROOT, "data")        # CSV files and backups
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")   # images
_DATA_FILES_LOCK = threading.RLock()
_REQUIRED_RECORD_FIELDS = {
    "Products.csv": ["Product ID", "Product Name"],
    "Inventory.csv": ["Product ID", "Warehouse"],
    "Sales.csv": ["Order ID", "Product ID"],
    "Purchases.csv": ["PO Number", "Product ID"],
    "Suppliers.csv": ["Supplier Name"],
    "Forecast.csv": ["Date", "Product ID"],
    "Seasonality.csv": ["Event Name", "Event Date"],
    "Pricing History.csv": ["Product ID", "Change Date"],
    "Competitor Prices.csv": ["Competitor Name", "Product ID"],
    "RCA Insights.csv": ["Issue Type", "Product ID"],
    "Customers.csv": ["Customer ID"],
    "Warehouses.csv": ["Warehouse ID", "Warehouse Name"],
}
_NUMERIC_RECORD_FIELDS = {
    "MRP", "Selling Price", "TaxRate", "Tax Rate", "Opening Stock",
    "Current Stock", "Reorder Level", "Maximum Stock", "Reserved Stock",
    "Quantity Sold", "Discount", "Ordered Quantity", "Unit Cost",
    "Received Quantity", "Actual Sales", "Forecast Sales",
    "Forecast Accuracy", "Expected Impact", "Historical Lift",
    "Old Price", "New Price", "Their Price", "Our Price",
    "Price Difference", "Rating", "On-Time Delivery %", "Quality Rating",
    "Average Delay (Days)", "Capacity",
}


def _allowed_dataset(filename: str) -> list[str]:
    """Return a schema only for a known ERP file; never accept arbitrary paths."""
    if filename not in EXPECTED_COLUMNS:
        raise ValueError("Choose one of the supported ERP datasets.")
    return EXPECTED_COLUMNS[filename]


def _read_dataset(filename: str) -> pd.DataFrame:
    columns = _allowed_dataset(filename)
    path = os.path.join(ERP_DIR, filename)
    if not os.path.isfile(path):
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _write_dataset(filename: str, frame: pd.DataFrame) -> None:
    """Back up and atomically replace a validated ERP CSV."""
    _allowed_dataset(filename)
    target = os.path.join(ERP_DIR, filename)
    backup_dir = os.path.join(ERP_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(target):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        shutil.copy2(target, os.path.join(backup_dir, f"{filename}.{stamp}.bak"))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", suffix=".tmp",
            dir=ERP_DIR, delete=False
        ) as handle:
            temporary = handle.name
            frame.to_csv(handle, index=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)

# Fix #1: allow_origins="*" is invalid together with allow_credentials=True per the
# CORS spec (browsers will reject it). Replace with your actual frontend origin(s)
# below, or set allow_credentials=False if you truly need a wildcard origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
def setup_auth_db():
    init_auth_db()  

app.include_router(auth_router)
# Mount the 'static' folder (CSS, JS, Images)
app.mount("/static", StaticFiles(directory=ASSETS_DIR), name="static")

# Fix #3: mounting a StaticFiles directory that doesn't exist yet crashes the whole
# app at startup (before any request is even served). Guard it so a missing
# react-chatbot/dist build doesn't take down the entire backend.
_react_dist = os.path.join(PROJECT_ROOT, "react-chatbot", "dist")
if os.path.isdir(_react_dist):
    app.mount("/react-chatbot", StaticFiles(directory=_react_dist, html=True), name="react_chatbot")
    app.mount("/assets", StaticFiles(directory=os.path.join(_react_dist, "assets")), name="chatbot_assets")
else:
    print(f"Warning: '{_react_dist}' not found — run 'npm run build' in react-chatbot/ first. "
          f"Chatbot UI will not be served until then.")

# Serve vite.svg used by the chatbot build
@app.get('/vite.svg')
async def vite_svg():
    svg_path = os.path.join(_react_dist, "vite.svg")
    if os.path.exists(svg_path):
        return FileResponse(svg_path)
    return JSONResponse(status_code=404, content={"success": False, "message": "vite.svg not found"})

# Setup templates
templates = Jinja2Templates(directory="templates")


@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse(os.path.join(PROJECT_ROOT, "index.html"), media_type="text/html")


@app.get("/index.css", include_in_schema=False)
async def frontend_css():
    return FileResponse(os.path.join(PROJECT_ROOT, "index.css"), media_type="text/css")


@app.get("/index.js", include_in_schema=False)
async def frontend_js():
    return FileResponse(os.path.join(PROJECT_ROOT, "index.js"), media_type="application/javascript")

@app.post("/chat")
async def chat(request: Request, file: UploadFile | None = File(None), user: dict = Depends(current_user),):
    """
    Main ERP AI chatbot endpoint.

    Supports:
    1. Normal JSON chatbot messages
    2. Multipart requests when an image is attached
    3. Conversation history for multi-turn conversations
    """

    try:
        content_type = request.headers.get("content-type", "")

        prompt = ""
        chat_history = []
        uploaded_file = None

        # ---------------------------------------------------------
        # JSON REQUEST FROM REACT CHATBOT
        # ---------------------------------------------------------
        if content_type.startswith("application/json"):
            data = await request.json()

            prompt = str(data.get("prompt", "")).strip()
            chat_history = data.get("chat_history", [])

        # ---------------------------------------------------------
        # MULTIPART REQUEST
        # Used when an image/file is attached
        # ---------------------------------------------------------
        elif content_type.startswith("multipart/form-data"):
            form = await request.form()

            prompt = str(form.get("prompt", "")).strip()
            

            uploaded_file = file or form.get("file")

            history_value = form.get("chat_history", "[]")

            try:
                import json
                chat_history = json.loads(history_value)
            except Exception:
                chat_history = []

        else:
            return JSONResponse(
                status_code=400,
                content={
                    "response": "Unsupported request format."
                }
            )

        # ---------------------------------------------------------
        # VALIDATE PROMPT
        # ---------------------------------------------------------
        if not prompt:
            return JSONResponse(
                status_code=400,
                content={
                    "response": "Please enter a question."
                }
            )

        # ---------------------------------------------------------
        # IMAGE HANDLING
        # ---------------------------------------------------------
        # Keep this section isolated for now.
        # Our main ERP chatbot works with structured ERP data.
        if isinstance(uploaded_file, UploadFile):

            filename = (uploaded_file.filename or "").lower()

            if filename.endswith((".csv", ".xlsx", ".xls")):
                return JSONResponse(
                    status_code=400,
                    content={
                        "response": (
                            "CSV and Excel files should be uploaded first. "
                            "After uploading, ask me what you want to know "
                            "about the business data."
                        )
                    }
                )

            if (
                not uploaded_file.content_type
                or not uploaded_file.content_type.startswith("image/")
            ):
                return JSONResponse(
                    status_code=400,
                    content={
                        "response": "Please attach a supported image file."
                    }
                )

            # Image AI can be integrated separately later.
            return JSONResponse(
                status_code=400,
                content={
                    "response": (
                        "Image analysis is not connected to the ERP assistant yet. "
                        "For now, ask me about sales, inventory, purchases, "
                        "suppliers, forecasts, pricing, or other ERP data."
                    )
                }
            )

        # ---------------------------------------------------------
        # IMPORT OUR NEW ERP AI AGENT
        # ---------------------------------------------------------
        from ai_agent import ask_erp

        # ---------------------------------------------------------
        # CALL ERP AI
        # ---------------------------------------------------------
        answer = ask_erp(
            user_question=prompt,
            chat_history=chat_history
        )

        return {
            "success": True,
            "response": answer
        }

    except Exception as error:

        import traceback

        print("========== CHAT ERROR ==========")
        print(traceback.format_exc())
        print("================================")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "response": (
                    "I couldn't process that request right now. "
                    "Please try again."
                )
            }
        )


@app.get("/api/stats")
async def get_stats(user: dict = Depends(current_user)):
    try:
        # Load your CSVs (support fallback to Excel files)
        def _read_table(csv_path: str) -> pd.DataFrame:
            csv_path = os.path.join(ERP_DIR, csv_path)
            if os.path.exists(csv_path):
                try:
                    return pd.read_csv(csv_path)
                except Exception as e:
                    print(f"Error reading {csv_path}: {e}")
                    pass
            return pd.DataFrame()

        # Load all data files
        sales_df = _read_table('Sales.csv')
        inventory_df = _read_table('Inventory.csv')
        products_df = _read_table('Products.csv')
        suppliers_df = _read_table('Suppliers.csv')
        purchases_df = _read_table('Purchases.csv')
        rca_df = _read_table('RCA Insights.csv')
        season_df = _read_table('Seasonality.csv')
        forecast_df = _read_table('Forecast.csv')

        print(f"Sales rows: {len(sales_df)}, Inventory rows: {len(inventory_df)}, Products rows: {len(products_df)}")

        # KPI Metrics
        total_sales = 0
        total_revenue = 0
        inventory_count = 0
        product_count = 0
        low_stock_count = 0
        supplier_risk_count = 0
        pending_orders = 0
        average_price = 0
        top_demand = []
        suppliers_list = []
        labels = []
        values = []
        inventory_values = []

        # Total Sales and Revenue calculation
        if not sales_df.empty:
            print("Processing sales data...")
            # Calculate revenue from quantity and price
            if 'Quantity Sold' in sales_df.columns and 'Selling Price' in sales_df.columns:
                sales_df['Revenue'] = sales_df['Quantity Sold'] * sales_df['Selling Price']
                total_revenue = float(sales_df['Revenue'].sum())
                total_sales = float(sales_df['Quantity Sold'].sum())
                print(f"Total sales: {total_sales}, Total revenue: {total_revenue}")

            # Monthly revenue for chart
            if 'Sale Date' in sales_df.columns:
                try:
                    sales_df['Sale Date'] = pd.to_datetime(sales_df['Sale Date'], errors='coerce')
                    monthly = sales_df.groupby(sales_df['Sale Date'].dt.to_period('M'))['Revenue'].sum() if 'Revenue' in sales_df.columns else sales_df.groupby(sales_df['Sale Date'].dt.to_period('M'))['Selling Price'].sum()
                    labels = [str(idx) for idx in monthly.index]
                    values = monthly.tolist()
                    print(f"Monthly labels: {labels}")
                    print(f"Monthly values: {values}")
                except Exception as e:
                    print(f"Error processing dates: {e}")

        # Inventory Count
        if not inventory_df.empty:
            print("Processing inventory data...")
            if 'Current Stock' in inventory_df.columns:
                inventory_count = int(inventory_df['Current Stock'].sum())
            elif 'Quantity' in inventory_df.columns:
                inventory_count = int(inventory_df['Quantity'].sum())
            elif 'Stock' in inventory_df.columns:
                inventory_count = int(inventory_df['Stock'].sum())
            print(f"Inventory count: {inventory_count}")
            if {'Current Stock', 'Reorder Level'}.issubset(inventory_df.columns):
                current = pd.to_numeric(inventory_df['Current Stock'], errors='coerce')
                reorder = pd.to_numeric(inventory_df['Reorder Level'], errors='coerce')
                if 'Product ID' in inventory_df.columns:
                    totals = pd.DataFrame({
                        'Product ID': inventory_df['Product ID'],
                        'Current Stock': current,
                        'Reorder Level': reorder,
                    }).groupby('Product ID', dropna=False).sum(numeric_only=True)
                    low_stock_count = int((totals['Current Stock'] <= totals['Reorder Level']).sum())
                else:
                    low_stock_count = int((current <= reorder).fillna(False).sum())

        # Product Count
        if not products_df.empty:
            product_count = len(products_df)
            price_column = 'Selling Price' if 'Selling Price' in products_df.columns else None
            if price_column:
                prices = pd.to_numeric(products_df[price_column], errors='coerce').dropna()
                average_price = float(prices.mean()) if not prices.empty else 0
            print(f"Product count: {product_count}")
        elif not inventory_df.empty:
            product_count = len(inventory_df)

        # Top Demand Items
        if not sales_df.empty and 'Product ID' in sales_df.columns and 'Quantity Sold' in sales_df.columns:
            print("Processing top demand items...")
            top_products = sales_df.groupby('Product ID')['Quantity Sold'].sum().nlargest(5)
            # Match with product names
            if not products_df.empty and 'Product ID' in products_df.columns and 'Product Name' in products_df.columns:
                product_dict = dict(zip(products_df['Product ID'], products_df['Product Name']))
                top_demand = [
                    {'product': product_dict.get(pid, f'Product {pid}'), 'quantity': int(qty)}
                    for pid, qty in top_products.items()
                ]
            else:
                top_demand = [{'product': f'Product {pid}', 'quantity': int(qty)} for pid, qty in top_products.items()]
            print(f"Top demand: {top_demand}")

        # Suppliers List
        if not suppliers_df.empty:
            print("Processing suppliers data...")
            supplier_records = suppliers_df.head(5).to_dict('records') if len(suppliers_df) > 0 else []
            suppliers_list = []
            for i, record in enumerate(supplier_records):
                supplier_name = record.get('Supplier Name') or record.get('Name') or f"Supplier {i+1}"
                suppliers_list.append({
                    'name': supplier_name,
                    'status': record.get('Status', 'Active'),
                    'rating': float(record.get('Quality Rating', 5)) if 'Quality Rating' in record else 5,
                    'delivery': str(record.get('On-Time Delivery %', 90))
                })
            print(f"Suppliers: {len(suppliers_list)}")
            risk_flags = pd.Series(False, index=suppliers_df.index)
            if 'On-Time Delivery %' in suppliers_df.columns:
                delivery = pd.to_numeric(suppliers_df['On-Time Delivery %'], errors='coerce')
                risk_flags = risk_flags | (delivery < 95).fillna(False)
            if 'Average Delay (Days)' in suppliers_df.columns:
                delay = pd.to_numeric(suppliers_df['Average Delay (Days)'], errors='coerce')
                risk_flags = risk_flags | (delay > 2).fillna(False)
            supplier_risk_count = int(risk_flags.sum())

        if not purchases_df.empty and 'Delivery Status' in purchases_df.columns:
            pending_orders = int(purchases_df['Delivery Status'].astype(str).str.casefold().isin({'pending', 'ordered', 'in transit'}).sum())
        elif not purchases_df.empty:
            pending_orders = len(purchases_df)

        # Default values if no data
        if not labels:
            labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
        if not values:
            values = [0, 0, 0, 0, 0, 0]
        if not inventory_values:
            inventory_values = [100, 110, 105, 115, 120, 125]

        result = {
            "success": True,
            "total_sales": total_sales,
            "total_revenue": total_revenue,
            "inventory_count": inventory_count,
            "product_count": product_count,
            "low_stock_products": low_stock_count,
            "supplier_risk_count": supplier_risk_count,
            "pending_purchase_orders": pending_orders,
            "average_selling_price": average_price,
            "open_rca_count": int((rca_df['Status'].astype(str).str.casefold() != 'closed').sum()) if not rca_df.empty and 'Status' in rca_df.columns else 0,
            "seasonality_count": len(season_df),
            "top_demand": top_demand,
            "suppliers": suppliers_list,
            "labels": labels,
            "values": values,
            "inventory_values": inventory_values,
        }

        print(f"Returning stats: {result}")
        return result

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(error_msg)
        return {
            "success": False,
            "error": str(e),
            "total_sales": 0,
            "total_revenue": 0,
            "inventory_count": 0,
            "product_count": 0,
            "top_demand": [],
            "suppliers": [],
            "labels": [],
            "values": [],
            "inventory_values": []
        }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(current_user),):
    """
    Accept CSV or Excel uploads. Validate columns and normalize to expected filenames.
    Supports .csv, .xlsx, .xls files.
    """
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

    content = await file.read(MAX_UPLOAD_SIZE + 1)

    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
          status_code=413,
          content={
            "success": False,
            "message": "File is too large. Maximum upload size is 10 MB.",
          },
        )    # Fix #2: sanitize the incoming filename so it can never be used for path
    # traversal (e.g. "../../app.py") in the unknown-file fallback branch below.
    raw_filename = file.filename or "unknown"
    filename = os.path.basename(raw_filename)
    name_lower = filename.lower()

    # Try to parse into a DataFrame depending on extension / content
    df = None
    parsed = False
    parse_error = None

    try:
        if name_lower.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
            parsed = True
        elif name_lower.endswith('.xlsx'):
            try:
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            except Exception:
                df = pd.read_excel(io.BytesIO(content))
            parsed = True
        elif name_lower.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(content))
            parsed = True
        else:
            # Try CSV parse first, then Excel
            try:
                df = pd.read_csv(io.BytesIO(content))
                parsed = True
            except Exception:
                try:
                    df = pd.read_excel(io.BytesIO(content))
                    parsed = True
                except Exception as e:
                    parse_error = str(e)
    except Exception as e:
        parse_error = str(e)

    if not parsed or df is None or df.empty:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": f"Failed to parse file: {parse_error or 'Unknown error'}"
        })

    
    # Normalize column names
    df.columns = df.columns.astype(str).str.strip()

    # Identify the dataset by its complete expected column schema
    uploaded_columns = set(df.columns)
    matching_files = [
        filename
        for filename, expected in EXPECTED_COLUMNS.items()
        if uploaded_columns == set(expected)
    ]

    if len(matching_files) != 1:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": (
                    "Could not uniquely identify this ERP dataset. "
                    "Please upload a file with the exact expected columns."
                ),
                "supported_files": list(EXPECTED_COLUMNS.keys()),
                "uploaded_columns": list(df.columns),
            },
        )

    target_file = matching_files[0]
    file_type = os.path.splitext(target_file)[0].lower().replace(" ", "_")


    # Validate the uploaded dataset before saving
    validation = validate_upload_schema(df, target_file)

    if not validation["valid"]:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Uploaded dataset failed schema validation.",
                "errors": validation["errors"],
                "missing_columns": validation["missing_columns"],
                "extra_columns": validation["extra_columns"],
            },
        )

    # Save the file
    
    # Save the validated dataset with a backup of existing data
    try:
        with _DATA_FILES_LOCK:
            target_path = os.path.join(ERP_DIR, target_file)
            backup_path = None
            if os.path.exists(target_path):
                backup_dir = os.path.join(ERP_DIR, "backups")
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
                backup_path = os.path.join(backup_dir, f"{target_file}.{timestamp}.bak")
                shutil.copy2(target_path, backup_path)

            temp_path = target_path + ".tmp"
            df.to_csv(temp_path, index=False)
            os.replace(temp_path, target_path)

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"File uploaded successfully as {target_file}",
                    "file_type": file_type,
                    "rows": len(df),
                    "columns": list(df.columns),
                    "saved_as": target_file,
                    "backup_created": backup_path is not None,
                    "backup_file": os.path.relpath(backup_path, ERP_DIR) if backup_path else None,
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Failed to save file: {str(e)}",
            },
        )

@app.get("/logout")
async def logout_redirect():
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/uploaded-files")
async def get_uploaded_files(user: dict = Depends(current_user)):
    """Get list of uploaded/available data files"""
    try:
        files = []
        data_files = {
            'Sales.csv': 'Sales Data',
            'Inventory.csv': 'Inventory Data',
            'Products.csv': 'Products Data',
            'Suppliers.csv': 'Suppliers Data',
            'Seasonality.csv': 'Seasonality Data',
            'Forecast.csv': 'Forecast Data',
            'Purchases.csv': 'Purchases Data'
        }

        for filename, description in data_files.items():
            file_path = os.path.join(ERP_DIR, filename)
            if os.path.exists(file_path):
                # Get file size and row count
                df = pd.read_csv(file_path)
                file_size = os.path.getsize(file_path)
                file_size_kb = round(file_size / 1024, 2)
                files.append({
                    'name': filename,
                    'description': description,
                    'rows': len(df),
                    'columns': len(df.columns),
                    'size_kb': file_size_kb,
                    'uploaded': True
                })

        return {
            "success": True,
            "files": files,
            "total_files": len(files)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": str(e)
        })


@app.get("/api/datasets")
async def list_datasets(user: dict = Depends(current_user)):
    """List supported ERP datasets and their current row counts."""
    datasets = []
    for filename, schema in EXPECTED_COLUMNS.items():
        try:
            with _DATA_FILES_LOCK:
                frame = _read_dataset(filename)
            datasets.append({
                "name": filename,
                "rows": len(frame),
                "columns": len(frame.columns) or len(schema),
                "fields": list(frame.columns) or list(schema),
            })
        except Exception as error:
            return JSONResponse(status_code=500, content={"detail": str(error)})
    return {"success": True, "datasets": datasets}


@app.get("/api/operational-products")
async def operational_products(user: dict = Depends(current_user)):
    """Join product, inventory and sales rows for dashboard and inventory views."""
    try:
        with _DATA_FILES_LOCK:
            products = _read_dataset("Products.csv")
            inventory = _read_dataset("Inventory.csv")
            sales = _read_dataset("Sales.csv")
        def number(value):
            parsed = pd.to_numeric(value, errors="coerce")
            return 0.0 if pd.isna(parsed) else float(parsed)

        stock_by_id = {}
        if not inventory.empty:
            for _, row in inventory.iterrows():
                pid = str(row.get("Product ID", ""))
                current = stock_by_id.setdefault(pid, {"stock": 0, "reorder": 0})
                current["stock"] += number(row.get("Current Stock", 0))
                current["reorder"] += number(row.get("Reorder Level", 0))
        sales_by_id = {}
        if not sales.empty:
            quantities = pd.to_numeric(sales.get("Quantity Sold"), errors="coerce").fillna(0)
            for pid, quantity in zip(sales.get("Product ID", []), quantities):
                key = str(pid)
                sales_by_id[key] = sales_by_id.get(key, 0) + float(quantity)
        result = []
        for _, row in products.iterrows():
            pid = str(row.get("Product ID", ""))
            stock = stock_by_id.get(pid, {"stock": 0, "reorder": 0})
            result.append({
                "id": pid,
                "name": str(row.get("Product Name", pid)),
                "category": str(row.get("Category", row.get("Subcategory", "Uncategorized"))),
                "stock": int(stock["stock"]),
                "reorder": int(stock["reorder"]),
                "units": int(sales_by_id.get(pid, 0)),
                "price": number(row.get("Selling Price", row.get("MRP", 0))),
                "supplier": str(row.get("Supplier Name", "")),
                "icon": "🥛" if "milk" in str(row.get("Product Name", "")).casefold() else "▦",
            })
        return {"success": True, "products": result}
    except Exception as error:
        return JSONResponse(status_code=500, content={"detail": f"Could not combine product records: {error}"})


@app.get("/api/data")
async def get_dataset(dataset: str, offset: int = 0, limit: int = 50, user: dict = Depends(current_user)):
    """Return a paged table of rows from one allow-listed ERP CSV."""
    try:
        with _DATA_FILES_LOCK:
            frame = _read_dataset(dataset)
        offset = max(0, offset)
        limit = min(max(1, limit), 250)
        rows = frame.iloc[offset:offset + limit].to_dict(orient="records")
        return {
            "success": True,
            "dataset": dataset,
            "columns": list(frame.columns),
            "rows": [{"row_index": offset + index, "record": record} for index, record in enumerate(rows)],
            "total": len(frame),
            "offset": offset,
            "limit": limit,
        }
    except ValueError as error:
        return JSONResponse(status_code=400, content={"detail": str(error)})
    except Exception as error:
        return JSONResponse(status_code=500, content={"detail": f"Could not read {dataset}: {error}"})


def _record_payload(dataset: str, payload: dict, columns: list[str]) -> dict:
    record = payload.get("record")
    if not isinstance(record, dict):
        raise ValueError("Provide a record object.")
    extra = [key for key in record if key not in columns]
    if extra:
        raise ValueError(f"Unknown field(s): {', '.join(extra)}")
    normalized = {column: str(record.get(column, "") or "").strip() for column in columns}
    required = _REQUIRED_RECORD_FIELDS[dataset]
    missing = [field for field in required if not normalized.get(field)]
    if missing:
        raise ValueError(f"Complete the required field(s): {', '.join(missing)}")
    for field in _NUMERIC_RECORD_FIELDS.intersection(columns):
        value = normalized.get(field, "")
        if not value:
            continue
        try:
            number = float(value.replace(",", "").replace("₹", "").replace("%", "").strip())
        except ValueError as error:
            raise ValueError(f"{field} must be a number.") from error
        if not math.isfinite(number):
            raise ValueError(f"{field} must be a finite number.")
    for field in columns:
        if "date" in field.casefold() and normalized.get(field):
            if pd.isna(pd.to_datetime(normalized[field], errors="coerce")):
                raise ValueError(f"{field} must be a valid date.")
    email = normalized.get("Contact Email", "")
    if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1]):
        raise ValueError("Contact Email must be a valid email address.")
    return normalized


@app.post("/api/data/records")
async def create_dataset_record(request: Request, user: dict = Depends(current_user)):
    try:
        payload = await request.json()
        filename = str(payload.get("dataset", ""))
        with _DATA_FILES_LOCK:
            frame = _read_dataset(filename)
            record = _record_payload(filename, payload, list(frame.columns))
            key_fields = _REQUIRED_RECORD_FIELDS[filename]
            duplicate = frame.apply(
                lambda row: all(str(row[field]).strip().casefold() == record[field].casefold() for field in key_fields),
                axis=1,
            ).any() if not frame.empty else False
            if duplicate:
                return JSONResponse(status_code=409, content={"detail": "A record with these identifying values already exists."})
            frame = pd.concat([frame, pd.DataFrame([record], columns=frame.columns)], ignore_index=True)
            _write_dataset(filename, frame)
        return {"success": True, "message": "Record created.", "total": len(frame)}
    except ValueError as error:
        return JSONResponse(status_code=400, content={"detail": str(error)})
    except Exception as error:
        return JSONResponse(status_code=500, content={"detail": f"Could not create record: {error}"})


@app.put("/api/data/records")
async def update_dataset_record(request: Request, user: dict = Depends(current_user)):
    try:
        payload = await request.json()
        filename = str(payload.get("dataset", ""))
        index = payload.get("row_index")
        if not isinstance(index, int) or index < 0:
            raise ValueError("Select a valid record to update.")
        with _DATA_FILES_LOCK:
            frame = _read_dataset(filename)
            if index >= len(frame):
                return JSONResponse(status_code=404, content={"detail": "That record no longer exists. Refresh the dataset and try again."})
            record = _record_payload(filename, payload, list(frame.columns))
            key_fields = _REQUIRED_RECORD_FIELDS[filename]
            duplicate = any(
                row_index != index and all(str(row[field]).strip().casefold() == record[field].casefold() for field in key_fields)
                for row_index, (_, row) in enumerate(frame.iterrows())
            )
            if duplicate:
                return JSONResponse(status_code=409, content={"detail": "Another record already uses these identifying values."})
            frame.iloc[index] = [record[column] for column in frame.columns]
            _write_dataset(filename, frame)
        return {"success": True, "message": "Record updated.", "total": len(frame)}
    except ValueError as error:
        return JSONResponse(status_code=400, content={"detail": str(error)})
    except Exception as error:
        return JSONResponse(status_code=500, content={"detail": f"Could not update record: {error}"})


@app.delete("/api/data/records")
async def delete_dataset_record(request: Request, user: dict = Depends(current_user)):
    try:
        payload = await request.json()
        filename = str(payload.get("dataset", ""))
        index = payload.get("row_index")
        if not isinstance(index, int) or index < 0:
            raise ValueError("Select a valid record to delete.")
        with _DATA_FILES_LOCK:
            frame = _read_dataset(filename)
            if index >= len(frame):
                return JSONResponse(status_code=404, content={"detail": "That record no longer exists. Refresh the dataset and try again."})
            frame = frame.drop(frame.index[index]).reset_index(drop=True)
            _write_dataset(filename, frame)
        return {"success": True, "message": "Record deleted.", "total": len(frame)}
    except ValueError as error:
        return JSONResponse(status_code=400, content={"detail": str(error)})
    except Exception as error:
        return JSONResponse(status_code=500, content={"detail": f"Could not delete record: {error}"})


@app.get("/api/search")
async def search_erp_data(query: str, user: dict = Depends(current_user)):
    """Search all datasets and include records linked to matching products."""
    terms = [term.strip().casefold() for term in query.split(",") if term.strip()]
    if not terms:
        return {"success": True, "query": query, "results": []}
    tables = {}
    with _DATA_FILES_LOCK:
        for filename in EXPECTED_COLUMNS:
            try:
                tables[filename] = _read_dataset(filename).to_dict(orient="records")
            except Exception:
                tables[filename] = []

    def contains_term(record):
        return any(term in " ".join(str(value) for value in record.values()).casefold() for term in terms)

    product_records = [record for record in tables.get("Products.csv", []) if contains_term(record)]
    product_ids = {str(record.get("Product ID", "")).strip() for record in product_records}
    supplier_names = {str(record.get("Supplier Name", "")).strip().casefold() for record in product_records}
    warehouse_names = {
        str(record.get("Warehouse", "")).strip().casefold()
        for record in tables.get("Inventory.csv", [])
        if str(record.get("Product ID", "")).strip() in product_ids
    }

    results = []
    for filename, records in tables.items():
        for index, record in enumerate(records):
            direct = contains_term(record)
            linked = (
                (bool(product_ids) and str(record.get("Product ID", "")).strip() in product_ids)
                or (bool(supplier_names) and str(record.get("Supplier Name", "")).strip().casefold() in supplier_names)
                or (bool(warehouse_names) and str(record.get("Warehouse Name", "")).strip().casefold() in warehouse_names)
            )
            if direct or linked:
                results.append({
                    "dataset": filename,
                    "row_index": index,
                    "match_type": "direct" if direct else "related",
                    "record": record,
                })
                if len(results) >= 250:
                    break
        if len(results) >= 250:
            break
    return {"success": True, "query": query, "count": len(results), "results": results}

@app.post("/api/admin-details")
async def save_admin_details(request: Request, user: dict = Depends(current_user), ):
    """Save admin/enterprise details"""
    try:
        data = await request.json()
        # In a real app, save to database
        # For now, we just return success
        return {
            "success": True,
            "message": "Admin details saved successfully",
            "data": data
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": str(e)
        })

if __name__ == "__main__":
    import uvicorn
    # Run using: python app.py
    uvicorn.run(app, host="127.0.0.1", port=8000)
