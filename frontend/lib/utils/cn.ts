/**
 * cn.ts — Tailwind class-name helper.
 *
 * Composes conditional class names with `clsx` and resolves Tailwind conflicts
 * with `tailwind-merge`. This is the shadcn/ui convention.
 */

import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
