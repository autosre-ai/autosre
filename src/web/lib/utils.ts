// UI Utilities

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

export function formatRelativeTime(date: string | Date): string {
  const now = new Date();
  const then = new Date(date);
  const diff = now.getTime() - then.getTime();

  const minutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return then.toLocaleDateString();
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case "critical":
      return "text-red-500 bg-red-500/10";
    case "high":
      return "text-orange-500 bg-orange-500/10";
    case "medium":
      return "text-yellow-500 bg-yellow-500/10";
    case "low":
      return "text-blue-500 bg-blue-500/10";
    default:
      return "text-gray-500 bg-gray-500/10";
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "resolved":
    case "completed":
    case "confirmed":
      return "text-green-500 bg-green-500/10";
    case "investigating":
    case "running":
      return "text-blue-500 bg-blue-500/10";
    case "pending":
      return "text-yellow-500 bg-yellow-500/10";
    case "escalated":
    case "failed":
    case "rejected":
      return "text-red-500 bg-red-500/10";
    default:
      return "text-gray-500 bg-gray-500/10";
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + "...";
}
