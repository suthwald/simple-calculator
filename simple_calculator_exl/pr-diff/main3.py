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

if not GITHUB_SECRET:
    logger.warning("GITHUB_WEBHOOK_SECRET is not set!")
if not GITHUB_TOKEN:
    logger.warning("GITHUB_TOKEN is not set!")


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
        logger.warning("Invalid webhook signature received")
        raise HTTPException(status_code=403, detail="Invalid signature")


# -----------------------------
# 📥 Fetch PR Files (Paginated)
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
                url,
                headers=headers,
                params={"page": page, "per_page": 100},
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch PR files: {response.status_code} - {response.text}")
                raise HTTPException(status_code=500, detail="Failed to fetch PR files from GitHub")

            data = response.json()
            if not data:
                break

            files.extend(data)
            page += 1

            if page > 10:  # Safety limit (~1000 files)
                logger.warning(f"PR #{pr_number} has too many files. Stopping pagination.")
                break

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
# 💬 Post Comment to Pull Request
# -----------------------------
async def post_comment_to_pr(owner: str, repo: str, pr_number: int, json_filename: str):
    comment_body = f"""## PR Changes Processed ✅

I have analyzed the changes in this pull request and saved a detailed report.

**Summary:**
- **Repository**: `{owner}/{repo}`
- **PR Number**: #{pr_number}
- **Files Changed**: {len(open(json_filename).readlines()) if os.path.exists(json_filename) else 'N/A'} (see attached JSON for full details)

The structured changes have been saved to: **`{json_filename}`**

You can download or view the full diff (added/removed lines per file) from the server.

---

*This comment was generated automatically by the GitHub Webhook Processor.*
"""

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = {"body": comment_body}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code in (201, 200):
            logger.info(f"Successfully posted comment on PR #{pr_number}")
        else:
            logger.error(f"Failed to post comment: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exception while posting comment to PR #{pr_number}: {e}")


# -----------------------------
# 🔄 Process PR Changes
# -----------------------------
async def safe_process_pr(owner: str, repo: str, pr_number: int):
    try:
        await process_pr(owner, repo, pr_number)
    except Exception as e:
        logger.error(f"Failed to process PR #{pr_number} in {owner}/{repo}", exc_info=True)


async def process_pr(owner: str, repo: str, pr_number: int):
    logger.info(f"Starting processing PR #{pr_number} in {owner}/{repo}")

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
            "blob_url": f.get("blob_url"),
        })

    # Save to JSON
    filename = f"changes_pr_{pr_number}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "pr_number": pr_number,
                "repository": f"{owner}/{repo}",
                "total_files": len(structured_changes),
                "files": structured_changes
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"Successfully saved changes to {filename}")

        # Post comment after successful save
        await post_comment_to_pr(owner, repo, pr_number, filename)

    except Exception as e:
        logger.error(f"Failed to save JSON or post comment for PR #{pr_number}: {e}")


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

    logger.info(f"Received PR #{pr_number} [{action}] in {owner}/{repo}")

    background_tasks.add_task(safe_process_pr, owner, repo, pr_number)

    return {
        "status": "accepted",
        "message": f"Processing PR #{pr_number} ({action})"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "github-pr-webhook-processor"}