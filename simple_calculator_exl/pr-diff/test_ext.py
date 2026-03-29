from atlassian import Confluence
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup

load_dotenv()

url = os.getenv("CF_URL")
token = os.getenv("CF_TOKEN")
account = os.getenv("ACCOUNT")

confluence = Confluence(
    url=url,
    username=account,
    password=token
)

page = confluence.get_page_by_id(
    page_id=65720,
    expand='body.storage'
)

html_content = page['body']['storage']['value']

# 🔽 Parse HTML
soup = BeautifulSoup(html_content, "lxml")

# ✅ Extract clean text
text = soup.get_text(separator="\n", strip=True)

print(text)