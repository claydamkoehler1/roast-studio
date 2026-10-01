// Stored telemetry and commands stay in the machine's native Celsius units.
export const toF = c => Number(c) * 1.8 + 32;
export const toC = f => (Number(f) - 32) / 1.8;
export const preheatC = f => Math.round(toC(f));
const display = n => String(Math.round(n * 10) / 10);

// Convert explicitly labelled source temperatures without guessing unlabelled numbers.
// Temperature changes/rates do not receive the +32 offset.
export function fahrenheitText(value) {
  const text = String(value ?? '');
  return text.replace(/(-?\d+(?:\.\d+)?)\s*(?:(?:–|—|-|to)\s*(-?\d+(?:\.\d+)?)\s*)?(?:°\s*|degrees?\s*)?(?:Celsius|centigrade|C)\b(\s*(?:\/\s*(?:min(?:ute)?|m)\b|per\s+minute\b))?/gi,
    (match, lo, hi, rate, offset) => {
      const before = text.slice(Math.max(0, offset - 45), offset);
      const after = text.slice(offset + match.length, offset + match.length + 35);
      const delta = !!rate || /(?:\bby|\bdelta(?:\s+of)?|\b(?:difference|change|increase|decrease|rise|drop)\s+of|\b(?:RoR|rate of rise)\s*(?::|of|is|at)?)\s*$/i.test(before)
        || /^\s+(?:rise|drop|increase|reduction|difference|change)\b/i.test(after);
      const convert = n => display(delta ? Number(n) * 1.8 : toF(n));
      return convert(lo) + (hi === undefined ? '' : '–' + convert(hi)) + ' °F' + (rate ? '/min' : '');
    });
}
