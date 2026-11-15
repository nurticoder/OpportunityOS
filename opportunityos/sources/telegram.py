"""Read public channel previews without Telegram authentication."""
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

VOID = {"br", "img", "meta", "link", "input", "hr", "source", "wbr"}


def channel_name(value):
    name = str(value).strip().removeprefix("@")
    if name.startswith("https://t.me/"):
        name = urlsplit(name).path.removeprefix("/s/").strip("/")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,63}", name):
        raise ValueError("Use a public Telegram channel username")
    return name


class Posts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts = []
        self.stack = []
        self.current = None
        self.text_depth = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag not in VOID:
            self.stack.append(tag)
        if "data-post" in attrs:
            ident = attrs["data-post"]
            self.current = {"id": "telegram:" + ident, "source_link": "https://t.me/" + ident,
                            "parts": [], "links": [], "depth": len(self.stack),
                            "published": None}
        if self.current:
            if "tgme_widget_message_text" in classes:
                self.text_depth = len(self.stack)
            if tag == "a" and self.text_depth:
                self.current["links"].append(attrs.get("href", ""))
            if tag == "time":
                self.current["published"] = attrs.get("datetime")
            if tag == "br" and self.text_depth:
                self.current["parts"].append("\n")

    def handle_data(self, text):
        if self.current and self.text_depth:
            self.current["parts"].append(text)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.current and self.text_depth == len(self.stack):
            self.text_depth = None
        if self.current and self.current["depth"] == len(self.stack):
            post = self.current
            self.posts.append({"id": post["id"], "raw_text": "".join(post["parts"]).strip(),
                               "source_link": post["source_link"], "links": post["links"],
                               "published": post["published"]})
            self.current = None
        if self.stack:
            self.stack.pop()


def fetch(channel):
    channel = channel_name(channel)
    request = Request(f"https://t.me/s/{channel}", headers={"User-Agent": "OpportunityOS/0.2"})
    with urlopen(request, timeout=20) as response:
        content = response.read(4_000_001)
    if len(content) > 4_000_000:
        raise ValueError("Channel preview exceeds size limit")
    parser = Posts()
    parser.feed(content.decode("utf-8"))
    if not parser.posts:
        raise ValueError("No public posts available for this channel")
    return [dict(post, source="telegram:" + channel) for post in parser.posts if post["raw_text"]]
