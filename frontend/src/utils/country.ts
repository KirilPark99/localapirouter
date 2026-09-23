/**
 * Converts a 2-letter ISO 3166-1 alpha-2 country code into an emoji flag.
 * Example: 'KZ' -> '🇰🇿', 'GB' -> '🇬🇧', 'UA' -> '🇺🇦', 'US' -> '🇺🇸'
 */
export function getCountryFlag(countryCode?: string | null): string {
  if (!countryCode || countryCode.trim().length !== 2) {
    return "🌐";
  }
  const clean = countryCode.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(clean)) {
    return "🌐";
  }
  const codePoints = clean
    .split("")
    .map((char) => 127397 + char.charCodeAt(0));
  try {
    return String.fromCodePoint(...codePoints);
  } catch {
    return "🌐";
  }
}
