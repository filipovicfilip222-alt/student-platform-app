/**
 * markdown.ts — Mini sanitized markdown renderer za TicketChat.
 *
 * KORAK 6 — chat poruke ne treba pun react-markdown (~30 kB), nego samo
 * **bold**, *italic* / _italic_, `code`, i auto-linkify URL-ova. Sve
 * ostalo se renderuje kao plain tekst, sa kompletnim HTML escapom da
 * sprečimo XSS.
 *
 * Render strategija:
 *   1. Tokenizuj tekst u redove (newline-aware).
 *   2. Za svaki red, escape-uj HTML, izvuci kod fence-ove i zatim
 *      bold/italic/links iterativnim splitting-om.
 *   3. Vrati React.Fragment-ove → roditelj kontroliše wrapping markup.
 *
 * Sigurnosne mere:
 *   - Linkovi prolaze kroz `safeUrl()` koja odbacuje sve scheme osim
 *     http(s) i mailto. `rel="noopener noreferrer"` + `target="_blank"`.
 *   - Niko ne renderuje sirov HTML (`dangerouslySetInnerHTML` se ne
 *     koristi nigde u ovom modulu).
 */

import * as React from "react"

const URL_REGEX = /\b(https?:\/\/[^\s<]+[^\s<.,!?;:'")\]])/gi
const SAFE_URL_REGEX = /^(https?:\/\/|mailto:)/i

function safeUrl(url: string): string | null {
  if (!SAFE_URL_REGEX.test(url)) return null
  try {
    const parsed = new URL(url)
    if (parsed.protocol === "javascript:") return null
    return parsed.toString()
  } catch {
    return null
  }
}

/**
 * Replace pattern with a tokenized version, returning an array of
 * mixed strings + React nodes. Used iteratively for bold → italic → code.
 */
function tokenize(
  parts: Array<string | React.ReactNode>,
  regex: RegExp,
  build: (match: string) => React.ReactNode
): Array<string | React.ReactNode> {
  const result: Array<string | React.ReactNode> = []
  for (const part of parts) {
    if (typeof part !== "string") {
      result.push(part)
      continue
    }
    let lastIndex = 0
    const re = new RegExp(regex.source, regex.flags.replace("g", "") + "g")
    let match: RegExpExecArray | null
    while ((match = re.exec(part)) !== null) {
      if (match.index > lastIndex) {
        result.push(part.slice(lastIndex, match.index))
      }
      result.push(build(match[1]!))
      lastIndex = match.index + match[0].length
    }
    if (lastIndex < part.length) {
      result.push(part.slice(lastIndex))
    }
  }
  return result
}

function linkifyParts(
  parts: Array<string | React.ReactNode>
): Array<string | React.ReactNode> {
  const result: Array<string | React.ReactNode> = []
  let key = 0
  for (const part of parts) {
    if (typeof part !== "string") {
      result.push(part)
      continue
    }
    let lastIndex = 0
    URL_REGEX.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = URL_REGEX.exec(part)) !== null) {
      const url = match[1]!
      const safe = safeUrl(url)
      if (match.index > lastIndex) {
        result.push(part.slice(lastIndex, match.index))
      }
      if (safe) {
        result.push(
          React.createElement(
            "a",
            {
              key: `lnk-${key++}`,
              href: safe,
              target: "_blank",
              rel: "noopener noreferrer",
              className:
                "underline decoration-dotted underline-offset-2 hover:text-current/80",
            },
            url
          )
        )
      } else {
        result.push(url)
      }
      lastIndex = match.index + url.length
    }
    if (lastIndex < part.length) {
      result.push(part.slice(lastIndex))
    }
  }
  return result
}

/**
 * Render a chat message string as inline markdown. Output is a list of
 * React nodes (strings + elements) safe to drop into a `<p>` / `<span>`.
 *
 * Pipeline: code → bold → italic → linkify. Order matters because
 * `**bold**` must not match before `*italic*`, and inline code is
 * verbatim (no inner markdown processing).
 */
export function renderInlineMarkdown(input: string): React.ReactNode[] {
  if (!input) return []

  let parts: Array<string | React.ReactNode> = [input]
  let codeIdx = 0
  let boldIdx = 0
  let italicIdx = 0

  // Inline code: `text`
  parts = tokenize(parts, /`([^`]+)`/, (match) =>
    React.createElement(
      "code",
      {
        key: `code-${codeIdx++}`,
        className:
          "rounded bg-foreground/10 px-1 py-0.5 font-mono text-[0.8em]",
      },
      match
    )
  )

  // Bold: **text**
  parts = tokenize(parts, /\*\*([^*\n]+?)\*\*/, (match) =>
    React.createElement(
      "strong",
      { key: `b-${boldIdx++}`, className: "font-semibold" },
      match
    )
  )

  // Italic: _text_ (kept simple — single * disabled to avoid clashing with bold)
  parts = tokenize(parts, /_([^_\n]+?)_/, (match) =>
    React.createElement("em", { key: `i-${italicIdx++}` }, match)
  )

  // Linkify trailing
  parts = linkifyParts(parts)

  return parts.map((p, idx) =>
    typeof p === "string" ? React.createElement(React.Fragment, { key: `t-${idx}` }, p) : p
  )
}

/**
 * Render a multi-line chat message. Empty lines become visual gaps.
 * Returns React fragments suitable for `<p className="whitespace-pre-wrap">`.
 */
export function renderChatMarkdown(input: string): React.ReactNode {
  const lines = input.split(/\r?\n/)
  return lines.map((line, idx) =>
    React.createElement(
      React.Fragment,
      { key: idx },
      renderInlineMarkdown(line),
      idx < lines.length - 1
        ? React.createElement("br", { key: `br-${idx}` })
        : null
    )
  )
}
