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
from erp_upload_validation import (
    EXPECTED_COLUMNS,
    validate_upload_schema,
)

app = FastAPI(title = "ERP System")

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
app.mount("/static", StaticFiles(directory="static"), name="static")

# Fix #3: mounting a StaticFiles directory that doesn't exist yet crashes the whole
# app at startup (before any request is even served). Guard it so a missing
# react-chatbot/dist build doesn't take down the entire backend.
_react_dist = "react-chatbot/dist"
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


@app.get("/", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request = request, name = "index.html", context={})


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
        season_df = _read_table('Seasonality.csv')
        forecast_df = _read_table('Forecast.csv')

        print(f"Sales rows: {len(sales_df)}, Inventory rows: {len(inventory_df)}, Products rows: {len(products_df)}")

        # KPI Metrics
        total_sales = 0
        total_revenue = 0
        inventory_count = 0
        product_count = 0
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

        # Product Count
        if not products_df.empty:
            product_count = len(products_df)
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
                    {'product': product_dict.get(int(pid), f'Product {pid}'), 'quantity': int(qty)}
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
        target_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            target_file,
        )

        backup_path = None

        if os.path.exists(target_path):
            from datetime import datetime

            backup_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "backups",
            )
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{target_file}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_name)

            import shutil
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
                "backup_file": (
                    os.path.relpath(backup_path, os.path.dirname(os.path.abspath(__file__)))
                    if backup_path else None
                ),
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
            if os.path.exists(filename):
                # Get file size and row count
                df = pd.read_csv(filename)
                file_size = os.path.getsize(filename)
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