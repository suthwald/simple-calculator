import os
import json
from typing import List, Dict, Any
from atlassian import Confluence
import requests  # only for type hinting / raise_for_status

# ========================== CONFIGURATION ==========================
# Set these via environment variables (recommended) or hardcode for testing
CONFLUENCE_URL = os.getenv("CF_URL")          # e.g. "https://yourcompany.atlassian.net/wiki"
USERNAME = os.getenv("ACCOUNT")            # Email for Cloud
API_TOKEN = os.getenv("CF_TOKEN")             # API token or PAT
PAGE_ID = CONFLUENCE_PAGE_ID                         # ← CHANGE TO YOUR PAGE ID (as string)

# Optional: Chunking parameters
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
# ===================================================================

def adf_to_markdown(adf: Dict[str, Any]) -> str:
    """Convert Confluence ADF to clean Markdown. Protects code blocks perfectly."""
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
                if mtype == "strong":
                    text = f"**{text}**"
                elif mtype == "em":
                    text = f"*{text}*"
                elif mtype == "code":
                    text = f"`{text}`"
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
            return "> " + text.replace("\n", "\n> ") + "\n\n"

        elif node_type == "rule":
            return "---\n\n"

        # Recurse for other containers
        if content:
            return "".join(render_node(child) for child in content)
        return ""

    markdown_parts = [render_node(node) for node in adf.get("content", [])]
    return "".join(markdown_parts).strip()


def markdown_header_splitter(markdown: str, headers_to_split_on=None) -> List[Dict]:
    """Simple hierarchical chunker by headers. No LangChain needed."""
    if headers_to_split_on is None:
        headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]

    chunks = []
    current_chunk = {"content": [], "metadata": {}}
    lines = markdown.split("\n")

    for line in lines:
        is_header = False
        for prefix, key in headers_to_split_on:
            if line.strip().startswith(prefix + " "):
                # Save previous chunk
                if current_chunk["content"]:
                    full_text = "\n".join(current_chunk["content"]).strip()
                    current_chunk["content"] = full_text
                    chunks.append(current_chunk)

                # Start new chunk
                heading_text = line.strip()[len(prefix)+1:].strip()
                current_chunk = {
                    "content": [line],
                    "metadata": {key: heading_text}
                }
                is_header = True
                break

        if not is_header:
            if "content" not in current_chunk:
                current_chunk = {"content": [], "metadata": {}}
            current_chunk["content"].append(line)

    # Add the last chunk
    if current_chunk["content"]:
        full_text = "\n".join(current_chunk["content"]).strip()
        current_chunk["content"] = full_text
        chunks.append(current_chunk)

    return chunks


# ========================== MAIN SCRIPT ==========================
if __name__ == "__main__":
    if not all([CONFLUENCE_URL, USERNAME, API_TOKEN, PAGE_ID]):
        raise ValueError("Missing environment variables: CF_URL, CF_ACCOUNT, CF_TOKEN and set PAGE_ID")

    print(f"Fetching Confluence page ID: {PAGE_ID}")

    # 1. Initialize Confluence client (handles auth)
    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=USERNAME,
        password=API_TOKEN,
        cloud=True
    )

    # 2. Fetch page using v2 API via the session (ADF format)
    endpoint = f"/api/v2/pages/{PAGE_ID}?body-format=atlas_doc_format"
    full_url = f"{confluence.url.rstrip('/')}/{endpoint.lstrip('/')}"

    response = confluence._session.get(full_url)
    response.raise_for_status()

    data = response.json()

    # ADF value comes as escaped JSON string → parse it twice
    adf_str = data["body"]["atlas_doc_format"]["value"]
    adf_json = json.loads(adf_str)

    page_title = data.get("title", "Untitled Page")

    print(f"✅ Fetched: {page_title}")

    # 3. Convert ADF → Clean Markdown (code blocks are fully protected)
    clean_markdown = adf_to_markdown(adf_json)

    # Optional: Save raw markdown for debugging
    with open(f"{page_title.replace(' ', '_')}.md", "w", encoding="utf-8") as f:
        f.write(clean_markdown)

    print(f"Markdown length: {len(clean_markdown)} characters")

    # 4. Chunk the markdown hierarchically
    chunks = markdown_header_splitter(clean_markdown)

    print(f"Created {len(chunks)} chunks\n")

    # 5. Print sample chunks (especially useful to verify ASCII diagrams and code blocks)
    for i, chunk in enumerate(chunks[:5]):   # Show first 5
        print(f"--- Chunk {i+1} ---")
        print(f"Metadata: {chunk['metadata']}")
        print(chunk['content'][:800] + "..." if len(chunk['content']) > 800 else chunk['content'])
        print("\n")

    # Optional: Add rich metadata to all chunks
    for chunk in chunks:
        chunk["metadata"].update({
            "source": "Confluence",
            "page_id": PAGE_ID,
            "page_title": page_title,
            "chunk_type": "section"
        })

    # Save chunks to JSON (for vector DB ingestion)
    with open(f"{page_title.replace(' ', '_')}_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print("✅ Done! Chunks saved to JSON file.")
