# Attribution and sources

## Artisan R2 integration

- Project: [Artisan](https://github.com/artisan-roaster-scope/artisan)
- Source: [src/artisanlib/aillio_r2.py](https://github.com/artisan-roaster-scope/artisan/blob/master/src/artisanlib/aillio_r2.py)
- Snapshot retrieved: September 14, 2026 (local date).
- Local unmodified reference: `research/aillio_r2_reference.py`
- SHA-256: `f909afd159ba74014e1887d8cd4ac9a61f7dd3a9fe4e22f9d3ded434b8ee29ad`
- Copyright (C) 2010–2026 The Artisan team, represented by Marko Luther and all contributors; R2 author mikefsq.
- License: GNU Affero General Public License version 3 or later. The license text is included in `LICENSE`.

Roast Studio's hardware adapter adapts the R2 device identifiers, protocol framing, command CRC behavior, control messages, and telemetry field definitions from this source. The standalone adapter is rewritten for a local recorder with explicit arming, stale-data handling, confirmed incremental controls, and no automatic hardware state cycling. The reference is not instantiated or executed by the application. Tests extract only its two pure packet/CRC methods for byte-for-byte comparison.

## Python USB dependencies

- [PyUSB 1.3.1](https://github.com/pyusb/pyusb): BSD-3-Clause.
- [libusb-package 1.0.26.4](https://github.com/pyocd/libusb-package): Apache-2.0 package, with bundled libusb under LGPL-2.1-or-later.
- [importlib_resources](https://github.com/python/importlib_resources): Apache-2.0; transitive dependency of libusb-package.

Installed distributions retain their own license metadata under `.venv` (macOS) or `.deps` (Windows). Dependencies are not vendored into the Git source tree.

## macOS setup tools

The launcher downloads official releases into the ignored `.runtime` folder:

- [uv](https://github.com/astral-sh/uv) installs a managed Python runtime and the project's virtual environment.
- [Python standalone builds](https://github.com/astral-sh/python-build-standalone) supply the runtime selected by uv.
- [OpenAI Codex CLI](https://github.com/openai/codex) handles official ChatGPT sign-in and model requests.

These tools retain their upstream licensing terms; their binaries are not included in this repository. Download versions and archive checksums for uv and Codex are recorded in `scripts/macos.sh`.

## Manufacturer references

- [R2 unpacking, mechanical checks and seasoning](https://docs.aillio.com/bullet-r2/operation/unpacking-and-preparing/)
- [R2 operation and maintenance](https://docs.aillio.com/bullet-r2/operation/)
- [RoasTime / Bullet connection troubleshooting](https://docs.aillio.com/roastime/troubleshooting/connection-issues/)

The application is an independent project, not an Aillio product. Its icons, grain texture and interface are authored locally. Fonts are served locally and make no external network requests.

## Typography and visual reference

- Instrument Serif, regular and italic: [Google Fonts repository](https://github.com/google/fonts/tree/main/ofl/instrumentserif), SIL Open Font License 1.1. Original font files and license are included under `web/fonts/`.
- [Onoera](https://onoera.com/) supplied the user-requested visual reference: dark space, grainy light fields, editorial serif typography and restrained pill controls. The application uses original code, copy, icons and texture; no site images, proprietary fonts or source code were copied.
