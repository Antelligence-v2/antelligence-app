# Antelligence — RULES.md

> What agents are allowed to do, what they're not, and why. Read every loop.

## The Operating Philosophy

This system was built **by an operator, for autonomous agents**. The rules aren't walls — they're guardrails that keep you productive while preventing damage.

**Default posture**: you have broad freedom to explore, build, test, and improve. When in doubt, act. The gates will catch you if you're wrong.

**But**: the few things marked DO NOT are absolute. They exist because violating them has caused real damage before.

## ALLOWED

### Code & Tests
- ✅ Read any file in the repo
- ✅ Write/edit code in `backend/`, `tests/`, `frontend/src/`
- ✅ Create new test files
- ✅ Run tests, lint, type-check
- ✅ Run simulations locally
- ✅ Modify up to 3 files per autonomous loop run
- ✅ Open GitHub PRs (operator approves merges)

### Infrastructure
- ✅ Read state files, logs, status JSONs
- ✅ Write status/ledger updates
- ✅ Use local models (Gemma4, Qwen3-Coder) for autonomous work
- ✅ Use free-tier APIs (Gemini Flash, Groq)
- ✅ Run sandbox validations
- ✅ Write Obsidian notes for durable memory

### Research & Analysis
- ✅ Search the web
- ✅ Read arxiv papers
- ✅ Extract data from PDFs
- ✅ Run EDA and scenario analysis
- ✅ Propose architectural changes as Obsidian briefs

## DO NOT (Absolute)

### Destructive Actions
- ❌ **Never** commit to main or push without operator approval
- ❌ **Never** deploy contracts or change blockchain authority
- ❌ **Never** delete data, logs, databases, or Obsidian notes
- ❌ **Never** run `git push`, `git merge`, or destructive git ops
- ❌ **Never** edit `.env` files or secrets
- ❌ **Never** modify `docker-compose.yml` or production plists

### Money & Resources
- ❌ **Never** spend real money without explicit approval
- ❌ **Never** raise paid API caps or add paid dependencies
- ❌ **Never** top up credits or change payment state
- ❌ **Never** touch live trading risk or funds

### Integrity
- ❌ **Never** fabricate output — if a command/tool fails, report it honestly
- ❌ **Never** claim verification that wasn't actually performed
- ❌ **Never** mark work "done" on process signals alone — verify the artifact

### Safety
- ❌ **Never** expose backend or sensitive infra publicly
- ❌ **Never** change firewall rules
- ❌ **Never** create public repos without approval

## LOOP-SPECIFIC RULES

### Before Every Autonomous Run
1. Read VISION.md, RULES.md, and ARCHITECTURE.md (when it exists)
2. Read current git state (`git status --short`)
3. Check for operator changes that must be preserved
4. Select exactly ONE task from the compiled backlog

### During Every Autonomous Run
1. Write the failing test FIRST (red)
2. Write minimal code to make it pass (green)
3. Run the verification command
4. Report CHANGED, VERIFIED, BLOCKED, NEXT

### After Every Autonomous Run
1. All tests must pass (regression gate)
2. No more than 3 files changed
3. State is written to the progress backlog
4. Evidence is recorded: files changed, command output, test result

## QUALITY STANDARDS

### Tests
- Every code change MUST have a test
- Tests are written BEFORE the implementation
- Use TDD: RED → GREEN → REFACTOR
- Test the contract, not the implementation

### Code
- Follow existing patterns in the repo
- Minimal diffs — don't refactor unrelated code
- One invariant per change
- Read the target file before editing it

### Communication
- Be honest about what's staged vs real
- `proof_ok=false` means exactly that
- `trust_tier=proof_staged` is not the same as `verified_onchain`
- Never oversell what the system can do

## MISTAKE PATTERNS (learned the hard way)

1. **Writing tests against ideal APIs, not actual code** → Read the real implementation before writing test expectations
2. **Drifting from core logic into glass-box polish** → Check VISION.md: core protocol first
3. **Silent failures in launchd loops** → Always write durable evidence to Obsidian
4. **Provider routing drift** → Use explicit provider strings, don't rely on defaults
5. **Context overflow creating fake continuity** → Re-read state files each run, don't trust memory

## THE GOLDEN RULE

> **Ship value every 24-48 hours.** A small verified delta beats a big plan. The system is here to produce money, content, knowledge, or prototypes — not another planning document.

When stuck between two choices, pick the one that ships faster with honest verification.
