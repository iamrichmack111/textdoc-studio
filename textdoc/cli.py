from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
DEFAULT_VOICE='/home/richmack/textdoc-cli/voices/en_GB-alan-medium.onnx'
INTRO=3.2
IMAGE_EXTS={'.jpg','.jpeg','.png','.webp'}

def run(cmd,input_text=None):
    p=subprocess.run(cmd,input=input_text,text=True,capture_output=True)
    if p.returncode: raise RuntimeError(f"Command failed: {' '.join(map(str,cmd))}\n{p.stderr}")
    return p.stdout.strip()
def need(n):
    if not shutil.which(n): raise RuntimeError(f'Missing dependency: {n}')
def duration(p): return float(run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)]))
def clean(s): return re.sub(r'\s+',' ',s).strip()
def assesc(s):
    # Preserve intentional ASS line breaks while stripping stray source slashes.
    marker = '<<<ASS_NEWLINE>>>'
    s = s.replace('\\N', marker)
    s = s.replace('\\', '')
    s = s.replace('{', '\\{').replace('}', '\\}')
    return s.replace(marker, '\\N')
def ts(t):
    h=int(t//3600); m=int((t%3600)//60); sec=t%60
    return f'{h}:{m:02d}:{sec:05.2f}'
def parse_script(path):
    raw=Path(path).read_text(encoding='utf-8'); title=Path(path).stem.replace('_',' ').title()
    m=re.search(r'^TITLE:\s*(.+)$',raw,re.M|re.I)
    if m: title=clean(m.group(1)); raw=raw[:m.start()]+raw[m.end():]
    blocks=[x.strip() for x in re.split(r'\n\s*\n',raw) if x.strip()]
    scenes=[]
    for b in blocks:
        kind='auto'; source=''; image=''
        dm=re.match(r'^\[(CHAPTER|PUNCH|QUOTE|WORDS)\]\s*',b,re.I)
        if dm: kind=dm.group(1).lower(); b=b[dm.end():]
        im=re.search(r'\nIMAGE:\s*(.+)$',b,re.I)
        if im: image=clean(im.group(1)); b=b[:im.start()]+b[im.end():]
        sm=re.search(r'\nSOURCE:\s*(.+)$',b,re.I)
        if sm: source=clean(sm.group(1)); b=b[:sm.start()]+b[sm.end():]
        txt=clean(b)
        if txt: scenes.append({'kind':kind,'text':txt,'source':source,'image':image})
    if not scenes: raise RuntimeError('The text file has no documentary text.')
    return title,scenes
def ass_header(w,h):
    return f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Body,DejaVu Sans,62,&H00F5F2EA,&H00FFFFFF,&H00101010,&H88000000,0,0,0,0,100,100,1,0,1,2,1,5,220,220,110,1\nStyle: Dim,DejaVu Sans,62,&H00908B82,&H00FFFFFF,&H00101010,&H88000000,0,0,0,0,100,100,1,0,1,2,1,5,220,220,110,1\nStyle: Highlight,DejaVu Sans,66,&H0000C8FF,&H00FFFFFF,&H00101010,&H88000000,-1,0,0,0,100,100,1,0,1,2,1,5,220,220,110,1\nStyle: Punch,DejaVu Sans,104,&H00F5F2EA,&H00FFFFFF,&H00000000,&H66000000,-1,0,0,0,100,100,3,0,1,1,2,5,120,120,100,1\nStyle: Chapter,DejaVu Sans,78,&H00F5F2EA,&H00FFFFFF,&H00000000,&H66000000,-1,0,0,0,100,100,5,0,1,1,2,5,150,150,100,1\nStyle: Quote,DejaVu Serif,60,&H00F4F1E8,&H00FFFFFF,&H00000000,&H66000000,0,-1,0,0,100,100,1,0,1,1,2,5,260,260,130,1\nStyle: Source,DejaVu Sans,27,&H00B0AAA0,&H00FFFFFF,&H00000000,&H44000000,0,0,0,0,100,100,1,0,1,1,1,2,100,100,65,1\nStyle: Footer,DejaVu Sans,24,&H009A958D,&H00FFFFFF,&H00000000,&H44000000,0,0,0,0,100,100,2,0,1,1,1,2,60,60,35,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'''
def dialogue(layer,start,end,style,text,tags=''):
    return f'Dialogue: {layer},{ts(start)},{ts(end)},{style},,0,0,0,,{{{tags}}}{assesc(text)}'
def chunks(text,target=8):
    words=text.split(); return [' '.join(words[i:i+target]) for i in range(0,len(words),target)] or [text]
def wrap(s,n=34): return '\\N'.join(textwrap.wrap(s,width=n,break_long_words=False,break_on_hyphens=False))
def keywords(text,n=2):
    words=re.findall(r"[A-Za-zÀ-ÿ0-9'’-]+",text)
    stop={'across','generations','the','and','that','with','from','have','this','their','were','into','they','them','such','should','not','been','over','through','about','would','could','there','which','when','what','where','while','your','than','then','also','only','united','states'}
    c=[]
    for w in words:
        if len(w)>=5 and w.lower() not in stop and w.lower() not in [x.lower() for x in c]: c.append(w)
    return sorted(c,key=len,reverse=True)[:n]
def resolve_image(sc,assets,idx):
    if sc.get('image'):
        p=Path(sc['image']).expanduser()
        if not p.is_absolute(): p=assets/p
        if p.exists(): return p
    if not assets.exists(): return None
    imgs=[p for p in assets.rglob('*') if p.suffix.lower() in IMAGE_EXTS]
    if not imgs: return None
    tokens=set(re.findall(r'[a-z0-9]+',sc['text'].lower()))
    scored=[]
    for p in imgs:
        stem=set(re.findall(r'[a-z0-9]+',p.stem.lower().replace('_',' ').replace('-',' ')))
        scored.append((len(tokens&stem),p))
    scored.sort(key=lambda x:(x[0],str(x[1])),reverse=True)
    return scored[0][1] if scored[0][0]>0 else imgs[(idx-1)%len(imgs)]
def make_scene_ass(sc,d,path,w,h,idx,total,title=False):
    """
    Generate collision-safe documentary typography.

    Rules:
      * one primary text treatment at a time
      * narration appears as restrained caption cards
      * punch/chapter text is capped and wrapped
      * WORDS cues never overlap
      * no automatic giant keyword overlays
    """
    lines=[]

    if title:
        title_text=wrap(sc['text'].upper(),24)
        lines.append(dialogue(
            5,0,d,'Chapter',title_text,
            r'\fad(350,450)\fscx103\fscy103\t(0,1800,\fscx100\fscy100)'
        ))
        lines.append(dialogue(
            4,.35,max(.4,d-.35),'Source',
            'A TEXTDOC DOCUMENTARY',
            r'\fad(500,400)\an2\pos(960,930)'
        ))

    else:
        lines.append(dialogue(
            0,0,d,'Footer',
            f'{idx:02d}  /  {total:02d}',
            r'\fad(180,180)'
        ))

        txt=sc['text']
        kind=sc['kind']

        if kind=='chapter':
            lines.append(dialogue(
                3,0,d,'Chapter',
                wrap(txt.upper(),24),
                r'\fad(300,400)\fscx105\fscy105\t(0,1400,\fscx100\fscy100)'
            ))

        elif kind=='quote':
            lines.append(dialogue(
                2,0,d,'Quote',
                '“'+wrap(txt,34)+'”',
                r'\fad(300,400)\an5\pos(960,520)'
            ))

        elif kind=='punch':
            # Keep hero typography short enough to remain inside title-safe area.
            hero=wrap(txt.upper(),20)

            # Long PUNCH blocks get smaller automatically.
            size=104
            if len(txt)>45:
                size=82
            if len(txt)>75:
                size=68

            lines.append(dialogue(
                3,0,d,'Punch',
                hero,
                rf'\fs{size}\fad(180,300)\an5\pos(960,520)'
            ))

        elif kind=='words':
            # Commas/semicolons create explicit sequential cards.
            ws=[x.strip() for x in re.split(r'[,;]|\s{2,}',txt) if x.strip()]

            if not ws:
                ws=[txt]

            seg=d/max(1,len(ws))

            for j,x in enumerate(ws):
                st=j*seg
                en=min(d,(j+1)*seg)

                size=96
                if len(x)>24:
                    size=78
                if len(x)>42:
                    size=64

                lines.append(dialogue(
                    3,st,en,'Punch',
                    wrap(x.upper(),20),
                    rf'\fs{size}\fad(100,120)\an5\pos(960,520)'
                ))

        else:
            # Narration:
            # Show one short readable caption card at a time.
            # NO duplicate dim/highlight layers and NO keyword overlays.
            cs=chunks(txt,7)
            weights=[max(1,len(c.split())) for c in cs]
            total_weight=sum(weights)
            t=0.0

            for c,wt in zip(cs,weights):
                seg=d*wt/total_weight
                st=t
                en=min(d,t+seg)

                lines.append(dialogue(
                    2,st,en,'Body',
                    wrap(c,30),
                    r'\fs54\fad(90,120)\an2\pos(960,875)'
                ))

                t+=seg

        if sc.get('source'):
            lines.append(dialogue(
                4,0,d,'Source',
                'SOURCE  •  '+sc['source'],
                r'\fad(200,200)\an1\pos(100,1000)'
            ))

    Path(path).write_text(
        ass_header(w,h)+'\n'.join(lines)+'\n',
        encoding='utf-8'
    )

def synth(text,out,voice,speed,silence): run(['piper','--model',voice,'--length-scale',str(speed),'--sentence-silence',str(silence),'--output_file',str(out)],text)
def render_visual(ass,out,d,w,h,fps,preset,crf,image=None):
    if image:
        # editorial-photo background: fill frame, slow Ken Burns push, darken for readable type
        vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},zoompan=z='min(zoom+0.00045,1.07)':d={max(1,int(d*fps))}:s={w}x{h}:fps={fps},eq=brightness=-0.22:contrast=1.12:saturation=.72,vignette=PI/5,noise=alls=3:allf=t+u,ass={ass.as_posix()}"
        cmd=['ffmpeg','-y','-v','error','-loop','1','-i',str(image),'-t',f'{d:.3f}','-vf',vf,'-an','-c:v','libx264','-preset',preset,'-crf',str(crf),'-pix_fmt','yuv420p',str(out)]
    else:
        vf=f"noise=alls=7:allf=t+u,vignette=PI/5,eq=brightness=-0.025:contrast=1.08,ass={ass.as_posix()}"
        cmd=['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color=c=0x0b0c0e:s={w}x{h}:r={fps}:d={d:.3f}','-vf',vf,'-an','-c:v','libx264','-preset',preset,'-crf',str(crf),'-pix_fmt','yuv420p',str(out)]
    run(cmd)
def build(a):
    for x in ('piper','ffmpeg','ffprobe'): need(x)
    title,scenes=parse_script(a.script); out=Path(a.output or (Path(a.script).stem+'.mp4')).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    work=Path(a.workdir).resolve() if a.workdir else Path(tempfile.mkdtemp(prefix='textdoc-v3-')); work.mkdir(parents=True,exist_ok=True)
    assets=Path(a.assets).expanduser().resolve(); wavs=[]; ds=[]; visuals=[]
    print(f'[textdoc v3] {len(scenes)} scenes | voice={a.voice} | assets={assets}')
    for i,sc in enumerate(scenes,1):
        wav=work/f'scene-{i:03d}.wav'; print(f'[voice] {i}/{len(scenes)}'); synth(sc['text'],wav,a.voice,a.speed,a.sentence_silence); wavs.append(wav); ds.append(duration(wav))
    silence=work/'intro.wav'; run(['ffmpeg','-y','-v','error','-f','lavfi','-i','anullsrc=r=22050:cl=mono','-t',str(INTRO),'-c:a','pcm_s16le',str(silence)])
    title_ass=work/'title.ass'; make_scene_ass({'text':title},INTRO,title_ass,a.width,a.height,0,len(scenes),True)
    title_v=work/'visual-000.mp4'; render_visual(title_ass,title_v,INTRO,a.width,a.height,a.fps,a.preset,a.crf,None); visuals.append(title_v)
    for i,(sc,d) in enumerate(zip(scenes,ds),1):
        ass=work/f'scene-{i:03d}.ass'; make_scene_ass(sc,d,ass,a.width,a.height,i,len(scenes))
        img=resolve_image(sc,assets,i); print(f"[visual] {i}/{len(scenes)} {'image='+str(img) if img else 'typography'}")
        v=work/f'visual-{i:03d}.mp4'; render_visual(ass,v,d,a.width,a.height,a.fps,a.preset,a.crf,img); visuals.append(v)
    alst=work/'audio.txt'; alst.write_text("file '%s'\n"%silence.as_posix()+''.join(f"file '{p.as_posix()}'\n" for p in wavs)); audio=work/'narration.wav'; run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(alst),'-c:a','pcm_s16le',str(audio)])
    vlst=work/'visuals.txt'; vlst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in visuals)); visual=work/'visual.mp4'; run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(vlst),'-c','copy',str(visual)])
    run(['ffmpeg','-y','-v','error','-i',str(visual),'-i',str(audio),'-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-shortest',str(out)])
    out.with_suffix('.json').write_text(json.dumps({'version':'0.3.0','title':title,'voice':a.voice,'scenes':len(scenes),'duration_seconds':round(INTRO+sum(ds),2),'assets':str(assets),'output':str(out)},indent=2))
    if not a.keep_work and not a.workdir: shutil.rmtree(work,ignore_errors=True)
    print(f'[done] {out}')
def doctor(_):
    for x in ('piper','ffmpeg','ffprobe'): print(f"{x:8} {'OK' if shutil.which(x) else 'MISSING'}")
def voice(a): subprocess.check_call([sys.executable,'-m','piper.download_voices',a.voice])
def main():
    p=argparse.ArgumentParser(prog='textdoc',description='Zero-API editorial documentary generator (Piper + FFmpeg + local images).'); s=p.add_subparsers(dest='cmd')
    b=s.add_parser('build'); b.add_argument('script'); b.add_argument('-o','--output'); b.add_argument('--voice',default=DEFAULT_VOICE); b.add_argument('--assets',default='assets'); b.add_argument('--speed',type=float,default=1.05); b.add_argument('--sentence-silence',type=float,default=.28); b.add_argument('--width',type=int,default=1920); b.add_argument('--height',type=int,default=1080); b.add_argument('--fps',type=int,default=30); b.add_argument('--crf',type=int,default=19); b.add_argument('--preset',default='medium'); b.add_argument('--workdir'); b.add_argument('--keep-work',action='store_true'); b.set_defaults(func=build)
    d=s.add_parser('doctor'); d.set_defaults(func=doctor); v=s.add_parser('voice'); v.add_argument('voice',nargs='?',default=DEFAULT_VOICE); v.set_defaults(func=voice)
    a=p.parse_args();
    if not a.cmd: p.print_help(); return
    try: a.func(a)
    except Exception as e: print(f'textdoc: error: {e}',file=sys.stderr); raise SystemExit(1)
if __name__=='__main__': main()
