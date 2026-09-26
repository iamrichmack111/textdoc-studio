from __future__ import annotations
import json, os, re, secrets, shutil, subprocess, threading, time, uuid
from pathlib import Path
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

ROOT = Path(os.environ.get('TEXTDOC_ROOT', Path.home()/'textdoc-cli')).resolve()
DATA = Path(os.environ.get('TEXTDOC_STUDIO_DATA', ROOT/'studio-data')).resolve()
PROJECTS = DATA/'projects'; SETTINGS = DATA/'settings.json'; TOKEN = DATA/'youtube-token.json'
ALLOWED = {'.jpg','.jpeg','.png','.webp'}
JOBS = {}; PROCS = {}; LOCK = threading.Lock()

def ensure():
    PROJECTS.mkdir(parents=True, exist_ok=True); DATA.mkdir(parents=True, exist_ok=True)

def read_json(p, default):
    try: return json.loads(Path(p).read_text())
    except Exception: return default

def write_json(p, obj, mode=None):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)
    if mode: os.chmod(p, mode)

def slug(s):
    x=re.sub(r'[^a-zA-Z0-9_-]+','-',s.strip()).strip('-').lower()
    return x or uuid.uuid4().hex[:8]

def pdir(pid): return PROJECTS/pid

def project(pid):
    p=read_json(pdir(pid)/'project.json', None)
    if not p: raise FileNotFoundError(pid)
    return p

def save_project(p):
    p['updated']=int(time.time()); write_json(pdir(p['id'])/'project.json',p)

def scene_block(s):
    typ=s.get('type','narration').upper()
    text=s.get('text','').strip()

    lines=[]

    if typ != 'NARRATION':
        lines.append(f'[{typ}]')

    # Keep spoken text first; the renderer strips trailing IMAGE metadata.
    lines.append(text)

    if s.get('image'):
        lines.append('IMAGE: '+Path(s['image']).name)

    if s.get('label'):
        lines.append('LABEL: '+s['label'].strip())

    # Source metadata remains owned by Studio/YouTube description.
    return '\n'.join(x for x in lines if x)

def build_input(p):
    d=pdir(p['id']); pics=d/'pictures'; pics.mkdir(exist_ok=True)
    txt='TITLE: '+(p.get('title') or 'Untitled Documentary')+'\n\n'+ '\n\n'.join(scene_block(x) for x in p.get('scenes',[]))+'\n'
    (d/'narration.txt').write_text(txt)
    return d

def yt_description(p):
    body=(p.get('youtube',{}).get('description') or '').strip()
    chapters=[]; t=0.0
    for s in p.get('scenes',[]):
        if s.get('type')=='chapter' and s.get('text'):
            mm=int(t)//60; ss=int(t)%60; chapters.append(f'{mm:02d}:{ss:02d} {s["text"].strip()}')
        t += float(s.get('duration_hint') or 8)
    sources=[]
    for i,s in enumerate(p.get('scenes',[]),1):
        if s.get('source'): sources.append(f'{i}. {s["source"].strip()}')
    parts=[body]
    if chapters: parts += ['CHAPTERS','\n'.join(chapters)]
    if sources: parts += ['SOURCES','\n'.join(sources)]
    return '\n\n'.join(x for x in parts if x)

def render_worker(pid):
    try:
        p=project(pid); d=build_input(p); out=d/'output.mp4'
        with LOCK: JOBS[pid]={'state':'rendering','progress':3,'message':'Preparing documentary'}
        cmd=[str(ROOT/'.venv/bin/python'),'-m','textdoc.documentary_v4',str(d),'--output',str(out)]
        proc=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)

        with LOCK:
            PROCS[pid]=proc

        total=max(1,len(p.get('scenes',[])))
        for line in proc.stdout:
            m=re.search(r'(?:scene|SCENE)\s*(\d+)\s*(?:/|of)\s*(\d+)',line)
            if m:
                n=int(m.group(1)); den=max(1,int(m.group(2))); prog=min(92,8+int(82*n/den))
                with LOCK: JOBS[pid]={'state':'rendering','progress':prog,'message':f'Rendering scene {n} of {den}'}
        rc=proc.wait()

        with LOCK:
            PROCS.pop(pid,None)

        if rc or not out.exists():
            raise RuntimeError(f'Renderer exited with code {rc}')

        with LOCK:
            JOBS[pid]={
                'state':'done',
                'progress':100,
                'message':'Documentary ready'
            }

    except Exception as e:
        with LOCK:
            PROCS.pop(pid,None)

            # Don't overwrite an intentional restart status.
            if JOBS.get(pid,{}).get('state') != 'restarting':
                JOBS[pid]={
                    'state':'error',
                    'progress':0,
                    'message':str(e)
                }

def create_app():
    ensure(); app=Flask(__name__); app.secret_key=os.environ.get('TEXTDOC_STUDIO_SECRET', secrets.token_hex(32))
    app.config['MAX_CONTENT_LENGTH']=1024*1024*1024

    @app.get('/')
    def home():
        items=[]
        for f in PROJECTS.glob('*/project.json'):
            q=read_json(f,{}); q['rendered']=(f.parent/'output.mp4').exists(); items.append(q)
        items.sort(key=lambda x:x.get('updated',0), reverse=True)
        return render_template('index.html',projects=items)

    @app.post('/api/projects')
    def create_project():
        body=request.get_json(silent=True) or {}; title=(body.get('title') or 'Untitled Documentary').strip()
        pid=slug(title)+'-'+uuid.uuid4().hex[:5]; d=pdir(pid); (d/'pictures').mkdir(parents=True)
        p={
            'id':pid,
            'title':title,
            'created':int(time.time()),
            'updated':int(time.time()),
            'format':'16:9',
            'quality':'1080p',
            'scenes':[],
            'youtube':{
                'title':title,
                'description':'',
                'tags':[],
                'categoryId':'27'
            }
        }
        save_project(p); return jsonify(p)

    @app.get('/project/<pid>')
    def editor(pid): return render_template('editor.html',p=project(pid))

    @app.get('/api/project/<pid>')
    def get_project(pid):
        p=project(pid)
        p.setdefault('format','16:9')
        p.setdefault('quality','1080p')
        p['media']=[
            x.name for x in sorted((pdir(pid)/'pictures').glob('*'))
            if x.suffix.lower() in ALLOWED
        ]
        p['has_video']=(pdir(pid)/'output.mp4').exists()
        p['youtube_description']=yt_description(p)
        return jsonify(p)

    @app.put('/api/project/<pid>')
    def put_project(pid):
        old=project(pid); body=request.get_json(force=True)
        for k in ('title','scenes','youtube','format','quality'):
            if k in body:
                old[k]=body[k]
        save_project(old); return jsonify({'ok':True})

    @app.post('/api/project/<pid>/upload')
    def upload(pid):
        project(pid); dest=pdir(pid)/'pictures'; names=[]
        for f in request.files.getlist('files'):
            name=secure_filename(f.filename or '')
            if Path(name).suffix.lower() not in ALLOWED: continue
            target=dest/name; stem=target.stem; ext=target.suffix; i=2
            while target.exists(): target=dest/f'{stem}-{i}{ext}'; i+=1
            f.save(target); names.append(target.name)
        return jsonify({'files':names})

    @app.get('/media/<pid>/<path:name>')
    def media(pid,name): return send_from_directory(pdir(pid)/'pictures',name)

    @app.get('/video/<pid>')
    def video(pid): return send_from_directory(pdir(pid),'output.mp4',conditional=True)

    @app.post('/api/project/<pid>/render')
    def render(pid):
        project(pid)
        if JOBS.get(pid,{}).get('state')=='rendering': return jsonify(JOBS[pid])
        threading.Thread(target=render_worker,args=(pid,),daemon=True).start(); return jsonify({'state':'starting','progress':1})

    @app.post('/api/project/<pid>/render/restart')
    def restart_render(pid):
        project(pid)

        with LOCK:
            proc=PROCS.get(pid)

        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        with LOCK:
            PROCS.pop(pid,None)
            JOBS[pid]={
                'state':'restarting',
                'progress':1,
                'message':'Restarting render'
            }

        out=pdir(pid)/'output.mp4'

        try:
            if out.exists():
                out.unlink()
        except Exception:
            pass

        threading.Thread(
            target=render_worker,
            args=(pid,),
            daemon=True
        ).start()

        return jsonify({
            'state':'restarting',
            'progress':1,
            'message':'Restarting render'
        })


    @app.get('/api/project/<pid>/status')
    def status(pid): return jsonify(JOBS.get(pid,{'state':'idle','progress':0,'message':'Ready'}))

    @app.get('/download/<pid>/video')
    def download_video(pid):
        project(pid)
        video=pdir(pid)/'output.mp4'
        if not video.exists():
            return 'Render the documentary first.',404
        return send_from_directory(
            pdir(pid),
            'output.mp4',
            as_attachment=True,
            download_name=f'{pid}.mp4'
        )

    @app.get('/download/<pid>/audio')
    def download_audio(pid):
        project(pid)
        video=pdir(pid)/'output.mp4'
        audio=pdir(pid)/'output.mp3'

        if not video.exists():
            return 'Render the documentary first.',404

        regenerate=(
            not audio.exists() or
            audio.stat().st_mtime < video.stat().st_mtime
        )

        if regenerate:
            cmd=[
                'ffmpeg','-y',
                '-i',str(video),
                '-vn',
                '-codec:a','libmp3lame',
                '-q:a','2',
                str(audio)
            ]

            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )

        return send_from_directory(
            pdir(pid),
            'output.mp3',
            as_attachment=True,
            download_name=f'{pid}.mp3'
        )

    @app.get('/settings')
    def settings():
        s=read_json(SETTINGS,{}); safe={'client_id':s.get('client_id',''),'api_key':s.get('api_key',''),'has_secret':bool(s.get('client_secret')),'connected':TOKEN.exists()}
        return render_template('settings.html',s=safe)

    @app.post('/api/settings/youtube')
    def save_settings():
        old=read_json(SETTINGS,{}); b=request.get_json(force=True)
        for k in ('client_id','client_secret','api_key'):
            if b.get(k): old[k]=b[k].strip()
        write_json(SETTINGS,old,0o600); return jsonify({'ok':True})

    @app.get('/youtube/connect')
    def youtube_connect():
        from google_auth_oauthlib.flow import Flow
        s=read_json(SETTINGS,{})
        if not s.get('client_id') or not s.get('client_secret'): return 'Save Client ID and Client Secret first.',400
        redirect_uri=url_for('youtube_callback',_external=True)
        cfg={'web':{'client_id':s['client_id'],'client_secret':s['client_secret'],'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token','redirect_uris':[redirect_uri]}}
        flow=Flow.from_client_config(cfg,scopes=['https://www.googleapis.com/auth/youtube.upload']); flow.redirect_uri=redirect_uri
        url,state=flow.authorization_url(access_type='offline',include_granted_scopes='true',prompt='consent'); session['oauth_state']=state; return redirect(url)

    @app.get('/youtube/callback')
    def youtube_callback():
        from google_auth_oauthlib.flow import Flow
        s=read_json(SETTINGS,{}); redirect_uri=url_for('youtube_callback',_external=True)
        cfg={'web':{'client_id':s['client_id'],'client_secret':s['client_secret'],'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token','redirect_uris':[redirect_uri]}}
        flow=Flow.from_client_config(cfg,scopes=['https://www.googleapis.com/auth/youtube.upload'],state=session.get('oauth_state')); flow.redirect_uri=redirect_uri; flow.fetch_token(authorization_response=request.url)
        write_json(TOKEN,json.loads(flow.credentials.to_json()),0o600); return redirect(url_for('settings'))

    @app.post('/api/project/<pid>/youtube/private')
    def youtube_upload(pid):
        p=project(pid); video=pdir(pid)/'output.mp4'
        if not video.exists(): return jsonify({'error':'Render the documentary first.'}),400
        if not TOKEN.exists(): return jsonify({'error':'Connect YouTube in Settings first.'}),400
        def worker():
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaFileUpload
                creds=Credentials.from_authorized_user_file(str(TOKEN),['https://www.googleapis.com/auth/youtube.upload'])
                yt=build('youtube','v3',credentials=creds,cache_discovery=False)
                meta=p.get('youtube',{}); tags=meta.get('tags',[])
                body={'snippet':{'title':meta.get('title') or p['title'],'description':yt_description(p),'tags':tags,'categoryId':meta.get('categoryId','27')},'status':{'privacyStatus':'private'}}
                req=yt.videos().insert(part='snippet,status',body=body,notifySubscribers=False,media_body=MediaFileUpload(str(video),chunksize=8*1024*1024,resumable=True))
                response=None
                while response is None:
                    st,response=req.next_chunk()
                    if st:
                        with LOCK: JOBS['yt:'+pid]={'state':'uploading','progress':int(st.progress()*100),'message':'Uploading privately to YouTube'}
                with LOCK: JOBS['yt:'+pid]={'state':'done','progress':100,'message':'Private upload complete','video_id':response['id']}
            except Exception as e:
                with LOCK: JOBS['yt:'+pid]={'state':'error','progress':0,'message':str(e)}
        threading.Thread(target=worker,daemon=True).start(); return jsonify({'state':'starting'})

    @app.get('/api/project/<pid>/youtube/status')
    def youtube_status(pid): return jsonify(JOBS.get('yt:'+pid,{'state':'idle','progress':0,'message':'Ready'}))

    @app.delete('/api/project/<pid>/media/<path:name>')
    def delete_project_media(pid, name):
        p = project(pid)

        # Filename only -- prevent traversal outside project media.
        safe_name = Path(name).name
        target = pdir(pid) / 'pictures' / safe_name

        deleted = False

        if target.exists() and target.is_file():
            target.unlink()
            deleted = True

        # Remove references from scenes.
        for scene in p.get('scenes', []):
            if scene.get('image') == safe_name:
                scene['image'] = ''

            if scene.get('secondary') == safe_name:
                scene['secondary'] = ''

        save_project(p)

        return jsonify({
            'ok': True,
            'deleted': deleted,
            'name': safe_name
        })

    return app
