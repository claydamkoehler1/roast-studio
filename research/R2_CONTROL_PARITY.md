# R2 control parity — evidence and implementation

Updated September 15, 2026. Reference: installed RoasTime **4.14.3**, standard Bullet **R2**, not R1 or R2 Pro.

## Status

**Roast Studio is not yet a one-for-one hardware replacement for RoasTime.** The recipe model now represents the inspected RoasTime condition/action behavior. The USB driver still uses verified Artisan-derived increment/decrement packets, while RoasTime requests absolute targets from its proprietary communications process. Similar final settings do not establish identical latency or packets. No physical R2 has been connected during this work.

This is the current status; [the earlier audit](ROASTIME_COMPATIBILITY.md) records the original defects.

## Implemented and tested in software

| Feature | Current implementation |
|---|---|
| Standard R2 settings | P0–P10, F1–F12, D1–D9. Telemetry accepts zero fan/drum readings in idle states. Pro-only power settings are rejected. |
| Recipe sensors | IBTS, bean probe, elapsed time. Sensor identity survives import, editing, storage and display. |
| Comparisons | Temperature ≥ and ≤. Time uses ≥. All conditions in a group must match. |
| Minimum elapsed time | Explicit per rule. Imported second time conditions follow RoasTime's five-second floor. No universal rising-temperature or 65-second gate on new/imported rules. |
| Older Roast Studio recipes | Database v5 preserves their previous hidden IBTS behavior as explicit `min_time=65` and `after_turn=true`; no silently accelerated existing recipes. |
| Actions | Ordered power/fan/drum settings, local yellowing and first-crack markers, text messages and end alerts. Groups run once. A trigger observed while a USB change is pending stays queued. |
| End settings | Imported as a condition group unless a regular group's first event already includes EndRoast, matching the inspected frontend. An end alert never sends PRS or drops the batch. |
| Import | Recipes → Import RoasTime → preview → save. Celsius and Fahrenheit conversion, model validation, unknown-action rejection. Original source JSON retained in SQLite guidance. |
| Editing | Multiple conditions/actions per rule; imported groups are not flattened into independent rules. |
| Replay | Completed hardware roasts can become recipes using observed P/F/D changes at their recorded times. Requires a recording from the start without telemetry gaps, explicit preheat review, and recipe preview before saving. Includes the source curve as a reference; it does not track temperature automatically. |
| Initial settings | Taken from the reviewed recipe and applied after telemetry reports roasting. |
| Timing | USB telemetry wakes the engine; it no longer imposes a one-second delay between confirmed increments. It still serializes changes and is not equivalent to absolute writes. |
| Manual intervention | App changes, unexpected panel setting changes, errors, lost telemetry and failed confirmations pause/disarm automation. Explicit resume skips queued/overdue changes. No unattended keep-alive. |
| Lifecycle | Preheat target, PRS phase progression, automatic charge detection, recording, cooling request and shutdown. Transitions use observed state and wait for telemetry. Physical door handling remains manual. |
| Diagnostics | Bounded raw packet/request trace, sensor data, error fields, fan RPMs, electrical readings; export through the machine dialog. No credentials or account data included. |

The graph workspace is now transparent and minimal: large curve, compact readings, phase button, P/F/D controls and small milestone/recipe controls. Recipe alerts appear only when needed. Its procedural background uses 55% of the normal pool size and 19% of the normal light intensity; other tabs retain their atmosphere.

## Confirmed interoperability observations

These are independently implemented observations from installed frontend text and public sources, not copied proprietary implementation code.

- RoasTime standard-R2 options enumerate P0–P10, F1–F12 and D1–D9. R2 Pro enumerates P0–P14.
- Recipe triggers in its implemented evaluator are IRBeanTemperature=0, ProbeBeanTemperature=1 and Time=3. RoR/milestone names in a shared enum do not establish working trigger support in this build.
- `events` contains AND groups. Groups are considered in stored order. Actions are collected in event/action order and each group commits once.
- RoasTime's application command IDs for R2 include phase progression **27**, preheat **31**, induction **33**, airflow **34**, drum **36**, first-crack start/end **38/39**, second-crack start **40**. These are **not raw USB opcodes**.
- Initial P/F/D are requested when roasting begins. EndRoast produces a notification, optionally a buzzer/blink, rather than initiating cooling.
- Yellowing is recorded locally by the inspected frontend. First crack also requests a machine marker; Roast Studio currently records it locally only.
- RoasTime playback uses historical setting changes at historical times. It is not feedback control that tracks a temperature curve. An overlay alone performs no control.

### Publicly verified USB path

Artisan's R2 adapter supplies the wire format currently used here:

| Request | Four-byte payload before device CRC |
|---|---|
| PRS | `30 01 00 00` |
| Power + / − | `34 01 AA AA` / `34 02 AA AA` |
| Air + / − | `31 01 AA AA` / `31 02 AA AA` |
| Drum + / − | `32 01 AA AA` / `32 02 AA AA` |
| Preheat °C | `35 00 high-byte low-byte` |

Do not derive a direct setting command by substituting RoasTime's internal IDs into this table. RoasTime's installed communications executable is compiled/obfuscated Go; symbol inspection alone did not reveal a verified absolute-command mapping. It was not executed for this investigation.

## Remaining gaps before claiming one-for-one control

1. **Absolute setting writes and grouped timing.** Obtain manufacturer protocol documentation or capture RoasTime USB output for selected targets on the actual R2. Confirm encoding, range handling and acknowledgment behavior before implementation.
2. **Cooling tray and back-to-back controls.** The manual describes C settings and F1 back-to-back. A verified R2 USB command/telemetry mapping is still needed. These controls remain on the panel.
3. **On-machine crack markers and alert hardware.** Local events/messages work. USB crack timestamps, buzzer and blink are unimplemented until their packet mappings are established.
4. **Phase and fault details.** Artisan labels state 8 both cooling and back-to-back in different constants; its control-board-critical field is 16-bit while newer RoasTime definitions mention additional bits. Preserve raw frames and resolve these against actual firmware before asserting complete state/fault parity. The current adapter retains its existing conservative state/error behavior.
5. **Playback timing.** Historical-setting replay is implemented, but observed samples cannot recover exact original command times. Its serialized USB writes retain the timing limitation above.
6. **Physical validation.** Readouts, P10, PRS transitions, preheat, charge detection, manual overrides, disconnects, failures and command timing have only been emulated. Firmware-dependent behavior and USB-driver compatibility remain unproven on this machine.

Firmware updates, calibration, device/account registration and Roast.World synchronization are not implemented as native RoasTime replacements.

## Physical comparison plan

Use one application owning USB at a time. Keep the operator at the panel. Do not bypass deadman protection.

1. Record exact R2 model/firmware and Windows USB interface/driver. Select USB RoasTime mode on the R2.
2. Compare RoasTime and Roast Studio **read-only** telemetry in separate sessions: IBTS, probe, RoRs, P/F/D, machine clock, states and errors.
3. Capture short RoasTime USB traces for each supported phase/setpoint/marker command using an ordinary packet capture tool. Capture only the roaster's USB device. Label the requested action and observed panel result.
4. Export Roast Studio diagnostics for the same deliberate sequence. Compare payloads and timestamps, not just screenshots or final levels.
5. Only after command mappings pass, exercise a supervised recipe with several actions at one trigger, a bean-probe rule, an early five-second IBTS rule, an end alert, a manual override and a telemetry interruption. Verify no action duplicates, unexpected phase changes or automatic resumes.
6. Run the normal cooling/shutdown sequence, then a supervised back-to-back sequence after its mapping is verified. Retain recorded samples, actual settings, events and capture evidence with the firmware version.

## Sources reviewed

- [Aillio R2 operating modes](https://docs.aillio.com/bullet-r2/operation/operating-the-r2/)
- [Aillio roasting procedure](https://docs.aillio.com/bullet-r2/operation/roasting-with-r2/)
- [R2 settings and USB mode](https://docs.aillio.com/bullet-r2/operation/settings-menu/)
- [R2 specifications](https://docs.aillio.com/bullet-r2/operation/r2-specifications/)
- [Manufacturer manual downloads](https://docs.aillio.com/bullet-r2/operation-manuals/)
- [Firmware changelog](https://docs.aillio.com/bullet-r2/firmware-updates-r2/firmware-files/)
- [RoasTime recipes](https://docs.aillio.com/roastime/five-tabs/recipes/)
- [RoasTime playback and overlays](https://docs.aillio.com/roastime/five-tabs/roasts/)
- [RoasTime USB troubleshooting](https://docs.aillio.com/roastime/troubleshooting/connection-issues/)
- [Artisan Aillio support](https://artisan-scope.org/machines/aillio/) and [upstream R2 driver](https://github.com/artisan-roaster-scope/artisan/blob/master/src/artisanlib/aillio_r2.py)
- [R2 integration history, including Artisan 3.1.2 release](https://community.roast.world/t/does-the-r2-pro-work-with-artisan/16703)
- [Community request for an official interface](https://community.roast.world/t/open-api-for-the-bullets-to-support-alternative-roasting-software-artisan/16788)
- [Aillio maintainer confirmation of R2 USB product ID](https://community.roast.world/t/roaster-not-connected-linux/2765/26)
- [Rostoc integration documentation](https://rostoc.co/docs/hardware/aillio-bullet/): explicitly experimental/read-only, not a source for control commands. Its catalog's capacity description conflicts with Aillio's specs, so manufacturer limits take precedence.
- Installed `RoasTime/app-4.14.3/resources/deps/roastime-frontend/dist/assets/index.4fc2271d.js`, its shared recipe definitions, and read-only communications-binary symbol inspection.

## Tests

`tests/test_roastime_compatibility.py` covers source-grounded condition structures, five-second timing, sensor discrimination, Fahrenheit conversion, comparisons, end-rule de-duplication, action ordering, rejected models/commands, P10 frames and packets, idle readings, missing confirmation, queued crossings, SQLite import/save/prepare/execution and migration. Existing lifecycle, disconnection, override, inventory, AI validation and security tests remain in the suite.

Browser checks use an isolated SQLite database and an emulated USB adapter on port 8743. They do not operate real hardware or add sample data to the user's database.

All 67 Python tests pass, including replay validation. JavaScript syntax checks pass for the studio, recipe helpers and atmosphere renderer. Browser checks cover grouped import/edit/save, initial P10, a grouped setting/message trigger, and the simplified workspace.
