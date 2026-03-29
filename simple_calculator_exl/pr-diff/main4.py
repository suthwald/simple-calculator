import hmac
import hashlib
import os
import logging
import json
from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from dotenv import load_dotenv
import httpx

# -----------------------------
# 🔧 Setup
# -----------------------------
load_dotenv()

app = FastAPI(title="GitHub PR Webhook Processor")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_SECRET or not GITHUB_TOKEN:
    logger.warning("Missing GITHUB_WEBHOOK_SECRET or GITHUB_TOKEN in .env")


# -----------------------------
# 🔐 Verify GitHub Signature
# -----------------------------
def verify_signature(payload_body: bytes, signature: str):
    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256 header")

    try:
        sha_name, sig = signature.split("=")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature format")

    if sha_name != "sha256":
        raise HTTPException(status_code=400, detail="Only sha256 signature is supported")

    mac = hmac.new(
        GITHUB_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )

    if not hmac.compare_digest(mac.hexdigest(), sig):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")


# -----------------------------
# 📥 Fetch PR Files
# -----------------------------
async def fetch_pr_files(owner: str, repo: str, pr_number: int):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    files = []
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            response = await client.get(
                url, headers=headers, params={"page": page, "per_page": 100}
            )

            if response.status_code != 200:
                logger.error(f"GitHub API error: {response.status_code}")
                raise HTTPException(status_code=500, detail="Failed to fetch PR files")

            data = response.json()
            if not data:
                break
            files.extend(data)
            page += 1
            if page > 10:
                break

    return files


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
# 📤 Create Gist for Downloadable JSON
# -----------------------------
async def create_gist_for_pr(owner: str, repo: str, pr_number: int, structured_changes: list):
    filename = f"pr_{pr_number}_changes.json"

    gist_data = {
        "description": f"PR #{pr_number} changes in {owner}/{repo}",
        "public": False,           # Secret gist (only people with link can view)
        "files": {
            filename: {
                "content": json.dumps({
                    "pr_number": pr_number,
                    "repository": f"{owner}/{repo}",
                    "total_files": len(structured_changes),
                    "generated_at": "auto",
                    "files": structured_changes
                }, indent=2, ensure_ascii=False)
            }
        }
    }

    url = "https://api.github.com/gists"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=gist_data)

        if response.status_code == 201:
            gist_url = response.json()["html_url"]
            raw_url = response.json()["files"][filename]["raw_url"]
            logger.info(f"Gist created successfully for PR #{pr_number}")
            return gist_url, raw_url
        else:
            logger.error(f"Gist creation failed: {response.text}")
            return None, None
    except Exception as e:
        logger.error(f"Exception creating Gist: {e}")
        return None, None


# -----------------------------
# 💬 Post Comment with Download Link
# -----------------------------
async def post_comment_to_pr(owner: str, repo: str, pr_number: int, gist_url: str = None, raw_url: str = None):
    if gist_url and raw_url:
        comment_body = f"""## ✅ PR Changes Analysis Complete

I have processed the code changes in this pull request.

**Download Full Changes:**
- [📥 Download JSON Report (Raw)]({raw_url})
- [View on Gist]({gist_url})

The report includes:
- List of all changed files
- Number of additions/deletions per file
- Exact added and removed lines

---

*This is an automated comment from the GitHub Webhook Processor.*
"""
    else:
        comment_body = f"""## ✅ PR Changes Processed

Changes have been analyzed and saved for PR #{pr_number}.

Unfortunately, I couldn't generate a downloadable link at this moment. Please check server logs for details.

---

*Automated comment*
"""

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json={"body": comment_body})

        if response.status_code in (201, 200):
            logger.info(f"✅ Comment posted successfully on PR #{pr_number}")
        else:
            logger.warning(f"Failed to post comment: {response.status_code}")
    except Exception as e:
        logger.error(f"Error posting comment: {e}")


# -----------------------------
# 🔄 Main Processing
# -----------------------------
async def safe_process_pr(owner: str, repo: str, pr_number: int):
    try:
        await process_pr(owner, repo, pr_number)
    except Exception as e:
        logger.error(f"Failed processing PR #{pr_number}", exc_info=True)


async def process_pr(owner: str, repo: str, pr_number: int):
    logger.info(f"Processing PR #{pr_number} in {owner}/{repo}")

    files = await fetch_pr_files(owner, repo, pr_number)

    structured_changes = []
    for f in files:
        added, removed = extract_changes(f.get("patch", ""))
        structured_changes.append({
            "file": f["filename"],
            "status": f["status"],
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
            "added_lines": added,
            "removed_lines": removed,
        })

    # Create Gist + Post Comment
    gist_url, raw_url = await create_gist_for_pr(owner, repo, pr_number, structured_changes)
    
    await post_comment_to_pr(owner, repo, pr_number, gist_url, raw_url)

    logger.info(f"Completed processing for PR #{pr_number}")


# -----------------------------
# 🎯 Webhook Endpoint
# -----------------------------
@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
):
    body = await request.body()
    verify_signature(body, x_hub_signature_256)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if x_github_event == "ping":
        return {"message": "pong"}

    if x_github_event != "pull_request":
        return {"message": "Ignored: Not a pull_request event"}

    action = payload.get("action")
    if action not in ["opened", "synchronize", "reopened", "edited"]:
        return {"message": f"Ignored action: {action}"}

    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pr_number = payload["pull_request"]["number"]

    logger.info(f"Webhook received: PR #{pr_number} [{action}] → {owner}/{repo}")

    background_tasks.add_task(safe_process_pr, owner, repo, pr_number)

    return {"status": "accepted", "message": f"Processing PR #{pr_number}"}


@app.get("/health")
async def health():
    return {"status": "healthy"}