# Changelog

## 0.4.1 - 2026-07-12

- Stabilized automated Windows portable packaging when antivirus scanning temporarily locks PyInstaller runtime files.
- Updated GitHub Actions to Node.js 24 based action versions.

## 0.4.0 - 2026-07-12

- Added a Windows 64-bit portable package that does not require Python to be installed.
- Added a bundled application icon and portable desktop shortcut helper.
- Separated bundled read-only assets from writable settings, logs, and offline models.
- Added a repeatable PyInstaller build with archive integrity checks.
- Renamed the Python-based package so users can distinguish it from the portable build.

## 0.3.3 - 2026-07-12

- Fixed `start_voice_input.vbs` failing on Windows systems that read UTF-8 VBScript as a legacy ANSI code page.

## 0.3.2 - 2026-07-12

- Added a visible first-run dependency installation flow.
- Added first-run offline model guidance, confirmation, progress, and safe retry handling.
- Changed new installations to default to offline direct-input mode.
- Added API Key validation before recording starts.
- Updated download instructions, troubleshooting, and renamed repository links.

## 0.3.1 - 2026-07-12

- Reorganized user launchers, developer tools, tests, and configuration files.
- Added a focused user-facing README and a maintainer guide.
- Reduced release packages to runtime files and user installation scripts.
- Fixed Windows CI test output and standardized repository text encoding.

## 0.3.0 - 2026-07-12

- Fixed the packaged Codex client window, whose actual process name is `ChatGPT.exe`.
- Replaced the legacy cat with state-driven frog animation frames.
- Added separate optional pet action sound effects.
- Removed the source video's white ground shadow and improved transparent edges.
- Added a separate optional shortcut-triggered laugh extracted from the source video.
- Added a 0-100% volume control for pet tones and laughter.
- Fixed shortcut laughter playing on stop instead of start and prevented pet tones from interrupting it.

## 0.2.0 - 2026-07-11

- Added editable global keyboard shortcuts.
- Added optional X1/X2 mouse side-button selection.
- Added direct-input support for API transcription mode.
- Fixed settings that silently disabled wake or voice feedback options.
- Fixed voice feedback testing when feedback is disabled.
- Added auto-listen readiness checks.
- Added Codex desktop client process matching.
- Prevented window focusing from breaking Windows snap layouts.
- Replaced clipboard paste with direct Unicode keyboard input.
- Added streaming endpoint segmentation and empty-stream protection.
- Added bounded privacy-conscious logs and worker exception traces.
- Reworked the settings interface and reduced empty panel space.
- Added MIT license, contribution guide, example settings, and release packaging.
