import hmac
import hashlib
import os
import logging
import json
import time
import jwt
import httpx
import datetime
import asyncio

from fastapi import FastAPI, Request, HTTPException, Header, BackgroundTasks
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
# 🔑 Generate JWT (Fixed for clock skew)
# -----------------------------
def generate_jwt():
    now = int(time.time()) - 30          # 30 seconds in the past
    payload = {
        "iat": now,
        "exp": now + 600,                # exactly 10 minutes (GitHub maximum)
        "iss": APP_ID,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


# -----------------------------
# 🎟️ Get Installation Token
# -----------------------------
async def get_installation_token(installation_id: int, client: httpx.AsyncClient):
    jwt_token = generate_jwt()

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }

    res = await client.post(url, headers=headers)

    if res.status_code != 201:
        logger.error(f"Token generation failed: {res.status_code} - {res.text}")
        raise HTTPException(500, "Failed to generate installation token")

    return res.json()["token"]


# -----------------------------
# 📄 Fetch Full File Content (with retry)
# -----------------------------
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.5, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException)),
    reraise=True,
)
async def fetch_file_content(owner: str, repo: str, file_path: str, ref: str, token: str, client: httpx.AsyncClient):
    if not file_path or not ref:
        return None

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={ref}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3.raw"
    }

    res = await client.get(url, headers=headers)

    if res.status_code == 200:
        return res.text
    elif res.status_code == 404:
        logger.info(f"File not found (404): {file_path} at ref {ref}")
        return None
    else:
        logger.warning(f"Failed to fetch {file_path} at ref {ref}: {res.status_code}")
        return None


# -----------------------------
# 📥 Fetch PR Details + Files + Branches
# -----------------------------
async def fetch_pr_details_and_files(owner, repo, pr, token, client):
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}"

    pr_res = await client.get(pr_url, headers={"Authorization": f"Bearer {token}"})
    if pr_res.status_code != 200:
        raise HTTPException(500, f"Failed to fetch PR details: {pr_res.status_code}")

    pr_data = pr_res.json()

    pr_title = pr_data.get("title", "")
    pr_description = pr_data.get("body", "") or ""
    base_branch = pr_data["base"]["ref"]
    head_branch = pr_data["head"]["ref"]
    base_sha = pr_data["base"]["sha"]
    head_sha = pr_data["head"]["sha"]

    # Fetch changed files
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/files"
    files = []
    page = 1
    while True:
        res = await client.get(
            files_url,
            headers={"Authorization": f"Bearer {token}"},
            params={"page": page, "per_page": 100}
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

    return files, base_sha, head_sha, pr_title, pr_description, base_branch, head_branch


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
async def comment_pr(owner, repo, pr, message, token, client):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr}/comments"
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.post(url, headers=headers, json={"body": message})
    if res.status_code not in (200, 201):
        logger.error(f"Comment failed: {res.status_code} - {res.text[:300]}")


# -----------------------------
# ✅ Approve PR
# -----------------------------
async def approve_pr(owner, repo, pr, token, client):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"event": "APPROVE", "body": "Auto-approved ✅"}

    res = await client.post(url, headers=headers, json=payload)
    if res.status_code not in (200, 201):
        logger.error(f"Approval failed: {res.status_code} - {res.text[:300]}")
    else:
        logger.info(f"PR #{pr} successfully approved")


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
# 🔄 Process PR
# -----------------------------
async def process_pr(owner, repo, pr, installation_id):
    timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        try:
            token = await get_installation_token(installation_id, client)

            # Fetch PR details + files
            files, base_sha, head_sha, pr_title, pr_description, base_branch, head_branch = \
                await fetch_pr_details_and_files(owner, repo, pr, token, client)

            structured_files = []
            semaphore = asyncio.Semaphore(5)

            async def fetch_file_safe(path: str, ref: str):
                async with semaphore:
                    return await fetch_file_content(owner, repo, path, ref, token, client)

            for f in files:
                filename = f["filename"]
                status = f.get("status", "modified")
                added, removed = extract_changes(f.get("patch", ""))

                before_path = f.get("previous_filename") or filename
                before_content = None
                after_content = None

                if status in ["modified", "removed", "renamed"]:
                    before_content = await fetch_file_safe(before_path, base_sha)

                if status in ["modified", "added", "renamed"]:
                    after_content = await fetch_file_safe(filename, head_sha)

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

            # Save JSON
            output = {
                "pr_number": pr,
                "repository": f"{owner}/{repo}",
                "pr_title": pr_title,
                "pr_description": pr_description,
                "base_branch": base_branch,
                "head_branch": head_branch,
                "total_files": len(structured_files),
                "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
                "files": structured_files
            }

            json_filename = f"changes_pr_{pr}.json"
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            logger.info(f"PR #{pr} processed and saved to {json_filename}")

            # Comment on PR
            await comment_pr(
                owner, repo, pr,
                f"✅ **PR Processed Successfully**\n\n"
                f"**Title:** {pr_title}\n\n"
                f"**Description:**\n{pr_description if pr_description else '_No description provided_'}\n\n"
                f"**Base Branch:** `{base_branch}` → **Head Branch:** `{head_branch}`\n\n"
                f"Full file contents saved to `{json_filename}`\n"
                f"Total files changed: **{len(structured_files)}**",
                token, client
            )

            # Auto approve if small
            if should_auto_approve(structured_files):
                await approve_pr(owner, repo, pr, token, client)
            else:
                logger.info(f"PR #{pr} not auto-approved (too large)")

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