/**
 * page-header.tsx — Consistent heading block for all logged-in pages.
 *
 * ROADMAP 2.2 — shared shell primitives.
 *
 * Usage:
 *   <PageHeader title="Moji termini" description="Pregled predstojećih i prošlih konsultacija">
 *     <Button>Zakaži novi termin</Button>
 *   </PageHeader>
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export interface PageHeaderProps {
  title: string
  description?: string
  /** Slot shown to the right of the title (action buttons). */
  children?: ReactNode
  className?: string
}

export function PageHeader({
  title,
  description,
  children,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-2 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="min-w-0 space-y-1">
        <h1 className="truncate text-2xl font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {children && (
        <div className="flex shrink-0 items-center gap-2">{children}</div>
      )}
    </header>
  )
}
