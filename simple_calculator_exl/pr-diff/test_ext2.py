from atlassian import Confluence
from dotenv import load_dotenv
import os
from markdownify import markdownify as md

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
    page_id=1048577,
    expand='body.storage'
)

html_content = page['body']['storage']['value']

# 🔽 Convert HTML → Markdown
markdown = md(html_content, heading_style="ATX")

print(markdown)  