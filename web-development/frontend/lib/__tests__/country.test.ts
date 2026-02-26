/**
 * lib/country.ts 엄격 단위 테스트.
 * - 모든 export 함수의 정상/엣지 케이스 검증.
 */
import {
  formatCountryDisplay,
  formatStoreDisplay,
  formatCityDisplay,
  stripApplePrefix,
  getCityKo,
  getContinentForCountry,
  getContinentInfo,
  resolveCountryToEn,
  resolveContinentToEn,
  resolveCityToEn,
} from '../country';

describe('formatCountryDisplay', () => {
  it('returns ko(en) for known country', () => {
    expect(formatCountryDisplay('South Korea')).toBe('한국(South Korea)');
    expect(formatCountryDisplay('United States')).toBe('미국(United States)');
  });
  it('returns en only for unknown country', () => {
    expect(formatCountryDisplay('Unknown')).toBe('Unknown');
  });
  it('handles empty string', () => {
    expect(formatCountryDisplay('')).toBe('');
  });
});

describe('formatStoreDisplay', () => {
  it('returns ko(en) for known store (case insensitive)', () => {
    expect(formatStoreDisplay('Gangnam')).toBe('강남(Gangnam)');
    expect(formatStoreDisplay('gangnam')).toBe('강남(Gangnam)');
  });
  it('returns en only for unknown store', () => {
    expect(formatStoreDisplay('Unknown Store')).toBe('Unknown Store');
  });
  it('handles empty string', () => {
    expect(formatStoreDisplay('')).toBe('');
  });
});

describe('formatCityDisplay', () => {
  it('returns ko(en) for known city', () => {
    expect(formatCityDisplay('Seoul')).toBe('서울(Seoul)');
  });
  it('returns en only for unknown city', () => {
    expect(formatCityDisplay('Unknown City')).toBe('Unknown City');
  });
});

describe('stripApplePrefix', () => {
  it('strips "Apple " (case insensitive)', () => {
    expect(stripApplePrefix('Apple Gangnam')).toBe('Gangnam');
    expect(stripApplePrefix('apple SoHo')).toBe('SoHo');
  });
  it('strips "애플 "', () => {
    expect(stripApplePrefix('애플 강남')).toBe('강남');
  });
  it('returns unchanged when no prefix', () => {
    expect(stripApplePrefix('Gangnam')).toBe('Gangnam');
  });
  it('handles empty string', () => {
    expect(stripApplePrefix('')).toBe('');
  });
  it('handles whitespace-only', () => {
    expect(stripApplePrefix('   ')).toBe('   ');
  });
});

describe('getCityKo', () => {
  it('returns ko for known city', () => {
    expect(getCityKo('Seoul')).toBe('서울');
  });
  it('returns undefined for unknown', () => {
    expect(getCityKo('Unknown')).toBeUndefined();
  });
  it('handles empty string', () => {
    expect(getCityKo('')).toBeUndefined();
  });
});

describe('getContinentForCountry', () => {
  it('returns ko continent for known country', () => {
    expect(getContinentForCountry('South Korea')).toBe('아시아');
    expect(getContinentForCountry('United States')).toBe('북미');
  });
  it('returns "기타" for unknown country', () => {
    expect(getContinentForCountry('Unknown')).toBe('기타');
  });
});

describe('getContinentInfo', () => {
  it('returns { ko, en } for known country', () => {
    const info = getContinentInfo('South Korea');
    expect(info).toEqual({ ko: '아시아', en: 'Asia' });
  });
  it('returns null for unknown country', () => {
    expect(getContinentInfo('Unknown')).toBeNull();
  });
});

describe('resolveCountryToEn', () => {
  it('converts ko to en', () => {
    expect(resolveCountryToEn('한국')).toBe('South Korea');
    expect(resolveCountryToEn('미국')).toBe('United States');
  });
  it('returns en as-is when already en', () => {
    expect(resolveCountryToEn('South Korea')).toBe('South Korea');
  });
  it('returns trimmed unknown as-is', () => {
    expect(resolveCountryToEn('  Unknown  ')).toBe('Unknown');
  });
  it('handles empty string', () => {
    expect(resolveCountryToEn('')).toBe('');
  });
});

describe('resolveContinentToEn', () => {
  it('converts ko to en', () => {
    expect(resolveContinentToEn('북미')).toBe('North America');
    expect(resolveContinentToEn('아시아')).toBe('Asia');
  });
  it('returns en as-is when already en', () => {
    expect(resolveContinentToEn('Asia')).toBe('Asia');
  });
  it('handles empty string', () => {
    expect(resolveContinentToEn('')).toBe('');
  });
});

describe('resolveCityToEn', () => {
  it('converts ko to en', () => {
    expect(resolveCityToEn('서울')).toBe('Seoul');
  });
  it('returns en as-is when already en', () => {
    expect(resolveCityToEn('Seoul')).toBe('Seoul');
  });
  it('handles empty string', () => {
    expect(resolveCityToEn('')).toBe('');
  });
});
