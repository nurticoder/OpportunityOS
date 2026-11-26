"""Group duplicate destinations without deleting original evidence or applications."""
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

def destination(url):
    if not url:return None
    p=urlsplit(url)
    if p.scheme=='mailto':return 'mailto:'+p.path.casefold()
    if p.scheme!='https':return None
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in {'ref','source','gh_src'}]
    return urlunsplit(('https',p.netloc.casefold(),p.path.rstrip('/'),urlencode(sorted(query)),''))

def group_duplicates(items,apps):
    applied={a['opportunity'] for a in apps}
    groups={}
    for item in items:
        key=destination(item.get('application_link'))
        if key:groups.setdefault(key,[]).append(item)
    for group in groups.values():
        if len(group)<2:continue
        group.sort(key=lambda i:(i['id'] in applied,i['state']=='Listed',i['checked']),reverse=True)
        primary=group[0]
        primary['also_seen_at']=list(dict.fromkeys(i.get('source_link') or i.get('evidence') for i in group))
        for item in group[1:]:item['duplicate_of']=primary['id']
    return items
