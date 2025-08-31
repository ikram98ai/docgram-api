import os
import io
import uuid
from markitdown import MarkItDown
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from fastapi import UploadFile

load_dotenv()

# Initialize clients and configuration from environment variables
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "docgram-index")
EMBED_DIM = int(os.getenv("PINECONE_DIM", 1536))
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

client = OpenAI()
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

def create_index():
    """Creates the Pinecone index if it doesn't already exist."""
    if PINECONE_INDEX not in pc.list_indexes().names():
        print(f"Creating Pinecone index: {PINECONE_INDEX}")
        spec = ServerlessSpec(cloud="aws", region=PINECONE_REGION)
        pc.create_index(
            name=PINECONE_INDEX,
            dimension=EMBED_DIM,
            metric="cosine",  # Cosine similarity is often better for normalized embeddings
            spec=spec
        )
        print(f"Successfully Created Pinecone index: {PINECONE_INDEX}")

# Call create_index at the module level to ensure the index exists when the app starts.
create_index()

async def upsert_data(pdf: UploadFile, post_id: str) -> str:
    """
    Processes a PDF file, chunks its content, creates embeddings, and upserts them to Pinecone.
    """
    index = pc.Index(PINECONE_INDEX)
    md = MarkItDown()

    try:
        file_bytes = await pdf.read()
        buffer = io.BytesIO(file_bytes)
        
        # Convert PDF to markdown and then get text content
        result = md.convert(buffer)
        
        # Chunk the text content by paragraphs
        chunks = result.text_content.split('\n\n')
        
        batch_size = 32
        vectors_to_upsert = []

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            
            # Filter out empty chunks
            batch_chunks = [chunk for chunk in batch_chunks if chunk.strip()]
            if not batch_chunks:
                continue

            # Create embeddings for the current batch.
            res = client.embeddings.create(input=batch_chunks, model=EMBED_MODEL)
            embeds = [record.embedding for record in res.data]
            
            # Prepare vectors for upsert
            for chunk, dense_embedding in zip(batch_chunks, embeds):
                vectors_to_upsert.append({
                    "id": str(uuid.uuid4()),
                    "values": dense_embedding,
                    "metadata": {"content": chunk, "post_id": post_id}
                })

        # Upsert all vectors in a single call if possible, or batch if the list is too large
        if vectors_to_upsert:
            index.upsert(vectors=vectors_to_upsert)

        print(f"Upsert of {len(vectors_to_upsert)} vectors for post_id '{post_id}' completed successfully.")
        return f"Upsert of {len(vectors_to_upsert)} vectors completed successfully."

    except Exception as e:
        print(f"Error during upsert for post_id '{post_id}': {e}")
        return f"Error during upsert: {e}"


def search_index(query_text: str, post_id: str, top_k: int = 3) -> list[dict]:
    """Search index for a given query and post_id, returning matches with metadata."""
    index = pc.Index(PINECONE_INDEX)

    # Generate embedding for the query text
    response = client.embeddings.create(input=[query_text], model=EMBED_MODEL)
    dense_embedding = response.data[0].embedding

    query_params = {
        "vector": dense_embedding,
        "top_k": top_k,
        "include_metadata": True,
        "filter": {"post_id": post_id}
    }

    res = index.query(**query_params)
    matches = res.get("matches", [])
    
    return [{**m.get("metadata", {}), "score": m.get("score"), "id": m.get("id")} for m in matches]

def retrieval(query_text: str, post_id: str) -> str:
    """Retrieves relevant context from the index for a given query and post_id."""
    matches = search_index(query_text, post_id)

    final_context = ""
    for match in matches:
        final_context += f"Source: {match.get('source', 'N/A')}\n"
        final_context += f"{match.get('content', '')}\n---\n"

    return final_context