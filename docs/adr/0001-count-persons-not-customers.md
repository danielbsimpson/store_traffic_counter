# Count Persons, not Customers

**Status:** accepted

The project is named *Store Traffic Counter* and frames its goal as counting customers, but the pipeline only detects and tracks generic people crossing a line; it has no signal to tell a shopper from a passerby or staff member. We decided the canonical counted entity is a **Person** (any detected human) rather than a **Customer**, so the system never claims more than the computer vision can actually support.

## Considered Options

- **Customer semantics** — would require distinguishing shoppers from passersby/staff, handling re-entries, and dwell/intent heuristics. Rejected: none of that signal exists today, and claiming it would overstate the PoC.
- **Person semantics (chosen)** — honest about what detection + tracking + tripwire crossing measures, and matches the MOT17 pedestrian data used for development.

## Consequences

- "Customer" is recorded in `GLOSSARY.md` as an explicit future refinement of Person, not a current capability.
- Documentation, labels, and metrics say IN/OUT and net occupancy of **Persons**, not customers.
- Reversing this (committing to Customer semantics) means reworking the glossary, UI labels, and public claims — hence this record.
