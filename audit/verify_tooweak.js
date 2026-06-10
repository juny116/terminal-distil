export const meta = {
  name: 'verify-tooweak',
  description: 'Verify too_weak tasks by actually running the grading test against a deliberately-wrong/trivial answer',
  phases: [{ title: 'Verify' }],
}

const SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['task', 'result', 'evidence'],
  properties: {
    task: { type: 'string' },
    result: { type: 'string', enum: ['TRIVIAL_PASSES', 'FAILS', 'CANT_RUN'] },
    n_tests_total: { type: 'integer' },
    n_tests_passed_with_trivial: { type: 'integer' },
    evidence: { type: 'string' },
  },
}

const ENV = '/home/juny116/Workspace/terminal-bench-env/environments_harbor'
let tasks
if (typeof args === 'string' && (args.startsWith('/') || args.endsWith('.json'))) {
  const raw = await agent(`Output the exact raw contents of the file ${args} (run: cat ${args}). Return ONLY the JSON array, no commentary, no code fences.`, { label: 'load' })
  const m = raw.match(/\[[\s\S]*\]/); tasks = JSON.parse(m ? m[0] : raw)
} else tasks = typeof args === 'string' ? JSON.parse(args) : args

phase('Verify')
const results = await parallel(tasks.map((task) => () => agent(
  `VERIFY whether terminal-bench task "${task}" has a too-weak grading test by actually RUNNING the test against a deliberately WRONG/trivial answer. If a wrong answer passes, the test is confirmed too_weak.

Files: ${ENV}/${task}/instruction.md , ${ENV}/${task}/tests/test_outputs.py , ${ENV}/${task}/tests/test.sh , ${ENV}/${task}/environment/Dockerfile , ${ENV}/${task}/environment/ (data).

METHOD (actually execute, do not just reason):
1. Read test_outputs.py + Dockerfile to learn: the exact OUTPUT path the test reads, and which INPUT data files are placed where (the Dockerfile COPY commands).
2. In a fresh temp dir, reproduce the setup: copy the needed input data to the paths the test expects (create dirs as needed; if the test reads absolute paths like /workspace or /tmp that you can write to, use them; otherwise copy test_outputs.py to the temp dir and run it there with the data placed relative). Install only lightweight pip deps if trivially available; if the task needs heavy/unavailable tooling (samtools, PIL on corrupt files, GPU, etc.), return CANT_RUN.
3. Write a DELIBERATELY WRONG but format-valid output to the expected output path: satisfy obvious structural requirements (right filename, line count, JSON keys, value types/ranges) but with fabricated/incorrect VALUES (e.g. all-zeros, all-"PASS", arbitrary in-range numbers) that do NOT solve the task.
4. Run the test: \`python -m pytest test_outputs.py -q\` (or bash test.sh if needed). Count how many tests pass.

Report:
- TRIVIAL_PASSES: your wrong/trivial answer passed ALL the grading tests -> confirmed too_weak.
- FAILS: at least one test correctly rejected your wrong answer -> the test is NOT actually too weak (the original audit over-called it).
- CANT_RUN: you could not reproduce the env / run the test (missing heavy deps, unwritable paths, etc.).
Put the pass counts in n_tests_total / n_tests_passed_with_trivial. Be honest — if the wrong answer fails any test, report FAILS.
CRITICAL: end by calling StructuredOutput with the verdict, even if CANT_RUN.`,
  { schema: SCHEMA, label: `verify:${task.slice(0, 24)}`, phase: 'Verify', model: 'sonnet' }
)))

const ok = results.filter(Boolean)
const by = (v) => ok.filter(r => r.result === v).length
log(`verified ${ok.length}/${tasks.length}: TRIVIAL_PASSES=${by('TRIVIAL_PASSES')} FAILS=${by('FAILS')} CANT_RUN=${by('CANT_RUN')}`)
return {
  n: ok.length, n_tasks: tasks.length,
  trivial_passes: by('TRIVIAL_PASSES'), fails: by('FAILS'), cant_run: by('CANT_RUN'),
  confirm_rate_excl_cantrun: (by('TRIVIAL_PASSES') + by('FAILS')) ? by('TRIVIAL_PASSES') / (by('TRIVIAL_PASSES') + by('FAILS')) : null,
  details: ok.map(r => ({ task: r.task, result: r.result, passed: r.n_tests_passed_with_trivial, total: r.n_tests_total, evidence: r.evidence })),
}
