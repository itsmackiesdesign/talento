import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMoney(value: number): string {
  return value.toLocaleString("ru-RU");
}

export function salaryLabel(
  from: number | null,
  to: number | null,
  currency: string,
): string | null {
  if (from && to) return `${formatMoney(from)} – ${formatMoney(to)} ${currency}`;
  if (from) return `от ${formatMoney(from)} ${currency}`;
  if (to) return `до ${formatMoney(to)} ${currency}`;
  return null;
}
