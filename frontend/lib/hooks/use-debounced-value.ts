/**
 * use-debounced-value.ts — Generic value debouncer.
 *
 * Used by search inputs so typing doesn't fire a request on every keystroke.
 */

"use client"

import { useEffect, useState } from "react"

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])

  return debounced
}
