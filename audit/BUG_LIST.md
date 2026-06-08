# Benchmark-bug audit — computed (batch 1: 49/120 of hardcoded-expected medium tasks)

**49 audited, 17 BUG (34.7%), 32 CLEAN.** Each verdict computed (real answer vs test hardcode).

Types: spec_contradicts_test=4, hardcoded_preview=3, corrupted_fixture=6, too_weak=4

## alloy_analyzer_scope_insufficient_medium  [spec_contradicts_test]
- hardcoded: Test expects exactly {"texture_units": >=16, "uniform_buffers": >=12} and asserts vertex_attributes and fragment_outputs are NOT included (expected_keys == {"texture_units","uniform_buffers"}).
- computed: From all 5 scenes, max requirements vs current limits: texture_units 20>8, vertex_attributes 12>10, uniform_buffers 15>6, fragment_outputs 6>4 — ALL FOUR exceed current limits and need increasing.
- evidence: The grader matches only scene #1 ("Forest Scene": tex16/vert8/ubo12/frag4) preview, but deployed scene_complexity.json has 5 scenes. "City Landscape" alone has vertex_attributes=12 (>10 current) and fragment_outputs=6 (>4 current), so a correct per-instruction solution must include all four resource

## annovar_annotation_databases_medium  [hardcoded_preview]
- hardcoded: installed_count == 3; missing_databases == {hg38_cosmic70, hg38_exac03}; outdated == [hg38_clinvar_20210501]
- computed: Real humandb_databases.txt has 13 non-idx .txt database files (installed_count=13, not 3). Missing per base-name rule = {hg38_cosmic70, hg38_exac03, hg38_intervar_20180118, hg38_revel} (not the hardco
- evidence: The deployed environment/data/humandb_databases.txt contains 24 lines (13 database .txt files + idx files), but the test hardcodes expected_count=3 with a comment admitting "looking at the preview, we see 5 lines, but line 5 is cut off" — the author counted from a truncated 5-line preview. Actual fi

## ansible_async_task_status_check_medium  [spec_contradicts_test]
- hardcoded: failed_job_ids = exactly 4 IDs (only finished=0 jobs): 987654321.54321, 222333444.55566, 777888999.11122, 888999000.22233; with strict len()==4 assertion
- computed: Applying the instruction's stated rule "status != 0 OR finished != 1" to the 10 real status files yields 6 failed jobs: the 4 hardcoded ones PLUS 111222333.44444 (rc=1, chmod 'Operation not permitted'
- evidence: The instruction objective 2 defines failure as "status != 0 or finished != 1" (an OR), which selects 6 jobs from the deployed data. The grader hardcodes only the 4 finished=0 jobs and asserts len(failed_job_ids)==4, so a solution that correctly follows the spec's OR rule (including rc=1 jobs 1112223

## apt_cache_depends_circular_medium  [hardcoded_preview]
- hardcoded: expected_packages = {'libssl', 'libcrypto', 'python-requests', 'python-urllib3'} (4 packages, derived from a 5-line file preview)
- computed: 14 packages: babel, binutils, containerd, cpp, docker, gcc, libcrypto, libmysql, libssl, mysql-client, python-requests, python-urllib3, runc, webpack
- evidence: The grader's test_correct_packages_identified asserts identified_packages == exactly the 4-package set taken from a file "preview" (first 5 lines). But the deployed /tmp/package_dependencies.txt has 64 lines with multiple additional cycles (mysql-client<->libmysql, gcc<->binutils/cpp, docker<->conta

## arp_spoofing_mitm_attack_medium  [corrupted_fixture]
- hardcoded: Test computes dynamically: first baseline-IP/non-baseline-MAC row => SPOOFED_IP 192.168.1.50, ATTACKER_MAC 00:1a:2b:3c:4d:50
- computed: Intended attack is 192.168.1.100 / aa:bb:cc:dd:ee:ff, but log uses 00:1a:2b:3c:4d:XX for ALL legit hosts (none match baseline 00:0c:29:XX), so 56 rows / 11 IPs falsely look spoofed; test breaks on fir
- evidence: The deployed arp_traffic.log assigns every legitimate host a 00:1a:2b:3c:4d:XX MAC that differs from its baseline 00:0c:29:XX MAC, so the grader flags the FIRST row (192.168.1.50) as the attack. The real attacker (192.168.1.100 / aa:bb:cc:dd:ee:ff, matching the instruction's example) is never select

## articulation_points_bridges_medium  [spec_contradicts_test]
- hardcoded: critical_nodes = ["D"] and critical_links = [["D","E"]]
- computed: 27 articulation points (incl. AB, AC, D, E, F, Firewall1, Gateway1/2, routers, switches...) and 41 bridges (incl. D-E plus 40 more)
- evidence: The deployed /workspace/network_topology.txt has 62 edges, but the test's hardcoded expected values (["D"], [["D","E"]]) match only the first 5 lines — the toy example shown in instruction.md. A correct solver run on the real data yields 27 articulation points and 41 bridges, so a correct solution f

## aws_iam_privilege_escalation_medium  [corrupted_fixture]
- hardcoded: Test only enforces vulnerable_user=="dev-user" (given verbatim in instruction), escalation_target=any non-empty string, and dangerous_permission=any of ~18 common AWS escalation substrings; the instru
- computed: No privilege escalation path exists in the deployed data. dev-user-policy.json is {"Statement":[{"Resource":"*"}]} with NO Action/Effect — it grants no iam:PassRole, sts:AssumeRole, or any dangerous p
- evidence: The fixture is corrupted: a correct analysis of /home/user/iam_policies/dev-user-policy.json finds no escalation permission at all, so the task's premise (dev-user can escalate to admin-role via a dangerous permission) is unprovable from the real data. Compounding this, the grader never checks the d

## aws_lambda_timeout_increase_medium  [too_weak]
- hardcoded: Per-function expected timeout = max(1,min(900, ceil(1.5 * p95_ms/1000))); from cloudwatch_logs the correct updates would include report-generator=16, data-processor=7, payment-handler=5, image-resizer
- computed: An empty solution {"updated_functions": [], "total_updated": 0} passes ALL 8 tests. Reason: the grader only flags "insufficient" funcs by reading first_item["Timeout"] as an int in config/lambda_confi
- evidence: Corrupted/inconsistent fixtures break the only enforcement path: test_insufficient_timeout_functions_updated never triggers (only int-Timeout config has adequate timeout), and test_config_files_updated only checks functions the agent voluntarily lists, so a no-op solution vacuously passes every test

## bayesian_network_structure_learning_medium  [too_weak]
- hardcoded: No expected STATUS at all; tests only check file exists, 4 lines, regex format, valid variable names, and edge order. STATUS is only constrained to be the literal "SUPPORTED" or "REJECTED".
- computed: From the real 1000-row data, all 4 edges are SUPPORTED (G-test conditional independence p-values: PriorKnowledge->TestScore p=2e-105, StudyHours->TestScore p=1e-41, Attendance->Participation p=2e-310,
- evidence: The grader never validates the STATUS values against the data-derived answer. test_validation_results_correct_edges checks only parent/child names and order (match.group(1)/(2)), ignoring group(3); no test compares STATUS to expected. An agent outputting all REJECTED (wrong; data says all SUPPORTED)

## bellman_ford_negative_cycles_medium  [hardcoded_preview]
- hardcoded: test_affected_currencies_correct asserts affected == {"USD","EUR","GBP"} (exact set equality)
- computed: All 10 currencies participate in negative cycles: AUD, BRL, CAD, CHF, CNY, EUR, GBP, INR, JPY, USD
- evidence: The hardcoded expected set comes from the 3-line example in the instruction, but the real exchange_rates.txt has 57 edges over 10 currencies. Floyd-Warshall on -log(rate) yields D[i][i] < 0 (positive-product self-cycle) for every one of the 10 currencies (products 556x to 5655x), so a correct soluti

## blast_interpolation_sequences_medium  [too_weak]
- hardcoded: No data value is asserted at all. Tests only check: file exists, exactly 3 lines, key=value format, keys ['violations','total_interpolants','max_trace_length'] in order, values isdigit() and >=0, and 
- computed: Correct values from the 4 logs: violations=3 (001,003,004 UNSAFE), total_interpolants=45 (12+9+16+8), max_trace_length=15. But the grader never verifies these.
- evidence: The instruction requires values that "correctly reflect the data," yet test_outputs.py contains zero assertions on the actual numbers. A trivially wrong output like 'violations=0\ntotal_interpolants=0\nmax_trace_length=0' satisfies every test (0 is numeric, non-negative, and in 0-4). The test only v

## blender_python_batch_render_medium  [corrupted_fixture]
- hardcoded: Tests expect 60 PNG frames (frame_0001.png..frame_0060.png) at 1280x720 rendered from /workspace/animation.blend, plus render_status.txt with frames_rendered=60.
- computed: The deployed animation.blend is not a Blender file — it is ASCII text beginning "I'll create the Python script that handles batch rendering..." containing the render_batch.py solution source, not BLEN
- evidence: `file animation.blend` reports "Python script, ASCII text executable"; its first bytes are "I'll create the Python script th" instead of the required "BLENDER" magic. bpy.ops.wm.open_mainfile would fail on it, so the 60-frame render the tests hardcode is impossible from the real fixture, making the 

## brms_custom_prior_specification_medium  [too_weak]
- hardcoded: No hardcoded expected booleans at all; test_validation_results_correct_values only re-asserts that the 5 fields exist, never comparing their values.
- computed: Under the spec (mean-in-range AND >=90% mass-in-range): treatment mass=0.866, age mean 0.5 out of [0.1,0.4], severity mass=0.789, intercept mass=0.683, sigma mean 8 out of [3,7] -> all five => false. 
- evidence: The supposed correctness test (test_validation_results_correct_values) builds an empty expected_validation dict and then only asserts the five keys are present (already covered by other tests); it never validates the boolean values against the priors. So all-true, all-false, or random outputs all pa

## caret_cross_validation_setup_medium  [corrupted_fixture]
- hardcoded: test_stratification_maintained reads the dataset from the hardcoded path /workspace/data/patient_data.csv
- computed: The deployed CSV exists only at /workspace/experiments/patient_data.csv (300 valid rows, IDs 1-300, ~73% recovered). /workspace/data/patient_data.csv is never created, so the stratification test raise
- evidence: Dockerfile line 26 copies data to /workspace/experiments/patient_data.csv (matching instruction line 11), but test_outputs.py line 66 reads /workspace/data/patient_data.csv. Nothing (Dockerfile, test.sh, task.toml) provisions /workspace/data/, so even a perfectly correct cv_config.json fails the str

## commix_command_injection_testing_medium  [corrupted_fixture]
- hardcoded: Grader dynamically computes expected vulnerable set = ['/api/ping','/admin/backup','/user/export','/system/check','/tools/convert','/admin/cleanup'] and requires exact-count + membership match.
- computed: The genuinely vulnerable routes are ['/api/ping','/admin/backup','/user/export','/system/check','/tools/convert','/logs/view'] (6). /admin/cleanup is SAFE (hardcoded path, list args, no user input); /
- evidence: The deployed /workspace/webapp.py (COPY in Dockerfile) is corrupted: the real Flask code ends at line 201 but lines 202-233 append stray markdown fences plus an 'analysis script' containing os.system()/os.popen()/request. references. The grader's greedy regex (capture until next @app.route or end) s

## context_free_grammar_parsing_medium  [spec_contradicts_test]
- hardcoded: expected_valid = ["5","1+2","3*4","1+2*3"], expected_invalid = ["+1"] (only 5 of the 15 expressions)
- computed: CYK parse of the real grammar.cfg yields valid=[] (none) and invalid=all 15 expressions; e.g. "5","1+2","3*4","1+2*3" are all INVALID
- evidence: The deployed grammar defines N -> D N | D E and E -> D D | D E, so the smallest N requires 3 digits; since every S derivation begins with N, no single-digit "number" can parse. A correct CYK parser marks all of "5","1+2","3*4","1+2*3" invalid, but test_correct_grammar_parsing hardcodes them as valid

## count_min_sketch_frequency_medium  [corrupted_fixture]
- hardcoded: Test compares estimates against ground_truth.json at runtime: 192.168.1.100=1342, 10.0.0.50=678, 172.16.0.1=145 (within 10% tolerance).
- computed: Real access_logs.txt has only 607 lines / 4 unique IPs (not the 50k claimed). True log frequencies: 192.168.1.100=243, 10.0.0.50=122, 172.16.0.1=121. A count-min sketch (which only overcounts) computi
- evidence: ground_truth.json (276 IPs summing to 63,074) is for the full 50,000-entry log in the instruction, but the deployed access_logs.txt is a 607-line stub. A correct CMS estimate (>= true freq of 243/122/121) can never reach gt 1342/678/145, so test_frequency_estimates_within_tolerance fails for any leg

