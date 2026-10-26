
from ai_agent import ask_erp

tests = [
    (
        20,
        "Customer membership analysis",
        "Summarize our active customers by membership tier, including customer counts and the total number of active customers."
    ),
    (
        21,
        "Customer preferred channels",
        "Summarize our active customers by preferred shopping channel. Report the count for each channel and the total."
    ),
    (
        22,
        "Personal Care inventory",
        "List all Personal Care products with their product IDs, current stock, and reorder levels."
    ),
    (
        23,
        "Specific product stock status",
        "Check the current inventory of product P014. Give its product name, current stock, reorder level, and whether it needs restocking."
    ),
    (
        24,
        "Inventory below reorder level",
        "Which products currently have stock at or below their reorder levels? Give the product names, current stock, and reorder levels."
    ),
    (
        25,
        "Sales revenue by category",
        "Calculate the sales revenue for each product category and verify whether the category totals equal total sales revenue."
    ),
    (
        26,
        "Product sales performance",
        "Give the sales quantity, sales revenue, current stock, and reorder level for product P009. Include forecast information only if available."
    ),
    (
        27,
        "Missing forecast handling",
        "Do we have a demand forecast for product P004? If available, report its forecast details. If unavailable, clearly say so."
    ),
    (
        28,
        "Supplier performance",
        "Summarize the performance and risk status of London Dairy Distributors using verified supplier data."
    ),
    (
        29,
        "Product pricing history",
        "Show the pricing history for product P002. If no pricing history is available, explicitly report that instead of guessing."
    ),
    (
        30,
        "Combined stock and sales question",
        "For product P001, summarize its current stock, reorder level, recorded sales quantity, and forecast sales if available. Identify any restocking concern using the verified data."
    ),
]

for number, title, question in tests:
    print("\n" + "=" * 100)
    print(f"TEST {number}: {title}")
    print("=" * 100)
    print(f"QUESTION: {question}")
    try:
        ask_erp(question)
    except Exception as error:
        print(f"TEST EXECUTION ERROR: {type(error).__name__}: {error}")
    print("\n" + "#" * 100)
