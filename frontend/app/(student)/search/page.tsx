/**
 * (student)/search/page.tsx — Professor discovery.
 *
 * ROADMAP 3.5 / Faza 3.4.
 *
 * Filters (all optional):
 *   - q (text, debounced 300 ms) — matches name/title/department via
 *     the backend's `unaccent` search (see migration 0002).
 *   - faculty (FON | ETF)
 *   - consultation_type (UZIVO | ONLINE)
 *   - subject (free-text contains)
 *
 * A sentinel "ALL" option is used for Select inputs because shadcn's
 * SelectItem disallows an empty-string value.
 */

"use client"

import { useState } from "react"
import { Search as SearchIcon, SearchX } from "lucide-react"

import { ProfessorSearchCard } from "@/components/student/professor-search-card"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { PageHeader } from "@/components/shared/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value"
import { useProfessorSearch } from "@/lib/hooks/use-professors"
import type { ProfessorSearchParams } from "@/lib/api/students"
import type { ConsultationType, Faculty } from "@/types"

type FacultyFilter = Faculty | "ALL"
type TypeFilter = ConsultationType | "ALL"

export default function SearchPage() {
  const [query, setQuery] = useState("")
  const [faculty, setFaculty] = useState<FacultyFilter>("ALL")
  const [type, setType] = useState<TypeFilter>("ALL")
  const [subject, setSubject] = useState("")

  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const debouncedSubject = useDebouncedValue(subject.trim(), 300)

  const params: ProfessorSearchParams = {
    ...(debouncedQuery ? { q: debouncedQuery } : {}),
    ...(faculty !== "ALL" ? { faculty } : {}),
    ...(type !== "ALL" ? { type } : {}),
    ...(debouncedSubject ? { subject: debouncedSubject } : {}),
  }

  const searchQuery = useProfessorSearch(params)
  const results = searchQuery.data ?? []

  const hasAnyFilter =
    debouncedQuery.length > 0 ||
    faculty !== "ALL" ||
    type !== "ALL" ||
    debouncedSubject.length > 0

  function clearFilters() {
    setQuery("")
    setFaculty("ALL")
    setType("ALL")
    setSubject("")
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pretraga profesora"
        description="Pronađite profesora po imenu, katedri ili predmetu."
      />

      <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-1.5 lg:col-span-2">
          <Label htmlFor="search-q">Pretraga</Label>
          <div className="relative">
            <SearchIcon
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <Input
              id="search-q"
              type="search"
              placeholder="Ime, prezime, katedra..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="search-faculty">Fakultet</Label>
          <Select
            value={faculty}
            onValueChange={(v) => setFaculty(v as FacultyFilter)}
          >
            <SelectTrigger id="search-faculty" className="w-full">
              <SelectValue placeholder="Svi fakulteti" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Svi fakulteti</SelectItem>
              <SelectItem value="FON">FON</SelectItem>
              <SelectItem value="ETF">ETF</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="search-type">Tip konsultacija</Label>
          <Select
            value={type}
            onValueChange={(v) => setType(v as TypeFilter)}
          >
            <SelectTrigger id="search-type" className="w-full">
              <SelectValue placeholder="Svi tipovi" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">Svi tipovi</SelectItem>
              <SelectItem value="UZIVO">Uživo</SelectItem>
              <SelectItem value="ONLINE">Online</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5 sm:col-span-2 lg:col-span-3">
          <Label htmlFor="search-subject">Predmet</Label>
          <Input
            id="search-subject"
            type="text"
            placeholder="npr. Programiranje II"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            autoComplete="off"
          />
        </div>

        <div className="flex items-end">
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={clearFilters}
            disabled={!hasAnyFilter}
          >
            Resetuj filtere
          </Button>
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {searchQuery.isLoading
              ? "Tražim..."
              : `Pronađeno profesora: ${results.length}`}
          </p>
        </div>

        {searchQuery.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Skeleton className="h-[160px] rounded-lg" />
            <Skeleton className="h-[160px] rounded-lg" />
            <Skeleton className="h-[160px] rounded-lg" />
          </div>
        ) : searchQuery.isError ? (
          <ErrorState
            title="Pretraga trenutno nije dostupna"
            description="Pokušajte ponovo za par sekundi."
            onRetry={() => searchQuery.refetch()}
            isRetrying={searchQuery.isFetching}
          />
        ) : results.length === 0 ? (
          <EmptyState
            icon={SearchX}
            title="Nema rezultata"
            description={
              hasAnyFilter
                ? "Promenite filtere ili probajte drugačije ključne reči."
                : "Počnite kucanjem u polje za pretragu."
            }
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((professor) => (
              <ProfessorSearchCard key={professor.id} professor={professor} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
