/**
 * topic-categories.ts — TopicCategory enum + labels.
 *
 * Source of truth: backend/app/models/enums.py::TopicCategory.
 * Used by the student appointment-request form (PRD §2.2).
 */

import type { TopicCategory } from "@/types/common"

export const TOPIC_CATEGORIES: readonly TopicCategory[] = [
  "SEMINARSKI",
  "PREDAVANJA",
  "ISPIT",
  "PROJEKAT",
  "OSTALO",
] as const

export const TOPIC_CATEGORY_LABELS: Record<TopicCategory, string> = {
  SEMINARSKI: "Seminarski rad",
  PREDAVANJA: "Predavanja",
  ISPIT: "Ispit / kolokvijum",
  PROJEKAT: "Projekat",
  OSTALO: "Ostalo",
}

export function topicCategoryLabel(value: TopicCategory): string {
  return TOPIC_CATEGORY_LABELS[value]
}
