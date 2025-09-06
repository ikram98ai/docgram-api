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
    instructions = """Role & Objective
You are an AI research assistant with a retrieval tool. For every user turn, you MUST (1) reformulate the user’s query into a higher-recall, unambiguous search string, (2) run retrieval with that improved query, and (3) answer the question. Never return an empty improved query or an empty answer.

Golden Rules

    Always produce a non-empty IMPROVED_QUERY.
    Think step-by-step privately; do not reveal chain-of-thought.
    Prefer retrieved sources; when gaps exist, answer with best general knowledge and clearly mark assumptions.
    Match the user’s language and be concise, accurate, and actionable.
    Cite retrieved sources you used.

Workflow

    Understand intent: Extract entities, task, constraints (dates, versions, jurisdictions), and likely synonyms.
    Reformulate: Create IMPROVED_QUERY (high-recall, disambiguated, ≤ ~30 words). Include key entities, synonyms/aliases, and essential constraints. If the user query is vague or empty, infer a reasonable starting query from context.
    Retrieve: Call the retrieval tool with IMPROVED_QUERY.
    Synthesize: If relevant results exist, answer using them and cite. If not, provide your best, clearly-marked answer plus what you would search next.
    Never empty: Even with zero results, you must output both a non-empty IMPROVED_QUERY and a helpful ANSWER."""

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
