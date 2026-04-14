import hmac
import hashlib
import os
import logging
import json
import time
import jwt
import httpx
import datetime

from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from dotenv import load_dotenv

# -----------------------------
# 🔧 Setup
# -----------------------------
load_dotenv()

app = FastAPI(title="GitHub PR Bot (Snippet Mode)")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")

with open(PRIVATE_KEY_PATH, "r") as f:
    PRIVATE_KEY = f.read()

# -----------------------------
# 🔐 Verify Signature
# -----------------------------
def verify_signature(payload_body: bytes, signature: str):
    if not signature:
        raise HTTPException(400, "Missing signature")
    try:
        sha_name, sig = signature.split("=")
    except ValueError:
        raise HTTPException(400, "Invalid signature format")
    if sha_name != "sha256":
        raise HTTPException(400, "Unsupported signature type")

    mac = hmac.new(GITHUB_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    if not hmac.compare_digest(mac.hexdigest(), sig):
        raise HTTPException(403, "Invalid signature")

# -----------------------------
# 🔑 Auth Helpers (JWT & Token)
# -----------------------------
def generate_jwt():
    payload = {"iat": int(time.time()), "exp": int(time.time()) + 600, "iss": APP_ID}
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

async def get_installation_token(installation_id: int):
    jwt_token = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {"Authorization": f"Bearer {jwt_token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers)
    if res.status_code != 201:
        raise HTTPException(500, "Failed to generate installation token")
    return res.json()["token"]

# -----------------------------
# 📄 Content Fetching
# -----------------------------
async def fetch_file_content(owner, repo, path, ref, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3.raw"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers, params={"ref": ref})
        return res.text if res.status_code == 200 else None

async def fetch_pr_files(owner, repo, pr, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/files"
    headers = {"Authorization": f"Bearer {token}"}
    files = []
    page = 1
    async with httpx.AsyncClient() as client:
        while True:
            res = await client.get(url, headers=headers, params={"page": page, "per_page": 100})
            data = res.json()
            if not data or res.status_code != 200: break
            files.extend(data)
            page += 1
    return files

# -----------------------------
# 🧠 Extract Changes as SNIPPETS
# -----------------------------
def extract_changes_as_snippets(patch: str):
    """
    Extracts changes and returns them as formatted code blocks (strings).
    """
    added_lines = []
    removed_lines = []

    if not patch:
        return "", ""

    for line in patch.split("\n"):
        # We check for '+' or '-' but exclude the '+++' or '---' file headers
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:]) 
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines.append(line[1:])

    # Join list into a single string with newlines
    added_snippet = "\n".join(added_lines)
    removed_snippet = "\n".join(removed_lines)

    return added_snippet, removed_snippet

# -----------------------------
# 🔄 Process PR logic
# -----------------------------
async def process_pr(owner, repo, pr, installation_id, head_sha, base_sha):
    try:
        token = await get_installation_token(installation_id)
        files = await fetch_pr_files(owner, repo, pr, token)

        structured_files = []

        for f in files:
            filename = f["filename"]
            # Get changes as snippets instead of lists
            added_snippet, removed_snippet = extract_changes_as_snippets(f.get("patch", ""))
            
            # Fetch 'Before' (base) and 'After' (head) content
            before_content = await fetch_file_content(owner, repo, filename, base_sha, token)
            after_content = await fetch_file_content(owner, repo, filename, head_sha, token)

            structured_files.append({
                "file": filename,
                "status": f.get("status", "modified"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "added_lines": added_snippet,    # Now a multiline string
                "removed_lines": removed_snippet, # Now a multiline string
                "before_content": before_content,
                "after_content": after_content
            })

        output = {
            "pr_number": pr,
            "repository": f"{owner}/{repo}",
            "total_files": len(structured_files),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "files": structured_files
        }

        with open(f"changes_pr_{pr}.json", "w") as f_out:
            json.dump(output, f_out, indent=2)

        logger.info(f"Processed PR #{pr} with code snippets.")

    except Exception as e:
        logger.error(f"Error processing PR #{pr}: {e}", exc_info=True)

# -----------------------------
# 🎯 Webhook Endpoint
# -----------------------------
@app.post("/webhook/github")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    body = await request.body()
    verify_signature(body, x_hub_signature_256)
    payload = json.loads(body)

    if x_github_event == "pull_request" and payload.get("action") in ["opened", "synchronize", "reopened"]:
        installation_id = payload["installation"]["id"]
        owner = payload["repository"]["owner"]["login"]
        repo = payload["repository"]["name"]
        pr = payload["pull_request"]["number"]
        
        # head = current PR state, base = what it's being merged into (the 'before')
        head_sha = payload["pull_request"]["head"]["sha"]
        base_sha = payload["pull_request"]["base"]["sha"]

        background_tasks.add_task(process_pr, owner, repo, pr, installation_id, head_sha, base_sha)

    return {"status": "accepted"}