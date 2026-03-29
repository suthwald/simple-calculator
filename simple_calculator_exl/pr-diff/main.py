import hmac
import hashlib
import os
import logging
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from dotenv import load_dotenv
import httpx

# Load env variables
load_dotenv()

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


# -----------------------------
# 🔐 Verify GitHub Signature
# -----------------------------
def verify_signature(payload_body: bytes, signature: str):
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    sha_name, sig = signature.split("=")
    if sha_name != "sha256":
        raise HTTPException(status_code=400, detail="Invalid signature format")

    mac = hmac.new(
        GITHUB_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )

    if not hmac.compare_digest(mac.hexdigest(), sig):
        raise HTTPException(status_code=403, detail="Invalid signature")


# -----------------------------
# 📥 Fetch PR Files (Paginated)
# -----------------------------
async def fetch_pr_files(owner: str, repo: str, pr_number: int):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    files = []
    page = 1

    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            response = await client.get(
                url,
                headers=headers,
                params={"page": page, "per_page": 100},
            )

            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to fetch PR files")

            data = response.json()
            if not data:
                break

            files.extend(data)
            page += 1

    return files


# -----------------------------
# 🧠 Extract Code Changes
# -----------------------------
def extract_changes(patch: str):
    added = []
    removed = []

    if not patch:
        return added, removed

    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    return added, removed


# -----------------------------
# 🔄 Process PR Changes
# -----------------------------
async def process_pr(owner: str, repo: str, pr_number: int):
    files = await fetch_pr_files(owner, repo, pr_number)

    structured_changes = []

    for f in files:
        added, removed = extract_changes(f.get("patch", ""))

        structured_changes.append({
            "file": f["filename"],
            "status": f["status"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "changes": f["changes"],
            "added_lines": added,
            "removed_lines": removed,
        })

    logger.info(f"Processed PR #{pr_number} with {len(structured_changes)} files")

    # 👉 You can store this in DB instead
    return structured_changes


# -----------------------------
# 🎯 Webhook Endpoint
# -----------------------------
@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    body = await request.body()

    # 🔐 Verify signature
    verify_signature(body, x_hub_signature_256)

    payload = await request.json()

    if x_github_event != "pull_request":
        return {"message": "Ignored event"}

    action = payload.get("action")
    if action not in ["opened", "synchronize", "reopened"]:
        return {"message": f"Ignored action {action}"}

    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pr_number = payload["pull_request"]["number"]

    # 🚀 Process in background
    background_tasks.add_task(process_pr, owner, repo, pr_number)

    return {
        "status": "accepted",
        "message": f"Processing PR #{pr_number}"
    }