# RoasTime compatibility audit

Historical audit: the fixes and remaining limitations are tracked in [R2 control parity](R2_CONTROL_PARITY.md). The defects below describe the implementation before those fixes.

Inspected September 15, 2026. Installed reference: **RoasTime 4.14.3**, Recipes → Aillio Select. This was a read-only inspection; no recipe was started and no USB device was opened.

## Conclusion

Roast Studio implements the same basic roasting controls, but its current recipe model and execution timing are **not equivalent to RoasTime**. Its passing internal tests do not establish RoasTime compatibility. The standard R2 power limit is also incorrect in Roast Studio: it must support P10, not stop at P9.

## Direct observations in Aillio Select

Two standard-R2 recipes were inspected (the collection also includes R1 and R2 Pro recipes, which must be distinguished).

- **[PRO] Julian Rivera's MX BrC Champion**: 200 g; preheat 225°C; initial P6/F1/D9. Its early IBTS conditions include 54.9°C with a minimum elapsed time of 5 seconds to request P8, and 56°C with the same time condition to request F3. It also mixes bean-probe temperature conditions, automatic yellowing/first-crack markers, and an end alert with a separate minimum time.
- **[LAB] Blackcurrant, Honey - 1000g**: explicitly labeled R2; preheat 310°C; initial P10/F3/D9. Later temperature conditions change power and airflow, with a 5-second minimum elapsed time displayed.

These are observations of recipe settings, not recommendations to use these settings for a different coffee or batch size.

## Behavior comparison

| Area | RoasTime reference | Roast Studio at audit time |
|---|---|---|
| Standard R2 power | Includes P10 | P0–P9 cap in hardware commands, telemetry decoder, recipe API, AI validator/context and UI |
| Temperature sensor | IBTS or bean probe | IBTS only |
| Conditions | Temperature comparison AND elapsed-time condition; temperature can use ≥ or ≤ | One time or IBTS threshold; only ≥ |
| Early IBTS triggers | Recipe-specific minimum time, commonly 5 seconds | Global >65-second and positive-RoR gate |
| Multiple actions | A condition group can request several actions | Separate single-control steps, serialized through one pending command |
| Setting changes | Sends requested absolute setting to the R2 communications layer | Sends increment/decrement USB commands, one confirmed step per worker iteration |
| Initial P/F/D | Issued once when roasting is detected | Applied after roasting is detected, sequentially |
| Markers | Recipe actions can mark yellowing and first crack | User marks them manually |
| Notifications | Recipe popups and end alerts; optional buzzer/blink commands | No corresponding recipe actions |
| End-roast action | Notification, with optional sound/blink; does not call cooling in the inspected dispatcher | User deliberately starts cooling; no recipe end alert |
| Model selection | R1, R2 and R2 Pro recipes are distinguished | Standard R2 only; no RoasTime recipe importer |

### A concrete timing mismatch

The Julian Rivera recipe can request its early IBTS-triggered P8 change once both its temperature threshold and 5-second condition are satisfied. Roast Studio would defer an equivalent IBTS rule until after 65 seconds and positive RoR. It cannot represent the original condition exactly, even if its target power is the same.

### A concrete power-limit failure

Read-only local checks reproduced three failures:

- A P10 recipe step is rejected by `validate_steps`.
- A bean-probe trigger is rejected by `validate_steps`.
- A synthetic valid-temperature R2 telemetry frame reporting P10 is rejected by `decode_frame` as an unsupported control reading.

Consequently the P9 assumption affects telemetry reception as well as selecting or executing a recipe. This is an implementation error, not a difference between an R2 and an R2 Pro recipe.

## Command-level evidence and limits

The installed frontend's `executeRecipeActions`, `checkForRecipe`, `checkForRecipeActions`, and `sendCommandToRoaster` were inspected as text, without executing vendor code.

- Recipe power, airflow and drum actions request absolute values.
- For R2-family devices, the frontend routes these requests to its NewEra setting commands (internal command IDs 33, 34 and 36). Preheat uses internal ID 31 and machine-state progression ID 27.
- These IDs belong to RoasTime's application/communications interface. They are **not USB opcodes** and must not be copied into Roast Studio's USB packet encoder.
- Roast Studio uses its Artisan-derived increment/decrement protocol path. Reaching the same final level does not establish identical timing, grouped-action behavior or packet sequences.
- The inspected recipe evaluator requires every condition in a group to pass and commits each group once. Its implemented switch handles IBTS, bean probe and time. Additional enum names for RoR and milestones exist in a shared model, but this audit does not claim those are executable trigger types in this build.
- Full on-wire equivalence remains unverified: RoasTime's communications executable was not traced against a connected roaster.

## Work needed before claiming recipe compatibility

1. Correct standard-R2 P10 support consistently, with tests for P10 telemetry and a P9→P10 change; retain rejection of R2 Pro-only levels.
2. Represent sensor choice, comparison, minimum elapsed time and grouped actions without losing recipe semantics. Replace the hard-coded 65-second rule with explicit recipe conditions.
3. Add marker, popup and end-alert actions; preserve the distinction between an alert and a physical phase command.
4. Verify the supported R2 absolute-setpoint command protocol before changing the USB implementation. Test grouped changes and initial settings against that protocol.
5. Add compatibility fixtures based on observed condition structures and expected commands, beyond tests of our own assumptions.
6. Verify both applications' requested settings, observed machine settings and command timing on the actual R2 after setup.

## Sources

- Installed RoasTime 4.14.3, Aillio Select recipe screens listed above.
- Installed frontend: `%LOCALAPPDATA%/RoasTime/app-4.14.3/resources/deps/roastime-frontend/dist/assets/index.4fc2271d.js`.
- Bundled shared definitions: `@aillio/aillio-common/lib/models/Recipe.ts`, `lib/roastime/Command.ts`, `lib/constants/index.ts`. The frontend contains newer R2 command routing than the shared legacy command enumeration.
- [Aillio recipe documentation](https://docs.aillio.com/roastime/five-tabs/recipes/): sensor choice, combined temperature/time conditions and notification actions.
- [Aillio R2 specifications](https://docs.aillio.com/bullet-r2/operation/r2-specifications/): standard R2 has ten heating levels and 1700 W; R2 Pro has fourteen and 2300 W.
- Roast Studio: `roasting/automation.py`, `roasting/hardware.py`, `roasting/engine.py`, `roasting/server.py`, `roasting/astra.py`, `roasting/knowledge.py`, `web/studio.js`.

No proprietary RoasTime implementation was copied into Roast Studio. This document records interoperability observations and remaining work.
