#!/home/mertb/.openclaw/workspace/.venv-graph/bin/python
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import msal
import requests

CLIENT_ID = '14d82eec-204b-4c2f-b7e8-296a70dab67e'
AUTHORITY = 'https://login.microsoftonline.com/common'
SCOPES = ['Mail.Read', 'User.Read']
CACHE_PATH = Path('/home/mertb/.openclaw/workspace/windows-bridge-bootstrap/graph-cache/msal_token_cache.json')

def load_token():
    cache = msal.SerializableTokenCache()
    if CACHE_PATH.exists():
        cache.deserialize(CACHE_PATH.read_text(encoding='utf-8'))
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
    accounts = app.get_accounts()
    if not accounts:
        raise RuntimeError('No cached Graph account found.')
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result or 'access_token' not in result:
        raise RuntimeError('Could not acquire token silently.')
    return result['access_token'], accounts[0].get('username')

def main():
    try:
        token, account = load_token()
        days_back = 90
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat().replace('+00:00', 'Z')
        url = 'https://graph.microsoft.com/v1.0/me/messages'
        params = {
            '$top': '100',
            '$select': 'id,subject,from,receivedDateTime,bodyPreview',
            '$filter': f'receivedDateTime ge {cutoff}',
            '$orderby': 'receivedDateTime desc',
        }
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        print(json.dumps(data.get('value', []), indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == '__main__':
    main()
