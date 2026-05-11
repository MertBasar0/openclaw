import json, re, html
from datetime import datetime, timedelta, timezone
from pathlib import Path
import msal, requests

CLIENT_ID='14d82eec-204b-4c2f-b7e8-296a70dab67e'
AUTHORITY='https://login.microsoftonline.com/common'
SCOPES=['Mail.Read','User.Read']
ROOT=Path('/home/mertb/.openclaw/workspace/windows-bridge-bootstrap')
CACHE_PATH=ROOT/'graph-cache/msal_token_cache.json'
OUT=ROOT/'artifacts/mail-pr-issue-scan-2026-05-11.json'

cache=msal.SerializableTokenCache()
if CACHE_PATH.exists():
    cache.deserialize(CACHE_PATH.read_text(encoding='utf-8'))
app=msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
accounts=app.get_accounts()
if not accounts:
    raise SystemExit('No cached Graph account found')
result=app.acquire_token_silent(SCOPES, account=accounts[0])
if not result or 'access_token' not in result:
    raise SystemExit('Could not acquire token silently')

token=result['access_token']
account=accounts[0].get('username')
cutoff_dt=datetime.now(timezone.utc)-timedelta(days=14)
cutoff=cutoff_dt.isoformat().replace('+00:00','Z')
headers={'Authorization':f'Bearer {token}'}
url='https://graph.microsoft.com/v1.0/me/messages'
params={
    '$top':'100',
    '$select':'id,subject,from,toRecipients,ccRecipients,receivedDateTime,sentDateTime,bodyPreview,webLink,conversationId,importance,isRead',
    '$filter':f'receivedDateTime ge {cutoff}',
    '$orderby':'receivedDateTime desc',
}
items=[]
page_count=0
next_url=url
next_params=params
while next_url and page_count < 100:
    resp=requests.get(next_url, headers=headers, params=next_params, timeout=60)
    resp.raise_for_status()
    data=resp.json()
    items.extend(data.get('value', []))
    next_url=data.get('@odata.nextLink')
    next_params=None
    page_count += 1

keywords=[
    'github','pull request','pull-request','pr #','review requested','requested your review','approved','changes requested','merged','closed','opened','assigned','mentioned you','commented','issue #','new issue','workflow run','failed','failure','check suite','dependabot','security alert','vulnerability',
    'openclaw','open claw','clawd','codex','acp','watch ceviz','cevizwatch','ceviz watch'
]
repo_re=re.compile(r'(?i)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)')
num_re=re.compile(r'#(\d+)')
url_re=re.compile(r'https?://[^\s<>"\)]+')

def addr(obj):
    email=(obj or {}).get('emailAddress') or {}
    return {'name': email.get('name'), 'address': email.get('address')}

def strip_html(text):
    text=re.sub(r'(?is)<(script|style).*?</\\1>', ' ', text or '')
    text=re.sub(r'(?s)<br\\s*/?>', '\n', text)
    text=re.sub(r'(?s)</p>|</div>|</li>|</tr>', '\n', text)
    text=re.sub(r'(?s)<[^>]+>', ' ', text)
    text=html.unescape(text)
    text=re.sub(r'[ \\t\\r\\f\\v]+', ' ', text)
    text=re.sub(r'\n\\s+', '\n', text)
    text=re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

candidates=[]
for item in items:
    subject=item.get('subject') or ''
    preview=item.get('bodyPreview') or ''
    from_obj=addr(item.get('from'))
    from_text=' '.join(x for x in [from_obj.get('name'), from_obj.get('address')] if x)
    haystack='\n'.join([subject, preview, from_text]).lower()
    reasons=[kw for kw in keywords if kw in haystack]
    github_sender='github' in (from_obj.get('address') or '').lower() or 'github' in (from_obj.get('name') or '').lower()
    if reasons or github_sender:
        candidates.append((item, sorted(set(reasons + (['github-sender'] if github_sender else [])))))

expanded=[]
for item, reasons in candidates:
    detail_url=f"https://graph.microsoft.com/v1.0/me/messages/{item['id']}"
    detail=requests.get(detail_url, headers=headers, params={'$select':'id,subject,from,receivedDateTime,body,bodyPreview,webLink,conversationId,importance,isRead'}, timeout=60)
    data=detail.json() if detail.status_code == 200 else item
    body=(data.get('body') or {}).get('content') or ''
    text=strip_html(body) if body else (item.get('bodyPreview') or '')
    combined='\n'.join([item.get('subject') or '', item.get('bodyPreview') or '', text])
    low=combined.lower()
    kind=[]
    if 'pull request' in low or re.search(r'\bpr\b', low): kind.append('pull_request')
    if 'issue' in low: kind.append('issue')
    if 'review' in low: kind.append('review')
    if 'workflow' in low or 'check suite' in low or 'failed' in low or 'failure' in low: kind.append('ci_or_failure')
    if 'dependabot' in low or 'security alert' in low or 'vulnerability' in low: kind.append('dependency_or_security')
    if 'assigned' in low or 'mentioned you' in low or 'requested your review' in low or 'changes requested' in low: kind.append('needs_attention')
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    signal=[]
    sig_words=('requested your review','assigned','mentioned you','changes requested','failed','failure','approved','merged','commented','opened','closed','dependabot','security alert','vulnerability','pull request','issue')
    for line in lines:
        l=line.lower()
        if any(word in l for word in sig_words):
            if line not in signal:
                signal.append(line[:500])
        if len(signal) >= 10:
            break
    expanded.append({
        'receivedAt': item.get('receivedDateTime'),
        'subject': item.get('subject'),
        'from': addr(item.get('from')),
        'importance': item.get('importance'),
        'isRead': item.get('isRead'),
        'webLink': item.get('webLink'),
        'reasons': reasons,
        'kind': sorted(set(kind)),
        'repos': sorted(set(m.group(1) for m in repo_re.finditer(combined)))[:20],
        'numbers': sorted(set(num_re.findall(combined)), key=lambda x:int(x))[:30],
        'urls': url_re.findall(combined)[:30],
        'preview': item.get('bodyPreview'),
        'signals': signal,
    })

payload={
    'status':'ok',
    'account':account,
    'cutoff':cutoff,
    'pageCount':page_count,
    'totalScanned':len(items),
    'matchedCount':len(expanded),
    'matches':expanded,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: payload[key] for key in ['status','account','cutoff','pageCount','totalScanned','matchedCount']}, ensure_ascii=False, indent=2))
print(OUT)
