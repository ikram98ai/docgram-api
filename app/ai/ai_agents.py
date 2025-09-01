from agents import (
    Agent,
    Runner,
    ModelSettings,
    function_tool,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
)
from openai.types.responses import ResponseTextDeltaEvent

from .rag import get_rag_instance
from typing import List
from ..config import settings


def get_model():
    gemini_client = AsyncOpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=settings.gemini_api_key,
    )

    model = OpenAIChatCompletionsModel(
        openai_client=gemini_client, model="gemini-2.0-flash-lite"
    )

    return model


async def agent_runner(messages: List[dict], post_id: str):
    instructions = f"""Answer the user's question based on the result of retrieval by passing improve query. 
    Before using the retrieval tool, make sure to think step by step and decide what to search for. 
    If the retrieval result does not contain relevant information, respond with your best knowledge."""

    @function_tool
    async def retrieval_tool(query: str) -> str:
        """Tool for retrieving relevant documents from the vector store."""
        print("Retrieval tool called with query:", query, "and post_id:", post_id)
        rag = get_rag_instance()
        results = rag.retrieval(query, post_id=post_id, top_k=3)
        prompt = rag.build_prompt(query, results)
        return prompt

    trademark_agent = Agent(
        name="Trademark detector",
        model=get_model(),
        instructions=instructions,
        tools=[retrieval_tool],
        model_settings=ModelSettings(temperature=0.1),
    )

    result = Runner.run_streamed(trademark_agent, input=messages)
    async for event in result.stream_events():
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            yield event.data.delta
