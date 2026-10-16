# Bullet-FVE reading study: synthesis tables

Exploratory. Part A tabulates the 288 reader records (24 batches x 12; stratified sample, not random). Part B summarises the all-data tests in synth_tests.json (67,317 bullets, 5,615 cells x 3 settings; intervals are chat-level percentile bootstrap, 149 chats, 1000 reps). Interactive page: https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#<k>.

Reader classes: error = invented_specific_detail, wrong_relation_or_attribute, persona_or_self_claim, misread_prompt_or_context; junk = off_topic_junk; vague = generic_or_vague; no_error = plausible_continuation_not_taken, judge_overstrict, not_wrong_clean.

## Part A: reading records

### A1. Reader blind_type by stratum

| | n | invented_specific_detail | wrong_relation_or_attribute | persona_or_self_claim | misread_prompt_or_context | off_topic_junk | generic_or_vague | plausible_continuation_not_taken | judge_overstrict | not_wrong_clean |
|---|---|---|---|---|---|---|---|---|---|---|
| A_wrong_high | 60 | 16 (27%) | 24 (40%) | 3 (5%) | 2 (3%) | 0 | 0 | 8 (13%) | 7 (12%) | 0 |
| B_wrong_low | 60 | 17 (28%) | 25 (42%) | 2 (3%) | 1 (2%) | 0 | 1 (2%) | 9 (15%) | 5 (8%) | 0 |
| C_clean_low_in_halluc | 36 | 3 (8%) | 3 (8%) | 0 | 1 (3%) | 0 | 1 (3%) | 1 (3%) | 0 | 27 (75%) |
| D_clean_high_in_consistent | 36 | 0 | 0 | 1 (3%) | 0 | 0 | 0 | 6 (17%) | 0 | 29 (81%) |
| E_disagree | 48 | 8 (17%) | 14 (29%) | 3 (6%) | 0 | 0 | 0 | 16 (33%) | 7 (15%) | 0 |
| F_wrong_unscored | 24 | 6 (25%) | 5 (21%) | 2 (8%) | 0 | 0 | 0 | 5 (21%) | 6 (25%) | 0 |
| G_offtopic | 24 | 3 (12%) | 3 (12%) | 0 | 3 (12%) | 7 (29%) | 0 | 4 (17%) | 4 (17%) | 0 |
| **all** | 288 | 53 | 74 | 11 | 7 | 7 | 2 | 49 | 29 | 56 |

### A2. Reader blind_type by setting (all strata)

| | n | invented_specific_detail | wrong_relation_or_attribute | persona_or_self_claim | misread_prompt_or_context | off_topic_junk | generic_or_vague | plausible_continuation_not_taken | judge_overstrict | not_wrong_clean |
|---|---|---|---|---|---|---|---|---|---|---|
| Original | 113 | 15 (13%) | 33 (29%) | 4 (4%) | 4 (4%) | 3 (3%) | 0 | 19 (17%) | 12 (11%) | 23 (20%) |
| Best of 32 | 86 | 16 (19%) | 23 (27%) | 3 (3%) | 2 (2%) | 1 (1%) | 1 (1%) | 10 (12%) | 9 (10%) | 21 (24%) |
| Combine 32 | 89 | 22 (25%) | 18 (20%) | 4 (4%) | 1 (1%) | 3 (3%) | 1 (1%) | 20 (22%) | 8 (9%) | 12 (13%) |
| **all** | 288 | 53 | 74 | 11 | 7 | 7 | 2 | 49 | 29 | 56 |

### A3. Reader blind_type by setting, wrong-bullet strata A, B, F only

| | n | invented_specific_detail | wrong_relation_or_attribute | persona_or_self_claim | misread_prompt_or_context | generic_or_vague | plausible_continuation_not_taken | judge_overstrict |
|---|---|---|---|---|---|---|---|---|
| Original | 54 | 11 (20%) | 25 (46%) | 2 (4%) | 2 (4%) | 0 | 7 (13%) | 7 (13%) |
| Best of 32 | 51 | 12 (24%) | 21 (41%) | 3 (6%) | 0 | 1 (2%) | 6 (12%) | 8 (16%) |
| Combine 32 | 39 | 16 (41%) | 8 (21%) | 2 (5%) | 1 (3%) | 0 | 9 (23%) | 3 (8%) |
| **all** | 144 | 39 | 54 | 7 | 3 | 1 | 22 | 18 |

### A4. Reader blind_type by source

| | n | invented_specific_detail | wrong_relation_or_attribute | persona_or_self_claim | misread_prompt_or_context | off_topic_junk | generic_or_vague | plausible_continuation_not_taken | judge_overstrict | not_wrong_clean |
|---|---|---|---|---|---|---|---|---|---|---|
| dailydialog | 143 | 22 (15%) | 30 (21%) | 10 (7%) | 5 (3%) | 3 (2%) | 0 | 28 (20%) | 14 (10%) | 31 (22%) |
| lmsys | 145 | 31 (21%) | 44 (30%) | 1 (1%) | 2 (1%) | 4 (3%) | 2 (1%) | 21 (14%) | 15 (10%) | 25 (17%) |
| **all** | 288 | 53 | 74 | 11 | 7 | 7 | 2 | 49 | 29 | 56 |

### A5. Reader agrees with the judge, by stratum

| | n | yes | partly | no |
|---|---|---|---|---|
| A_wrong_high | 60 | 34 (57%) | 21 (35%) | 5 (8%) |
| B_wrong_low | 60 | 36 (60%) | 16 (27%) | 8 (13%) |
| C_clean_low_in_halluc | 36 | 27 (75%) | 9 (25%) | 0 |
| D_clean_high_in_consistent | 36 | 34 (94%) | 2 (6%) | 0 |
| E_disagree | 48 | 18 (38%) | 13 (27%) | 17 (35%) |
| F_wrong_unscored | 24 | 12 (50%) | 8 (33%) | 4 (17%) |
| G_offtopic | 24 | 3 (12%) | 17 (71%) | 4 (17%) |
| **all** | 288 | 164 | 86 | 38 |

### A6. Reader agrees with the judge, by setting

| | n | yes | partly | no |
|---|---|---|---|---|
| Original | 113 | 68 (60%) | 33 (29%) | 12 (11%) |
| Best of 32 | 86 | 52 (60%) | 27 (31%) | 7 (8%) |
| Combine 32 | 89 | 44 (49%) | 26 (29%) | 19 (21%) |
| **all** | 288 | 164 | 86 | 38 |

### A7. Judge bullet label x reader verdict class

| | n | error | junk | vague | no_error |
|---|---|---|---|---|---|
| judge WRONG | 192 | 128 (67%) | 0 | 1 (1%) | 63 (33%) |
| judge clean | 72 | 8 (11%) | 0 | 1 (1%) | 63 (88%) |
| judge OFF-TOPIC | 24 | 9 (38%) | 7 (29%) | 0 | 8 (33%) |
| **all** | 288 | 145 | 7 | 2 | 134 |

### A8. Direction of reader-judge disagreement, by stratum

judge_too_strict = judge WRONG/OFF-TOPIC, reader sees no error; judge_missed_error = judge clean, reader sees an error; boundary_* = both see a problem but disagree on wrong vs off-topic.

| | n | agree_wrong | agree_clean | agree_offtopic | agree_weak | judge_too_strict | judge_missed_error | boundary_offtopic_should_be_wrong |
|---|---|---|---|---|---|---|---|---|
| A_wrong_high | 60 | 45 (75%) | 0 | 0 | 0 | 15 (25%) | 0 | 0 |
| B_wrong_low | 60 | 45 (75%) | 0 | 0 | 1 (2%) | 14 (23%) | 0 | 0 |
| C_clean_low_in_halluc | 36 | 0 | 28 (78%) | 0 | 1 (3%) | 0 | 7 (19%) | 0 |
| D_clean_high_in_consistent | 36 | 0 | 35 (97%) | 0 | 0 | 0 | 1 (3%) | 0 |
| E_disagree | 48 | 25 (52%) | 0 | 0 | 0 | 23 (48%) | 0 | 0 |
| F_wrong_unscored | 24 | 13 (54%) | 0 | 0 | 0 | 11 (46%) | 0 | 0 |
| G_offtopic | 24 | 0 | 0 | 7 (29%) | 0 | 8 (33%) | 0 | 9 (38%) |
| **all** | 288 | 128 | 63 | 7 | 2 | 71 | 8 | 9 |

### A9. Direction of disagreement, by setting

| | n | agree_wrong | agree_clean | agree_offtopic | agree_weak | judge_too_strict | judge_missed_error | boundary_offtopic_should_be_wrong |
|---|---|---|---|---|---|---|---|---|
| Original | 113 | 53 (47%) | 26 (23%) | 3 (3%) | 0 | 28 (25%) | 0 | 3 (3%) |
| Best of 32 | 86 | 36 (42%) | 23 (27%) | 1 (1%) | 1 (1%) | 17 (20%) | 3 (3%) | 5 (6%) |
| Combine 32 | 89 | 39 (44%) | 14 (16%) | 3 (3%) | 1 (1%) | 26 (29%) | 5 (6%) | 1 (1%) |
| **all** | 288 | 128 | 63 | 7 | 2 | 71 | 8 | 9 |

### A10. relation_to_context keyword codes by stratum

Heuristic regex codes on the readers' free text; several codes can apply to one record. Patterns are in synth_tests.py (REL_CODES).

| | n | right_frame_or_slot | filler_swapped | predicts_next_text | echoes_earlier_text | plausible_untaken_continuation | adds_unsupported_detail | topic_or_domain_drift | persona_self_claim | none |
|---|---|---|---|---|---|---|---|---|---|---|
| A_wrong_high | 60 | 14 (23%) | 22 (37%) | 29 (48%) | 10 (17%) | 7 (12%) | 21 (35%) | 4 (7%) | 5 (8%) | 4 (7%) |
| B_wrong_low | 60 | 10 (17%) | 22 (37%) | 18 (30%) | 19 (32%) | 6 (10%) | 19 (32%) | 2 (3%) | 5 (8%) | 8 (13%) |
| C_clean_low_in_halluc | 36 | 2 (6%) | 4 (11%) | 23 (64%) | 6 (17%) | 5 (14%) | 3 (8%) | 1 (3%) | 3 (8%) | 4 (11%) |
| D_clean_high_in_consistent | 36 | 1 (3%) | 0 | 29 (81%) | 5 (14%) | 8 (22%) | 5 (14%) | 2 (6%) | 5 (14%) | 3 (8%) |
| E_disagree | 48 | 12 (25%) | 13 (27%) | 17 (35%) | 8 (17%) | 12 (25%) | 13 (27%) | 0 | 4 (8%) | 5 (10%) |
| F_wrong_unscored | 24 | 1 (4%) | 6 (25%) | 19 (79%) | 4 (17%) | 4 (17%) | 7 (29%) | 1 (4%) | 1 (4%) | 1 (4%) |
| G_offtopic | 24 | 9 (38%) | 8 (33%) | 9 (38%) | 1 (4%) | 5 (21%) | 4 (17%) | 11 (46%) | 0 | 1 (4%) |
| **all** | 288 | 49 | 75 | 144 | 53 | 47 | 72 | 21 | 23 | 26 |

### A11. score_reading keyword codes by stratum (reader's explanation of the FVE numbers)

Patterns in SCORE_CODES. error_invisible_to_score = the reader says the error costs nothing / is ignored / is unscored.

| | n | frame_template_format | opening_matches_next_text | error_invisible_to_score | mentions_redundancy_any_bullet | unscored_tail | short_or_fragment | language_script | whole_readout_low | echo_or_backward | none |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A_wrong_high | 60 | 33 (55%) | 20 (33%) | 41 (68%) | 11 (18%) | 6 (10%) | 1 (2%) | 4 (7%) | 10 (17%) | 7 (12%) | 2 (3%) |
| B_wrong_low | 60 | 29 (48%) | 16 (27%) | 20 (33%) | 29 (48%) | 0 | 11 (18%) | 11 (18%) | 12 (20%) | 5 (8%) | 3 (5%) |
| C_clean_low_in_halluc | 36 | 16 (44%) | 15 (42%) | 11 (31%) | 19 (53%) | 2 (6%) | 11 (31%) | 14 (39%) | 2 (6%) | 6 (17%) | 1 (3%) |
| D_clean_high_in_consistent | 36 | 13 (36%) | 11 (31%) | 13 (36%) | 8 (22%) | 1 (3%) | 3 (8%) | 10 (28%) | 3 (8%) | 5 (14%) | 3 (8%) |
| E_disagree | 48 | 21 (44%) | 9 (19%) | 28 (58%) | 9 (19%) | 4 (8%) | 1 (2%) | 6 (12%) | 1 (2%) | 0 | 5 (10%) |
| F_wrong_unscored | 24 | 3 (12%) | 8 (33%) | 15 (62%) | 6 (25%) | 21 (88%) | 0 | 3 (12%) | 0 | 4 (17%) | 0 |
| G_offtopic | 24 | 11 (46%) | 6 (25%) | 10 (42%) | 10 (42%) | 0 | 1 (4%) | 5 (21%) | 5 (21%) | 2 (8%) | 1 (4%) |
| **all** | 288 | 126 | 85 | 138 | 92 | 34 | 28 | 53 | 33 | 29 | 15 |

### A12. Judge/pipeline problems mentioned in note or score_reading

Patterns in NOTE_CODES.

| | n | span_not_counted | cross_setting_inconsistency | judge_overstrict_note | judge_misreads_chinese | stage2_rationale_glitch | lenient_or_missed | none |
|---|---|---|---|---|---|---|---|---|
| A_wrong_high | 60 | 4 (7%) | 11 (18%) | 11 (18%) | 1 (2%) | 0 | 4 (7%) | 36 (60%) |
| B_wrong_low | 60 | 3 (5%) | 10 (17%) | 15 (25%) | 2 (3%) | 0 | 4 (7%) | 34 (57%) |
| C_clean_low_in_halluc | 36 | 4 (11%) | 3 (8%) | 7 (19%) | 1 (3%) | 0 | 4 (11%) | 20 (56%) |
| D_clean_high_in_consistent | 36 | 1 (3%) | 1 (3%) | 4 (11%) | 0 | 2 (6%) | 2 (6%) | 26 (72%) |
| E_disagree | 48 | 2 (4%) | 29 (60%) | 7 (15%) | 0 | 3 (6%) | 7 (15%) | 12 (25%) |
| F_wrong_unscored | 24 | 2 (8%) | 4 (17%) | 3 (12%) | 1 (4%) | 0 | 2 (8%) | 14 (58%) |
| G_offtopic | 24 | 1 (4%) | 4 (17%) | 2 (8%) | 3 (12%) | 0 | 1 (4%) | 16 (67%) |
| **all** | 288 | 17 | 62 | 49 | 8 | 5 | 24 | 158 |

### A13. E_disagree: why the settings disagree (hand-coded from the readers' "all settings" notes)

judge_inconsistent = same or near-identical content judged differently; judge_overstrict = flagged span is a reasonable continuation the other settings lack; span_match = an uncounted span decides the label; sample_change_real = a different sample carries an error the reader accepts.

| | n | judge_inconsistent | judge_overstrict | span_match | sample_change_real |
|---|---|---|---|---|---|
| E1_orig_halluc_best_consistent | 24 | 11 (46%) | 1 (4%) | 1 (4%) | 11 (46%) |
| E2_orig_consistent_combine_halluc | 24 | 17 (71%) | 0 | 1 (4%) | 6 (25%) |
| **all** | 48 | 28 | 1 | 2 | 17 |

### A14. E_disagree, sample_change_real only: reader blind_type

| | n | invented_specific_detail | wrong_relation_or_attribute | persona_or_self_claim | plausible_continuation_not_taken | judge_overstrict |
|---|---|---|---|---|---|---|
| E1_orig_halluc_best_consistent | 11 | 3 | 4 | 2 | 1 | 1 |
| E2_orig_consistent_combine_halluc | 6 | 2 | 4 | 0 | 0 | 0 |
| **all** | 17 | 5 | 8 | 2 | 1 | 1 |

### A15. E_disagree cases

| k | sub | cause | why | labels O/B/C |
|---|---|---|---|---|
| chat-dailydialog-0069.L20.p244 | E1 | judge_inconsistent | "substance abuse" WRONG in Original, "signs of overdose" unverifiable in Best | hallucinated/consistent/consistent |
| chat-dailydialog-0036.L36.p66 | E2 | sample_change_real | Combine pools sample #24 "fictional pizzeria" | consistent/consistent/hallucinated |
| chat-dailydialog-0007.L36.p101 | E1 | sample_change_real | stance clause "there’s no reason to fear it" only in the Original sample | hallucinated/consistent/consistent |
| chat-lmsys-0056.L52.p231 | E2 | judge_inconsistent | "print ... (`first`)" WRONG in Best, stage-2 true in Combine | consistent/hallucinated/hallucinated |
| chat-dailydialog-0027.L36.p59 | E1 | judge_inconsistent | "finding a gift idea" WRONG in Original, "find the perfect gift idea" clean in Best and Combine | hallucinated/consistent/hallucinated |
| chat-lmsys-0024.L44.p451 | E2 | judge_inconsistent | same frame, "Existential AI Risk" clean in Original, near-synonym WRONG in Best | consistent/hallucinated/hallucinated |
| chat-dailydialog-0044.L60.p136 | E2 | sample_change_real | Best and Combine both pick sample #4 Mid-Autumn bullet | consistent/hallucinated/hallucinated |
| chat-dailydialog-0032.L20.p44 | E1 | sample_change_real | different odd tail after the same correct prefix in each setting ("virtual library") | hallucinated/consistent/hallucinated |
| chat-dailydialog-0012.L20.p26 | E2 | judge_inconsistent | similar self-inclusive social claim only unverifiable in Best | consistent/consistent/hallucinated |
| chat-lmsys-0030.L60.p95 | E1 | sample_change_real | different filler in a shared template ("installing the library via pip"); readers split on the flag | hallucinated/consistent/consistent |
| chat-lmsys-0029.L44.p83 | E1 | sample_change_real | Original assigns the shortcut to Pause; Best uses generic wording | hallucinated/consistent/hallucinated |
| chat-lmsys-0001.L52.p484 | E2 | judge_inconsistent | identical sample-#10 bullet WRONG in Best, clean in Combine; same claim clean in b0/b1 | consistent/hallucinated/hallucinated |
| chat-dailydialog-0071.L20.p154 | E1 | judge_inconsistent | "Answering thousands of questions" WRONG in Original, unverifiable in Best | hallucinated/consistent/hallucinated |
| chat-lmsys-0005.L60.p169 | E2 | judge_inconsistent | near-identical story-choice content true/unverifiable in Original, WRONG in Combine | consistent/hallucinated/hallucinated |
| chat-dailydialog-0070.L60.p252 | E2 | judge_inconsistent | similar pessimistic stance clean in Original/Best | consistent/consistent/hallucinated |
| chat-dailydialog-0042.L20.p67 | E1 | sample_change_real | Original sample swaps the baby for a wedding | hallucinated/consistent/consistent |
| chat-lmsys-0054.L52.p358 | E2 | judge_inconsistent | nearly identical "distribute reports" content; single-token oddities flagged unevenly | consistent/hallucinated/hallucinated |
| chat-lmsys-0052.L52.p302 | E1 | judge_inconsistent | "85°C" WRONG in Original, Best "212°F" equally off but unflagged | hallucinated/consistent/hallucinated |
| chat-dailydialog-0046.L60.p22 | E2 | sample_change_real | Combine adds a polarity-flipped 4th bullet (drop 0.0011) | consistent/consistent/hallucinated |
| chat-lmsys-0036.L44.p51 | E1 | judge_inconsistent | borderline modality span; equally unsupported claims clean elsewhere | hallucinated/consistent/consistent |
| chat-lmsys-0032.L60.p112 | E1 | judge_overstrict | invented numbered heading after a list item flagged; reader calls it a reasonable continuation | hallucinated/consistent/consistent |
| chat-lmsys-0066.L44.p403 | E2 | judge_inconsistent | identical sample-#15 heading clean in Best, WRONG in Combine | consistent/hallucinated/hallucinated |
| chat-lmsys-0041.L60.p237 | E1 | judge_inconsistent | conditional "impossible" WRONG in Original, same claim unverifiable in Best | hallucinated/consistent/hallucinated |
| chat-dailydialog-0028.L44.p318 | E2 | sample_change_real | Combine pools sample #10 with the name "John" for Joe | consistent/consistent/hallucinated |
| chat-dailydialog-0020.L36.p60 | E2 | sample_change_real | Combine pools sample #1 "your father's new job" | consistent/consistent/hallucinated |
| chat-lmsys-0034.L52.p470 | E1 | sample_change_real | garbled formula name "Bredt-Batavier" only in the Original sample | hallucinated/consistent/consistent |
| chat-lmsys-0051.L44.p313 | E2 | judge_inconsistent | MDMA-therapy wording clean in Original/Best, WRONG in Combine | consistent/consistent/hallucinated |
| chat-lmsys-0070.L20.p253 | E1 | sample_change_real | invented company name "MintSolutions" only in the Original sample | hallucinated/consistent/consistent |
| chat-dailydialog-0054.L20.p107 | E2 | judge_inconsistent | "suggest snacks" clean in Original, WRONG in Combine | consistent/consistent/hallucinated |
| chat-dailydialog-0073.L36.p36 | E1 | sample_change_real | privacy claim only in the Original sample; Best/Combine vaguer | hallucinated/consistent/consistent |
| chat-dailydialog-0010.L52.p24 | E2 | judge_inconsistent | identical "or a bank account" bullet clean in Original, WRONG in Combine | consistent/consistent/hallucinated |
| chat-lmsys-0010.L36.p45 | E1 | sample_change_real | invented "EDESKTOP" only in the Original sample | hallucinated/consistent/hallucinated |
| chat-dailydialog-0063.L44.p118 | E1 | sample_change_real | first-person taste claims only in the Original sample (Raw with identical text judged consistent) | hallucinated/consistent/consistent |
| chat-lmsys-0059.L20.p350 | E2 | judge_inconsistent | identical sample-#29 bullet clean in Best, WRONG in Combine | consistent/consistent/hallucinated |
| chat-lmsys-0068.L44.p104 | E1 | judge_inconsistent | identical sample-#22 bullet clean in Best, WRONG in Combine | hallucinated/consistent/hallucinated |
| chat-dailydialog-0022.L60.p48 | E2 | judge_inconsistent | coffee remark WRONG once, unverifiable in three other bullets | consistent/consistent/hallucinated |
| chat-dailydialog-0072.L20.p84 | E2 | judge_inconsistent | identical sample-#1 text clean in Best, WRONG in Combine | consistent/consistent/hallucinated |
| chat-dailydialog-0031.L52.p300 | E1 | judge_inconsistent | same sample-#28 "fresh, original idea" bullet clean in Best, OFF-TOPIC in Combine | hallucinated/consistent/off_topic |
| chat-dailydialog-0049.L44.p215 | E1 | judge_inconsistent | identical "Internal Structure" text WRONG as Original b3, clean as Combine b2 | hallucinated/consistent/hallucinated |
| chat-lmsys-0018.L52.p350 | E2 | sample_change_real | Combine pools sample #5 with an inverted bound (also identical-text verdict flip) | consistent/consistent/hallucinated |
| chat-dailydialog-0057.L36.p46 | E2 | judge_inconsistent | "usual spot" questions unverifiable, declarative "usual bar" WRONG | consistent/consistent/hallucinated |
| chat-lmsys-0022.L52.p102 | E1 | span_match | Best of 32 consistent only because its wrong span was NOT counted (backticks) | hallucinated/consistent/hallucinated |
| chat-lmsys-0063.L20.p520 | E2 | judge_inconsistent | identical sample-#6 string clean in Best, WRONG in Combine | consistent/consistent/hallucinated |
| chat-lmsys-0035.L52.p502 | E1 | sample_change_real | Original scales by "number of Americans"; Best sample names area targets | hallucinated/consistent/hallucinated |
| chat-lmsys-0042.L36.p99 | E2 | span_match | Original consistent only because its "Laravel validation" span was NOT counted | consistent/consistent/hallucinated |
| chat-dailydialog-0053.L60.p187 | E1 | judge_inconsistent | invented item-4 heading WRONG in Original, stage-2 true in Best/Combine | hallucinated/consistent/consistent |
| chat-lmsys-0048.L36.p255 | E2 | judge_inconsistent | equally invented food details unverifiable in Original | consistent/hallucinated/hallucinated |
| chat-dailydialog-0058.L60.p59 | E1 | judge_inconsistent | "at each restaurant" WRONG in Original, "for each restaurant" unflagged in Combine | hallucinated/consistent/hallucinated |

### A16. Reading summary numbers

- n_records: 288
- reader_judge_disagree_any: 124
- reader_judge_disagree_no: 38
- A_frame_or_next_text_and_error_invisible: 32
- A_n: 60
- low_BC_coef0_or_short_or_script_or_wholelow: 72
- low_BC_coef0_or_short_or_script_or_wholelow_or_frame_or_echo: 87
- low_BC_n: 96
- low_BC_coef0_in_sample: 38
- focus_coef0_by_stratum: {'A_wrong_high': 0, 'B_wrong_low': 22, 'C_clean_low_in_halluc': 16, 'D_clean_high_in_consistent': 0, 'E_disagree': 1, 'F_wrong_unscored': 0, 'G_offtopic': 8}
- A_vs_B_reader_error_class: {'A_wrong_high': {'error': 45, 'no_error': 15}, 'B_wrong_low': {'no_error': 14, 'error': 45, 'vague': 1}}
- A_vs_B_error_with_frame_or_next_or_swap_codes: {'A_wrong_high': 37, 'B_wrong_low': 31}
- judge_agrees_by_setting_ABF: {'Original': {'yes': 32, 'no': 4, 'partly': 18}, 'Best of 32': {'yes': 31, 'no': 6, 'partly': 14}, 'Combine 32': {'yes': 19, 'partly': 13, 'no': 7}}
- C_reader_says_error: 7
- F_judge_too_strict: 11
- span_not_counted_mentions: 17
- cross_setting_inconsistency_mentions: 62
- stage2_glitch_mentions: 5
- judge_misreads_chinese_mentions: 8
- G_reader_says_junk: 7
- G_n: 24

## Part B: all-data tests (details in synth_tests.json)

Pair rate = P(clean bullet scores higher than a wrong bullet of the same readout), ties 1/2; 0.5 = no separation. Original and Best of 32 use position-adjusted percentiles; Combine 32 raw scores.

| test | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| solo, all wrong vs clean | 0.511 [0.496, 0.527] | 0.504 [0.489, 0.521] | 0.503 [0.486, 0.519] |
| solo, error in head (first third of scored text) | 0.527 [0.507, 0.548] | 0.528 [0.511, 0.547] | 0.533 [0.511, 0.554] |
| solo, error in tail of scored text | 0.496 [0.475, 0.517] | 0.478 [0.453, 0.501] | 0.474 [0.450, 0.499] |
| solo, wrong span <= 3 words | 0.502 [0.471, 0.532] | 0.485 [0.450, 0.518] | 0.488 [0.454, 0.523] |
| solo, wrong span > 10 words | 0.523 [0.497, 0.550] | 0.525 [0.496, 0.554] | 0.536 [0.509, 0.567] |
| solo, wrong covers >= 60% of bullet | 0.521 [0.495, 0.548] | 0.524 [0.499, 0.550] | 0.562 [0.533, 0.594] |
| solo, top readout-FVE tertile | 0.526 [0.502, 0.554] | 0.502 [0.477, 0.529] | 0.494 [0.468, 0.522] |
| solo, layer 20 | 0.513 [0.480, 0.549] | 0.503 [0.471, 0.537] | 0.503 [0.472, 0.536] |
| solo, layer 60 | 0.544 [0.515, 0.577] | 0.530 [0.496, 0.568] | 0.492 [0.454, 0.535] |
| solo, wrong span has a novel number | 0.493 [0.446, 0.541] | 0.524 [0.474, 0.575] | 0.450 [0.394, 0.498] |
| solo, wrong span has a novel capitalised name | 0.507 [0.469, 0.543] | 0.470 [0.433, 0.504] | 0.456 [0.422, 0.488] |
| solo, OFF-TOPIC vs clean | 0.547 [0.514, 0.583] | 0.529 [0.489, 0.566] | 0.552 [0.516, 0.588] |
| solo, after relabelling uncounted wrong spans | 0.509 [0.494, 0.524] | 0.503 [0.487, 0.520] | 0.503 [0.487, 0.520] |
| solo, twin-holding bullets only (baseline for the next two rows) | 0.400 [0.000, 1.000] | 0.533 [0.426, 0.656] | 0.482 [0.400, 0.567] |
| solo, twin-holding: replicated WRONG vs clean | 0.333 [0.000, 1.000] | 0.452 [0.326, 0.594] | 0.489 [0.385, 0.600] |
| solo, twin-holding: wrong vs replicated CLEAN | 0.333 [0.000, 1.000] | 0.568 [0.452, 0.697] | 0.473 [0.385, 0.570] |
| solo, wrong vs VERIFIED-true clean (all stage-2 claims true) | 0.510 [0.478, 0.541] | 0.493 [0.461, 0.524] | 0.527 [0.493, 0.563] |
| solo, wrong + extra disputed claim vs VERIFIED-true clean | 0.562 [0.368, 0.750] | 0.464 [0.303, 0.647] | 0.375 [0.130, 0.684] |
| P(clean bullet is VERIFIED true) | 0.200 [0.181, 0.217] | 0.199 [0.180, 0.218] | 0.179 [0.161, 0.194] |
| solo, excluding wrong bullets with any unscored wrong text | 0.516 [0.500, 0.532] | 0.507 [0.492, 0.524] | 0.508 [0.491, 0.525] |

| what FVE tracks (same-readout pair rate on solo) | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| longer bullet (scored+tail chars) scores higher | 0.561 [0.554, 0.568] | 0.600 [0.593, 0.607] | 0.553 [0.547, 0.560] |
| later position scores higher | 0.546 [0.538, 0.553] | 0.577 [0.570, 0.585] | n/a |
| higher next-text head overlap scores higher | 0.515 [0.507, 0.523] | 0.508 [0.500, 0.517] | 0.535 [0.526, 0.545] |
| first token = reply next token scores higher | 0.516 [0.496, 0.535] | 0.486 [0.464, 0.508] | 0.566 [0.544, 0.589] |
| no mismatched list-number opener scores higher | 0.595 [0.551, 0.638] | 0.525 [0.486, 0.565] | 0.542 [0.505, 0.578] |
| no-CJK bullet beats mostly-CJK (>=50% CJK) bullet | 0.596 [0.561, 0.631] | 0.614 [0.574, 0.651] | 0.637 [0.594, 0.683] |
| no-CJK bullet beats bullet with only a CJK lead word (<20% CJK) | 0.471 [0.452, 0.490] | 0.434 [0.416, 0.453] | 0.478 [0.462, 0.496] |
| higher previous-text head overlap scores higher | 0.512 [0.503, 0.522] | 0.507 [0.497, 0.517] | 0.518 [0.510, 0.527] |

| within-readout regression of solo FVE | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| coef is_w (wrong vs clean, solo units) | -0.003 [-0.007, 0.001] | -0.005 [-0.011, -0.001] | -0.002 [-0.005, 0.001] |
| coef is_o (off-topic vs clean) | -0.014 [-0.022, -0.007] | -0.019 [-0.029, -0.011] | -0.011 [-0.018, -0.005] |
| coef log_len (per SD) | 0.011 [0.009, 0.013] | 0.019 [0.017, 0.022] | 0.008 [0.007, 0.010] |
| coef wrong, error in head | -0.004 [-0.009, 0.001] | -0.009 [-0.015, -0.002] | -0.003 [-0.007, 0.001] |
| coef wrong, error in tail/unscored | 0.001 [-0.004, 0.006] | -0.001 [-0.008, 0.006] | 0.003 [-0.002, 0.006] |
| head minus tail | -0.004 [-0.010, 0.002] | -0.008 [-0.015, -0.001] | -0.006 [-0.011, -0.001] |
| within-readout R2 (all features / label only) | 0.038 / 0.0003 | 0.0754 / 0.0003 | 0.0421 / 0.0007 |
| within-readout SD of solo | 0.0706 | 0.0861 | 0.0597 |

| other | Original | Best of 32 | Combine 32 |
|---|---|---|---|
| P(coef 0 | wrong) | 0.143 [0.131, 0.155] | 0.194 [0.179, 0.209] | n/a |
| P(coef 0 | clean) | 0.142 [0.134, 0.150] | 0.197 [0.187, 0.207] | n/a |
| P(coef 0 | lowest-share bullet of readout) | 0.355 [0.337, 0.372] | 0.453 [0.435, 0.470] | n/a |
| P(wrong | lowest-share bullet, mixed readouts) | 0.436 [0.412, 0.461] | 0.436 [0.413, 0.460] | n/a |
| chance level for the line above | 0.443 [0.430, 0.455] | 0.454 [0.442, 0.465] | n/a |
| P(all wrong text past 32 tokens | wrong) | 0.001 [0.000, 0.002] | 0.000 [0.000, 0.001] | 0.001 [0.000, 0.002] |
| P(some wrong text past 32 tokens | wrong) | 0.032 [0.027, 0.037] | 0.030 [0.025, 0.036] | 0.042 [0.035, 0.049] |
| P(wrong span starts after first third of scored text) | 0.372 [0.345, 0.399] | 0.363 [0.338, 0.387] | 0.396 [0.371, 0.421] |
| P(wrong spans cover < 1/3 of bullet) | 0.390 [0.352, 0.427] | 0.384 [0.348, 0.419] | 0.424 [0.387, 0.464] |
| head Jaccard, wrong vs clean sibling | 0.150 [0.142, 0.158] | 0.149 [0.140, 0.160] | 0.158 [0.148, 0.169] |
| head Jaccard, clean vs clean sibling | 0.152 [0.146, 0.159] | 0.151 [0.145, 0.158] | 0.157 [0.151, 0.162] |
| head Jaccard, off-topic vs clean sibling | 0.154 [0.140, 0.169] | 0.142 [0.131, 0.154] | 0.142 [0.131, 0.153] |
| wrong-span kind: novel_number | 0.131 [0.092, 0.171] | 0.134 [0.096, 0.175] | 0.131 [0.091, 0.173] |
| wrong-span kind: novel_capitalised_name | 0.242 [0.204, 0.279] | 0.239 [0.201, 0.277] | 0.248 [0.209, 0.287] |
| wrong-span kind: first_person | 0.105 [0.079, 0.135] | 0.107 [0.081, 0.135] | 0.098 [0.072, 0.128] |
| wrong-span kind: short_other(<=4 words) | 0.186 [0.161, 0.211] | 0.175 [0.153, 0.197] | 0.194 [0.172, 0.217] |
| wrong-span kind: long_other | 0.336 [0.302, 0.375] | 0.346 [0.311, 0.384] | 0.329 [0.297, 0.363] |
| first-person wrong span, dailydialog | 0.314 [0.257, 0.373] | 0.319 [0.260, 0.382] | 0.302 [0.243, 0.364] |
| first-person wrong span, lmsys | 0.035 [0.019, 0.055] | 0.033 [0.018, 0.051] | 0.034 [0.017, 0.055] |
| P(bullet scored part has a novel number or capitalised name) | 0.336 [0.305, 0.366] | 0.338 [0.306, 0.369] | 0.356 [0.325, 0.388] |
| P(wrong | bullet has novel specific) | 0.379 [0.343, 0.415] | 0.374 [0.340, 0.410] | 0.372 [0.335, 0.411] |
| P(wrong | no novel specific) | 0.209 [0.188, 0.234] | 0.200 [0.180, 0.224] | 0.211 [0.189, 0.237] |
| pair rate solo: novel-specific bullet beats one without (all labels) | 0.513 [0.498, 0.529] | 0.542 [0.526, 0.559] | 0.527 [0.511, 0.542] |
| same, clean bullets only | 0.508 [0.486, 0.529] | 0.544 [0.521, 0.565] | 0.519 [0.499, 0.539] |
| same, wrong bullets only | 0.498 [0.467, 0.527] | 0.528 [0.498, 0.558] | 0.516 [0.479, 0.548] |
| P(novel specific) minus Original | n/a | 0.002 [-0.005, 0.009] | 0.021 [0.013, 0.029] |

| judge reliability | value |
|---|---|
| Original vs Raw, texts differ only in whitespace (n=119 cells, separate judge calls): P(same hallucinated flag) | 0.866 [0.800, 0.924] |
| same cells, bullet level: P(same wrong status given wrong in either) | 0.656 [0.504, 0.773] |
| identical bullet text in two different readouts of a cell (n=5552 pairs): label agreement | 0.782 [0.764, 0.799] |
| same, P(labels differ given one is WRONG) | 0.519 [0.487, 0.552] |
| Original: clean bullets holding an uncounted (unverified) wrong span | 92 of 14372; consistent readouts that would flip: 21 |
| Best of 32: clean bullets holding an uncounted (unverified) wrong span | 104 of 14632; consistent readouts that would flip: 23 |
| Combine 32: clean bullets holding an uncounted (unverified) wrong span | 115 of 14267; consistent readouts that would flip: 25 |

| settings | Best of 32 | Combine 32 |
|---|---|---|
| P(fix): Original hallucinated -> consistent | 0.249 [0.221, 0.279] | 0.249 [0.220, 0.279] |
| P(break): Original consistent -> hallucinated | 0.236 [0.213, 0.265] | 0.263 [0.236, 0.296] |
| Best of 32, low gain (<0.031): P(fix) / P(break) | 0.265 [0.226, 0.305] / 0.258 [0.221, 0.296] | |
| Best of 32, mid gain [0.031,0.063): P(fix) / P(break) | 0.247 [0.208, 0.288] / 0.243 [0.207, 0.285] | |
| Best of 32, high gain [0.063,9.000): P(fix) / P(break) | 0.262 [0.222, 0.305] / 0.229 [0.196, 0.267] | |
| Combine 32 P(wrong), pick 1 | | 0.271 [0.245, 0.301] |
| Combine 32 P(wrong), pick 2 | | 0.267 [0.241, 0.296] |
| Combine 32 P(wrong), pick 3 | | 0.263 [0.238, 0.289] |
| Combine 32 P(wrong), pick 4 | | 0.272 [0.245, 0.300] |
