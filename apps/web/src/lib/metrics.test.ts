import { describe, expect, it } from 'vitest';
import { formatUnits, intervalCoverage } from './metrics';

describe('forecast display helpers', () => {
  it('formats finite units and renders unavailable values explicitly', () => {
    expect(formatUnits(1250.4)).toBe('1,250');
    expect(formatUnits(Number.NaN)).toBe('—');
  });

  it('calculates empirical interval coverage and handles empty samples', () => {
    expect(intervalCoverage([1, 5, 9], [0, 0, 10], [2, 4, 10])).toBeCloseTo(1 / 3);
    expect(intervalCoverage([], [], [])).toBeNull();
  });
});
