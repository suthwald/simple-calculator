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

app = FastAPI(title="GitHub PR Bot (GitHub App)")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
APP_ID = os.getenv("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")

# Load private key
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

    mac = hmac.new(
        GITHUB_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )

    if not hmac.compare_digest(mac.hexdigest(), sig):
        raise HTTPException(403, "Invalid signature")


# -----------------------------
# 🔑 Generate JWT
# -----------------------------
def generate_jwt():
    payload = {
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "iss": APP_ID,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


# -----------------------------
# 🎟️ Get Installation Token
# -----------------------------
async def get_installation_token(installation_id: int):
    jwt_token = generate_jwt()

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers)

    if res.status_code != 201:
        logger.error(f"Token error: {res.text}")
        raise HTTPException(500, "Failed to generate installation token")

    return res.json()["token"]


# -----------------------------
# 📥 Fetch PR Files + PR Details
# -----------------------------
async def fetch_pr_details_and_files(owner, repo, pr, token):
    """Fetch PR details (for base/head SHA) and changed files."""
    # Get PR details for base.sha and head.sha
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        pr_res = await client.get(pr_url, headers=headers)
        if pr_res.status_code != 200:
            raise HTTPException(500, "Failed to fetch PR details")

        pr_data = pr_res.json()
        base_sha = pr_data["base"]["sha"]
        head_sha = pr_data["head"]["sha"]

        # Fetch changed files
        files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/files"
        files = []
        page = 1
        while True:
            res = await client.get(
                files_url,
                headers=headers,
                params={"page": page, "per_page": 100},
            )
            if res.status_code != 200:
                raise HTTPException(500, "Failed to fetch PR files")

            data = res.json()
            if not data:
                break
            files.extend(data)
            page += 1
            if page > 10:
                break

    return files, base_sha, head_sha


# -----------------------------
# 📄 Fetch Full File Content at Specific Commit
# -----------------------------
async def fetch_file_content(owner, repo, file_path, ref, token):
    """
    Fetch raw file content at a specific commit SHA or branch.
    Returns None if file does not exist at that ref.
    """
    if not file_path or not ref:
        return None

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={ref}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.raw"  # Raw text content
    }

    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)

        if res.status_code == 200:
            return res.text
        elif res.status_code == 404:
            return None  # File doesn't exist (new file or deleted)
        else:
            logger.warning(f"Failed to fetch {file_path} at ref {ref}: {res.status_code}")
            return None


# -----------------------------
# 🧠 Extract Changes
# -----------------------------
def extract_changes(patch: str):
    added, removed = [], []

    if not patch:
        return added, removed

    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].lstrip() if line[1:].startswith(" ") else line[1:]
            added.append(content)
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:].lstrip() if line[1:].startswith(" ") else line[1:]
            removed.append(content)

    return added, removed


# -----------------------------
# 💬 Comment on PR
# -----------------------------
async def comment_pr(owner, repo, pr, message, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr}/comments"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json={"body": message})


# -----------------------------
# ✅ Approve PR
# -----------------------------
async def approve_pr(owner, repo, pr, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"event": "APPROVE", "body": "Auto-approved ✅"}

    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers, json=payload)

    if res.status_code not in (200, 201):
        logger.error(f"Approval failed: {res.text}")


# -----------------------------
# ✅ Should Auto Approve
# -----------------------------
def should_auto_approve(files):
    if len(files) > 20:
        return False
    if sum(f.get("deletions", 0) for f in files) > 200:
        return False
    return True


# -----------------------------
# 🔄 Process PR (With Full Before & After Content)
# -----------------------------
async def process_pr(owner, repo, pr, installation_id):
    try:
        token = await get_installation_token(installation_id)

        files, base_sha, head_sha = await fetch_pr_details_and_files(owner, repo, pr, token)

        structured_files = []

        for f in files:
            filename = f["filename"]
            status = f.get("status", "modified")  # added, modified, removed, renamed, etc.

            added, removed = extract_changes(f.get("patch", ""))

            # Fetch full contents
            before_content = None
            after_content = None

            # For renamed files, before uses previous_filename
            before_path = f.get("previous_filename") or filename

            if status in ["modified", "removed", "renamed"]:
                before_content = await fetch_file_content(owner, repo, before_path, base_sha, token)

            if status in ["modified", "added", "renamed"]:
                after_content = await fetch_file_content(owner, repo, filename, head_sha, token)

            structured_files.append({
                "file": filename,
                "status": status,
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),
                "added_lines": added,
                "removed_lines": removed,
                "before_content": before_content,
                "after_content": after_content,
            })

        # Desired output structure
        output = {
            "pr_number": pr,
            "repository": f"{owner}/{repo}",
            "total_files": len(structured_files),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "files": structured_files
        }

        filename = f"changes_pr_{pr}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        logger.info(f"PR #{pr} full content saved to {filename}")

        await comment_pr(
            owner,
            repo,
            pr,
            f"✅ Full file contents (before & after) processed and saved to `{filename}`\n"
            f"Total files changed: **{len(structured_files)}**",
            token
        )

        if should_auto_approve(structured_files):
            await approve_pr(owner, repo, pr, token)
        else:
            logger.info(f"PR #{pr} not auto-approved")

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

    if x_github_event != "pull_request":
        return {"msg": "ignored"}

    if payload.get("action") not in ["opened", "synchronize", "reopened"]:
        return {"msg": "ignored action"}

    installation = payload.get("installation")
    if not installation:
        return {"msg": "no installation"}

    installation_id = installation["id"]
    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pr = payload["pull_request"]["number"]

    background_tasks.add_task(process_pr, owner, repo, pr, installation_id)

    return {"status": "processing"}


# -----------------------------
# ❤️ Health Check
# -----------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}