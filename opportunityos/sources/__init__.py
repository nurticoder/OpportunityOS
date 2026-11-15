import json

from .greenhouse import BOARDS, inspect_form
from . import greenhouse, telegram
from ..extraction import extract
from ..store import now


def source_names(settings):
    return {**BOARDS, **{"telegram:" + telegram.channel_name(c): "Telegram · " + telegram.channel_name(c)
                        for c in settings.get("telegram_channels", [])}}


def refresh(store, source, adapter=None):
    if adapter is not None:
        data, evidence = adapter(source)
        posts = [dict(item, raw_text=item["description"], source_link=item["url"],
                      application_link=item["url"]) for item in greenhouse.normalize(source, data, evidence)]
    else:
        posts = telegram.fetch(source.split(":", 1)[1]) if source.startswith("telegram:") else greenhouse.fetch(source)
    listings = [extract(post) for post in posts]
    stamp = now()
    with store.db() as db:
        # Telegram previews are rolling windows. Older messages remain valid evidence.
        if not source.startswith("telegram:"):
            db.execute("UPDATE opportunities SET state='Unlisted' WHERE source=?", (source,))
        for item in listings:
            db.execute("""
                INSERT INTO opportunities VALUES (?, ?, ?, ?, ?, ?, 'Listed')
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                    checked=excluded.checked, state='Listed'
            """, (item["id"], source, item["source_link"], json.dumps(item), stamp, stamp))
        db.execute("INSERT OR REPLACE INTO health VALUES (?, ?, 'OK', ?)", (source, stamp, len(listings)))
    store.log(f"{source} · {len(listings)} posts extracted")
    return len(listings)
