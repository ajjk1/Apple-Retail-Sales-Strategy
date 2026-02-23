const COUNTRY_LABELS: { en: string; ko: string }[] = [
  { en: 'United States', ko: '미국' },
  { en: 'Canada', ko: '캐나다' },
  { en: 'Mexico', ko: '멕시코' },
  { en: 'Colombia', ko: '콜롬비아' },
  { en: 'United Kingdom', ko: '영국' },
  { en: 'France', ko: '프랑스' },
  { en: 'Germany', ko: '독일' },
  { en: 'Austria', ko: '오스트리아' },
  { en: 'Spain', ko: '스페인' },
  { en: 'Italy', ko: '이탈리아' },
  { en: 'Netherlands', ko: '네덜란드' },
  { en: 'China', ko: '중국' },
  { en: 'Japan', ko: '일본' },
  { en: 'South Korea', ko: '한국' },
  { en: 'Taiwan', ko: '대만' },
  { en: 'Singapore', ko: '싱가포르' },
  { en: 'Thailand', ko: '태국' },
  { en: 'UAE', ko: '아랍에미리트' },
  { en: 'Australia', ko: '호주' },
];

/** 국가 → 대륙 매핑 */
const COUNTRY_TO_CONTINENT: Record<string, { ko: string; en: string }> = {
  'United States': { ko: '북미', en: 'North America' },
  Canada: { ko: '북미', en: 'North America' },
  Mexico: { ko: '북미', en: 'North America' },
  Colombia: { ko: '남미', en: 'South America' },
  'United Kingdom': { ko: '유럽', en: 'Europe' },
  France: { ko: '유럽', en: 'Europe' },
  Germany: { ko: '유럽', en: 'Europe' },
  Austria: { ko: '유럽', en: 'Europe' },
  Spain: { ko: '유럽', en: 'Europe' },
  Italy: { ko: '유럽', en: 'Europe' },
  Netherlands: { ko: '유럽', en: 'Europe' },
  China: { ko: '아시아', en: 'Asia' },
  Japan: { ko: '아시아', en: 'Asia' },
  'South Korea': { ko: '아시아', en: 'Asia' },
  Taiwan: { ko: '아시아', en: 'Asia' },
  Singapore: { ko: '아시아', en: 'Asia' },
  Thailand: { ko: '아시아', en: 'Asia' },
  UAE: { ko: '중동', en: 'Middle East' },
  Australia: { ko: '오세아니아', en: 'Oceania' },
};

/** 국가명 표시: 한글(영문) 형식 */
export function formatCountryDisplay(enName: string): string {
  const c = COUNTRY_LABELS.find((x) => x.en === enName);
  return c ? `${c.ko}(${c.en})` : enName;
}

/** 도시명 한글 매핑 */
const CITY_LABELS: { en: string; ko: string }[] = [
  { en: 'Paris', ko: '파리' },
  { en: 'London', ko: '런던' },
  { en: 'Dubai', ko: '두바이' },
  { en: 'New York', ko: '뉴욕' },
  { en: 'Melbourne', ko: '멜버른' },
  { en: 'Tokyo', ko: '도쿄' },
  { en: 'Mexico City', ko: '멕시코시티' },
  { en: 'Bangkok', ko: '방콕' },
  { en: 'Singapore', ko: '싱가포르' },
  { en: 'Seoul', ko: '서울' },
  { en: 'Beijing', ko: '베이징' },
  { en: 'Chicago', ko: '시카고' },
  { en: 'Los Angeles', ko: '로스앤젤레스' },
  { en: 'Toronto', ko: '토론토' },
  { en: 'Shanghai', ko: '상하이' },
  { en: 'Bogota', ko: '보고타' },
  { en: 'San Francisco', ko: '샌프란시스코' },
  { en: 'Vienna', ko: '빈' },
  { en: 'Amsterdam', ko: '암스테르담' },
  { en: 'Rome', ko: '로마' },
  { en: 'Berlin', ko: '베를린' },
  { en: 'Taipei', ko: '타이베이' },
  { en: 'Abu Dhabi', ko: '아부다비' },
  { en: 'Munich', ko: '뮌헨' },
  { en: 'Kyoto', ko: '교토' },
  { en: 'Honolulu', ko: '호놀룰루' },
  { en: 'Montreal', ko: '몬트리올' },
  { en: 'Macau', ko: '마카오' },
  { en: 'Cologne', ko: '쾰른' },
];

/** 스토어명 한글 매핑 (Apple 접두사 제거 후 영문명 기준) */
const STORE_LABELS: { en: string; ko: string }[] = [
  { en: 'Gangnam', ko: '강남' },
  { en: 'Yeouido', ko: '여의도' },
  { en: 'Kyoto', ko: '교토' },
  { en: 'South Coast Plaza', ko: '사우스코스트 플라자' },
  { en: 'Grand Central', ko: '그랜드 센트럴' },
  { en: 'SoHo', ko: '소호' },
  { en: 'Covent Garden', ko: '코벤트 가든' },
  { en: 'Regent Street', ko: '리젠트 스트리트' },
  { en: 'Brompton Road', ko: '브롬프턴 로드' },
  { en: 'Beverly Center', ko: '베버리 센터' },
  { en: 'Michigan Avenue', ko: '미시건 애비뉴' },
  { en: 'Downtown Brooklyn', ko: '다운타운 브루클린' },
  { en: 'Eaton Centre', ko: '이턴 센터' },
  { en: 'Rideau Centre', ko: '리도 센터' },
  { en: 'Dubai Mall', ko: '두바이 몰' },
  { en: 'Mall of the Emirates', ko: '에미리츠 몰' },
  { en: 'Yas Mall', ko: '야스 몰' },
  { en: 'Marunouchi', ko: '마루노우치' },
  { en: 'Shinjuku', ko: '신주쿠' },
  { en: 'Omotesando', ko: '오모테산도' },
  { en: 'Fukuoka', ko: '후쿠오카' },
  { en: 'Nanjing East', ko: '난징동' },
  { en: 'Taikoo Li', ko: '타이쿠 리' },
  { en: 'Taipei 101', ko: '타이페이 101' },
  { en: 'Jewel Changi Airport', ko: '주얼 창이 공항' },
  { en: 'Orchard Road', ko: '오차드 로드' },
  { en: 'Iconsiam', ko: '아이콘시암' },
  { en: 'Santa Fe', ko: '산타페' },
  { en: 'Antara', ko: '안타라' },
  { en: 'Parque La Colina', ko: '파르케 라 콜리나' },
  { en: 'Andino', ko: '안디노' },
  { en: 'Passeig de Gracia', ko: '파세이그 데 그라시아' },
  { en: 'Piazza Liberty', ko: '피아자 리베르타' },
  { en: 'Kurfuerstendamm', ko: '쿠어푸르스텐담' },
  { en: 'Rosenstrasse', ko: '로젠슈트라세' },
  { en: 'Bondi', ko: '본디' },
  { en: 'Chadstone', ko: '채드스톤' },
  { en: 'Sydney', ko: '시드니' },
  { en: 'Ala Moana', ko: '알라 모아나' },
  { en: 'Park Visitor Center', ko: '파크 방문자 센터' },
  { en: 'The Dubai Mall', ko: '두바이 몰' },
  { en: 'The Americana at Brand', ko: '아메리카나' },
  { en: 'Via Santa Fe', ko: '비아 산타페' },
  { en: 'Champs-Elysees', ko: '샹젤리제' },
  { en: 'Kaerntner Strasse', ko: '쾰른 거리' },
  { en: 'Cheltenham', ko: '첼튼햄' },
  { en: 'North Michigan Avenue', ko: '노스 미시간 애비뉴' },
  { en: 'Pioneer Place', ko: '파이오니어 플레이스' },
  { en: 'Union Square', ko: '유니온 스퀘어' },
  { en: 'The Grove', ko: '더 그로브' },
  { en: 'Fifth Avenue', ko: '파이프스 애비뉴' },
  { en: 'Walnut Street', ko: '월넛 스트리트' },
  { en: 'Leidseplein', ko: '레이드세플레인' },
  { en: 'Metrotown', ko: '메트로타운' },
  { en: 'Causeway Bay', ko: '코즈웨이 베이' },
  { en: 'Yorkdale', ko: '요크데일' },
  { en: 'Galeries Lafayette', ko: '갤러리 라파예트' },
  { en: 'Central World', ko: '센트럴 월드' },
  { en: 'Southland', ko: '사우스랜드' },
  { en: 'Highpoint', ko: '하이포인트' },
  { en: 'Schildergasse', ko: '실더가세' },
  { en: 'Brisbane', ko: '브리즈번' },
  { en: 'Cotai Central', ko: '코타이 센트럴' },
];

/** 스토어명 표시: 한글(영문) 형식 (매핑 있으면), 없으면 영문만 */
export function formatStoreDisplay(enName: string): string {
  const t = (enName || '').trim();
  if (!t) return enName || '';
  const c = STORE_LABELS.find((x) => x.en.toLowerCase() === t.toLowerCase());
  return c ? `${c.ko}(${c.en})` : enName;
}

/** 스토어명에서 'Apple '/ '애플 ' 접두사 제거 */
export function stripApplePrefix(s: string): string {
  const t = (s || '').trim();
  if (!t) return s || '';
  if (t.toLowerCase().startsWith('apple ')) return t.slice(6).trim();
  if (t.startsWith('애플 ')) return t.slice(3).trim();
  return t;
}

/** 도시명 표시: 한글(영문) 형식 (매핑 있으면), 없으면 영문만 */
export function formatCityDisplay(enName: string): string {
  const t = (enName || '').trim();
  if (!t) return enName || '';
  const c = CITY_LABELS.find((x) => x.en.toLowerCase() === t.toLowerCase());
  return c ? `${c.ko}(${c.en})` : enName;
}

/** 도시 영문 → 한글 매핑 조회 */
export function getCityKo(enName: string): string | undefined {
  const t = (enName || '').trim();
  return t ? CITY_LABELS.find((x) => x.en.toLowerCase() === t.toLowerCase())?.ko : undefined;
}

/** 국가 → 대륙 (한글) */
export function getContinentForCountry(enName: string): string {
  return COUNTRY_TO_CONTINENT[enName]?.ko ?? '기타';
}

/** 국가 → 대륙 전체 정보 */
export function getContinentInfo(enName: string): { ko: string; en: string } | null {
  return COUNTRY_TO_CONTINENT[enName] ?? null;
}

/** 대륙 한글 ↔ 영문 매핑 */
const CONTINENT_KO_TO_EN: Record<string, string> = {
  북미: 'North America',
  남미: 'South America',
  유럽: 'Europe',
  아시아: 'Asia',
  중동: 'Middle East',
  오세아니아: 'Oceania',
};
const CONTINENT_EN_TO_KO: Record<string, string> = Object.fromEntries(
  Object.entries(CONTINENT_KO_TO_EN).map(([k, v]) => [v, k])
);

/**
 * 국가명 정규화: 한글 또는 영문 → 영문 (API 호출용)
 * "한국" | "South Korea" → "South Korea"
 */
export function resolveCountryToEn(term: string): string {
  if (!term?.trim()) return term?.trim() ?? '';
  const t = term.trim();
  const byKo = COUNTRY_LABELS.find((x) => x.ko === t);
  if (byKo) return byKo.en;
  const byEn = COUNTRY_LABELS.find((x) => x.en === t);
  if (byEn) return byEn.en;
  return t;
}

/**
 * 대륙명 정규화: 한글 또는 영문 → 영문 (API 호출용)
 */
export function resolveContinentToEn(term: string): string {
  if (!term?.trim()) return term?.trim() ?? '';
  const t = term.trim();
  if (CONTINENT_KO_TO_EN[t]) return CONTINENT_KO_TO_EN[t];
  if (CONTINENT_EN_TO_KO[t]) return t; // 이미 영문
  return t;
}

/**
 * 도시명 정규화: 한글 또는 영문 → 영문 (API 호출용)
 */
export function resolveCityToEn(term: string): string {
  if (!term?.trim()) return term?.trim() ?? '';
  const t = term.trim();
  const byKo = CITY_LABELS.find((x) => x.ko === t);
  if (byKo) return byKo.en;
  const byEn = CITY_LABELS.find((x) => x.en === t);
  if (byEn) return byEn.en;
  return t;
}
