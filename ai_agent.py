import os
import json

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.tools import tool

from erp_tools import (
    get_low_inventory,
    get_critical_inventory,
    get_restock_recommendations,
    get_top_selling_products,
    get_total_sales_revenue,
    get_sales_by_product,
    get_sales_by_category,
    get_product_sales_performance,
    get_supplier_performance,
    get_purchase_summary,
    get_pending_purchases,
    get_demand_forecast,
    get_seasonal_opportunities,
    get_competitor_price_analysis,
    get_pricing_history,
    get_business_issues,
    get_customer_summary,
    get_warehouse_overview,
    get_business_overview,
    get_products_by_category,
    get_product_inventory_by_id,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

model_name = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)

if not api_key:
    raise ValueError(
        "GROQ_API_KEY is not set in the .env file"
    )


# ============================================================
# ERP SYSTEM PROMPT
# ============================================================

ERP_SYSTEM_PROMPT = """
You are an intelligent ERP business assistant for a large
retail business.

Your job is to help business owners, store managers,
inventory managers and operations teams understand the
business data.

IMPORTANT:

The user may NOT use technical language.

They may ask questions using:

- simple English
- broken English
- short phrases
- business slang
- Hinglish
- informal language
- incomplete sentences
- words like "maal", "stock", "order", "sale",
  "problem", "supplier", "demand", etc.

Understand the BUSINESS INTENT behind the question.

Examples:

"what should I order?"
"which maal is low?"
"anything running out?"
"what do I need to buy?"
"kaunsa stock mangwana hai?"
"bhai kya restock karna hai?"
"which items are almost finished?"

These should be understood as inventory/restocking questions.

============================================================
AVAILABLE BUSINESS CAPABILITIES
============================================================

Use the appropriate ERP tool.

Inventory:
- low_inventory_tool
- critical_inventory_tool
- restock_recommendation_tool

Sales:
- top_selling_products_tool
- total_sales_revenue_tool
- sales_by_product_tool
- sales_by_category_tool
- product_sales_performance_tool

Purchasing:
- purchase_summary_tool
- pending_purchases_tool

Suppliers:
- supplier_performance_tool

Forecast / demand:
- demand_forecast_tool
- seasonal_opportunities_tool

Pricing:
- competitor_price_analysis_tool
- pricing_history_tool

Business intelligence:
- business_issues_tool
- customer_summary_tool
- warehouse_overview_tool
- business_overview_tool

============================================================
TOOL SELECTION RULES
============================================================

Use LOW INVENTORY when the user asks:

- which products are low
- what is running low
- low stock
- items below reorder
- stock shortage

Use CRITICAL INVENTORY when the user asks:

- critically low
- almost finished
- urgent stock shortage
- dangerous stock levels

Use RESTOCK RECOMMENDATIONS when the user asks:

- what should I order
- what should I buy
- what needs restocking
- what do I need to replenish
- which products should I order
- kaunsa maal mangwana hai

Use TOP SELLING PRODUCTS when the user asks:

- best sellers
- fastest selling
- top products
- which products sell most

Use TOTAL SALES REVENUE when the user asks:

- total sales
- total revenue
- how much did we make
- sales amount
- revenue

Use SALES BY PRODUCT when the user asks about sales
of a particular product.

Use SALES BY CATEGORY when the user asks:

- best category
- category sales
- category revenue
- which category performs best

Use PRODUCT SALES PERFORMANCE when the user asks:

- how is [product] doing
- performance of [product]
- sales + stock + forecast of [product]

Use SUPPLIER PERFORMANCE when the user asks:

- supplier problems
- supplier delays
- bad suppliers
- supplier reliability
- which suppliers are risky

Use PURCHASE SUMMARY when the user asks:

- purchases
- purchase orders
- what did we order
- purchasing summary

Use PENDING PURCHASES when the user asks:

- pending orders
- pending purchases
- what has not arrived
- which purchase orders are delayed

Use DEMAND FORECAST when the user asks:

- future demand
- forecast
- expected sales
- demand prediction
- what will sell

Use SEASONAL OPPORTUNITIES when the user asks:

- seasonal demand
- festival demand
- upcoming demand
- summer demand
- Diwali demand
- seasonal products

Use COMPETITOR PRICE ANALYSIS when the user asks:

- competitor prices
- are we cheaper
- pricing competition
- compare our price
- market price

Use PRICING HISTORY when the user asks:

- price changes
- why price changed
- previous prices
- pricing history

Use BUSINESS ISSUES when the user asks:

- what problems do we have
- business issues
- risks
- root cause
- why is something going wrong
- what needs attention

Use CUSTOMER SUMMARY when the user asks:

- customers
- customer types
- membership
- customer segments

Use WAREHOUSE OVERVIEW when the user asks:

- warehouses
- warehouse stock
- warehouse information
- storage locations

Use BUSINESS OVERVIEW when the user asks:

- how is the business
- give me an overview
- business summary
- overall situation
- dashboard summary
- what is happening in the business

============================================================
MULTI-TOOL QUESTIONS
============================================================

If the question genuinely requires multiple datasets,
you may call multiple tools.

Example:

"Which products are low and are any of them affected by
increasing demand?"

Possible tools:

1. low_inventory_tool
2. demand_forecast_tool

Another example:

"Which low-stock products should I order urgently?"

Possible tools:

1. restock_recommendation_tool

Do NOT call tools unnecessarily.

============================================================
DATA ACCURACY
============================================================

Never invent ERP numbers.

Never calculate business figures from your own assumptions
when an ERP tool can provide the calculation.

Use the returned ERP data as the source of truth.

If data is missing, say that the ERP data does not contain
enough information.

============================================================
RESPONSE STYLE
============================================================

Talk like a helpful business assistant.

Do not sound like a programmer.

Do not mention:

- pandas
- DataFrame
- Python
- tool calls
- model
- API
- internal implementation

unless the user explicitly asks about the technical system.

Prefer concise business-friendly answers.

For lists, show:

Product
Stock
Reorder level
Recommended order
Urgency

when those fields are available.

If there are many results, summarize first and then show
the most important items.

Do not overwhelm the business owner with raw database output.

============================================================
LANGUAGE
============================================================

Understand English, Hinglish and informal business language.

If the user asks in Hinglish, you may answer in Hinglish.

If the user asks in English, answer in English.

Keep the meaning business-focused.
"""


# ============================================================
# LANGCHAIN TOOLS
# ============================================================

@tool
def low_inventory_tool() -> str:
    """
    Find products whose current stock is at or below
    the reorder level.
    """
    result = get_low_inventory()
    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def critical_inventory_tool() -> str:
    """
    Find critically low inventory.
    Critical means current stock is <= 50% of reorder level.
    """
    result = get_critical_inventory()
    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def restock_recommendation_tool() -> str:
    """
    Find products that should be restocked and calculate
    suggested order quantities.
    """
    result = get_restock_recommendations()
    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def top_selling_products_tool(
    top_n: int = 5
) -> str:
    """
    Return the top-selling products by quantity sold.
    """
    result = get_top_selling_products(top_n)

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def total_sales_revenue_tool() -> str:
    """
    Calculate total sales revenue.
    """
    result = get_total_sales_revenue()

    return json.dumps(
        {
            "total_sales_revenue": result,
            "currency": "INR"
        }
    )


@tool
def sales_by_product_tool(
    product: str = ""
) -> str:
    """
    Return sales quantity and revenue for a specific product.
    """
    result = get_sales_by_product(product)

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def sales_by_category_tool() -> str:
    """
    Return sales quantity and revenue by product category.
    """
    result = get_sales_by_category()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def product_sales_performance_tool(
    product: str = ""
) -> str:
    """
    Return detailed sales, inventory and forecast
    performance for a product.
    """
    result = get_product_sales_performance(product)

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def supplier_performance_tool() -> str:
    """
    Return supplier delivery, quality and risk information.
    """
    result = get_supplier_performance()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def purchase_summary_tool() -> str:
    """
    Return purchase order summary.
    """
    result = get_purchase_summary()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def pending_purchases_tool() -> str:
    """
    Return purchase orders that are pending or partially received.
    """
    result = get_pending_purchases()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def demand_forecast_tool(
    product: str = ""
) -> str:
    """
    Return demand forecast information.
    """
    result = get_demand_forecast(product)

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def seasonal_opportunities_tool() -> str:
    """
    Return seasonal and festival demand opportunities.
    """
    result = get_seasonal_opportunities()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def competitor_price_analysis_tool(
    product: str = ""
) -> str:
    """
    Compare our prices against competitor prices.
    """
    result = get_competitor_price_analysis(product)

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def pricing_history_tool(
    product: str = ""
) -> str:
    """
    Return historical pricing information.
    """
    result = get_pricing_history(product)

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def business_issues_tool() -> str:
    """
    Return current ERP business issues and RCA insights.
    """
    result = get_business_issues()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def customer_summary_tool() -> str:
    """
    Return customer segment information.
    """
    result = get_customer_summary()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def warehouse_overview_tool() -> str:
    """
    Return warehouse information and inventory summary.
    """
    result = get_warehouse_overview()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def business_overview_tool() -> str:
    """
    Return a high-level business snapshot.
    """
    result = get_business_overview()

    return result.to_json(
        orient="records",
        date_format="iso"
    )


@tool
def product_inventory_tool(category: str) -> str:
    """
    Find products in a category and return their current stock
    and reorder levels. Use for questions such as which dairy
    products or beverages are currently in stock.
    """
    df = get_products_by_category(category)

    if df.empty:
        return f"No products found in the {category} category."

    return df.to_json(orient="records")


@tool
def product_inventory_by_id_tool(product_id: str) -> str:
    """
    Return product name, category, current stock, and reorder level
    for a specific product ID such as P014.
    """
    df = get_product_inventory_by_id(product_id)

    if df.empty:
        return f"No product or inventory record found for {product_id}."

    return df.to_json(orient="records", date_format="iso")


# ============================================================
# TOOL REGISTRY
# ============================================================

ERP_TOOLS = [
    low_inventory_tool,
    critical_inventory_tool,
    restock_recommendation_tool,
    top_selling_products_tool,
    total_sales_revenue_tool,
    sales_by_product_tool,
    sales_by_category_tool,
    product_sales_performance_tool,
    supplier_performance_tool,
    purchase_summary_tool,
    pending_purchases_tool,
    demand_forecast_tool,
    seasonal_opportunities_tool,
    competitor_price_analysis_tool,
    pricing_history_tool,
    business_issues_tool,
    customer_summary_tool,
    warehouse_overview_tool,
    business_overview_tool,
    product_inventory_tool,
    product_inventory_by_id_tool,
]


# ============================================================
# MODEL
# ============================================================

llm = ChatGroq(
    model=model_name,
    temperature=0,
    api_key=api_key,
)

llm_with_tools = llm.bind_tools(
    ERP_TOOLS
)


# ============================================================
# TOOL DISPATCH
# ============================================================

TOOL_FUNCTIONS = {
    "low_inventory_tool":
        low_inventory_tool,

    "critical_inventory_tool":
        critical_inventory_tool,

    "restock_recommendation_tool":
        restock_recommendation_tool,

    "top_selling_products_tool":
        top_selling_products_tool,

    "total_sales_revenue_tool":
        total_sales_revenue_tool,

    "sales_by_product_tool":
        sales_by_product_tool,

    "sales_by_category_tool":
        sales_by_category_tool,

    "product_sales_performance_tool":
        product_sales_performance_tool,

    "supplier_performance_tool":
        supplier_performance_tool,

    "purchase_summary_tool":
        purchase_summary_tool,

    "pending_purchases_tool":
        pending_purchases_tool,

    "demand_forecast_tool":
        demand_forecast_tool,

    "seasonal_opportunities_tool":
        seasonal_opportunities_tool,

    "competitor_price_analysis_tool":
        competitor_price_analysis_tool,

    "pricing_history_tool":
        pricing_history_tool,

    "business_issues_tool":
        business_issues_tool,

    "customer_summary_tool":
        customer_summary_tool,

    "warehouse_overview_tool":
        warehouse_overview_tool,

    "business_overview_tool":
        business_overview_tool,

    "product_inventory_tool":
        product_inventory_tool,

    "product_inventory_by_id_tool":
        product_inventory_by_id_tool,
}


# ============================================================
# TOOL EXECUTION
# ============================================================

def execute_tool(tool_call):
    """
    Execute a selected ERP tool safely.

    The LLM chooses the tool.
    Python executes the actual deterministic business logic.
    """

    tool_name = tool_call["name"]

    tool_args = tool_call.get(
        "args",
        {}
    )

    if not isinstance(tool_args, dict):
        tool_args = {}

    if tool_name not in TOOL_FUNCTIONS:
        return (
            f"ERROR: Unknown ERP tool '{tool_name}'"
        )

    print("\n" + "-" * 80)
    print("ERP TOOL SELECTED:", tool_name)
    print("TOOL ARGUMENTS:", tool_args)
    print("-" * 80)

    try:
        selected_tool = TOOL_FUNCTIONS[tool_name]

        result = selected_tool.invoke(
            tool_args
        )

        return result

    except Exception as exc:

        print(
            f"ERP TOOL ERROR [{tool_name}]:",
            exc
        )

        return (
            f"ERP tool '{tool_name}' failed: {exc}"
        )


# ============================================================
# MAIN CHAT FUNCTION
# ============================================================

def ask_erp(
    user_question: str,
    chat_history=None
):
    """
    Main ERP chatbot function.

    Flow:

        User question
              ↓
        LLM understands intent
              ↓
        LLM selects ERP tool(s)
              ↓
        Python executes tool(s)
              ↓
        Verified ERP results
              ↓
        LLM explains results
              ↓
        Final business answer
    """

    if not user_question or not user_question.strip():
        return "Please tell me what you would like to know about the business."

    messages = [
        {
            "role": "system",
            "content": ERP_SYSTEM_PROMPT,
        }
    ]

    # --------------------------------------------------------
    # OPTIONAL CONVERSATION HISTORY
    # --------------------------------------------------------

    if chat_history:

        for message in chat_history:

            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")

            if role in ("user", "assistant") and content:

                messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

    messages.append(
        {
            "role": "user",
            "content": user_question,
        }
    )

    # --------------------------------------------------------
    # FIRST LLM CALL
    # --------------------------------------------------------

    print("\n" + "=" * 90)
    print("USER QUESTION")
    print("=" * 90)
    print(user_question)


    try:
        response = llm_with_tools.invoke(messages)

    except Exception as exc:
        print("\n[ERP AI ERROR] First LLM call failed:")
        print(f"{type(exc).__name__}: {exc}")
        raise

    print("\n" + "=" * 90)
    print("FIRST LLM RESPONSE")
    print("=" * 90)
    print(response)


    # --------------------------------------------------------
    # NO TOOL NEEDED
    # --------------------------------------------------------

    if not response.tool_calls:

        return response.content

    # --------------------------------------------------------
    # EXECUTE ERP TOOLS
    # --------------------------------------------------------

    tool_results = []

    for tool_call in response.tool_calls:

        result = execute_tool(
            tool_call
        )

        tool_results.append(
            {
                "tool": tool_call["name"],
                "arguments": tool_call.get(
                    "args",
                    {}
                ),
                "result": result,
            }
        )

    # --------------------------------------------------------
    # VERIFIED DATA
    # --------------------------------------------------------

    verified_data = json.dumps(
        tool_results,
        indent=2,
        ensure_ascii=False
    )

    print("\n" + "=" * 90)
    print("VERIFIED ERP DATA")
    print("=" * 90)
    print(verified_data)

    # --------------------------------------------------------
    # FINAL RESPONSE
    #
    # IMPORTANT:
    #
    # Do NOT bind tools here.
    #
    # This prevents the GPT-OSS tool-call validation issue
    # you previously encountered.
    # --------------------------------------------------------

    final_prompt = f"""
You are the final response layer of an ERP business assistant.

The user asked:

{user_question}

The ERP system already executed the required business
operations.

Below is VERIFIED ERP DATA returned by the backend:

---------------- VERIFIED DATA ----------------

{verified_data}

---------------- END VERIFIED DATA ----------------

Answer the user's question using ONLY the verified ERP data.

IMPORTANT RESPONSE RULES:

1. ERP monetary values are in Indian Rupees (INR).
2. Always display monetary amounts using ₹.
3. Do not convert INR to USD or any other currency.
4. Only state metrics that are present in VERIFIED DATA.
5. Do not invent, assume, or estimate missing business metrics.
6. If a metric is not present in VERIFIED DATA, say that it is not available.
7. Use concise business-friendly language.
8. For lists, use bullets or compact tables.
9. The verified tool result is the source of truth.

Answer naturally.
"""

    final_response = llm.invoke(
        final_prompt
    )

    print("\n" + "=" * 90)
    print("FINAL AI ANSWER")
    print("=" * 90)
    print(final_response.content)

    return final_response.content


# ============================================================
# MANUAL TERMINAL TESTING
# ============================================================

if __name__ == "__main__":

    test_questions = [
        "Which products are running low?",
        "Which products are critically low?",
        "What should I order?",
        "How much sales revenue did we make?",
        "What are our top selling products?",
        "Which category is performing best?",
        "Are there any supplier problems?",
        "Which purchase orders are still pending?",
        "What is the demand forecast?",
        "Are there any seasonal opportunities?",
        "Are our prices competitive?",
        "What problems should I worry about?",
        "Give me a business overview.",
    ]

    print("\n")
    print("#" * 100)
    print("# ERP AI ASSISTANT TEST")
    print("#" * 100)

    for question in test_questions:

        print("\n")
        print("#" * 100)
        print("QUESTION:", question)
        print("#" * 100)

        try:

            answer = ask_erp(question)

            print("\nANSWER:")
            print(answer)

        except Exception as exc:

            print("\nERROR:")
            print(exc)