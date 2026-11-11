export function formatUnits(value: number): string {
  return Number.isFinite(value) ? Math.round(value).toLocaleString() : '—';
}

export function intervalCoverage(
  actual: number[],
  lower: number[],
  upper: number[],
): number | null {
  if (!actual.length || actual.length !== lower.length || actual.length !== upper.length)
    return null;
  return (
    actual.filter((value, index) => lower[index] <= value && value <= upper[index]).length /
    actual.length
  );
}
