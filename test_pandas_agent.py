
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_experimental.agents.agent_toolkits import (
    create_pandas_dataframe_agent,
)

load_dotenv()

model_name = os.getenv("GROQ_MODEL")
api_key = os.getenv("GROQ_API_KEY")

print("Model:", model_name)

# Load one CSV
csv_files = sorted(Path.cwd().glob("*.csv"))

if not csv_files:
    raise FileNotFoundError("No CSV files found.")

df = pd.read_csv(csv_files[0])

print("Using CSV:", csv_files[0].name)
print("Columns:", list(df.columns))
print("Rows:", len(df))

llm = ChatGroq(
    model=model_name,
    api_key=api_key,
    temperature=0,
)

agent = create_pandas_dataframe_agent(
    llm,
    [df],
    verbose=True,
    allow_dangerous_code=True,
    agent_type="tool-calling",
)

print("\nAgent created.")
print("\nRunning test query...\n")

response = agent.invoke({
    "input": "How many rows are in the dataframe?"
})

print("\nFINAL RESPONSE:")
print(response)

