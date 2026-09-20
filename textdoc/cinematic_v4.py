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
    # Smooth deterministic Ken Burns movement.
    #
    # The filename selects one of four camera directions so
    # consecutive photographs do not all move identically.
    motion = sum(primary.name.encode("utf-8")) % 4

    if motion == 0:
        # Left -> right
        pan_x = "(iw-iw/zoom)*(on/{frames})"
        pan_y = "(ih-ih/zoom)/2"
    elif motion == 1:
        # Right -> left
        pan_x = "(iw-iw/zoom)*(1-on/{frames})"
        pan_y = "(ih-ih/zoom)/2"
    elif motion == 2:
        # Top -> bottom
        pan_x = "(iw-iw/zoom)/2"
        pan_y = "(ih-ih/zoom)*(on/{frames})"
    else:
        # Bottom -> top
        pan_x = "(iw-iw/zoom)/2"
        pan_y = "(ih-ih/zoom)*(1-on/{frames})"

    pan_x = pan_x.format(frames=max(1, frames - 1))
    pan_y = pan_y.format(frames=max(1, frames - 1))

    # Reach approximately 1.08x at the end of the shot,
    # regardless of scene duration.
    zoom_step = 0.05 / max(1, frames - 1)

    main = (
        f"[0:v]"
        f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
        f"zoompan="
        f"z='min(zoom+{zoom_step:.8f},1.05)':"
        f"x='{pan_x}':"
        f"y='{pan_y}':"
        f"d={frames}:"
        f"s={width}x{height}:"
        f"fps={fps},"
        f"eq=brightness=-0.16:contrast=1.10:saturation=.72"
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
        "x='W-w-105':"
        "y='115':"
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
        "vignette=PI/5"
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


# ============================================================
# V4 VISUAL TREATMENTS
# ============================================================

def make_graphic_scene(
    ass_file,
    output,
    duration,
    treatment="narration",
    width=1920,
    height=1080,
    fps=30,
    preset="veryfast",
    crf=20,
):
    """
    Image-free documentary graphics.

    treatment:
        chapter
        narration
        punch
        quote
        words
    """

    ass_file = Path(ass_file)
    output = Path(output)

    treatment = str(treatment).lower()

    if treatment == "chapter":
        filters = (
            "noise=alls=7:allf=u,"
            "drawgrid="
            "width=160:height=160:"
            "thickness=1:"
            "color=white@0.018,"
            "drawbox="
            "x=0:y=0:w=1920:h=1080:"
            "color=0x5b4935@0.10:t=fill,"
            "drawbox="
            "x=120:y=180:w=8:h=420:"
            "color=0xb89146@0.90:t=fill,"
            "drawbox="
            "x=155:y=180:w=260:h=3:"
            "color=0xb89146@0.55:t=fill,"
            "vignette=PI/4"
        )

    elif treatment == "punch":
        filters = (
            "noise=alls=9:allf=u,"
            "drawbox="
            "x=0:y=0:w=1920:h=1080:"
            "color=0x38120f@0.18:t=fill,"
            "drawbox="
            "x=0:y=470:w=1920:h=8:"
            "color=0xa62c24@0.92:t=fill,"
            "drawbox="
            "x=0:y=490:w=1920:h=2:"
            "color=0xb89146@0.65:t=fill,"
            "vignette=PI/3.7"
        )

    elif treatment == "quote":
        filters = (
            "noise=alls=5:allf=u,"
            "drawgrid="
            "width=90:height=90:"
            "thickness=1:"
            "color=black@0.025,"
            "drawbox="
            "x=170:y=120:w=1580:h=840:"
            "color=0xd8cbb2@0.94:t=fill,"
            "drawbox="
            "x=190:y=140:w=1540:h=800:"
            "color=0x181512@0.08:t=3,"
            "drawbox="
            "x=225:y=205:w=8:h=170:"
            "color=0x9f2720@0.90:t=fill,"
            "vignette=PI/5"
        )

    elif treatment == "words":
        filters = (
            "noise=alls=8:allf=u,"
            "drawgrid="
            "width=240:height=240:"
            "thickness=2:"
            "color=0xb89146@0.035,"
            "drawbox="
            "x=110:y=100:w=6:h=880:"
            "color=0xb89146@0.80:t=fill,"
            "drawbox="
            "x=135:y=100:w=2:h=880:"
            "color=0x9f2720@0.65:t=fill,"
            "vignette=PI/4"
        )

    else:
        filters = (
            "noise=alls=6:allf=u,"
            "drawgrid="
            "width=120:height=120:"
            "thickness=1:"
            "color=white@0.018,"
            "drawbox="
            "x=0:y=760:w=1920:h=320:"
            "color=black@0.30:t=fill,"
            "drawbox="
            "x=72:y=86:w=8:h=116:"
            "color=0x9f2720@0.95:t=fill,"
            "drawbox="
            "x=95:y=86:w=160:h=3:"
            "color=0xb89146@0.70:t=fill,"
            "vignette=PI/4"
        )

    source = (
        f"color="
        f"c=0x151311:"
        f"s={width}x{height}:"
        f"r={fps}:"
        f"d={duration:.3f}"
    )

    vf = (
        filters
        + ","
        + f"ass='{ass_file.as_posix()}'"
    )

    run([
        "ffmpeg",
        "-y",
        "-v",
        "error",

        "-f",
        "lavfi",
        "-i",
        source,

        "-vf",
        vf,

        "-t",
        f"{duration:.3f}",

        "-c:v",
        "libx264",

        "-preset",
        preset,

        "-crf",
        str(crf),

        "-pix_fmt",
        "yuv420p",

        str(output),
    ])


def make_document_scene(
    image,
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
    Historical newspaper/document treatment.

    A blurred copy fills the frame while the readable document
    slowly pushes toward the viewer.
    """

    image = Path(image)
    ass_file = Path(ass_file)
    output = Path(output)

    frames = max(
        1,
        int(duration * fps),
    )

    bg = (
        f"[0:v]"
        f"scale={width}:{height}:"
        "force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        "boxblur=18:8,"
        "eq=brightness=-0.30:saturation=0.35"
        "[bg]"
    )

    paper = (
        "[0:v]"
        "scale=1920:1350:"
        "force_original_aspect_ratio=decrease,"
        "pad=iw+42:ih+42:21:21:"
        "color=0xe0d3b9,"
        f"zoompan="
        "z='min(zoom+0.00020,1.035)':"
        "x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':"
        f"d={frames}:"
        "s=1308x928:"
        f"fps={fps},"
        "format=rgba"
        "[paper]"
    )

    composite = (
        "[bg][paper]"
        "overlay="
        "x='(W-w)/2':"
        "y='(H-h)/2-20'"
        "[doc]"
    )

    finish = (
        "[doc]"
        "drawbox="
        "x=0:y=790:w=1920:h=290:"
        "color=black@0.48:t=fill,"
        "drawbox="
        "x=115:y=90:w=8:h=120:"
        "color=0x9f2720@0.90:t=fill,"
        "vignette=PI/5"
        "[graded]"
    )

    subtitles = (
        f"[graded]"
        f"ass='{ass_file.as_posix()}'"
        "[final]"
    )

    fc = ";".join([
        bg,
        paper,
        composite,
        finish,
        subtitles,
    ])

    run([
        "ffmpeg",
        "-y",
        "-v",
        "error",

        "-loop",
        "1",
        "-i",
        str(image),

        "-filter_complex",
        fc,

        "-map",
        "[final]",

        "-t",
        f"{duration:.3f}",

        "-c:v",
        "libx264",

        "-preset",
        preset,

        "-crf",
        str(crf),

        "-pix_fmt",
        "yuv420p",

        str(output),
    ])


def choose_treatment(scene_kind, has_image=True, document=False):
    """
    Lightweight treatment selector.
    Director V4 will eventually supersede this.
    """

    kind = str(scene_kind).lower()

    if kind in {
        "chapter",
        "punch",
        "quote",
        "words",
    }:
        return kind

    if not has_image:
        return "narration"

    if document:
        return "document"

    return "archive"
