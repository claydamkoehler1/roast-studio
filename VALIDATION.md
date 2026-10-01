# Validation · Roast Studio

## Conversational recipes and chat repair · September 16, 2026

- Fixed a SQLite type mismatch: conversation IDs from HTTP paths were strings, so JSON job lookups returned no jobs. Numeric normalization restores pending state, errors, replies and recipe attachments. Regression coverage exercises the HTTP getter with a string ID.
- Diagnosed the immediate model failure as Windows access denied in the restricted development-launched server. Relaunched the local server with normal permissions. The Codex request itself remains read-only, tool-disabled, ephemeral and authenticated with the existing ChatGPT account; no API key or replacement model.
- Unified chat output into a conversational message plus an optional validated recipe. The prompt creates recipes when requested or after an accepted offer; ordinary discussion can continue without a recipe. Attached drafts retain full conversation context and can be saved idempotently. Retrying a failed turn does not duplicate the user's message.
- Replaced Send/Generate buttons with a wrapping message box and Enter submission. Bean parameters collapse above the thread. Recipes appear within their assistant message, and progress/errors remain visible. Keyboard input and saving were exercised on an isolated fixture server, with no hardware connection.
- All 70 Python tests pass; JavaScript syntax passes. A real account-backed retry of the user's original 250 g Guatemala request completed with a validated recipe attached to the original conversation. It remains a draft for user review; no roast was started.
- CLI behavior cross-checked against [official non-interactive mode documentation](https://learn.chatgpt.com/docs/non-interactive-mode) and the installed client's help output.

## Navigation and contextual cleanup · September 15, 2026

- Replaced persistent tabs with an accessible full-screen Menu: large serif page links, current-page styling, native focus containment and Escape dismissal. Settings and temperature units live inside the menu. An open workspace remains accessible through Return to roast on other pages.
- The graph's Recipe action opens a read-only view using the prepared batch weight, preheat and frozen execution steps. It offers no replacement or edit actions. Library and planned-batch actions respect an existing workspace; duplicate raw machine commands are absent during a session.
- Removed empty conversation sections, redundant recipe instructions and unusable overlay/comparison actions. Search text survives filtering. Removed unused header styles.
- Page palettes interpolate over several seconds on the existing canvas: teal Home, olive Recipes, forest Beans and slate History. Workspace light size/intensity stays subdued. Reduced-motion and CSS fallback behavior are preserved.
- JavaScript syntax checks passed. Browser checks verified recipe context, menu navigation, Escape/focus return, settings access, comparison visibility, a single healthy WebGL canvas and no console warnings/errors. No data changes or hardware commands were required.

## Minimal workspace and R2 compatibility updates · September 15, 2026

- Replaced the workspace title, phase rail, cards and sidebar with a transparent full-width graph, compact readouts, phase control and P/F/D controls. Workspace background pools are smaller and dimmer; other pages retain their atmosphere. Saving a cooling roast remains available without a connected roaster.
- Corrected P10 support; implemented AND condition groups, bean-probe triggers, ordered actions, local markers and alerts, reviewed RoasTime JSON import, and historical-setting replay. SQLite v5 preserves the old implicit trigger guard for existing recipes.
- All 67 Python tests pass. JavaScript syntax checks pass. Isolated browser checks cover grouped recipe import/edit/save, P10 initialization, grouped trigger execution and the revised graph controls. No physical R2 was operated.
- The [current compatibility report](research/R2_CONTROL_PARITY.md) documents verified behavior and unresolved USB mappings. This is not yet a one-for-one hardware replacement for RoasTime.

## RoasTime compatibility audit · subsequent findings

The [RoasTime 4.14.3 audit](research/ROASTIME_COMPATIBILITY.md) originally found an incorrect P9 limit and missing grouped time/temperature conditions, bean-probe triggers, markers and alerts. Those findings prompted the updates above. The earlier 52-test result below describes the implementation at that time, not parity with RoasTime.

## Recipe execution and R2 phases · September 15, 2026

- Workspace title now uses the batch name. Four machine phases expose state-checked preheat, charge/roast, cooling and optional shutdown commands. The app records automatically after a user-started preparation sequence when telemetry reports roasting.
- Recipes and manual starting settings use the actual R2 command encoder, applying one incremental P/F/D change at a time and waiting for telemetry confirmation. Reviewed recipe steps are frozen at preparation. Manual changes, physical-panel changes, machine errors, stale data and missing acknowledgments pause execution. Resume skips overdue settings. Phase changes remain deliberate; no automatic drop, shutdown or curve-tracking PID was added.
- All 52 tests pass, including 14 new hardware-emulation tests covering the full phase sequence, automatic charge detection, time and temperature recipe triggers, confirmation waits, failures, pause/resume, late joins, inventory accounting, restart behavior, recipe validation and stale-phase races. JavaScript syntax passes.
- Browser exercised connected emulated hardware in an isolated port-8743 database: enable controls, preheat, charge, start roasting, automatic initial settings and timed power change, pause/resume, cooling, shutdown and saving. Production USB was never opened. Physical R2 validation remains pending setup.

## Procedural background · recording reference

- Added an original WebGL light field in `web/atmosphere.js`: independently deforming green/cyan pools, a black center, and grain concentrated in illuminated areas. The renderer persists across navigation, underneath the existing controls.
- Browser confirmed shader compilation, a single active canvas, desktop and 390 × 844 rendering, and collection readability. JavaScript syntax checks passed. The existing CSS background remains available if WebGL initialization fails or the context is lost.
- Rendering is capped at 30 fps and one million pixels, pauses while the document is hidden, redraws once for reduced-motion preference, and resizes with the viewport. No external rendering library or remote assets were added.

## Begin Roast setup refinement

- Updated the chooser to equal full-width squares with olive Manual and teal Recipe themes carried through settings and the action button. Removed the visible header, roaster selector and seasoning checkbox; preparation targets hardware with seasoning disabled.
- Verified the revised desktop and 390 × 844 layouts and recipe preparation into the Bullet R2 workspace, then closed that workspace. No connection, preheat or roast commands were sent, and inventory was unchanged. JavaScript syntax passed.
- Replaced the two-step chooser with one tall dialog containing selectable Manual / Recipe squares, shared batch fields, manual setpoints and a recipe dropdown with starting-setting preview.
- Browser verified both preparation paths in Practice mode. Custom manual values (220 °C, P6/F4/D8) reached the workspace; recipe preparation showed its own preheat and P7/F3/D9. Closed both prepared workspaces without starting a roast or changing inventory.
- Manual inputs survive mode switching; inactive controls are disabled and excluded from required-field validation. Checked the 390 × 844 layout, restored the viewport, and verified JavaScript syntax and an empty browser error log.

## Editorial redesign · September 15, 2026

- Replaced the previous UI stylesheet with a complete design inspired by Onoera: locally served Instrument Serif, original CSS light fields and grain, a persistent compact header, editorial collection lists, redesigned dialogs and a full-width roast workspace. Font licensing and inspiration are documented in THIRD_PARTY.md.
- All 38 automated tests passed. JavaScript syntax passed. Browser console had no errors during the redesign checks.
- Inspected all four sections, recipe selection, Astra conversation layout, bean profile, stock/cost dialogs, and roast history detail. At 390 × 844, inventory values remain accessible without sideways scrolling and the conversation composer remains visible. Restored the normal browser viewport afterward.
- Completed a practice roast in the isolated port-8742 database: preheat, charge, power adjustment, yellowing, first crack, drop, cooling, shutdown, and saving 425 g from a 500 g charge. Verified the resulting History curve and events. Practice left stock unchanged. No physical roaster was operated.
- Preserved production SQLite records. The old UI was backed up under test-results/before-onoera-redesign before replacement. Actual ChatGPT-account and physical hardware qualifications below remain separate from this visual verification.

## Automated checks

**29 Python unittest tests**, plus Python compilation and JavaScript syntax checks.

Existing recorder and protocol coverage includes inventory transactions and rollback, duplicate sessions, seasoning/practice packaging exclusion, over-packaging, milestone ordering, invalid/non-finite inputs, durable samples, interrupted-session recovery, SQLite backup/integrity, process ownership locks, same-origin/token protection, cooling transitions, stale USB data and command confirmation. R2 command bytes are compared against the pinned Artisan reference. Hardware tests use fakes.

New coverage includes:

- Standard R2 recipe limits; rejection of Pro power, changed batch weight, invalid drop ranges, unsupported commands and unknown sources.
- Required initial P/F/D settings and ascending milestones.
- ChatGPT-only authentication checks and removal of environment API-key/base-URL overrides.
- Context filtering to the selected bean and completed, non-seasoning hardware roasts.
- Missing bean measurements remain missing; financial fields are excluded.
- Fixed Astra model selection, structured output, tool-disable arguments and untrusted-data framing.
- Cancellation, failed-job save rejection and interrupted-generation recovery.
- Idempotent recipe saves, SQLite provenance and unchanged inventory.
- Refinement retains the parent recipe and parent ID for retry.
- Edited settings retain their original AI provenance and are marked modified.
- v1 schema migration preserves existing beans and recipes.

## Actual ChatGPT-account integration

Verified with the installed official Codex CLI, version `0.154.0-alpha.6.2`:

- `codex login status` reports ChatGPT sign-in.
- Explicit `gpt-6-astra` smoke request completed successfully.
- A full structured Astra recipe was generated **from the app's Recipes form**, using an isolated Guatemala test lot.
- The result passed validation, saved to SQLite, appeared in the recipe library, and preselected the correct bean/recipe in a new roast.
- A refinement request included the previous draft; cancellation completed and remained visible after reload.

No API key, model substitution, browser credential scraping or physical machine command was used in generation.

## Browser checks

Test app: port 8741, `test-results/v2-browser.sqlite3`, separate from the actual user database.

- Visually inspected the new four-section interface at the browser's normal viewport.
- Checked Recipes and Roast at 390 px viewport width; no horizontal page overflow. Corrected chart text sizing for narrow screens and restored the viewport afterward.
- Created a coffee with origin, process, stock, cost and flavor notes.
- Generated, saved and used the real Astra draft.
- Started a practice roast, changed speed to 30×, adjusted power, and marked yellowing/first crack/drop.
- Saved 425 g from a 500 g simulated charge; History showed 15.0% loss.
- Reloaded the recording and saved tasting notes/score afterward.
- Confirmed practice left the green stock unchanged.
- Created a planned batch and verified the saved queue.
- Used a clearly labeled database fixture to test packaging: one 340.194 g bag at $17, calculated contribution, saved ledger entry and label view. The fixture involved no hardware. Physical printing was not performed.
- Browser console error list was empty after these flows.
- Validated CSV/JSON exports and downloaded SQLite backups separately.

## Production upgrade

The app on port 8740 uses the real SQLite database. It contains no QA inventory or generated QA recipes. The unfinished **My first roast** practice session was preserved as interrupted, with **all 1,252 recorded samples** and no invented final weight. The pre-upgrade snapshot and upgraded database both pass `PRAGMA integrity_check`.

## Physical hardware limitation

Not performed: live USB connection, driver/firmware acceptance, panel-to-app temperature comparison, actual heat/fan/drum commands or a physical roast. A supervised acceptance run on the user's standard R2 remains necessary before treating the hardware adapter as validated. Recipe quality also requires actual roasting and tasting; software simulation is not thermal validation.

## Dark Roast Studio refinement

Renamed the app, replaced the light palette throughout, removed the roast sidebar and repeated page copy, widened the main canvas, enlarged readings and controls, and expanded history/compare dialogs. Temperature axes now fit the recorded curve. JavaScript syntax and Python compilation passed. Browser checks covered the four sections and saved-roast display; the desktop live graph spans 1,167 px in a 1,280 px viewport.

## Bean importer · v3.1

- 38 automated tests: extraction of visible page text and Product JSON-LD, public URL/address restrictions, failed fetch behavior, flexible document validation, idempotent save, provenance retention, recipe context propagation, and prior inventory/roast/conversation regressions.
- Live Astra/ChatGPT test against the supplied Sweet Maria’s Guatemala San Martin Jilotepeque product page, in a separate database on port 8742. Read approximately 13.5k characters of captured context; generated 21 facts and five narrative sections.
- Browser checked pending import, completed review, save to test inventory, clicking the coffee to reopen its popup, original-source disclosure availability and absence of console errors.
- A recipe conversation for the imported test lot includes the full captured source and generated document. No test coffee or invented stock was added to the production database.
- Public-page fetching can fail on sign-in, anti-bot, JavaScript-only or oversized pages; pasted page text is supported. Physical R2 testing remains outside this UI/import change.
### Direct inventory editing

- Verified clickable stock and cost values in the Beans list using the isolated test database.
- Added 1 lb (453.59237 g), then subtracted the same weight in grams; stock returned to 1000 g. Excessive subtraction was rejected without altering stock.
- Saved $12 per 1 lb and verified $26.46/kg; saved $8 per 500 g and verified $16/kg. Cost updates left stock unchanged.
- Removed stock/cost editing from the bean profile and import preview. Profile notes remain editable.
- All 38 existing tests and JavaScript syntax check passed. Production inventory was not modified during validation.
### Visual refinement

- Added a shared finish stylesheet: copper and teal gradients, serif studio title, clearer selected tabs, layered dark surfaces, and restrained hover/page/dialog motion.
- Reviewed Roast, Recipes, Beans, History and roast selection in the browser. Checked the 390 × 844 Roast layout with no page overflow; restored the normal viewport afterward.
- JavaScript syntax check passed; browser console contained no errors. Reduced-motion styles disable transitions and animation. Print styles remain outside the screen-only finish.
- Kept the user's existing recipe pane intact and opened the updated design in a separate preview tab. No inventory, recipe or roast records were changed.
### Stable tab layout and earth-tone palette

- Header and navigation now remain mounted. The app uses a fixed viewport shell with scrolling inside the content area and a reserved scrollbar gutter. Page transitions use opacity only.
- Browser geometry checks across all four tabs: identical 1434 px header width and 1424 px content width at 1434 × 1272; identical 390 px header and 380 px content at 390 × 700.
- At 1000 × 480, History overflowed vertically while Roast did not; both retained a 1000 px header and 990 px content width. Document dimensions stayed 1000 × 480.
- Verified the borderless stock dialog actions and horizontal table scrolling at narrow widths. Restored normal viewport afterward. No browser errors; JavaScript syntax check passed.
- Applied the supplied espresso, roast, bark, walnut, dust, parchment, olive, sage, coffee, caramel, crema and status colors, including chart curves. No inventory or recipe data changed.

## Fahrenheit, experience levels and graph readability · September 16

- All temperature displays and entry fields use Fahrenheit. Explicit Celsius temperatures in existing chat, recipe and bean source prose are converted for display; rate-of-rise and temperature differences use the correct scale conversion without the absolute-temperature offset. Machine commands, stored telemetry and raw data exports retain native Celsius.
- Added persistent Beginner, Intermediate and Advanced experience settings to Astra. Beginner is the default. The current setting applies to the next reply in existing conversations as well as new conversations.
- Increased chart curve thickness, axis and annotation sizes, guide contrast, live readings, and power/air/drum controls while preserving the muted workspace background.
- Validation: 71 Python tests and 4 JavaScript conversion tests passed; JavaScript syntax check passed. A real isolated Astra conversation converted a 200 Celsius source reference to 392 Fahrenheit and gave a short beginner explanation. No test messages were added to the production conversation.
- Browser reviewed the recipe conversation, converted legacy recipe prose, experience switching and roast workspace. Prepared a saved recipe for visual review only; no connection or machine operation was started. Physical hardware acceptance remains outstanding.

## Recipe graph guide cleanup · September 16

- Moved recipe action/condition text from the plotting area into a spaced, color-matched step key. Each step retains its complete conditions, including minimum elapsed time and turning-point qualification.
- Removed vertical time-guard markers for combined temperature/time rules; standalone scheduled time actions still have vertical guides. The existing recipe had four coincident 90-second guard markers.
- Labelled the dashed recipe target as an illustrative sketch and distinguished recorded overlays. Moved preheat into the chart key instead of plotting it as a bean-temperature threshold.
- Browser checked the production prepared workspace with four distinct step colors, no overlapping labels and no console errors. JavaScript syntax passed. Recipe conditions, saved data and machine control execution are unchanged.

## Focused live graph · September 16

- Removed recipe threshold guides, automatic illustrative target curves and the step strip from the live workspace. Recipes remain available in the existing read-only Recipe panel without leaving the roast. Explicitly chosen recorded overlays remain supported.
- Removed the unused guide/step-key rendering and styles. This presentation change does not modify recipe automation, trigger conditions or saved recipes.
- JavaScript syntax passed. Browser verified the clean graph and opening/closing the recipe panel; no console errors. No hardware actions were performed.

## Integrated recipe progress · September 16

- Added a connected recipe timeline inside the upper roast control area. Starting settings form one charge step, followed by the actual recipe condition/action groups. The recipe title opens the existing full details panel; the duplicate footer Recipe button was removed.
- Progress comes from runner acknowledgements, with separate applying, current, applied, next, upcoming and skipped presentation. Pausing shows the last applied step without asserting that settings remain current after a manual override. Cooling clears the current marker, and recipe completion does not imply that cooling has started.
- Runner snapshots expose initialization, applying index and last confirmed index. Command execution semantics are unchanged. Out-of-order triggers retain their own completion state.
- Passed 15 recipe control tests (including pending-versus-confirmed progress), five frontend progress tests, four temperature tests and JavaScript syntax validation. Browser reviewed prepared, running and paused timelines; running/paused used an isolated UI fixture with no hardware or production records. The fixture was shut down after validation.

## Recipe color bar and start markers · September 16

- Moved recipe segments directly beneath the graph. Every segment has its own color, a numbered Start/temperature-and-time condition, and complete Power/Air/Drum settings carried forward through the recipe. Active segments use a filled highlight; upcoming, applying, applied and skipped states remain distinguished.
- Record each recipe step's actual execution-start time, IBTS and intended full settings as a SQLite recipe_step event. Starting settings are one combined marker. Matching dots render from these events in the live graph and saved roast chart; planned future steps do not produce invented points. Older recordings without these events do not gain retrospective markers.
- Confirmed start events are emitted once, before final acknowledgement but only after a successful command request or already-satisfied setting. Execution ordering and command targets are unchanged.
- Validation: 73 Python tests and seven frontend progress tests passed, plus syntax validation. An isolated practice-display fixture verified colored segments, active fill and matching graph dots; it was shut down afterward. Both open production app tabs were refreshed; no hardware was connected or operated.

## Auto/Manual switch and coordinated solid colors · September 16

- Added a persistent Auto/Manual choice before roasting and a real recipe execution switch while roasting. Manual pauses the recipe and replaces its bar with Power/Air/Drum controls. Auto resumes future conditions without replaying overdue changes. Automatic pause/error states also expose manual controls. Auto requires a recipe and fresh, armed roasting telemetry when resuming hardware control.
- A recipe prepared in Manual starts with its recipe runner paused, sending no initial or subsequent recipe settings; the operator controls the machine. Existing manual-roast startup behavior is preserved. Manual adjustments pause automation consistently for practice and hardware.
- Moved the recipe title to the upper left, retaining click-through to its details. Removed the redundant Pause/Resume footer buttons.
- Final visual preference: opaque, solid olive, khaki, sand, caramel and walnut segments. Active steps use a brighter solid fill; markers share the same coordinated palette. No translucent segment backgrounds.
- All 75 Python tests and seven frontend progress tests passed; JavaScript syntax passed. Browser verified prepared Auto/Manual switching, persistence on refresh, title placement, hidden/shown controls and an isolated active-step preview. Production remained disconnected; no hardware commands were sent during QA. Preview shut down after inspection.
# macOS release preparation - October 1, 2026

- Added Finder-launchable Start, Stop, and Connect ChatGPT scripts; private virtual-environment setup, Apple Silicon/Intel Homebrew discovery, official browser login, background startup, and idle-sleep prevention.
- macOS uses `~/Library/Application Support/Roast Studio`; Windows retains its existing database location. No personal database or credential cache is part of the source distribution.
- Local verification: 84 Python tests and 11 JavaScript tests pass. New tests exercise platform paths, subscription-only environment handling, cross-process SQLite locking, existing-server reuse, foreign-service rejection, login orchestration, HTTP startup, and refusal to stop an unfinished roast. Shell syntax and frontend syntax checks pass.
- Checked the official Codex CLI 0.160.0 execution flags and disabled-feature names. No AI prompt or account credential was copied during these checks. Live account/model availability still depends on each installation.
- Gitleaks 8.30.1 scanned the staged source with no leaks found. A separate staged-file audit checked for databases, authentication/configuration folders, logs, private planning notes, and personal identifiers. Commit identity uses GitHub's no-reply address.
- GitHub Actions covers macOS ARM64, macOS Intel, Windows, and Linux. CI does not exercise physical USB commands, browser OAuth completion, or an actual roast; hardware acceptance remains outstanding.
- Hosted runs passed all Python/JavaScript checks on both Apple Silicon and Intel Macs, plus Windows. Both Macs also passed actual background-launch, existing-server reuse, and shutdown tests with an isolated database and no account or hardware connection. CI installs Linux's system libusb and checks native library linking without requiring a USB bus; Mac setup additionally checks backend initialization. Hosted Linux backend initialization returned no backend, so no Linux USB-device support is claimed by these tests.
