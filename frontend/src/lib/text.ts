// Text hygiene for anything Alpha says. Em/en dashes read as an "AI wrote this" tell, so we cleanse
// them everywhere a reply is shown: a spaced dash becomes a comma, any straggler becomes a hyphen.

export function stripDashes(text: string): string {
  if (!text) return text;
  return text
    .replace(/\s*[—–―]\s+/g, ", ") // " — word"  ->  ", word"
    .replace(/[—–―]/g, "-"); // any remaining em/en/horizontal bar -> hyphen
}
