# Code style for this project

This is a learning project. The person reading the code knows Python basics
(classes, methods, variables, loops, lists, if/else) but not advanced or
"clever" Python idioms. Code should read like a clear explanation, not a
puzzle. Optimize for a beginner-to-intermediate human reading the code, not
for fewer lines or maximum elegance.

## Language

- All code is written in English: variable names, function names, class
  names, comments, docstrings. This applies even though the in-app UI text
  is translated into German by default (see `i18n.py`) - the source code
  itself always stays English.

## What to avoid

- No emojis anywhere in code, comments, or commit messages.
- No decorators (`@something`), except where a library strictly requires one
  to function. Prefer plain functions and explicit calls.
- No `lambda`. Write a normal named function instead, even for a one-liner.
- No dense or unclear abbreviations in names (for example `cfg`, `mgr`, `tmp`,
  `idx`, `res`). Spell words out (`config`, `manager`, `temporary`, `index`,
  `result`). Short, well-known names like `i` in a simple loop are fine.
- No "too clever" one-liners: nested ternaries, chained comprehensions,
  walrus operator tricks, or anything that needs to be re-read twice to
  understand. Prefer a few extra lines that are obvious at a glance.

## What to include

- Comments that explain the "why", not just repeat the code, but be
  generous with them in this project: if a beginner might pause and wonder
  "why is this here" or "what does this step do", add a short comment above
  it. It is fine to comment more than usual - the goal is that a human with
  basic Python knowledge can follow the logic without looking anything up.
- Simple, direct control flow (if/else, for loops, while loops) over
  advanced patterns, even when a shorter alternative exists.
- Descriptive names for functions, variables, and classes that make the
  code self-explanatory alongside the comments.
