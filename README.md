# Roast Studio

A local coffee-roasting workspace for the **standard Aillio Bullet R2**. Home, Recipes, Beans, and History share a dark, atmospheric interface. Record roasts, manage green coffee, follow recipes, and discuss roasting with Astra through your ChatGPT account. Everything is stored in SQLite on your computer.

**macOS (Apple Silicon and Intel) and Windows.** No web hosting, API key, or Node build is required to run the app.

> Hardware control is experimental. Protocol and simulated-machine tests pass, but physical R2 USB/thermal behavior has not yet been validated. This is an independent project, not an official Aillio app or a verified one-for-one replacement for RoasTime. See [control compatibility](research/R2_CONTROL_PARITY.md).

## Start on a Mac

1. Clone or download this repository and put it in a local folder, outside iCloud/Dropbox/OneDrive.
2. If you do not already have Python 3.12+ or Homebrew, install [Homebrew](https://brew.sh). The launcher can then install Python for you. Alternatively, install [Python 3.12+](https://www.python.org/downloads/macos/) yourself.
3. Double-click **Start Roasting.command**.
4. On first launch, it creates a private Python environment and installs the USB libraries. If Homebrew is available, it also installs the official Codex CLI if missing.
5. If ChatGPT is not connected, complete the sign-in in the browser that opens. Roast Studio then opens at **http://127.0.0.1:8740**.

Subsequent launches reuse the installed dependencies and saved login. You can close the launcher Terminal window after the app opens; the recorder keeps running. **Stop Roasting.command** stops the app, refusing to interrupt an unfinished roast.

**Connect ChatGPT.command** runs setup/sign-in separately if you skipped it or need to reconnect. Without Homebrew, you can install the official CLI using `npm install -g @openai/codex` if Node.js is installed. The app also works without AI.

If a ZIP download loses execute permissions, open Terminal in the extracted folder and run:

```sh
chmod +x ./*.command
./Start\ Roasting.command
```

Do not disable macOS security protections. If macOS blocks a downloaded launcher, inspect the code and use the system's normal Open/Privacy & Security controls only if you trust this repository.

### Where Mac data lives

```text
~/Library/Application Support/Roast Studio/roasting.sqlite3
```

Logs are stored beside that database. Updating or replacing the code folder does not replace your beans, recipes, or history. `ROAST_DB` or `python run.py --database /path/to/roasting.sqlite3` can override the database path.

The Mac launcher uses `caffeinate` to prevent idle system sleep while its server is running. Keep the laptop open and powered during a roast; closing the lid or explicitly sleeping the computer can still interrupt USB communication.

## Start on Windows

Double-click **Start Roasting.cmd**. It looks for `.venv`, the bundled Codex Python runtime, then Python on PATH. Install Python 3.12+ if none is available. Run **Install USB support.cmd** once for physical USB support. **Stop Roasting.cmd** stops the server after the active batch is saved.

The default Windows database remains `data/roasting.sqlite3` so existing installations retain their records. Use a local, non-synchronized database for hardware recording.

## ChatGPT setup and privacy

Astra uses the **official Codex CLI**, signed in with **ChatGPT**, and explicitly requests **`gpt-6-astra`**. It uses your account's available Codex usage. Model access depends on your account; the app does not substitute a different model or fall back to API billing.

- On Mac, launch **Connect ChatGPT.command**, then sign in in the browser.
- On Windows, sign in with ChatGPT in Codex, or run `codex login`.
- Open **Menu → Settings → Check sign-in** in Roast Studio.
- Choose Beginner, Intermediate, or Advanced to adjust explanation depth.
- In **Recipes → Add recipe**, chat normally. Enter sends a message. Ask Astra to create a recipe when ready, then review and save the draft.

Codex stores its own login locally or in the OS credential store. Roast Studio never reads, copies, or stores your login tokens. API-key sign-in is rejected; API credential environment overrides are removed from child processes. The launcher and app use the same CLI discovery and login location.

Only the selected coffee's captured source/profile, conversation, goal, machine reference pack, and relevant completed real roasts are sent to OpenAI. Financial data and unrelated beans are excluded. Requests and replies are saved in your **local** database. Beans and roasts are not uploaded to GitHub.

Generation uses an ephemeral, read-only Codex process with user configuration, hooks, plugins, shell, browser, and device tools disabled. Output is validated before becoming a draft. Creating a recipe never operates the roaster. If the CLI is outdated, update it with `brew upgrade --cask codex` or `npm install -g @openai/codex`, then retry. CLI argument compatibility was checked with 0.160.0; this does not guarantee model entitlement.

Official references: [ChatGPT/Codex authentication](https://learn.chatgpt.com/docs/auth), [Codex CLI](https://learn.chatgpt.com/docs/codex/cli).

## The workspace

| Page | Purpose |
|---|---|
| Home | Prepare a manual or recipe roast, view live temperatures, control machine phases, and save the batch. |
| Recipes | Chat with Astra, create/edit recipes, review source context, and select a recipe for a roast. |
| Beans | Import a seller-page URL or pasted text into a flexible bean profile; edit stock and cost. |
| History | Review graphs, compare roasts, record tasting notes, export CSV/JSON, and track packaging. |

The roast graph shows large readouts and a compact recipe bar with complete **P / F / D** settings. Active steps are highlighted; matching graph dots record where they began. **Manual override** replaces the recipe bar with controls; **Exit manual** resumes future automation, skipping overdue changes. The interface uses Fahrenheit; native machine data and exported raw telemetry remain Celsius.

## Connect the Bullet R2

1. Complete Aillio's setup, ventilation, and seasoning instructions.
2. Plug in USB, select USB for RoasTime on the R2, and close RoasTime/Artisan so they release the device. On Mac, allow the USB accessory if macOS asks.
3. Prepare a batch and click **Connect R2**. Compare readings with the physical panel before enabling controls.
4. Enable machine controls explicitly. Start preheating and let the R2 reach Charge.
5. Add the beans physically. The app starts recording when the R2 reports roasting, applies starting settings, and deducts inventory once.
6. Recipe mode follows its time/temperature conditions. Manual override pauses recipe execution.
7. Start cooling, then physically open the door to discharge. After the beans cool, optionally initiate the machine's shutdown/cooldown sequence.
8. Save the cooled weight and later add tasting notes.

Supported standard R2 settings: **P0–P10, F1–F12, D1–D9**. This adapter does not support the R2 Pro's higher power stages. Stale readings, unconfirmed commands, and machine errors disarm controls. The app does not bypass the machine's deadman behavior, update firmware, open doors, or autonomously restart a roast after a server restart. If the app or USB fails, use the physical controls.

USB uses PyUSB/libusb-package and an Artisan-derived protocol. No hardware access occurs at app launch or during AI setup. On Windows, consult [Aillio's connection guidance](https://docs.aillio.com/roastime/troubleshooting/connection-issues/) if a driver is needed. On Mac, no Windows driver installer is used. If libusb cannot load, run `brew install libusb` and restart; keep Python and dependencies native to the Mac's architecture.

## Back up or move from Windows to Mac

1. Finish and save any roast. In **Settings → Storage & backup**, download a consistent SQLite backup.
2. Transfer that backup privately to the Mac. It contains your conversations and other personal data; do not commit it to Git.
3. Stop Roast Studio on the Mac. Preserve any existing Mac database separately.
4. Put the backup at `~/Library/Application Support/Roast Studio/roasting.sqlite3` and start the app again. Alternatively, point `ROAST_DB` at the backup's new local path.
5. Sign in to ChatGPT on the Mac using **Connect ChatGPT.command**. Do not transfer login-token files.

Database migrations are additive. A server restart marks unfinished recordings as interrupted; History allows recovery with the actual cooled weight. Only one process can own a database at a time. The server binds to `127.0.0.1` and validates request origin and write tokens; do not expose it to the Internet.

## Development

Python 3.12+, optionally Node 22+ for JavaScript tests. USB packages are pinned in `requirements.txt`. No frontend build step.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
python -m unittest discover -s tests -v
node --test tests/temperature.test.mjs tests/recipe-progress.test.mjs
node --check web/studio.js
```

GitHub Actions tests Apple Silicon macOS, Intel macOS, Windows, and Linux, including USB backend loading without opening a device, SQLite locking, local HTTP lifecycle, recipe automation fixtures, AI request validation, and JavaScript helpers. These checks cannot validate an attached physical Bullet or your ChatGPT entitlement.

| File | Responsibility |
|---|---|
| `roasting/hardware.py` | USB frames and confirmed commands |
| `roasting/engine.py`, `roasting/automation.py` | Recording and recipe execution |
| `roasting/store.py` | SQLite, migrations, inventory, backup |
| `roasting/astra.py`, `roasting/knowledge.py` | ChatGPT jobs, validation, roasting references |
| `roasting/runtime.py`, `launcher.py`, `scripts/macos.sh` | Platform paths, setup, startup, sign-in |
| `roasting/server.py` | Local HTTP API |
| `web/` | Interface, charts, atmospheric background |

`.gitignore` excludes databases, logs, exports, local credentials, environments, and private planning notes. Review staged files before publishing; do not rely on ignore rules alone. See [VALIDATION.md](VALIDATION.md) for test history.

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md), including the Artisan protocol and Instrument Serif font attribution.
