import type { CSSProperties } from "react";

export const DEFAULT_MERCHANT_ACCENT = "#435744";

export const MERCHANT_ACCENT_PRESETS = [
  { label: "Forest", value: "#435744" },
  { label: "Ocean", value: "#255B78" },
  { label: "Plum", value: "#704568" },
  { label: "Terracotta", value: "#93483D" },
] as const;

const HEX_COLOR = /^#[0-9a-f]{6}$/i;

export function isValidAccent(value: string): boolean {
  return HEX_COLOR.test(value);
}

export function normalizeAccent(value: string): string {
  return isValidAccent(value) ? value.toUpperCase() : DEFAULT_MERCHANT_ACCENT;
}

function linearChannel(value: number): number {
  const channel = value / 255;
  return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

export function readableTextOn(accent: string): "#FFFFFF" | "#20251F" {
  const normalized = normalizeAccent(accent);
  const red = Number.parseInt(normalized.slice(1, 3), 16);
  const green = Number.parseInt(normalized.slice(3, 5), 16);
  const blue = Number.parseInt(normalized.slice(5, 7), 16);
  const luminance =
    0.2126 * linearChannel(red) +
    0.7152 * linearChannel(green) +
    0.0722 * linearChannel(blue);
  const whiteContrast = 1.05 / (luminance + 0.05);
  const darkContrast = (luminance + 0.05) / 0.05;
  return whiteContrast >= darkContrast ? "#FFFFFF" : "#20251F";
}

export type MerchantThemeStyle = CSSProperties & {
  "--merchant-accent": string;
  "--merchant-accent-foreground": string;
};

export function merchantThemeStyle(accent: string): MerchantThemeStyle {
  const normalized = normalizeAccent(accent);
  return {
    "--merchant-accent": normalized,
    "--merchant-accent-foreground": readableTextOn(normalized),
  };
}
