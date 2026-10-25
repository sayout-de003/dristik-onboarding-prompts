import re
from typing import List

def extract_internal_links(base_url: str, html: str) -> List[str]:
    links = re.findall(r"""href=["'](.*?)["']""", html)
    return [l for l in links if l.startswith("/") or base_url in l]
