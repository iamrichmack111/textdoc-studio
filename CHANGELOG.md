# Changelog

All notable TextDoc Studio development milestones are documented here.

## [Unreleased]

### Planned

- Native 2560×1440 YouTube HQ rendering
- Native 1080×1920 Shorts rendering
- Documentary-to-Short workflow
- Primary and secondary image controls
- Scene-level preview rendering
- Piper pronunciation dictionary
- SRT/VTT caption export
- Incremental render caching
- Render history and master recovery
- Project ZIP import/export
- Automatic documentary source credits
- Improved image reuse avoidance
- Private YouTube OAuth delivery improvements

## [0.4.0] - 2026-09-20

### Added

- TextDoc Studio Flask interface
- Documentary project dashboard
- Three-pane directing workspace
- Story Stack
- Media Library
- Director Inspector
- Semantic documentary scene types
- Bulk structured-story importer
- Local image assignment
- Auto Assign
- Scene Guide
- Export interface
- Documentary preflight
- MP4 download
- MP3 extraction
- Render restart support
- YouTube metadata workspace
- Playwright screenshot automation
- Narrated demo tooling
- Docker and Docker Compose support
- GitHub Actions CI
- Container workflow
- D2 architecture documentation

### Changed

- Studio project data uses structured scene information.
- Local uploaded imagery is the preferred/default media source.
- Source metadata is kept separate from spoken narration.
- Studio rendering uses the Documentary V4 pipeline.

## [0.3.0] - 2026-09-20

### Added

- Deterministic Director V4
- Scene-intent classification
- Concept matching
- Editorial tags
- Project-image scoring
- Document detection
- Graphic-first structural scenes
- Image reuse penalties
- Local-first directing

### Changed

- Removed the normal rendering pipeline's dependency on live Wikimedia Commons.
- Improved relevance scoring for historical and cultural imagery.

## [0.2.0] - 2026-09-20

### Added

- Cinematic V4
- Archive/photo treatment
- Document treatment
- Graphic treatment
- Deterministic Ken Burns movement
- Typography treatments for Chapter, Quote, Punch and Words

### Fixed

- Temporal film-grain flashing
- Excessive secondary-card movement
- Unstable photographic movement
- Scene-to-scene narration volume pumping

### Audio

Narration now receives one final documentary loudness-normalization pass rather
than independent normalization on every scene.

Target:

- Integrated loudness: -16 LUFS
- True peak: -1.5 dB
- Loudness range: 11 LU

## [0.1.0] - 2026-09-19

### Added

- Initial TextDoc CLI
- Piper narration
- FFmpeg documentary rendering
- Chapter scenes
- Quote scenes
- Punch scenes
- Sequential Words scenes
- Local documentary project format

### Fixed

- Duplicate center captions
- Oversized punch typography
- Narration caption placement
- Literal newline escape artifacts
