export const meta = {
  name: 'benchmark-bug-audit-full',
  description: 'Audit all hardcoded-expected terminal-bench tasks for benchmark bugs (compute real answer vs hardcoded); return every verdict',
  phases: [{ title: 'Audit' }],
}

const SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['task', 'verdict', 'bug_type', 'evidence'],
  properties: {
    task: { type: 'string' },
    verdict: { type: 'string', enum: ['BUG', 'CLEAN', 'UNCERTAIN'] },
    bug_type: { type: 'string', enum: ['hardcoded_preview', 'spec_contradicts_test', 'corrupted_fixture', 'too_weak', 'none', 'unknown'] },
    evidence: { type: 'string', description: '1-2 sentences; for BUG cite the computed mismatch' },
  },
}

const ENV = '/home/juny116/Workspace/terminal-bench-env/environments_harbor'
let tasks
if (typeof args === 'string' && (args.startsWith('/') || args.endsWith('.json'))) {
  const raw = await agent(`Output the exact raw contents of the file ${args} (run: cat ${args}). Return ONLY the file contents verbatim — a JSON array — with no commentary and no code fences.`, { label: 'load-tasklist' })
  const m = raw.match(/\[[\s\S]*\]/)
  tasks = JSON.parse(m ? m[0] : raw)
} else {
  tasks = typeof args === 'string' ? JSON.parse(args) : args
}

phase('Audit')
const results = await parallel(tasks.map((task) => () => agent(
  `Audit terminal-bench task "${task}" for a BENCHMARK BUG (grading test is wrong, not the agent).
Read: ${ENV}/${task}/instruction.md , ${ENV}/${task}/tests/test_outputs.py (find HARDCODED expected values), ${ENV}/${task}/environment/ (real input data).
Determine if the test's hardcoded expected answer matches what a CORRECT solution yields from the REAL deployed data.
Method: find the hardcode + what it represents; find the real data; WRITE+RUN a short script to compute the correct answer; compare.
EFFICIENCY: cap yourself at ~8 tool calls. If computing the exact answer is too expensive/needs heavy domain tooling, return UNCERTAIN — do NOT keep grinding.
Verdict (CONSERVATIVE, avoid false positives):
- BUG: you computed the correct answer and it demonstrably differs from the test's hardcode (e.g. test hardcodes N items from a file preview but real data has M>N; expected is for a small example but deployed data is large; instruction rule contradicts the expected set); OR corrupted/unprovisioned fixtures make it unpassable; OR test is so weak an empty/trivial output passes.
- CLEAN: hardcode matches the real data, or the test checks structural properties (no data-derived hardcode).
- UNCERTAIN: cannot compute within budget. Prefer UNCERTAIN over a guessed BUG.
CRITICAL: your ONLY valid output is a call to the StructuredOutput tool with {task, verdict, bug_type, evidence}. Call it as your FINAL action no matter what — even if UNCERTAIN. Do not end without calling it.`,
  { schema: SCHEMA, label: `audit:${task.slice(0, 26)}`, phase: 'Audit' }
)))

const ok = results.filter(Boolean)
const by = (v) => ok.filter(r => r.verdict === v)
const bugs = by('BUG'), clean = by('CLEAN'), unc = by('UNCERTAIN')
log(`audited ${ok.length}/${tasks.length}: BUG=${bugs.length} CLEAN=${clean.length} UNCERTAIN=${unc.length}`)
return {
  n_audited: ok.length, n_tasks: tasks.length,
  n_bug: bugs.length, n_clean: clean.length, n_uncertain: unc.length,
  bug_rate_excl_uncertain: (bugs.length + clean.length) ? bugs.length / (bugs.length + clean.length) : 0,
  verdicts: ok.map(r => ({ task: r.task, verdict: r.verdict, bug_type: r.bug_type })),
  bugs: bugs.map(r => ({ task: r.task, bug_type: r.bug_type, evidence: r.evidence })),
}
