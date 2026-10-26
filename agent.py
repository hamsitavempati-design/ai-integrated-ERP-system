import os
import base64
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

load_dotenv()

# 1. SETUP API KEY AND MODEL FROM ENVIRONMENT
# Note: Groq deprecated llama-3.3-70b-versatile and llama-3.1-8b-instant.
# openai/gpt-oss-120b is the current recommended general-purpose/reasoning model.
model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # Default to qwen3-32b if not set
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError(
        "GROQ_API_KEY is not set. Add it in your shell or .env file before running this agent."
    )

def _load_dataframes() -> list[pd.DataFrame]:
    dataframes = []
    for path in sorted(Path.cwd().glob("*.csv")):
        try:
            dataframe = pd.read_csv(path)
            if not dataframe.empty:
                dataframes.append(dataframe)
        except Exception as error:
            print(f"Skipping unreadable dataset {path.name}: {error}")
    return dataframes


def _create_agent():
    dataframes = _load_dataframes()
    if not dataframes:
        raise FileNotFoundError("No readable CSV datasets are available.")
    llm = ChatGroq(model=model_name, api_key=api_key, temperature=0)
    return create_pandas_dataframe_agent(
        llm,
        dataframes,
        verbose=False,
        allow_dangerous_code=True,
        agent_type="tool-calling",
        prefix=(
            "You are an ERP data analyst. Analyze all provided dataframes carefully. "
            "Answer business questions with calculations and cite relevant datasets "
            "and columns. Never invent data."
        ),
    )


def ask_agent(query: str) -> str:
    response = _create_agent().invoke({"input": query})
    return response["output"]


def analyze_image(image_bytes: bytes, content_type: str, query: str) -> str:
    vision_model = os.getenv(
        "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
    )
    vision_llm = ChatGroq(model=vision_model, api_key=api_key, temperature=0)
    message = HumanMessage(content=[
        {"type": "text", "text": f"Read this image for an ERP analyst. User question: {query}"},
        {"type": "image_url", "image_url": {
            "url": f"data:{content_type};base64,{base64.b64encode(image_bytes).decode()}"
        }},
    ])
    return vision_llm.invoke([message]).content


def test_agent(query):
    print(ask_agent(query))


if __name__ == "__main__":
    test_agent("What are the names of items with low stock in df1?")