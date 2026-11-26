"""Official, public Ashby posting API; no employer credentials required."""
import re
from urllib.parse import urlsplit
from .greenhouse import get_json,clean

BOARDS={"ashby:openai":"OpenAI","ashby:perplexity":"Perplexity","ashby:notion":"Notion"}
EARLY=re.compile(r"\b(intern(?:ship)?|co-op|student researcher|fellowship|residency)\b",re.I)

def fetch(source):
    if source not in BOARDS:raise ValueError("Unsupported employer feed")
    board=source.split(':',1)[1]
    endpoint='https://api.ashbyhq.com/posting-api/job-board/'+board
    data=get_json(endpoint)
    if not isinstance(data.get('jobs'),list):raise ValueError('Invalid Ashby response')
    posts=[]
    for job in data['jobs']:
        if not job.get('isListed',True) or not EARLY.search(job.get('title','')):continue
        link=job.get('applyUrl') or job.get('jobUrl','')
        parsed=urlsplit(link)
        if parsed.scheme!='https' or parsed.hostname!='jobs.ashbyhq.com':continue
        posts.append({'id':source+':'+str(job.get('id') or parsed.path.rsplit('/',1)[-1]),
            'source':source,'source_link':job.get('jobUrl') or link,'application_link':link,
            'title':job['title'],'organization':BOARDS[source],'raw_text':job.get('descriptionPlain') or clean(job.get('descriptionHtml','')),
            'location':job.get('location','Unknown'),'category':'Research' if 'residency' in job['title'].lower() else 'Internship',
            'source_updated':job.get('publishedAt'),'official_feed':endpoint})
    return posts
