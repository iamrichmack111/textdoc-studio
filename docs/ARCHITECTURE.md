# Architecture

TextDoc Studio separates editorial intent from rendering. `textdoc_studio/` is the Flask workspace. `documentary_v4.py` orchestrates the render, `director_v4.py` chooses treatments, and `cinematic_v4.py` implements archive, graphic, and document visuals. Piper narrates locally and FFmpeg composites/encodes the result.

```text
Browser -> Flask Studio -> project.json + pictures/ -> Documentary V4
                                                |-> Director V4
                                                |-> Piper
                                                |-> Cinematic V4 / FFmpeg
                                                -> output.mp4
```

V3 remains separate as a compatibility/recovery path. Runtime projects, tokens, voices, renders, and recovery snapshots are excluded from Git.
