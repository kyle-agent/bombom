# Output Style

How agents communicate in this repo. Advisory — overridden by Tier 0 rules and by
explicit user instruction.

- **Lead with the answer.** State the result or recommendation first, then the
  reasoning. Don't narrate options you won't pursue.
- **Be concrete.** Reference `file:line`. Show the command and its output, not a
  paraphrase. "Tests pass (42 passed in 3.1s)" beats "everything works".
- **Truthful over tidy.** A failing test reported with its output is more useful than a
  clean-sounding summary. Label partial work as partial.
- **Match the surrounding code.** Comment density, naming, and idiom should look like
  the file the change lives in.
- **No filler.** Skip "Great question", "Certainly", and restating the request.
