# Knot question guide

The rules the question bank is written to. This file has **no actual questions**. Baron doesn't read the bank; it's generated to these rules, sealed into `.pack` files and imported unseen. Any question that misses gets retired in play with "Never show this one again".

## Who it's for
- Two people who met in senior high and are adults now. "When we were younger" or "back in school" means senior high, never childhood.
- Ghana / West Africa context: local food, places, music, weather, school life, family life.
  - No US/UK-only brands, chains, holidays or experiences (fast-food chains, snow days, prom, Thanksgiving…).
  - Globally shared things are fine (films, phones, travel, the sea).
- **Where they are physically: holding hands, no kiss yet, gently breaking the ice.**
  - Nothing assumes physical history. Spicy is about attraction, anticipation, firsts, flirting and what each would like, never "the last time we…".

## Mix (first bank)
- Heavier on **Silly**, **Cozy** and **Big questions** (the deeper talk); lighter on Sweet, Memories and Future; Spicy moderate.
- **By depth, in every category:** roughly 45% Light, 35% Medium, 20% Deep.
- **By type:** roughly 40% Both answer, 25% Guess, 20% Would you rather, 15% Just you.

## Depth means the same everywhere
- **Light:** easy, playful, low stakes. Favourites, firsts, what-ifs.
- **Medium:** more personal. Real preferences, feelings, the "why".
- **Deep:** the most intimate. Fears, hopes, needs, things not usually said.
- **Spicy specifically:**
  - Light is flirty: noticing each other, compliments, the idea of a first kiss.
  - Medium is what you'd like: kisses, closeness, what makes you feel wanted.
  - Deep is desire and trust: what you'd want someday, what would make you feel safe and ready.
  - Always tasteful, never graphic, and never pressuring.

## Craft rules
- **Guess** cards name the other person with `{p}` ("What would {p}…") and must be answerable by the subject in a few words.
- **Would you rather** options are short, roughly balanced, and both fun to defend.
- **Just you** cards invite a story or a reflection, not a one-word answer.
- **No trick or test questions**, nothing that ranks the relationship or invites jealousy, and no quizzes on facts.
- **Deep isn't heavy for its own sake.** No trauma digging, no questions about exes, no "what would you change about me".
- Every question should be answerable by both people as they are now.
- One idea per question, plain words, under about 25 words.

## Pack format
- Packs are named `<category>-<nnn>` (`cozy-001`, `silly-002`…). Question ids are `<pack>-<nnnn>` and permanent.
- A new pack in an existing category just adds to the pool; nothing already played comes back.
- Packs travel encrypted with a transport key (`transport.key` beside them):
  ```
  python -m app.tools.import_pack packs/*.pack --key-file packs/transport.key
  ```
  The import prints counts only. Remove the throwaway test pack first with `--remove test-000`.
