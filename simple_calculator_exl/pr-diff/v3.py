import os
import json
from typing import List, Dict, Any
from atlassian import Confluence

# ========================== CONFIGURATION ==========================
CONFLUENCE_URL = os.getenv("CF_URL")
USERNAME = os.getenv("ACCOUNT")
API_TOKEN = os.getenv("CF_TOKEN")
PAGE_ID = CONFLUENCE_PAGE_ID                    # ← Set this or use os.getenv("CONFLUENCE_PAGE_ID")

SOURCE_NAME = "Confluence_Python_Coding_Standards"

# Chunking settings
MAX_CHUNK_SIZE = 1500      # characters
CHUNK_OVERLAP = 200        # ← NEW: Overlap between sub-chunks (recommended 150-300)

# ChromaDB settings
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "python_coding_standards"

# Embedding model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# ===================================================================

def adf_to_markdown(adf: Dict[str, Any]) -> str:
    """Convert ADF to Markdown while protecting code blocks (including # inside them)."""
    if not adf or adf.get("type") != "doc":
        return ""

    def render_node(node: Dict[str, Any]) -> str:
        node_type = node.get("type")
        content = node.get("content", [])
        attrs = node.get("attrs", {})
        marks = node.get("marks", [])

        if node_type == "heading":
            level = attrs.get("level", 1)
            text = "".join(render_node(child) for child in content)
            return f"{'#' * level} {text.strip()}\n\n"

        elif node_type == "paragraph":
            text = "".join(render_node(child) for child in content)
            return f"{text.strip()}\n\n" if text.strip() else ""

        elif node_type == "text":
            text = node.get("text", "")
            for mark in marks:
                mtype = mark.get("type")
                if mtype == "strong":   text = f"**{text}**"
                elif mtype == "em":     text = f"*{text}*"
                elif mtype == "code":   text = f"`{text}`"
            return text

        elif node_type == "codeBlock":
            language = attrs.get("language", "") or ""
            code = content[0].get("text", "") if content else ""
            return f"```{language}\n{code}\n```\n\n"

        elif node_type == "bulletList":
            items = [f"- {''.join(render_node(c) for c in item.get('content', [])).strip()}"
                     for item in content]
            return "\n".join(items) + "\n\n"

        elif node_type == "orderedList":
            items = [f"{i}. {''.join(render_node(c) for c in item.get('content', [])).strip()}"
                     for i, item in enumerate(content, 1)]
            return "\n".join(items) + "\n\n"

        elif node_type == "table":
            rows = []
            for row in content:
                if row.get("type") == "tableRow":
                    cells = ["".join(render_node(c) for c in cell.get("content", [])).strip()
                             for cell in row.get("content", [])]
                    rows.append("| " + " | ".join(cells) + " |")
            if rows:
                separator = "| " + " | ".join(["---"] * (len(rows[0].split("|")) - 2)) + " |"
                return rows[0] + "\n" + separator + "\n" + "\n".join(rows[1:]) + "\n\n"
            return ""

        elif node_type == "blockquote":
            text = "".join(render_node(child) for child in content)
            return "> " + "\n> ".join(text.splitlines()) + "\n\n"

        elif node_type == "rule":
            return "---\n\n"

        if content:
            return "".join(render_node(child) for child in content)
        return ""

    return "".join(render_node(node) for node in adf.get("content", [])).strip()


def create_structured_chunks(markdown: str, page_title: str, 
                           max_chunk_size: int = 1500, 
                           chunk_overlap: int = 200) -> List[Dict]:
    """Create chunks with header hierarchy + overlap for large sections."""
    chunks = []
    lines = markdown.split("\n")
    current_content = []
    current_header = page_title
    current_level = 1
    parent_section = page_title
    chunk_counter = 1

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("#"):
            # Save previous chunk
            if current_content:
                content_text = "\n".join(current_content).strip()
                if content_text:
                    chunks.append({
                        "chunk_id": f"chunk_{chunk_counter}",
                        "section_title": current_header,
                        "header_level": current_level,
                        "content": content_text,
                        "parent_section": parent_section,
                        "source": SOURCE_NAME
                    })
                    chunk_counter += 1

            # Update header and parent
            if stripped.startswith("### "):
                current_level = 3
                current_header = stripped[4:].strip()
            elif stripped.startswith("## "):
                current_level = 2
                current_header = stripped[3:].strip()
                parent_section = current_header
            elif stripped.startswith("# "):
                current_level = 1
                current_header = stripped[2:].strip()
                parent_section = current_header

            current_content = [line]
        else:
            current_content.append(line)

    # Final chunk
    if current_content:
        content_text = "\n".join(current_content).strip()
        if content_text:
            chunks.append({
                "chunk_id": f"chunk_{chunk_counter}",
                "section_title": current_header,
                "header_level": current_level,
                "content": content_text,
                "parent_section": parent_section,
                "source": SOURCE_NAME
            })

    # === Apply overlap when splitting large chunks ===
    final_chunks = []
    for chunk in chunks:
        content = chunk["content"]

        if len(content) <= max_chunk_size:
            final_chunks.append(chunk)
            continue

        # Split large chunk with overlap
        start = 0
        part_num = 1
        while start < len(content):
            end = min(start + max_chunk_size, len(content))
            part = content[start:end]

            new_chunk = {
                "chunk_id": f"{chunk['chunk_id']}_{part_num}",
                "section_title": chunk["section_title"],
                "header_level": chunk["header_level"],
                "content": part,
                "parent_section": chunk["parent_section"],
                "source": SOURCE_NAME
            }
            final_chunks.append(new_chunk)

            # Move forward with overlap
            if end >= len(content):
                break
            start = end - chunk_overlap
            part_num += 1

    return final_chunks


# ========================== CHROMA DB INTEGRATION ==========================
def store_in_chroma(chunks: List[Dict], page_title: str):
    """Store chunks in ChromaDB using Sentence Transformers"""
    try:
        from chromadb import PersistentClient
        from chromadb.utils import embedding_functions
    except ImportError:
        print("❌ Please install: pip install chromadb sentence-transformers")
        return

    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    client = PersistentClient(path=CHROMA_PERSIST_DIR)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"Storing {len(chunks)} chunks into collection: {COLLECTION_NAME}")

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["content"])
        metadatas.append({
            "chunk_id": chunk["chunk_id"],
            "section_title": chunk["section_title"],
            "header_level": chunk["header_level"],
            "parent_section": chunk["parent_section"],
            "source": chunk["source"],
            "page_title": page_title
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"✅ Successfully stored {len(chunks)} chunks in ChromaDB!")
    print(f"   Collection : {COLLECTION_NAME}")
    print(f"   Location   : {CHROMA_PERSIST_DIR}")


# ========================== MAIN EXECUTION ==========================
if __name__ == "__main__":
    if not all([CONFLUENCE_URL, USERNAME, API_TOKEN, PAGE_ID]):
        print("❌ Missing environment variables. Set CF_URL, ACCOUNT, CF_TOKEN, CONFLUENCE_PAGE_ID")
        exit(1)

    print(f"Fetching Confluence page: {PAGE_ID}")

    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=USERNAME,
        password=API_TOKEN,
        cloud=True
    )

    endpoint = f"api/v2/pages/{PAGE_ID}?body-format=atlas_doc_format"
    full_url = f"{confluence.url.rstrip('/')}/{endpoint.lstrip('/')}"

    response = confluence._session.get(full_url)
    response.raise_for_status()

    data = response.json()
    adf_str = data["body"]["atlas_doc_format"]["value"]
    adf_json = json.loads(adf_str)

    page_title = data.get("title", "Untitled")
    print(f"✅ Fetched page: {page_title}")

    clean_markdown = adf_to_markdown(adf_json)

    # Create chunks with overlap
    chunks = create_structured_chunks(
        clean_markdown, 
        page_title, 
        max_chunk_size=MAX_CHUNK_SIZE, 
        chunk_overlap=CHUNK_OVERLAP
    )

    print(f"✅ Created {len(chunks)} chunks (with overlap)")

    # Save JSON backup
    output_file = f"{page_title.replace(' ', '_')}_chunks.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    # Store in ChromaDB
    store_in_chroma(chunks, page_title)

    # Preview
    print("\nPreview of first 2 chunks:")
    for chunk in chunks[:2]:
        print(f"\n--- {chunk['chunk_id']} | {chunk['section_title']} (H{chunk['header_level']}) ---")
        preview = chunk['content'][:400] + "..." if len(chunk['content']) > 400 else chunk['content']
        print(preview)
