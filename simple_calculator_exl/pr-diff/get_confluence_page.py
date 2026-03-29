from atlassian import Confluence
from dotenv import load_dotenv
import os

load_dotenv()

url=os.getenv("CF_URL")
token=os.getenv("CF_TOKEN")
account=os.getenv("ACCOUNT")

confluence = Confluence(
    url=url,
    username=account,
    password=token
)

page = confluence.get_page_by_id(page_id=65720, expand='body.storage')
content = page['body']['storage']['value']

print(content)