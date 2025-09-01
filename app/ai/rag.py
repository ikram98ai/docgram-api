import io
import logging
from markitdown import MarkItDown
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional, Tuple
from uuid import uuid4
from ..config import settings

()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
EMBED_MODEL = "text-embedding-004"
EMBED_DIM = 768
PINECONE_INDEX = "docgram-index"
PINECONE_REGION = "us-east-1"


def _smart_chunk_text(
    text: str, chunk_size: int, overlap: int
) -> List[Tuple[str, int, int]]:
    """
    Chunk text at word boundaries. Returns list of (chunk_text, start_offset, end_offset)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    tokens = text.split()  # simple whitespace tokenization (keeps code dependency-free)
    if not tokens:
        return []

    # Reconstruct windows of tokens up to approx chunk_size characters
    chunks = []
    token_positions = []  # store (token, start_pos, end_pos)
    pos = 0
    for token in tokens:
        # find next occurrence of token in text from pos
        find_at = text.find(token, pos)
        if find_at == -1:
            # fallback: approximate
            find_at = pos
        token_positions.append((token, find_at, find_at + len(token)))
        pos = find_at + len(token)

    i = 0
    n = len(token_positions)
    while i < n:
        # accumulate tokens until approx chunk_size
        start_pos = token_positions[i][1]
        chunk_tokens = []
        j = i
        end_pos = start_pos
        while j < n:
            token, s, e = token_positions[j]
            approx_len = e - start_pos
            if approx_len > chunk_size and chunk_tokens:
                break
            chunk_tokens.append(token)
            end_pos = e
            j += 1
        chunk_text = text[start_pos:end_pos]
        chunks.append((chunk_text.strip(), start_pos, end_pos))
        # advance i: go forward by token window minus overlap (in chars)
        # find next i such that token_positions[next_i].1 >= end_pos - overlap_chars
        overlap_target = max(start_pos, end_pos - overlap)
        next_i = j
        while next_i < n and token_positions[next_i][1] < overlap_target:
            next_i += 1
        if next_i == i:  # ensure progress
            next_i = j
        i = next_i
    return chunks


class RAGIndexer:
    def __init__(
        self,
        pinecone_client: Pinecone,
        openai_client: OpenAI,
        index_name: str = PINECONE_INDEX,
        embed_model: str = EMBED_MODEL,
        embed_dim: int = EMBED_DIM,
        pinecone_region: str = PINECONE_REGION,
    ):
        self.pc = pinecone_client
        self.client = openai_client
        self.index_name = index_name
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.region = pinecone_region

    def create_index_if_not_exists(self) -> None:
        if not self.pc.has_index(self.index_name):
            logger.info(f"Creating Pinecone index: {self.index_name}")
            spec = ServerlessSpec(cloud="aws", region=self.region)
            self.pc.create_index(
                self.index_name,
                vector_type="dense",
                metric="dotproduct",
                dimension=self.embed_dim,
                spec=spec,
            )
            logger.info("Index created.")

        # sanity: check dimension (best-effort)
        # NOTE: Pinecone SDK specific methods differ by version; adapt if required.
        logger.debug("Index exists or was created.")

    async def _extract_text_from_pdf(self, file_bytes: bytes) -> str:
        md = MarkItDown()
        buffer = io.BytesIO(file_bytes)
        result = md.convert(buffer)
        # Use filename without extension as prefix
        text_content = (
            result.text_content if hasattr(result, "text_content") else str(result)
        )
        return text_content

    async def pdf_to_chunks(
        self, pdf_bytes: bytes, chunk_size: int = 1000, overlap: int = 200
    ) -> List[Dict]:
        """
        Returns list of dicts:
            {"chunk_id": str, "text": str, "source": filename, "start": int, "end": int}
        """
        content = await self._extract_text_from_pdf(pdf_bytes)
        chunks_meta = _smart_chunk_text(content, chunk_size=chunk_size, overlap=overlap)
        chunks = []
        for idx, (chunk_text, start, end) in enumerate(chunks_meta):
            chunks.append(
                {
                    "chunk_id": f"{uuid4().hex}",
                    "text": chunk_text,
                    "start": start,
                    "end": end,
                    "length": end - start,
                }
            )
        return chunks

    def _batch_iter(self, items: List, batch_size: int):
        for i in range(0, len(items), batch_size):
            yield items[i : i + batch_size], i, min(i + batch_size, len(items))

    def _safe_create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for a list of texts with simple retries.
        """
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                res = self.client.embeddings.create(input=texts, model=self.embed_model)
                embeds = [record.embedding for record in res.data]
                return embeds
            except Exception as e:
                logger.warning(f"Embedding request failed (attempt {attempt}): {e}")
                if attempt == max_retries:
                    raise
        return []

    def upsert_chunks(
        self,
        chunks: List[Dict],
        title: str,
        post_id: Optional[str] = None,
        batch_size: int = 32,
    ) -> str:
        """
        Upsert chunks into pinecone. Returns summary dict with counts.
        """
        if not chunks:
            return {"upserted": 0}
        self.create_index_if_not_exists()
        index = self.pc.Index(self.index_name)

        total_upserted = 0
        for batch, start_idx, end_idx in self._batch_iter(chunks, batch_size):
            try:
                texts = [c["text"] for c in batch]
                ids = [c["chunk_id"] for c in batch]

                embeddings = self._safe_create_embeddings(texts)
                if len(embeddings) != len(texts):
                    raise RuntimeError("Embedding length mismatch")

                vectors = []
                for _id, emb, c in zip(ids, embeddings, batch):
                    metadata = {
                        "text": c.get("text"),
                        "post_id": post_id,
                        "source": title,
                        "start": c.get("start"),
                        "end": c.get("end"),
                        "length": c.get("length"),
                    }
                    vectors.append(
                        {"id": str(_id), "values": emb, "metadata": metadata}
                    )

                # Upsert
                _ = index.upsert(vectors=vectors)
                total_upserted += len(vectors)
                logger.info(
                    f"Upserted batch {start_idx}:{end_idx} -> {len(vectors)} vectors"
                )
            except Exception as e:
                logger.exception(f"Failed to upsert batch {start_idx}:{end_idx}: {e}")
                # continue with remaining batches
        return f"upserted {total_upserted} chunks"

    async def upsert_pdf(
        self,
        pdf_bytes: bytes,
        title: str,
        post_id: Optional[str] = None,
        chunk_size: int = 1000,
        overlap: int = 200,
        batch_size: int = 32,
    ) -> str:
        """
        High-level helper: read PDF (async UploadFile) and upsert chunks.
        This function is now async; await pdf.read before calling.
        """
        chunks = await self.pdf_to_chunks(
            pdf_bytes, chunk_size=chunk_size, overlap=overlap
        )
        return self.upsert_chunks(chunks, title, post_id=post_id, batch_size=batch_size)

    def retrieval(
        self,
        query_text: str,
        post_id: Optional[str] = None,
        top_k: int = 5,
        include_metadata: bool = True,
    ) -> List[Dict]:
        """
        Returns list of matches: {"id", "score", "metadata", "text"}
        """
        if not query_text:
            return []

        index = self.pc.Index(self.index_name)
        emb_res = self.client.embeddings.create(
            input=query_text, model=self.embed_model
        )
        dense_embedding = emb_res.data[0].embedding

        query_filter = {"post_id": post_id} if post_id is not None else None

        query_kwargs = {
            "vector": dense_embedding,
            "top_k": top_k,
            "include_metadata": include_metadata,
        }
        if query_filter:
            query_kwargs["filter"] = query_filter

        res = index.query(**query_kwargs)
        matches = (
            res.get("matches", [])
            if isinstance(res, dict)
            else getattr(res, "matches", [])
        )

        results = []
        for m in matches:
            metadata = (
                m.get("metadata", {})
                if isinstance(m, dict)
                else getattr(m, "metadata", {})
            )

            results.append(
                {
                    "id": m.get("id"),
                    "score": m.get(
                        "score",
                        m.get("payload", {}).get("score")
                        if isinstance(m, dict)
                        else None,
                    ),
                    "metadata": metadata,
                }
            )
        return results

    def build_prompt(
        self, query: str, contexts: List[Dict], max_context_chars: int = 4000
    ) -> str:
        """
        Build a prompt (context + query) for an LLM. Truncates contexts to the most relevant until char budget is reached.
        """
        assembled = ""
        for c in contexts:
            meta = c.get("metadata", {})
            src = meta.get("source", "unknown")
            snippet = meta.get("text") or meta.get("content") or ""
            candidate = f"Source: {src}\n{snippet}\n---\n"
            if len(assembled) + len(candidate) > max_context_chars:
                break
            assembled += candidate
        prompt = f"""You are an assistant. Use the following context to answer the user's question. Cite the 'Source' lines when relevant.

Context:
{assembled}

User question:
{query}

Answer concisely and cite sources where useful."""
        return prompt


def get_rag_instance() -> RAGIndexer:
    gemini_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    client = OpenAI(base_url=gemini_base_url, api_key=settings.gemini_api_key)
    pc = Pinecone(api_key=settings.pinecone_api_key)
    return RAGIndexer(pc, client)
