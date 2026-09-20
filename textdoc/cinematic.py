from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run(cmd):
    print("[cinematic]", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def load_manifest(path):
    p = Path(path)

    if not p.exists():
        return []

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def image_files(directory):
    root = Path(directory)

    if not root.exists():
        return []

    exts = {".jpg", ".jpeg", ".png", ".webp"}

    return sorted(
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )


def source_for(image, manifest):
    name = Path(image).name

    for item in manifest:
        local = Path(item.get("local_file", "")).name

        if local == name or name.endswith(local):
            title = item.get("title", "")
            artist = item.get("artist", "")
            license_name = item.get("license", "Public domain")

            bits = [x for x in (title, artist, license_name) if x]
            return " • ".join(bits)

    return "WIKIMEDIA COMMONS • PUBLIC DOMAIN"


def make_cinematic_scene(
    primary,
    secondary,
    ass_file,
    output,
    duration,
    width=1920,
    height=1080,
    fps=30,
    preset="veryfast",
    crf=20,
):
    """
    Compose an archival documentary scene.

    Primary:
        large animated photograph

    Secondary:
        floating archival card

    ASS:
        TextDoc captions / titles
    """

    primary = Path(primary)
    secondary = Path(secondary) if secondary else primary
    ass_file = Path(ass_file)
    output = Path(output)

    frames = max(1, int(duration * fps))

    # Main image:
    # crop -> subtle Ken Burns push -> grade.
    main = (
        f"[0:v]"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan="
        f"z='min(zoom+0.00035,1.055)':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={frames}:"
        f"s={width}x{height}:"
        f"fps={fps},"
        f"eq=brightness=-0.16:contrast=1.10:saturation=.72,"
        f"boxblur=1:1"
        f"[bg]"
    )

    # Secondary archival photograph.
    card = (
        "[1:v]"
        "scale=650:650:force_original_aspect_ratio=decrease,"
        "pad=iw+20:ih+20:10:10:color=0xddd2bd,"
        "rotate=-0.025:fillcolor=0x00000000,"
        "format=rgba"
        "[card]"
    )

    # Composite.
    composite = (
        "[bg][card]"
        "overlay="
        "x='W-w-105+8*sin(t*0.55)':"
        "y='115+5*sin(t*0.7)':"
        "format=auto"
        "[collage]"
    )

    # Add dark gradient-ish lower region, vignette and grain.
    grade = (
        "[collage]"
        "drawbox=x=0:y=760:w=1920:h=320:"
        "color=black@0.48:t=fill,"
        "drawbox=x=72:y=86:w=8:h=116:"
        "color=0x9f2720@0.95:t=fill,"
        "vignette=PI/5,"
        "noise=alls=4:allf=t+u"
        "[graded]"
    )

    # Burn TextDoc ASS after visual composition.
    subtitles = (
        f"[graded]"
        f"ass='{ass_file.as_posix()}'"
        "[final]"
    )

    fc = ";".join([
        main,
        card,
        composite,
        grade,
        subtitles,
    ])

    run([
        "ffmpeg",
        "-y",
        "-v", "error",

        "-loop", "1",
        "-i", str(primary),

        "-loop", "1",
        "-i", str(secondary),

        "-filter_complex", fc,

        "-map", "[final]",
        "-t", f"{duration:.3f}",

        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",

        str(output),
    ])
