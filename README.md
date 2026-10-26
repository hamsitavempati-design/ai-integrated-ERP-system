# AI-Powered ERP Dashboard

An ERP-style business operations dashboard built with **Python, FastAPI, Pandas, React, and Groq-powered AI integration**. The project brings business datasets into one interface for operational monitoring, inventory analysis, sales insights, and natural-language business queries.

This project is a software prototype demonstrating backend API development, data processing, spreadsheet uploads, validation, dashboard integration, and AI-assisted business analytics.

## Overview

Businesses often manage inventory, sales, purchasing, suppliers, and forecasts across separate spreadsheets. This project explores how these datasets can be brought together in a centralized dashboard.

The application uses CSV files as its current data layer, a FastAPI backend for processing and API endpoints, and a web interface for displaying operational information. An embedded React chatbot provides an interface for AI-assisted business queries.

## Key Features

### 📊 Business Dashboard
- Display key operational metrics and business summaries.
- Visualize sales and inventory information.
- Identify high-demand products.
- Present supplier-related information.
- Process business datasets using Pandas.

### 📦 Data Upload and Validation
- Upload CSV and supported Excel spreadsheet files.
- Identify the expected dataset using its column structure.
- Validate uploaded data against dataset-specific schemas.
- Save accepted data to the corresponding dataset file.
- Create backups of existing CSV files before replacement.
- Use temporary files and atomic replacement when saving updated datasets.

### 🤖 AI-Assisted Business Queries
- Explore business data using natural-language questions.
- Integrate Groq-hosted language models through Python AI tooling.
- Support an experimental AI-agent workflow for business analytics.
- Connect business questions with relevant datasets and analytical functions.

Example questions to try:

- Which products need restocking?
- Which products have low inventory?
- What are the current inventory levels?
- Which products have the highest sales?
- Which suppliers are associated with our inventory?

*The availability and accuracy of individual queries depend on the implemented tools, the underlying datasets, and the configured AI model.*

### 🔐 Authentication
- Authentication-related routes are organized in `auth_routes.py`.
- Authentication functionality is integrated with the application.

*Authentication security, session management, and access-control behavior should be reviewed before production deployment.*

### 🧪 Data Validation and Testing
- Validate ERP dataset schemas.
- Check uploaded files before accepting them.
- Use test scripts to evaluate data processing and AI-agent behavior.
- Maintain test results for development and debugging.

## Technology Stack

| Component | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Data processing | Pandas |
| API and server | FastAPI, Uvicorn |
| Templates | Jinja2, HTML |
| Frontend | JavaScript, HTML, CSS |
| Chatbot interface | React, Vite |
| AI integration | Groq API, LangChain |
| Data storage | CSV files |
| Authentication storage | SQLite database, where configured |
| File formats | CSV, XLSX, XLS |
| Version control | Git and GitHub |

## Architecture

The application is organized into several cooperating components.

```text
                   ┌─────────────────────────┐
                   │      Web Dashboard      │
                   │ HTML, CSS, JavaScript   │
                   └────────────┬────────────┘
                                │
                   HTTP Requests / Responses
                                │
                   ┌────────────▼────────────┐
                   │      FastAPI Backend    │
                   │       app.py            │
                   └────────────┬────────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
       ┌───────▼────────┐ ┌─────▼────────┐ ┌────▼──────────┐
       │ Data Processing│ │ Upload and   │ │ Authentication│
       │ and ERP Tools  │ │ Validation   │ │ Routes        │
       │ Pandas         │ │              │ │               │
       └───────┬────────┘ └─────┬────────┘ └───────────────┘
               │                │
               └────────┬───────┘
                        │
              ┌─────────▼──────────┐
              │    CSV Datasets    │
              │ Sales, Inventory,  │
              │ Products, Suppliers│
              │ and other datasets │
              └────────────────────┘

              ┌────────────────────┐
              │  React Chatbot     │
              │  AI Integration    │
              └─────────┬──────────┘
                        │
                  AI Agent / API
                        │
              ┌─────────▼──────────┐
              │ Groq-hosted LLM    │
              └────────────────────┘
```

The diagram illustrates the project's logical components. Exact request paths and integration details may vary with the current implementation.

## Project Structure

```text
ERP_Project/
│
├── app.py
├── auth_routes.py
├── agent.py
├── ai_agent.py
├── erp_data.py
├── erp_tools.py
├── erp_upload_validation.py
│
├── validate_erp.py
├── validate_erp_data.py
├── batch_test.py
├── test_pandas_agent.py
│
├── requirements.txt
├── README.md
├── .gitignore
│
├── Customers.csv
├── Inventory.csv
├── Products.csv
├── Sales.csv
├── Suppliers.csv
├── Purchases.csv
├── Warehouses.csv
├── Forecast.csv
├── Seasonality.csv
├── Pricing History.csv
├── Competitor Prices.csv
├── RCA Insights.csv
│
├── static/
│   ├── css/
│   └── js/
│
├── templates/
│   └── index.html
│
└── react-chatbot/
    ├── src/
    ├── public/
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    └── index.html
```

*This is a representative project layout. Generated files, local databases, environment files, backups, and temporary test datasets are intentionally omitted.*

### Important Modules

| File | Responsibility |
|---|---|
| `app.py` | Main FastAPI application, routes, dashboard APIs, and upload processing |
| `auth_routes.py` | Authentication-related routes |
| `erp_data.py` | Loading ERP datasets |
| `erp_tools.py` | Business data analysis and reusable ERP tools |
| `erp_upload_validation.py` | Dataset identification and upload schema validation |
| `agent.py` | Experimental LangChain-based data analysis |
| `ai_agent.py` | AI-agent implementation and business tool integration |
| `validate_erp.py` | ERP data validation utilities |
| `validate_erp_data.py` | Dataset integrity and business-rule validation |
| `batch_test.py` | Batch testing |
| `test_pandas_agent.py` | AI-agent testing |

## Dataset Overview

The project uses sample datasets to represent common ERP operations.

| Dataset | Purpose |
|---|---|
| `Products.csv` | Product information |
| `Inventory.csv` | Inventory levels and stock monitoring |
| `Sales.csv` | Sales records and demand analysis |
| `Purchases.csv` | Purchase order information |
| `Suppliers.csv` | Supplier information |
| `Customers.csv` | Customer records |
| `Warehouses.csv` | Warehouse information |
| `Forecast.csv` | Forecasting data |
| `Seasonality.csv` | Seasonal demand information |
| `Pricing History.csv` | Historical pricing information |
| `Competitor Prices.csv` | Competitor pricing information |
| `RCA Insights.csv` | Root-cause analysis insights |

The CSV-based approach makes it easy to inspect the sample