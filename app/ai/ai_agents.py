from agents import Agent, Runner, ModelSettings, function_tool
from .rag import RAGIndexer
import os
from typing import List
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

gemini_base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
client = OpenAI( base_url=gemini_base_url, api_key=os.getenv("GEMINI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))


#############################################################Compliance Verification Agent#############################################################
@function_tool
async def retrieval_tool(query: str, post_id:str) -> str:
    """Tool for retrieving relevant documents from the vector store."""
    rag = RAGIndexer(pc, client)
    results = rag.retrieval(query, post_id=post_id, top_k=3)
    prompt = rag.build_prompt(query, results)
    return prompt

async def trademark_agent_runner(messages: List[dict],post_id:str) -> str:

    instructions=f"""Answer the user's question based on the result of retrieval by passing improve query and exact post_id:{post_id}. 
    Before using the retrieval tool, make sure to think step by step and decide what to search for. 
    If the retrieval result does not contain relevant information, respond with your best knowledge."""    

    trademark_agent = Agent(
        name="Trademark detector",
        model="gpt-4o-mini",
        instructions=instructions,   
        tools=[retrieval_tool], 
        model_settings=ModelSettings(temperature=0.1),
    )
    
    result = await Runner.run(trademark_agent, input=messages)
    return result.final_output