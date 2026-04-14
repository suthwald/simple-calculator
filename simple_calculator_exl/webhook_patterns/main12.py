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
    """
    Verify GitHub webhook signature using HMAC SHA256.
    """
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
    """
    Generate a JWT for GitHub App authentication.
    """
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
    """
    Fetch an installation access token for a GitHub App.
    """
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
# 📥 Fetch PR Files
# -----------------------------
async def fetch_pr_files(owner, repo, pr, token):
    """
    Retrieve files changed in a pull request.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/files"

    headers = {"Authorization": f"Bearer {token}"}

    files = []
    page = 1

    async with httpx.AsyncClient() as client:
        while True:
            res = await client.get(
                url,
                headers=headers,
                params={"page": page, "per_page": 100},
            )

            if res.status_code != 200:
                logger.error(res.text)
                raise HTTPException(500, "Failed to fetch PR files")

            data = res.json()
            print(f"Fetched page {page} with {len(data)} files")  # Debug log
            print("**"*50)
            print(f"Type of data: {type(data)}")  # Should be a list
            print("**"*50)
            print(f"Data sample: {data}")
            print("**"*50)
            if not data:
                break

            files.extend(data)
            page += 1

            if page > 10:
                break

    return files


# -----------------------------
# 🧠 Extract Changes (Improved)
# -----------------------------
def extract_changes(patch: str):
    """
    Extract added and removed lines from a Git patch.
    Properly trims the leading space after + / - for clean output.
    """
    added, removed = [], []

    if not patch:
        return added, removed

    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            # Remove '+' and the following space (GitHub patch format)
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
    """
    Post a comment on a pull request.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr}/comments"

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json={"body": message})


# -----------------------------
# ✅ Approve PR
# -----------------------------
async def approve_pr(owner, repo, pr, token):
    """
    Submit an approval review for a pull request.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews"

    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "event": "APPROVE",
        "body": "Auto-approved ✅"
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(url, headers=headers, json=payload)

    if res.status_code not in (200, 201):
        logger.error(f"Approval failed: {res.text}")


# -----------------------------
# ✅ Should Auto Approve
# -----------------------------
def should_auto_approve(files):
    """
    Determine whether a PR qualifies for automatic approval.
    """
    if len(files) > 20:
        return False
    if sum(f["deletions"] for f in files) > 200:
        return False
    return True


# -----------------------------
# 🔄 Process PR (Main Logic - Updated)
# -----------------------------
async def process_pr(owner, repo, pr, installation_id):
    """
    Main workflow for processing a pull request with the exact desired output format.
    """
    try:
        token = await get_installation_token(installation_id)

        files = await fetch_pr_files(owner, repo, pr, token)

        structured_files = []

        for f in files:
            added, removed = extract_changes(f.get("patch", ""))

            structured_files.append({
                "file": f["filename"],
                "status": f.get("status", "modified"),   # GitHub provides: added, modified, removed, renamed, etc.
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "changes": f.get("changes", 0),          # GitHub already gives total changes
                "added_lines": added,
                "removed_lines": removed,
            })

        # Final desired output structure
        output = {
            "pr_number": pr,
            "repository": f"{owner}/{repo}",
            "total_files": len(structured_files),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "files": structured_files
        }

        # Save to JSON file
        filename = f"changes_pr_{pr}.json"
        with open(filename, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"PR #{pr} changes saved to {filename}")

        # Comment on PR
        await comment_pr(
            owner,
            repo,
            pr,
            f"✅ Changes processed and saved to `{filename}`\n"
            f"Total files changed: **{len(structured_files)}**",
            token
        )

        # Auto-approve if criteria met
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
    """
    GitHub webhook endpoint for pull request events.
    """
    body = await request.body()

    verify_signature(body, x_hub_signature_256)

    payload = json.loads(body)

    logger.info(f"Event: {x_github_event}")

    if x_github_event != "pull_request":
        return {"msg": "ignored"}

    if payload.get("action") not in ["opened", "synchronize", "reopened"]:
        return {"msg": "ignored action"}

    installation = payload.get("installation")
    if not installation:
        logger.warning("No installation found in payload")
        return {"msg": "no installation"}

    installation_id = installation["id"]

    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pr = payload["pull_request"]["number"]

    background_tasks.add_task(
        process_pr,
        owner,
        repo,
        pr,
        installation_id
    )

    return {"status": "processing"}


# -----------------------------
# ❤️ Health Check
# -----------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}