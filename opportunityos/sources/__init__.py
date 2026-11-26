from .greenhouse import inspect_form
from . import greenhouse, telegram, ashby
BOARDS = {**greenhouse.BOARDS, **ashby.BOARDS}
from ..store import now


def source_names(settings):
    return {**BOARDS, **{"telegram:" + telegram.channel_name(c): "Telegram · " + telegram.channel_name(c)
                        for c in settings.get("telegram_channels", [])}}


def refresh(store, source, adapter=None, budget=None, should_stop=None, quick=False):
    from ..ingestion import ingest_posts
    if adapter is not None:
        data, evidence = adapter(source)
        posts = [dict(item, raw_text=item["description"], source_link=item["url"],
                      application_link=item["url"]) for item in greenhouse.normalize(source, data, evidence)]
    else:
        posts = telegram.fetch(source.split(":", 1)[1]) if source.startswith("telegram:") else ashby.fetch(source) if source.startswith("ashby:") else greenhouse.fetch(source)
    seen = ingest_posts(store, source, posts, budget, should_stop, quick=quick)
    stamp = now()
    with store.db() as db:
        # Only complete board snapshots can delist jobs. Telegram previews are rolling windows.
        if not source.startswith("telegram:"):
            db.execute("UPDATE opportunities SET state='Unlisted' WHERE source=?", (source,))
            db.executemany("UPDATE opportunities SET state='Listed' WHERE id=?", [(ident,) for ident in seen])
        db.execute("INSERT OR REPLACE INTO health VALUES (?, ?, 'OK', ?)", (source, stamp, len(seen)))
    store.log(f"{source} · {len(seen)} posts checked")
    return len(seen)
