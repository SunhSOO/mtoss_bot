// 금액·수량 포매팅. 입력은 언제나 문자열이며 Number()로 변환하지 않는다.
// NUMERIC(28,10) 값은 float64를 통과하면 정밀도를 잃는다.

const MINUS = "−"; // U+2212 MINUS SIGN — 하이픈이 아니다 (§4)

function splitSign(value: string): { negative: boolean; digits: string } {
  const trimmed = value.trim();
  if (trimmed.startsWith("-") || trimmed.startsWith(MINUS)) {
    return { negative: true, digits: trimmed.slice(1) };
  }
  if (trimmed.startsWith("+")) {
    return { negative: false, digits: trimmed.slice(1) };
  }
  return { negative: false, digits: trimmed };
}

function group(integerPart: string): string {
  return integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** 소수점 이하 자릿수를 문자열 연산만으로 맞춘다. 반올림 없이 자른다. */
function fixed(digits: string, places: number): string {
  const [whole, fraction = ""] = digits.split(".");
  if (places === 0) return whole || "0";
  const padded = (fraction + "0".repeat(places)).slice(0, places);
  return `${whole || "0"}.${padded}`;
}

function trimTrailingZeros(digits: string): string {
  if (!digits.includes(".")) return digits;
  return digits.replace(/\.?0+$/, "");
}

const SYMBOLS: Record<string, string> = { KRW: "₩", USD: "$", JPY: "¥" };
const PLACES: Record<string, number> = { KRW: 0, USD: 2, JPY: 0 };

/** `₩12,450,000` / `$8,921.30` */
export function money(value: string, currency: string): string {
  const symbol = SYMBOLS[currency] ?? "";
  const places = PLACES[currency] ?? 2;
  const { negative, digits } = splitSign(value);
  const shaped = fixed(digits, places);
  const [whole, fraction] = shaped.split(".");
  const body = fraction ? `${group(whole)}.${fraction}` : group(whole);
  return `${negative ? MINUS : ""}${symbol}${body}`;
}

/** 부호를 항상 붙인 금액. 수익·손실 표기에 사용한다. */
export function signedMoney(value: string, currency: string): string {
  const { negative } = splitSign(value);
  const rendered = money(value, currency);
  return negative ? rendered : `+${rendered}`;
}

/** 비율 문자열(0.0124)을 `+1.24%` 형태로 바꾼다. */
export function signedPercent(value: string, places = 2): string {
  const { negative, digits } = splitSign(value);
  const [whole, fraction = ""] = digits.split(".");
  const shifted = shiftDecimal(whole, fraction, 2);
  const body = fixed(shifted, places);
  return `${negative ? MINUS : "+"}${body}%`;
}

/** 이미 퍼센트 단위인 값(92.0)을 `92.0%`로 바꾼다. */
export function percent(value: string, places = 1): string {
  const { negative, digits } = splitSign(value);
  return `${negative ? MINUS : ""}${fixed(digits, places)}%`;
}

/** 비율 문자열을 퍼센트 문자열로 (부호 없이). 0.184 → 18.4 */
export function ratioToPercent(value: string, places = 1): string {
  const { negative, digits } = splitSign(value);
  const [whole, fraction = ""] = digits.split(".");
  return `${negative ? MINUS : ""}${fixed(shiftDecimal(whole, fraction, 2), places)}`;
}

function shiftDecimal(whole: string, fraction: string, by: number): string {
  const padded = fraction + "0".repeat(by);
  const moved = padded.slice(0, by);
  const rest = padded.slice(by).replace(/0+$/, "");
  const newWhole = `${whole}${moved}`.replace(/^0+(?=\d)/, "");
  return rest ? `${newWhole}.${rest}` : newWhole;
}

/** 수량. 불필요한 0을 지우고 자릿수를 유지한다. */
export function quantity(value: string): string {
  const { negative, digits } = splitSign(value);
  const cleaned = trimTrailingZeros(digits);
  const [whole, fraction] = cleaned.split(".");
  const body = fraction ? `${group(whole)}.${fraction}` : group(whole);
  return `${negative ? MINUS : ""}${body}`;
}

/** 비율 문자열을 0~100 사이 숫자로. 진행 막대 폭 계산 전용이며 표시에는 쓰지 않는다. */
export function barWidth(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.min(100, parsed));
}

/** 차트 좌표 계산 전용. 표시 값에는 절대 쓰지 않는다. */
export function plotValue(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function isNegative(value: string): boolean {
  return splitSign(value).negative && trimTrailingZeros(splitSign(value).digits) !== "0";
}

export function isZero(value: string): boolean {
  return /^0*(\.0*)?$/.test(splitSign(value).digits);
}

/** 손익 색상 방향. 한국식으로 상승·수익이 빨강이다. */
export function pnlTone(value: string): "up" | "down" | "flat" {
  if (isZero(value)) return "flat";
  return isNegative(value) ? "down" : "up";
}

export const MINUS_SIGN = MINUS;
