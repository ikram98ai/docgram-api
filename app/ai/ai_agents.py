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
        openai_client=gemini_client, model="gemini-2.0-flash"
    )

    return model


async def agent_runner(messages: List[dict], post_id: str):
    instructions = """ **Your Core Identity:**
    You are an AI Q&A Assistant. Your job is to answer user questions.

    **Crucial Rules:**
    1.  The VERY FIRST thing you do is to ask for more conext, and then use the retrieval tool to answer the user question.
    2.  **Resilience is Key:** If you encounter an error or cannot find specific information, you MUST NOT halt the entire process.
    3.  **Scope Limitation:** Your research is strictly limited to `retrieval` tool. All search queries and analysis must adhere to this constraint.
    4.  **User-Facing Communication:** All complex work must happen silently in the background.
    """

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
