# IronStore Assistant: interface study and design system

## 1. Who uses it and what it must do
An IronStore employee mid-task (support agent with a customer waiting, a manager approving a refund, a new hire checking leave rules). They need **one answer they can act on, and proof they can show someone**. So the interface must make three things obvious: the answer, where it came from, and when not to trust it.

## 2. Audit of the first version (before)
| # | Problem | Heuristic / guideline | Severity |
|---|---|---|---|
| 1 | Answer is a wall of text; bullets shown as literal `- ` | Nielsen 8, aesthetic and minimalist design | High |
| 2 | Citations repeated twice (inline `[Title, p. X]` and the chip list), never linked to each other | Nielsen 6, recognition over recall | High |
| 3 | "The documents differ" looks like any other answer: the most important trust signal is invisible | Nielsen 1, visibility of system status | Critical |
| 4 | "Not found" and "partial answer" are not distinguished | Nielsen 9, help users recognise and recover | High |
| 5 | Newest question added at the top: reading order is reversed | Nielsen 4, consistency with chat conventions | Medium |
| 6 | 5–10 s wait with only "Searching the documents…", no way to cancel | Nielsen 1 and 3, user control and freedom | High |
| 7 | Sources open a raw PDF in a new tab: context switch for every check | Nielsen 7, efficiency of use | Medium |
| 8 | No product identity; generic orange; no brand voice | Aesthetic integrity | Medium |
| 9 | No live region, no landmarks, no reduced-motion support, single-line input | WCAG 2.1: 4.1.3 Status messages, 1.3.1, 2.3.3 | High |
| 10 | Silent about its limits: users don't know each question is answered on its own, or that only documents are used | Nielsen 2, match with the real world | Medium |

## 3. References and what was taken from each
**toyfight.co**: warm paper background (#FAF6EF), headline built from mixed-shape blocks (pill next to square, pastel fills), small mono labels on highlighter-yellow tags, the "Press / for ?" keyboard hint, a playful but controlled tone.
→ Taken: the **tag collage** for the starter questions, mono metadata tags, highlighter yellow, the `/` shortcut, tilt-on-hover.

**hugeinc.com**: one grotesk at huge sizes with very tight tracking ("Hello." at 285 px, -7% tracking), statements that end in a full stop, a single magenta accent word ("matter to **teams.**"), near-black #0D0B0A and cream #F7F4EE, pill buttons, numbered lists (01–06), easing `cubic-bezier(.625,.05,0,1)`.
→ Taken: the **"Ask IronStore."** display headline with the magenta accent word, full-stop headings, numbered "how it works", the dark theme, the easing curve for large movements.

**What was not copied**: the proprietary fonts (FK Raster Grotesk, Spezia, Matter), the 3D artwork and the cookie-wall patterns. The fonts are replaced with open-licence equivalents.

## 4. Direction
**Paper and ink, with receipts.** A company handbook you can question. The domain metaphor is the *receipt*: every claim carries a highlighter-yellow footnote that links to its source card and opens the exact PDF page.

- **Signature:** footnote marker ↔ source card ↔ page viewer. Hover a marker and its source card lights up, and the other way round. Click it and the page opens beside the answer.
- **Second signature:** a conflict is not a paragraph. Each document gets its own card, side by side, under a magenta "Documents disagree" tag.

## 5. Tokens
| Token | Light | Dark | Role |
|---|---|---|---|
| `--paper` | #F6F3EC | #0E0C0B | page |
| `--sheet` | #FFFDF8 | #181614 | raised: dock, source cards |
| `--well` | #EFEBE3 | #211E1B | inset, hover |
| `--ink` / `--ink-2` / `--ink-3` | #0E0C0B / #3F3A34 / #6B645B | #F6F3EC / #CFC8BD / #9C948A | text levels |
| `--magenta` | #C8106F | #FF5CB0 | action and identity only |
| `--highlighter` | #FFE14D | #FFE14D | receipts (footnotes, source numbers) |
| `--tab-*` | pastel | deep tint | one index-tab colour per document area |

Contrast (WCAG 2.1 AA, all checked): ink on paper 17.6:1 · ink-3 on paper 5.3:1 (light) / 6.5:1 (dark) · magenta text on paper 5.0:1 / 6.9:1 · text on every tab ≥ 12:1.

Area colours: People & HR lilac · Customer support blush · Deliveries mint · IT & security sky · Sales peach · Finance highlighter · Legal stone · Product catalogue ink (inverted).

**Type:** Bricolage Grotesque (variable: weight, width, optical size; OFL) for everything; Geist Mono (OFL) for metadata, steps and tags. Both bundled in `static/fonts/`, so there are no requests to Google: this avoids GDPR issues and works offline.
Scale: display 96–176 px / -5.8% tracking · question 28–44 px / -3.5% · lead 20–28 px · answer 19 px / 1.6 · body 17 px · mono 12–14 px. Starter chips use width 84% (condensed), a nod to Toyfight's Spezia Condensed.

**Depth:** subtle layered shadows in light mode, a 1 px ring in dark mode. Radius: tags 6, cards 14, dock 22, pills 999.
**Spacing:** 4 px base; sections 72 px apart; answer column 880 px; text measure 64ch.

## 6. Answer states (copy included)
| State | Tag | What the user reads |
|---|---|---|
| Answered | `Answered` (mint) | Answer + numbered sources |
| Partial | `Partial answer` (yellow) | "The documents cover this, but they don't give the exact detail you asked for." |
| Conflict | `Documents disagree` (magenta) | "IronStore's documents give different rules for this. Don't pick one yourself: check with the policy owner before you act." + one card per document |
| Not found | `Not in the documents` (stone) | "I could not find this in the IronStore documents." + "Try naming the policy, product or team…" |
| Error | `No answer` | "We couldn't reach the assistant. Check that the server is running, then try again." + Try again |
| Stopped | `Stopped` | "You stopped this answer." + Ask again |
| Unread page cited | warning on the source card | "Check this page: it wasn't among the passages the assistant read." |

Progress uses the **real pipeline steps** sent by the API (not a fake spinner): *Choosing where to look → Searching internal policies / the product catalogue → Writing the answer from N documents*.

## 7. UX writing rules
- Sentence case, short, active. Headings end with a full stop (Huge).
- Say what happens, not how it's built: "Searching internal policies", not "Querying vector store".
- Be honest about limits in the interface itself: "Answers come only from IronStore documents. Each question is answered on its own, so include the details."
- Never blame the user. Errors say what happened and what to do next.
- Starter chips show a short label; the full question is in the accessible name and previewed below the chips on hover or focus.

## 8. Motion
| Moment | Motion | Duration / curve |
|---|---|---|
| First load | headline words rise out of a mask, chips pop in staggered (45 ms) | 900 ms `.625,.05,0,1` · 500 ms ease-out |
| Chip hover | lift 3 px and tilt ±1.2° | 220 ms |
| Ask | home fades up and away; the question appears and the page scrolls to it | 260 ms |
| Working | current step drawn with the highlighter, dots tick | 350 ms, 1.2 s loop |
| Streaming | text appears word by word with a magenta caret | live |
| Done | conflict cards and source cards rise in, staggered 60–70 ms | 450 ms |
| Marker ↔ source | ink ring on both | 140–160 ms |
| Page viewer | slides in from the right over a scrim | 340 ms |
| Theme switch | circular reveal from the toggle (View Transitions) | 550 ms |
| Buttons | press scale .97 | 120 ms |

Only `transform`, `opacity` and `clip-path` are animated. `prefers-reduced-motion` turns all movement off.

## 9. Accessibility checklist (WCAG 2.1 AA)
- Landmarks: header, main, named form ("Ask a question"); one h1 in each view; each answer is an `article` labelled by its question.
- Live region announces each step and "Answer ready. Documents disagree. 3 sources." The streaming text itself is not announced word by word.
- Footnote markers are buttons named "Source 2: Refund and Complaint Handling Policy, page 3. View the page"; hit area extended beyond the visual size.
- Page viewer is a native modal `<dialog>`: focus moves in, Esc closes, focus returns to the button that opened it.
- Keyboard: `/` focuses the question box, Enter asks, Shift+Enter adds a new line, the Ask button turns into Stop while answering. Skip link to the question box.
- Targets ≥ 44 px; question field 17 px (no iOS zoom); visible 3 px focus ring; forced-colours borders; no horizontal scroll at 390 px.
- Verified with axe-core (WCAG 2.0/2.1 A and AA + best practice): 0 violations in light and dark, on home, conversation and viewer.

## 10. Files
- `static/index.html`: the whole interface (HTML, CSS, JS in one file, no build step)
- `static/fonts/`: Bricolage Grotesque + Geist Mono (OFL)
- `answer_format.py`: answer kind and numbered citations (pure Python, testable)
- `api.py`: `POST /ask/stream` (NDJSON events), `POST /ask`, `GET /health`
- `test/fake_api.py` + `test/ui_test.js`: fake server with canned answers and the Playwright + axe test used for the screenshots
