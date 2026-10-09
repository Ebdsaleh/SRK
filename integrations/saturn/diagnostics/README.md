# SRK Saturn Diagnostic Core

This directory contains the hardware-neutral C core for SRK's standalone Sega Saturn diagnostic application.

Current implemented core pieces:

- stable eight-item diagnostic menu state;
- normalized digital-pad state with raw-word preservation;
- pressed / held / released edge tracking;
- per-button hold durations and multi-button combination duration;
- explicit L+R combination tracking;
- 30-second / 60 Hz rolling application flight recorder;
- host-driven application shell rendering the main menu, input test, and recorder screen;
- placeholders for video, VDP1/3D, audio, timing/interrupt, memory/dump, and system-information diagnostics.

The core deliberately contains no direct Saturn BIOS controller-buffer address, no SAROO `SS_TIMER` dependency, and no SAROO file-writing call.  Those belong to a host adapter.

The next milestone is a **standalone Saturn host** that implements `SRK_DIAG_HOST` using reviewed Saturn hardware services and drives `srk_diag_app_frame()` from a bootable Saturn application.

Persistent recorder export and memory dumps remain disabled until the standalone storage path has been proven independently.
