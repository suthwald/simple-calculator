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




from langchain_text_splitters import HTMLHeaderTextSplitter

headers_to_split_on = [
    ("h1", "Header 1"),
    ("h2", "Header 2"),
    ("h3", "Header 3"),
]

splitter = HTMLHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
docs = splitter.split_text(content)

for d in docs:
    print(d)
    print("-" * 40)