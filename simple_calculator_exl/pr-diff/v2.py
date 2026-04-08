import os
import json
import uuid
from typing import List, Dict, Any
from atlassian import Confluence

# ========================== CONFIGURATION ==========================
CONFLUENCE_URL = os.getenv("CF_URL")
USERNAME = os.getenv("ACCOUNT")
API_TOKEN = os.getenv("CF_TOKEN")
PAGE_ID = CONFLUENCE_PAGE_ID                    # ← Change this

SOURCE_NAME = "Confluence_Python_Coding_Standards"

# Chunking settings
MAX_CHUNK_SIZE = 1500   # characters (adjust based on your embedding model)
# ===================================================================

def adf_to_markdown(adf: Dict[str, Any]) -> str:
    """Convert ADF to Markdown while protecting code blocks."""
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


def create_structured_chunks(markdown: str, page_title: str) -> List[Dict]:
    """Create chunks in your desired JSON format"""
    chunks = []
    lines = markdown.split("\n")
    current_content = []
    current_header = page_title
    current_level = 1
    parent_section = page_title
    chunk_counter = 1

    for line in lines:
        stripped = line.strip()

        # Detect headings
        if stripped.startswith("#"):
            # Save previous chunk if it has content
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

            # Update current header
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

            current_content = [line]   # start new chunk with heading

        else:
            current_content.append(line)

    # Add the final chunk
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

    # Optional: Post-process to merge very small chunks or split very large ones
    final_chunks = []
    for chunk in chunks:
        if len(chunk["content"]) > MAX_CHUNK_SIZE and chunk["header_level"] >= 2:
            # Simple split for very large chunks (e.g., big ASCII diagrams)
            parts = [chunk["content"][i:i+MAX_CHUNK_SIZE] 
                    for i in range(0, len(chunk["content"]), MAX_CHUNK_SIZE)]
            for i, part in enumerate(parts):
                final_chunks.append({
                    "chunk_id": f"{chunk['chunk_id']}_{i+1}",
                    "section_title": chunk["section_title"],
                    "header_level": chunk["header_level"],
                    "content": part,
                    "parent_section": chunk["parent_section"],
                    "source": SOURCE_NAME
                })
        else:
            final_chunks.append(chunk)

    return final_chunks


# ========================== MAIN EXECUTION ==========================
if __name__ == "__main__":
    if not all([CONFLUENCE_URL, USERNAME, API_TOKEN, PAGE_ID]):
        print("❌ Missing environment variables. Set CF_URL, CF_ACCOUNT, CF_TOKEN")
        exit(1)

    print(f"Fetching Confluence page: {PAGE_ID}")

    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=USERNAME,
        password=API_TOKEN,
        cloud=True
    )

    # Fetch ADF
    endpoint = f"api/v2/pages/{PAGE_ID}?body-format=atlas_doc_format"
    full_url = f"{confluence.url.rstrip('/')}/{endpoint.lstrip('/')}"

    response = confluence._session.get(full_url)
    response.raise_for_status()

    data = response.json()
    adf_str = data["body"]["atlas_doc_format"]["value"]
    adf_json = json.loads(adf_str)

    page_title = data.get("title", "Untitled")

    print(f"✅ Fetched page: {page_title}")

    # Convert to Markdown
    clean_markdown = adf_to_markdown(adf_json)

    # Create structured chunks
    chunks = create_structured_chunks(clean_markdown, page_title)

    print(f"✅ Created {len(chunks)} chunks")

    # Save to JSON
    output_file = f"{page_title.replace(' ', '_')}_chunks.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    print(f"✅ Chunks saved to: {output_file}")

    # Preview first 3 chunks
    for chunk in chunks[:3]:
        print(f"\n--- {chunk['chunk_id']} | {chunk['section_title']} (H{chunk['header_level']}) ---")
        print(chunk['content'][:500] + "..." if len(chunk['content']) > 500 else chunk['content'])
