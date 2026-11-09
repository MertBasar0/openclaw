#!/usr/bin/env python3
"""Run the actual macOS product against a disposable real Gateway; export no state."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import threading

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--kit', required=True)
p.add_argument('--out', required=True)
p.add_argument('--variant', choices=['baseline', 'candidate'], required=True)
a = p.parse_args()
assert sys.platform == 'darwin' and os.environ.get('GITHUB_ACTIONS') == 'true'
assert os.environ.get('GITHUB_REPOSITORY') == 'MertBasar0/openclaw'
source, kit, out = (Path(x).resolve() for x in [a.source, a.kit, a.out])
out.mkdir(parents=True, exist_ok=False)
root = Path(os.environ['RUNNER_TEMP']).resolve() / ('real-menu-' + a.variant)
manifest = json.loads((kit/'candidate.json').read_text())
profile = 'proof-' + a.variant[0]
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
owned = []
private_logs = []
secret = ''
paths = None
keychain = None
keychain_env = None
keychain_created = False
summary = {'variant': a.variant, 'startedUTC': started, 'candidate': manifest['candidate'],
           'baseline': manifest['base'], 'launch': 'real unbundled SwiftPM development app',
           'input': 'external CGEvent through normal status menu; AX readback',
           'gateway': 'real same-source isolated loopback Gateway; no model invocation',
           'profile': profile, 'status': 'running', 'cleanup': []}

def clean_env(extra=None):
    env = {k:v for k,v in os.environ.items() if not (
        re.search(r'^(ACTIONS_|OPENCLAW_|CLAWDBOT_|MOLTBOT_|OPENAI_|ANTHROPIC_|GEMINI_|AWS_|AZURE_|GOOGLE_API_|GROQ_|MISTRAL_|COHERE_|XAI_)', k)
        or re.search(r'(?:^|_)(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|SECRET|PASSWORD)$', k)
        or k in ['GH_TOKEN','GITHUB_TOKEN','NODE_OPTIONS','NODE_AUTH_TOKEN','NPM_TOKEN'])}
    env.update({'NO_COLOR':'1','FORCE_COLOR':'0'})
    env.update(extra or {})
    return env

def safe(text):
    if secret: text = text.replace(secret, '<private-test-token>')
    return text.replace(str(root), '<task-root>')

def write(name, value):
    (out/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def run(cmd, env=None, timeout=120, label=None, check=True):
    if label: print('START '+label, flush=True)
    args=[str(x) for x in cmd]
    child=subprocess.Popen(args,cwd=source,env=env or clean_env(),text=True,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        stdout,stderr=child.communicate(timeout=timeout)
    except BaseException:
        if child.poll() is None and os.getpgid(child.pid)==child.pid:
            os.killpg(child.pid,signal.SIGKILL)
        stdout,stderr=child.communicate(timeout=5)
        if label: (out/(label+'.interrupted.log')).write_text(safe(stdout+'\n'+stderr))
        raise
    r=subprocess.CompletedProcess(args,child.returncode,stdout,stderr)
    if label:
        (out/(label+'.log')).write_text(safe(r.stdout+'\n'+r.stderr))
        write(label+'.receipt.json', {'command':[str(x) for x in cmd], 'exit':r.returncode})
    if check and r.returncode:
        raise RuntimeError(f'{label or Path(str(cmd[0])).name} failed ({r.returncode}): '+safe(r.stderr[-2500:]))
    return r

def utility(mode, label):
    run(['node',kit/'real-gateway-setup.mjs',mode,'--root',root,'--label',label],timeout=180)
    data=(Path(paths['evidence'])/(label+'.json')).read_text()
    (out/('rpc-'+label+'.json')).write_text(safe(data))
    return json.loads(data)

def launch(name, cmd, env):
    log = root/(name+'.log')
    handle = open(log,'w')
    child = subprocess.Popen([str(x) for x in cmd], cwd=source, env=env,
                             stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    handle.close()
    identity = subprocess.check_output(['ps','-p',str(child.pid),'-o','lstart='],text=True).strip()
    owned.append((name,child,identity))
    private_logs.append((name,log))
    write(name+'-process.json', {'pid':child.pid,'pgid':os.getpgid(child.pid),
        'started':identity,'command':[str(x) for x in cmd]})
    return child

def alive(child):
    if child.poll() is not None: raise RuntimeError(f'Owned process {child.pid} exited {child.returncode}')

def wait_gateway(child, env):
    for attempt in range(30):
        alive(child)
        r=run(['pnpm','--silent','openclaw','gateway','call','health','--port',str(paths['port']),
               '--expect-url',paths['url'],'--json','--timeout','5000'],env,timeout=30,check=False)
        if r.returncode == 0:
            json.loads(r.stdout)
            (out/'gateway-health.json').write_text(safe(r.stdout))
            return
        time.sleep(2)
    (out/'gateway-readiness-error.log').write_text(safe(r.stdout+r.stderr))
    raise RuntimeError('Real Gateway did not become healthy')

def wait_app(cli, child, env):
    last=None
    for attempt in range(18):
        alive(child)
        last=run([cli,'--profile',profile,'status','--no-launch','--timeout','3000','--json'],env,timeout=8,label=f'app-status-{attempt+1:02d}',check=False)
        (out/'app-status-last.log').write_text(safe(last.stdout+'\n'+last.stderr))
        print('App status attempt '+str(attempt+1)+' exit '+str(last.returncode),flush=True)
        if last.returncode == 0:
            state=json.loads(last.stdout)
            if state.get('primary',{}).get('connection',{}).get('state') == 'connected':
                write('app-connected.json',state)
                return
        time.sleep(2)
    (out/'app-readiness-error.log').write_text(safe(last.stdout+last.stderr))
    raise RuntimeError('Actual app did not report an authenticated primary connection')

def menu(child, label, pref, expected, name, selection=None):
    alive(child)
    cmd=[Path(os.environ['RUNNER_TEMP'])/'real-menu-driver','--pid',str(child.pid),
         '--session-label',label,'--preference',pref,'--expected',expected,'--out',out/name]
    if selection: cmd += ['--select',selection]
    run(cmd,timeout=90,label=name+'-driver')

def export_logs():
    for name,log in list(private_logs):
        if log.exists(): (out/(name+'.log')).write_text(safe(log.read_text(errors='replace')))

stop_logs=threading.Event()
def log_pump():
    while not stop_logs.wait(5):
        try: export_logs()
        except OSError: pass
threading.Thread(target=log_pump,daemon=True).start()

def assert_rows(receipt, thinking, verbose):
    rows={x['name']:x for x in receipt['state']['rows']}
    assert rows['inherited']['thinkingLevel']==thinking, rows['inherited']
    assert rows['inherited']['verboseLevel']==verbose, rows['inherited']
    assert rows['explicit-off']['thinkingLevel']=='off'
    assert rows['explicit-off']['verboseLevel']=='off'

try:
    git=lambda *args: subprocess.check_output(['git',*args],cwd=source,text=True).strip()
    assert git('rev-parse','HEAD')==manifest['candidate']
    blob=git('show', (manifest['base'] if a.variant=='baseline' else manifest['candidate'])+':'+manifest['productionPath'])
    assert (source/manifest['productionPath']).read_text().strip()==blob
    summary['productionSHA256']=hashlib.sha256((source/manifest['productionPath']).read_bytes()).hexdigest()
    run(['node',kit/'real-gateway-setup.mjs','prepare','--root',root,'--repo',source,
         '--port','29683' if a.variant=='baseline' else '29684'],label='prepare')
    paths=json.loads((root/'paths.json').read_text())
    secret=json.loads(Path(paths['gateway']['config']).read_text())['gateway']['auth']['token']
    gw_env=clean_env(paths['gateway']['env'])
    run(['pnpm','openclaw','--version'],gw_env,timeout=900,label='gateway-version')
    run(['pnpm','openclaw','config','validate'],gw_env,timeout=90,label='gateway-config-validation')
    gateway=launch('gateway',['pnpm','openclaw','gateway','run','--port',str(paths['port']),'--bind','loopback'],gw_env)
    wait_gateway(gateway,gw_env)
    assert_rows(utility('seed','initial-state'),None,None)
    bindir=Path(run(['swift','build','--package-path','apps/macos','--build-system','native','--show-bin-path']).stdout.strip())
    app,cli=bindir/'OpenClaw',bindir/'openclaw-mac'
    summary['appSHA256']=hashlib.sha256(app.read_bytes()).hexdigest()
    control_socket=Path(paths['app']['home']) / ('.openclaw-'+profile) / 'mac-control.sock'
    assert len(os.fsencode(control_socket)) <= 103, 'macOS control socket path exceeds sockaddr_un limit'
    app_env=clean_env({**paths['app']['env'],'CFFIXED_USER_HOME':paths['app']['home'],
                       'OPENCLAW_PROFILE':profile})
    # Match scripts/test-macos-native.mts: the fresh HOME needs its own unlocked
    # user-domain Keychain before real catalog migration attempts SecItemAdd.
    keychain=Path(paths['app']['home'])/'Library/Keychains/real-menu.keychain-db'
    keychain_env=app_env
    keychain.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    (Path(paths['app']['home'])/'Library/Preferences').mkdir(parents=True,exist_ok=True,mode=0o700)
    assert not keychain.exists(), 'Refusing to replace a pre-existing test Keychain'
    summary['keychain']={'path':safe(str(keychain)),'preparation':'started','cleanup':'pending'}
    run(['/usr/bin/security','create-keychain','-p','',keychain],app_env,timeout=30,label='keychain-create')
    keychain_created=True
    for label,args in [
        ('unlock',['unlock-keychain','-p','',keychain]),
        ('settings',['set-keychain-settings',keychain]),
        ('search-list',['list-keychains','-d','user','-s',keychain]),
        ('default',['default-keychain','-d','user','-s',keychain]),
    ]:
        run(['/usr/bin/security',*args],app_env,timeout=30,label='keychain-'+label)
    selected=run(['/usr/bin/security','default-keychain','-d','user'],app_env,
                 timeout=30,label='keychain-default-readback').stdout.strip().strip('"')
    assert Path(selected).resolve()==keychain.resolve(), 'Test Keychain was not selected as user default'
    run(['/usr/bin/security','list-keychains','-d','user'],app_env,timeout=30,label='keychain-search-list-readback')
    summary['keychain']['preparation']='verified'
    tokenfile=root/'private-token'
    tokenfile.write_text(secret); tokenfile.chmod(0o600)
    run([cli,'configure-remote','--profile',profile,'--direct-url',paths['url'],
         '--token-file',tokenfile,'--json'],app_env,label='configure-app')
    tokenfile.unlink()
    for key in ['computerControlEnabled','peekabooBridgeEnabled','desktopSharingEnabled','cameraEnabled',
                'swabbleEnabled','voicePushToTalkEnabled','talkEnabled','cookieSyncEnabled',
                'quickChatEnabled','activeComputerPresenceEnabled']:
        run(['/usr/bin/defaults','write','ai.openclaw.mac.profile.'+profile,'openclaw.'+key,'-bool','false'],app_env)
    child=launch('app',[app,'--attach-only','--background-only','--no-activate'],app_env)
    run(['/usr/sbin/screencapture','-x','-m',out/'app-startup.png'],label='startup-screen')
    wait_app(cli,child,app_env)
    expected='off' if a.variant=='baseline' else 'none'
    for pref in ['Thinking','Verbose']:
        menu(child,'Inherited proof',pref,expected,'initial-inherited-'+pref.lower())
        menu(child,'Explicit Off proof',pref,'off','initial-explicit-off-'+pref.lower())
    # Real UI writes, independently read back through the Gateway owner.
    menu(child,'Inherited proof','Thinking',expected,'select-thinking-off','Off')
    time.sleep(1)
    assert_rows(utility('record-state','after-thinking-click'),'off',None)
    menu(child,'Inherited proof','Verbose',expected,'select-verbose-off','Off')
    time.sleep(1)
    assert_rows(utility('record-state','after-verbose-click'),'off','off')
    for pref in ['Thinking','Verbose']:
        menu(child,'Inherited proof',pref,'off','reuse-off-'+pref.lower())
    menu(child,'Inherited proof','Thinking','off','select-thinking-high','High')
    time.sleep(1)
    assert_rows(utility('record-state','after-high-click'),'high','off')
    menu(child,'Inherited proof','Verbose','off','select-verbose-on','On')
    time.sleep(1)
    assert_rows(utility('record-state','after-on-click'),'high','on')
    menu(child,'Inherited proof','Thinking','high','reuse-high-thinking')
    menu(child,'Inherited proof','Verbose','on','reuse-on-verbose')
    # There is no inherit action in this UI. Clear overrides using the real supported RPC.
    assert_rows(utility('inherit','restore-inheritance'),None,None)
    time.sleep(1)
    for pref in ['Thinking','Verbose']:
        menu(child,'Inherited proof',pref,expected,'reuse-inherited-'+pref.lower())
    assert_rows(utility('record-state','final-state'),None,None)
    summary['sameAppPIDAcrossOpens']=child.pid
    summary['status']='passed'
except BaseException as e:
    summary['status']='failed'
    summary['error']=safe(str(e))
    print(summary['error'],file=sys.stderr,flush=True)
    try:
        run(['/usr/sbin/screencapture','-x','-m',out/'failure-screen.png'],timeout=10,check=False)
        run(['/usr/bin/log','show','--style','compact','--last','3m','--predicate','process == \"OpenClaw\"'],timeout=20,label='app-system',check=False)
    except Exception: pass
finally:
    stop_logs.set()
    for name,child,identity in reversed(owned):
        entry={'name':name,'pid':child.pid,'originalStart':identity}
        try:
            if child.poll() is None:
                now=subprocess.check_output(['ps','-p',str(child.pid),'-o','lstart='],text=True).strip()
                if now!=identity or os.getpgid(child.pid)!=child.pid: raise RuntimeError('Process identity changed')
                os.killpg(child.pid,signal.SIGTERM)
                try: child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL); child.wait(timeout=10)
            # A child may outlive its group leader. Detect rather than silently claim clean retirement.
            r=subprocess.run(['pgrep','-g',str(child.pid)],text=True,capture_output=True)
            if r.returncode==0: raise RuntimeError('Owned group still has members: '+r.stdout.strip())
            entry['status']='retired'
        except Exception as e:
            entry['status']='unverified'; entry['error']=str(e)
            summary['status']='failed'
        summary['cleanup'].append(entry)
    if keychain is not None and 'keychain' in summary:
        if keychain_created and all(entry['status']=='retired' for entry in summary['cleanup']):
            try:
                run(['/usr/bin/security','delete-keychain',keychain],keychain_env,
                    timeout=30,label='keychain-delete')
                if keychain.exists(): raise RuntimeError('Test Keychain file remains after deletion')
                summary['keychain']['cleanup']='deleted-after-owned-process-retirement'
            except Exception as e:
                summary['keychain']['cleanup']='unverified-retained'
                summary['keychain']['error']=safe(str(e))
                summary['status']='failed'
        elif keychain_created or keychain.exists():
            summary['keychain']['cleanup']='retained-unverified-creation-or-process-retirement'
            summary['status']='failed'
        else:
            summary['keychain']['cleanup']='not-created'
    for name,log in private_logs:
        if log.exists(): (out/(name+'.log')).write_text(safe(log.read_text(errors='replace')))
    if paths:
        for file in Path(paths['evidence']).glob('*.json'):
            (out/('rpc-'+file.name)).write_text(safe(file.read_text()))
    summary['completedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    write('summary.json',summary)
    if secret:
        for file in out.rglob('*'):
            if file.is_file() and secret.encode() in file.read_bytes():
                file.unlink()
                raise RuntimeError('Private test token in outgoing evidence; removed the file')
    print(json.dumps(summary,indent=2))
    # Disposable task state remains private until the Actions worker is destroyed.
sys.exit(0 if summary['status']=='passed' else 1)
