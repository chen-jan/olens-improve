"""Manual reading of the 36 role_bound_association cases in read_sample.json -> read_records.json.

The judgments below (verdicts, reader codes, notes) were written by hand after reading every case
(story, gold binding, judge answers + evidence, all four bullets, scores). This script only attaches
them to the case data, checks that every quoted fragment is verbatim bullet text, and tallies.
No judge/API calls, no GPU. Exploratory: all items were inspected before.

Reader code per bullet (all four bullets of every readout):
  C = carries the binding: assigns the right participant(s) to the action in the right direction
      (paraphrased verbs and role words allowed; one participant may be implicit/absent)
  P = partial: names parts without connecting them in a direction, hedged, or relation too vague
  R = states the reversed direction
  W = wrong relation or wrong entities (different action, different role pair)
  N = no binding content (setting, template, instruction echo only)
"""
import json, re, collections, os

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, 'read_sample.json')))
CASES = {c['case_id']: c for c in S['cases']}


def q(cid, idx, frag):
    """Verbatim fragment of bullet idx of case cid, checked."""
    t = CASES[cid]['bullets'][idx]['scored_text']
    if frag not in t:  # typed apostrophe may differ; keep whichever form is verbatim in the bullet
        for a, b in (("’", "'"), ("'", "’")):
            if frag.replace(a, b) in t:
                frag = frag.replace(a, b)
                break
    assert frag in t, (cid, idx, frag, t)
    return f'[{idx}] "{frag}"'


R = {}  # case number -> annotation


def add(n, codes, verdict, substance, scope, says, frame, driver, sib, sib_fn=()):
    dedup = lambda s: re.sub(r'\[(\d)\] \[\1\] ', r'[\1] ', s)  # "[2] " typed before q()'s own "[2] "
    says, frame, driver, sib = map(dedup, (says, frame, driver, sib))
    R[n] = dict(codes=codes, verdict=verdict, substance=substance, binding_scope=scope,
                what_bullet_says=says, frame_vs_filler=frame, fve_driver=driver,
                top_sibling_note=sib, sibling_false_negatives=list(sib_fn))


c = lambda n: f'rba-read-{n:02d}'

# ---------------- A: hit bullets with high share ----------------
add(0, 'PCPC', 'correct_weak', 'patient_action_only', 'partial_needs_siblings',
    f"Husband (丈夫) tracked with a hidden ledger, {q(c(0),1,'suspecting infidelity or unusual behavior')}; the tracker is only {q(c(0),1,'The narrator')}, never 'wife'. Direction recoverable, agent role comes from siblings.",
    "Frame = story paraphrase of covert tracking (ledger, movements); filler: patient right (Chinese role word), action right, agent unnamed.",
    "Length/story-surveillance paraphrase. The two long bullets take 0.81 of the share; [3] (wife + husband, no suspect verb) nearly ties (0.373 vs 0.437). " +
    f"[0] {q(c(0),0,'2: A wife tracking her husband')}... is the cleanest A+P statement but has the '2:' opener and 70 chars: share 0.107.",
    f"{q(c(0),3,'a classic case of a wife doing silent surveillance')} (miss_pass_other, relaxed hit), share 0.373.", [3])
add(1, 'PCPP', 'correct_weak', 'agent_action_only', 'partial_needs_siblings',
    f"{q(c(1),1,'Marcus sets tray on table, and Marcus apologizes')}: story name copied, verb paraphrases 'said he was sorry'; no patient, no role word. The judge got 'customer' from [0] and inferred 'waiter' from tray/apron.",
    "Story-event paraphrase (soup tray, apron, table) is the frame; the binding filler is just name + verb.",
    f"Closest story paraphrase wins (share 0.601). [3] {q(c(1),3,'Marcus carefully carries the corrected soup tray back to table')} (no apology) is second, 0.226.",
    "[3] story-paraphrase without the action, share 0.226.")
add(2, 'CRCR', 'correct_weak', 'full_binding_muddled', 'self_contained',
    f"{q(c(2),0,'Dale, a naive and untrained taxpayer, knowingly submits false expense reports to his dishonest tax preparer,')}: Dale deceives the preparer (right direction), but the matched action term 'dishonest' describes the preparer, so the A+V match is accidental; 'tax preparer' is not an accountant alias.",
    "Right frame (tax filing fraud) and right agent name; the role words are muddled ('naive', 'dishonest' on the wrong people).",
    f"Highest solo (0.30), longest English with story nouns. The most explicit gold binding, {q(c(2),2,'deliberately understating his expenses by $500 to defraud him')}, has the LOWEST share (0.045, solo 0.0385) and is labelled miss ('defraud' is not an alias). Two reversed bullets in this passing readout ({q(c(2),1,'who knowingly deducted expenses')}; {q(c(2),3,'An opportunistic accountant, working with his naive client')}) out-share it: 0.224 and 0.274.",
    "[3] reversed (accountant as fraudster), share 0.274, label_relaxed = hit because it names both roles.", [2])
add(3, 'PPCP', 'ambiguous', 'roles_no_direction', 'partial_needs_siblings',
    f"{q(c(3),1,'a bystander (Caleb) and a professional (paramedic), highlighting gratitude and procedure')}: both roles, gratitude, no direction. It is a hit only through an evidence-overlap tie.",
    "Frame-level summary (emergency response + gratitude); direction absent.",
    f"Top share 0.472 with summary-meta wording ({q(c(3),1,'The text is concise and')}). The bullet that carries the direction, {q(c(3),2,'the paramedic acknowledged the citizen')}, has the lowest share (0.115).",
    "[3] Chinese 'bystander contribution and thanks', direction ambiguous, share 0.249.", [])
add(4, 'PCCP', 'correct_weak', 'patient_action_only', 'self_contained',
    f"{q(c(4),1,'sending the client a smaller amount, constituting embezzlement. He falsely claimed to send the full refund')}: client explicit, agent 'He', deception by paraphrase ('falsely claimed'). Direction right.",
    "Filler here is story-event detail (refund split, false summary), which is what the binding rests on.",
    "Share 0.713, solo 0.434 (position percentile 0.97): the most story-faithful event paraphrase. FVE and binding coincide here, through event content rather than role words; " +
    f"[2] {q(c(4),2,'accusing an accountant of skimming tax refunds')} names the agent explicitly and gets 0.204.",
    "[2] accountant skims refunds, a carrier (miss_pass_other), share 0.204.", [2])
add(5, 'CCCC', 'correct', 'full_binding', 'self_contained',
    f"{q(c(5),2,'警方 officer John captures a robber after a brief chase.')} Full binding, right direction.",
    "All four bullets state the same full binding; they differ only in form.",
    f"Instruction-echo tails take the share: [2] {q(c(5),2,'(Or, if you prefer a single-sentence summary:')} 0.434 and [3] {q(c(5),3,'(This is the most concise and direct summary of the events.)')} 0.394, against the two plain full-binding sentences [0] {q(c(5),0,'**A police officer apprehended a wallet thief in a swift chase.**')} 0.045 (coef 0) and [1] 0.127. Read site is the '.' of 'sentence.'.",
    "[3] the Chinese full binding ('一名警察在短暂追逃后成功抓获入室盗窃犯', a policeman catches a burglar after a short chase), labelled miss because 追逃/抓获/盗窃犯 are not in the CJK tables; share 0.394.", [3])
add(6, 'WNCP', 'correct_weak', 'roles_action_implicit', 'self_contained',
    f"{q(c(6),2,'(an old father) routine and emotional response to his daughter')}'s delayed return: both roles, right direction; worry only implied ('emotional response').",
    "Roles right; action paraphrased vaguely.",
    f"Read site 'ize' (Summarize). The meta tail {q(c(6),2,'Here is a summary of the story:')} helps; the second-highest bullet carries no binding: {q(c(6),1,'Summarize the story in one sentence.')} (share 0.316). [3] (father waits for daughter) gets 0.064, coef 0.",
    "[1] pure instruction echo with a wrong name ('老 Jim'), share 0.316.")
add(7, 'CCCC', 'correct', 'full_binding', 'self_contained',
    f"{q(c(7),1,'Nurse Priya masks her distress when a dying patient asks')}... {q(c(7),1,'choosing to lie to spare him further pain')}: full binding with the story's name.",
    "All four bullets carry nurse-deceives-dying-patient; only [1] has the story name.",
    "Long dying-patient paraphrases [1] 0.435 and [2] 0.364 lead. The story name may add a little ([1] Priya vs [2] Elena), but [0], a carrier with an invented name, gets 0.144 with coef 0.",
    f"[2] {q(c(7),2,'hides the truth from the dying patient to spare him pain')} (miss_pass_other), share 0.364.", [0, 2, 3])
add(8, 'CWWC', 'correct_weak', 'agent_action_only', 'self_contained',
    f"{q(c(8),0,'the doctor reached out to provide comfort and support,')}: agent and action; patient cut off.",
    "Frame = the answer preamble; the filler 'doctor ... comfort' is right.",
    f"Read site 'assistant'. Answer-preamble echo {q(c(8),0,'Here is the rewritten paragraph, condensed into a single sentence as requested:')} gives the top share (0.333), but shares are flat (0.17-0.33). The other carrier, [3] {q(c(8),3,'the doctor offered a small, sympathetic smile to console her')} ('console' is not an alias), gets 0.248; nurse-comforts-patient bullets (wrong agent role) get 0.174/0.245.",
    "[3] doctor consoles, a carrier labelled miss, share 0.248.", [3])
add(9, 'CPWC', 'correct_weak', 'full_binding_paraphrase', 'self_contained',
    f"{q(c(9),0,'holding her accountable for his academic decline. This is a classic, tense meeting between a teacher and a parent')}: blame by paraphrase; the agent is elided under the CJK opener 指出.",
    "Roles named only inside a meta sentence ('This is a classic ... meeting between').",
    f"Shares flat (0.21-0.34). The other carrier [3] {q(c(9),3,'指责 a neglected student’s academic failures to her absent mother')} gets 0.233.",
    "[3] blame-the-mother carrier, share 0.233.", [3])
add(10, 'CCCC', 'correct_weak', 'patient_action_only', 'self_contained',
    f"{q(c(10),2,'John successfully silenced the heckler through his compelling storytelling, leaving the attacker embarrassed')}: right direction, but the agent is a storyteller named John, not a comedian.",
    "All four bullets say a storyteller silenced a heckler/critic; the role word for the agent is wrong in every one.",
    f"All four carry the same binding; shares 0.13-0.37, lowest for [3], which ends in {q(c(10),3,'**Option 2:')}.",
    f"[0] {q(c(10),0,'silenced his heckler')}, share 0.266 (miss).", [0, 1, 3])
add(11, 'CCCW', 'correct', 'full_binding', 'self_contained',
    f"{q(c(11),1,'A soccer referee warns a sluggish striker named Dylan of a pending red card')}: full binding; the verb is copied from the story ('he warned Omar').",
    "Full binding with invented filler (names, card details).",
    f"Shares flat: [0] 0.309, [1] 0.300, [2] 0.197, [3] 0.194. [2] {q(c(11),2,'issues player David a final warning')} is a full binding missed by the rule (bare 'player' needs a determiner). [3] {q(c(11),3,'Teacher Davidson warned soccer player Dan')} (wrong agent role) gets almost the same share as [2].",
    "[0] full binding, share 0.309.", [2])

# ---------------- B: hit bullets with low share ----------------
add(12, 'CCCC', 'correct', 'full_binding', 'self_contained',
    f"{q(c(12),3,'Young Private Stanley Jones briefly salutes his new superior, General Omonaltz')}: full binding.",
    "All four bullets: low-ranking soldier salutes a General. The rule makes [0],[3] hits and [1],[2] misses ('Army private', 'Marine' and bare 'General' are not matched).",
    f"Lowest share (0.078): it carries a tail, {q(c(12),3,'Here are three rephrased')}. Top: [2] {q(c(12),2,'A fresh Army private stops to salute a visiting General')}, the longest, 0.454 (miss).",
    "[2] full binding labelled miss, share 0.454.", [1, 2])
add(13, 'PCCC', 'correct_weak', 'victim_frame_only', 'self_contained',
    f"{q(c(13),1,'receiving red audit reports from her accountant, her trust in them, and the eventual discovery of fraud')}: the client is the victim, so the accountant is the implied deceiver; the client has a wrong name (Elara).",
    "Frame = routine of trusting the accountant's reports; the deception is implicit.",
    f"Low share is redundancy, not content: coef 0, drop 0. Near-duplicate [2] {q(c(13),2,'from a trusted accountant, unaware of the gradual fraud')} takes 0.519.",
    "[2] near-duplicate hit_anchor, share 0.519.")
add(14, 'PCCC', 'correct_weak', 'garbled', 'partial_needs_siblings',
    f"{q(c(14),3,'landlord’s attempt to collect rent through avoidance')} ... {q(c(14),3,'how Elara avoided')}: avoid + landlord, tenant unnamed, sentence garbled.",
    "Frame = avoidance + rent conflict; filler muddled.",
    f"Top [1] {q(c(14),1,'逃避（avoiding) the landlord all day through avoidance')} 0.684. [2] {q(c(14),2,'actions to avoid the landlord')} (carrier, miss) gets 0.155. [0] {q(c(14),0,'2: The Cat and Mouse Game (Eva avoiding rent)')} gets 0.027.",
    "[1] hit, share 0.684.", [2])
add(15, 'PWCP', 'ambiguous', 'garbled_spurious_strict', 'partial_needs_siblings',
    f"{q(c(15),0,'3-term mayor and senior journalist mayor interviewed a colleague')}: hit_strict, but the journalist is a co-subject and the patient is 'a colleague'; the strict match is spurious.",
    "Story details copied ('3-term', 'district office'), but the binding is wrong.",
    f"The clearest carrier, [2] {q(c(15),2,'councilwoman used a recent meeting to interview a journalist')} ('councilwoman' is not an alias, so miss), has the TOP share (0.392). Here FVE agrees with the reader and the rule label disagrees.",
    "[2] politician-interviews-journalist, share 0.392 (miss).", [2])
add(16, 'CCCC', 'correct', 'full_binding', 'self_contained',
    f"{q(c(16),3,'General Sherman, the highest-ranking officer present, pauses before a severely wounded Marine')} ... to offer a salute: full binding (hit_anchor only, because bare 'General' and 'Marine' are not matched).",
    "All four bullets: general salutes or honours a wounded soldier.",
    f"Low share (0.105) is redundancy: coef 0, drop 0. Top [1] {q(c(16),1,'Highest-ranked Major General Morrison pauses in the hospital to salute a lowly-ranked sergeant')} 0.515 (miss_pass_other).",
    "[1] full binding labelled miss, share 0.515.", [0, 1, 2])
add(17, 'CCCC', 'correct', 'full_binding', 'self_contained',
    f"{q(c(17),0,'A nurse named Patricia lied to a dying patient, Pat')}: full binding.",
    "All four bullets: nurse conceals the prognosis from or lies to the patient.",
    f"Shortest, redundant: share 0.083, coef 0. Top [3] {q(c(17),3,'telling him the blood work was normal')} (0.378) is the closest to the story's actual lie. [2] {q(c(17),2,'护士 Pat lies to patient Terry')} is missed (bare 'patient').",
    "[3] concealment carrier, share 0.378 (miss).", [1, 2, 3])
add(18, 'CCCW', 'correct', 'full_binding', 'self_contained',
    f"{q(c(18),0,'12-year-old girl player stops the game to warn the referee about loose electrical wiring.')} Full binding.",
    "Story frame (safety hazard on the pitch) with invented filler (wiring vs sprinkler cap).",
    f"Top share goes to a bullet with the wrong relation: [3] {q(c(18),3,"the player's gratitude toward the referee for stopping the game")}, 0.492, the longest. [1] {q(c(18),1,'alerts the referee')} (carrier, missed) gets 0.075, coef 0.",
    "[3] gratitude rather than a warning, share 0.492.", [1, 2])
add(19, 'CCCC', 'correct', 'full_binding', 'self_contained',
    f"{q(c(19),0,'The child ran past the kitchen to hug Granny.')} Full binding ('Granny' is not an alias).",
    "All four bullets: child rushes to grandma for a hug.",
    f"Lowest share (0.111), with a '2:' opener. Top [2] {q(c(19),2,'冲到奶奶那里 seeking a hug')} 0.406 (miss_pass_other).",
    "[2] carrier labelled miss, share 0.406.", [2, 3])
add(20, 'CCCC', 'correct_weak', 'role_word_wrong', 'self_contained',
    f"{q(c(20),2,'2: Nurse Priya eases the patient')}'s anxiety by offering comfort: the name is copied right, the role word is wrong (gold: Priya, the doctor).",
    "All four bullets are 'Nurse Priya eases ... anxiety'; the story name carries the judge to the right option.",
    f"Lowest share (0.116): '2:' opener and only 72 chars. [0] {q(c(20),0,'护士 Priya eases the narrator’s anxiety')} is the same binding (miss: no 'patient'/'comfort' word) and has the top share, 0.334.",
    "[0] same binding labelled miss, share 0.334.", [0])
add(21, 'CCPP', 'correct_weak', 'role_word_wrong', 'self_contained',
    f"{q(c(21),1,'23-year-old Clara’s assumption about her uncle’s competence')}: the name is copied right; the patient role is wrong (uncle for butler); underestimate is paraphrased.",
    "Every bullet: a young woman misjudges a male relative's management. No bullet says butler.",
    f"The correct story name did NOT win: [0] {q(c(21),0,'(Elara) inherits the estate and makes a fatal assumption about how her uncle managed it')} (wrong name, same content) has the top share, 0.389, vs 0.200.",
    "[0] same content with the wrong name, share 0.389 (miss).", [0])
add(22, 'CPCP', 'ambiguous', 'hedged', 'self_contained',
    f"{q(c(22),3,'3 kept his distance from a thief, or a detective keeping track of a suspect by walking at the same distance?')}: the binding is offered as an alternative inside a question.",
    "Hedged; question form.",
    f"Lowest share (0.157). Top [0] {q(c(22),0,'kept a careful distance from a suspect all the way to his apartment')} (0.325, miss) is the closest story paraphrase.",
    "[0] carrier labelled miss, share 0.325.", [0])
add(23, 'NCCP', 'correct', 'full_binding', 'self_contained',
    f"{q(c(23),1,'Mark suspects his wife of being unfaithful and resolves to investigate her every move')}: full binding (the husband is implied by 'his wife').",
    "Full binding with an invented frame (whiskey).",
    f"Read site 'assistant'. The two answer-preamble bullets take 0.67 of the share: [0] {q(c(23),0,'assistantHere is a one-sentence summary of the passage:')} (no binding: {q(c(23),0,'Distracted by guilt over his wife’s prolonged absence,')}) 0.360 and [3] {q(c(23),3,'Based on the prompt, here is a one-sentence summary of the paragraph:')} 0.311. The focus gets 0.153.",
    "[0] answer-preamble echo with no binding, share 0.360.")

# ---------------- C1: wrong_specific with high share ----------------
add(24, 'WWWW', 'correct', 'wrong_action_stated', 'self_contained',
    f"{q(c(24),0,'the mother secretly monitors and protects her despite the daughter')}'s complete lack of suspicion: 'protects' is the judge's wrong action. The entities are wrong too (mother/daughter for manager/intern).",
    "Frame right, filler wrong: the story's structure (a power figure secretly watches an unsuspecting subordinate) is kept, with the wrong role pair and a wrong verb.",
    f"Top share 0.446, solo 0.287. All four bullets are mother-watches-daughter; the one closest to 'distrusted', [3] {q(c(24),3,'a suspicious mother watches her from afar')}, gets 0.167 with coef 0.",
    "[2] paranoid mother monitors daughter, share 0.211.")
add(25, 'WWWW', 'mixed', 'subject_reversal_wrong_entity', 'self_contained',
    f"{q(c(25),2,'一位 teacher dismisses a complaining student and continues her lesson')}: the teacher is the subject of 'dismisses'. The complaint goes to the teacher, as in the story, but the complainer is a student, not the parent. All four bullets get the same wrong_reversed_partial label.",
    "Frame right (a complaint to the teacher), filler wrong (student for parent), with the teacher as grammatical agent.",
    f"Share 0.705 against 0.046-0.140 for near-identical siblings. Driver: the parenthetical {q(c(25),2,'(This is concise and captures the core event.)')} at the '.' read site; [0] starts with '- ' and gets 0.046.",
    f"[3] {q(c(25),3,'A teacher named Ms. Bertolli accepts a student’s complaint')}, share 0.140.")
add(26, 'NNNN', 'no_wrong_value', 'subject_only', 'self_contained',
    f"{q(c(26),2,'/priest Thomas, who served at the altar, was carrying a heavy load.')} The right person and role (copied name, priest inferred from altar and vestments), but no action toward anyone. The judge's 'reversed' Q1 reflects grammatical subjecthood; the bullet states no reversed binding.",
    "Pure entity filler (Thomas, priest, altar) with no relation.",
    "Top share 0.406. All four bullets describe minister/pastor/preacher Thomas; [3] (trays of food) gets 0.085 with coef 0. Story copying, not binding.",
    "[1] 牧师 Thomas exhausted after communion, share 0.260.")
add(27, 'RWCR', 'correct', 'reversed_stated', 'self_contained',
    f"{q(c(27),3,'**Summary: A Teacher Rebukes a Student for a Prank**')}: reversed binding stated.",
    "Instruction-echo frame wrapping a reversed binding.",
    f"Share 0.542 from solo 0.094, at the 'ize' read site: {q(c(27),3,'interaction and its outcome in one sentence, based on the text provided:')}. [1] {q(c(27),1,'in a few sentences. Here is a summary of')} (no binding) takes 0.368. The ONLY right-direction bullet, [2] {q(c(27),2,'主角（Jesse）因老师的不当批评而进行了抗议')} (the student protests the teacher's improper criticism), gets 0.068 with coef 0.",
    "[1] instruction echo about a boss's criticism, share 0.368.")
add(28, 'NNPP', 'no_wrong_value', 'subject_only', 'self_contained',
    f"{q(c(28),0,'著名 actor Dario leaving a pub after a photoshoot.')} Right name and role, no action toward anyone. 'after a photoshoot', if anything, fits gold (he is the one photographed). The judge's reversed Q1 = subjecthood.",
    "Entity filler right (copied name, celebrity) plus meta frame; no relation.",
    f"Top share 0.428 and top solo 0.405, likely from the right name and the meta frame {q(c(28),0,'The text is a short news-style report about a celebrity sighting,')}. [3] {q(c(28),3,'2: Famous actor James has just left the cinema.')} gets 0.073.",
    "[2] star spotting fans, share 0.254.")
add(29, 'RWWW', 'correct', 'reversed_stated', 'self_contained',
    f"{q(c(29),0,'After canceling a promised trip, a disappointed mother serves her son dinner, and he defends his absence')}: the mother holds the negative emotion (reversed).",
    "Story events copied (cancelled promised trip, dinner, retreating), emotion holder reversed.",
    "Top share 0.465: the most story-faithful event paraphrase. Every sibling also makes the mother the emotion holder, with a daughter as the other party.",
    "[1] mother confronts disappointed daughter, share 0.246.")

# ---------------- C2: miss that out-shares every hit ----------------
add(30, 'CNCP', 'false_negative', 'carries_binding_paraphrase', 'self_contained',
    f"{q(c(30),2,'主人 (owner) and the repairman’s interaction.')} ... {q(c(30),2,'she extracts a disproportionate share of')}: the owner overcharges the repairman, right direction ('She had just fixed a pipe' is garbled). 主人, 'repairman' and 'extracts a disproportionate share' are not aliases.",
    "Paraphrased roles and verb; direction right.",
    f"Readout FVE only 0.098; shares 0.12-0.37 with no clear form driver. The judge's anchor is [0] {q(c(30),0,'she demanded a larger payment')} (hit_anchor, 0.218).",
    "[3] garbled Chinese (the hostess haggles over her labour), share 0.294.")
add(31, 'CCCC', 'false_negative', 'carries_binding_paraphrase', 'self_contained',
    f"{q(c(31),1,'赞美 her hair and outfit while the customer tried to make small talk. During the cut, Stella continued')}: Stella (the judge's 'hairdresser/stylist') praises the customer, right direction. A miss only because evidence-best went to [2].",
    "All four bullets: hairdresser compliments client. The hair/outfit filler matches the story (wave, green coat).",
    "Shares flat 0.20-0.36; the hit [2] has coef 1.5, redundant with [1].",
    "[2] hit_evidence, share 0.224.", [0, 3])
add(32, 'CCCC', 'false_negative', 'carries_binding_paraphrase', 'self_contained',
    f"{q(c(32),2,'(being mean to a server) and redemption through apology.')} The patron is mean, then apologizes ('apology' as a noun is not an alias).",
    "All four bullets carry customer-apologizes-to-server.",
    f"Top share 0.547 at the 'ize' site, with the meta tail {q(c(32),2,'Here’s a scene capturing the waitress')}. The strict hit [3] (0.132) has an ambiguous 'her internal regret'.",
    f"[0] {q(c(32),0,'1: Melissa’s rude behavior toward her server and her subsequent regret')} (evidence-best, miss), share 0.226.", [0, 1])
add(33, 'CCCC', 'false_negative', 'carries_binding_paraphrase', 'self_contained',
    f"{q(c(33),2,'Army private named Abe briefly halts his daily routine to salute a passing general')}: full binding; 'Army private' fails the determiner rule.",
    "All four bullets: a low-ranking soldier salutes a passing general.",
    f"Top share 0.517, the longest. [3] {q(c(33),3,'salutes General Wallace while taking out garbage')} is the closest to the story (trash detail) and gets 0.288 (hit). [1] (Chinese opener, hit_strict) gets 0.075.",
    "[3] hit_strict, share 0.288.", [0])
add(34, 'CCCC', 'false_negative_weak', 'coarse_roles', 'self_contained',
    f"{q(c(34),0,'parent’s quiet vigil and sacrifice based on the girl’s late return')}: the role words are coarse (parent/girl) and worry is implicit, but the direction is right.",
    "All four bullets: father waits for or worries about the late daughter.",
    f"Shares flat (0.19-0.31). The most explicit bullet, [3] {q(c(34),3,'一位父亲对女儿晚归的担忧')} (a father's worry about his daughter's late return), gets 0.252.",
    "[3] explicit hit_strict, share 0.252.", [1])
add(35, 'CWWW', 'false_negative', 'carries_binding_paraphrase', 'self_contained',
    f"{q(c(35),0,'律师 (cross-examiner) meticulously prepares to extract a specific narrative from a casual witness')}: lawyer to witness, cross-examination (not an alias of interrogate).",
    "The roles are right in [0] and [2]; only [0] has the right relation.",
    f"Shares flat (0.19-0.30). The rule's hit [2] {q(c(35),2,'meticulously prepares the witness')} states the wrong relation (coaching, not interrogating) and gets 0.256.",
    "[3] cross-examiner preparing his witness, share 0.257.")

# ---------------- assemble ----------------
recs = []
for n in range(36):
    cid = c(n)
    cs = CASES[cid]
    a = R[n]
    assert len(a['codes']) == len(cs['bullets']) == 4, cid
    fb = cs['bullets'][cs['focus_bullet']]
    top = max(cs['bullets'], key=lambda b: b['share'])
    recs.append(dict(
        case_id=cid, stratum=cs['stratum'], setting=cs['setting_display'], k=cs['k'], cell_id=cs['cell_id'],
        layer=cs['layer'], read_site_token=cs['read_site']['token'],
        gold=cs['target']['gold_label'], judge_class=cs['judge']['readout_class'],
        judge_choices=cs['judge']['choices'], judge_evidence=cs['judge']['evidence'],
        readout_fve=cs['readout_fve'], focus_bullet=cs['focus_bullet'], focus_text=fb['scored_text'],
        label=fb['label'], label_fine=fb['label_fine'], label_relaxed=fb['label_relaxed'],
        binding_named=fb['binding_named'],
        scores={k: fb.get(k) for k in ('share', 'solo', 'drop', 'coef', 'solo_pos_pct', 'share_rank_in_readout')},
        label_verdict=a['verdict'], substance=a['substance'], binding_scope=a['binding_scope'],
        what_bullet_says=a['what_bullet_says'], frame_vs_filler=a['frame_vs_filler'], fve_driver=a['fve_driver'],
        top_share_bullet=dict(index=top['index'], label_fine=top['label_fine'], reader_code=a['codes'][top['index']],
                              share=top['share'], solo=top['solo'], text=top['scored_text']),
        top_sibling_note=a['top_sibling_note'],
        reader_codes=[dict(index=b['index'], label_fine=b['label_fine'], reader_code=a['codes'][b['index']],
                           share=b['share'], solo=b['solo']) for b in cs['bullets']],
        sibling_false_negatives=a['sibling_false_negatives'],
    ))

# ---------------- tallies ----------------
summ = {'n': len(recs)}
vb = collections.defaultdict(collections.Counter)
for r in recs:
    vb[r['label']][r['label_verdict']] += 1
summ['label_verdict_by_label'] = {k: dict(v) for k, v in vb.items()}
sb = collections.defaultdict(collections.Counter)
for r in recs:
    sb[r['stratum']][r['substance']] += 1
summ['substance_by_stratum'] = {k: dict(v) for k, v in sb.items()}
sc = collections.defaultdict(collections.Counter)
for r in recs:
    sc[r['stratum']][r['label_verdict']] += 1
summ['verdict_by_stratum'] = {k: dict(v) for k, v in sc.items()}

# all bullets of passing readouts: rule label vs reader code
conf = collections.defaultdict(collections.Counter)
top_c = n_pass = 0
pairs = collections.Counter()
meta_re = re.compile(r"summar|one sentence|single sentence|single-sentence|concise|here is|here[’']s|rewrit|"
                     r"option \d|in a few sentences|based on the|the text |the narrative|the story|key elements|"
                     r"as requested|the line |the article|the scene|it highlights|it describes", re.I)
meta_pairs = collections.Counter()
for r in recs:
    cs = CASES[r['case_id']]
    codes = R[int(r['case_id'][-2:])]['codes']
    for b in cs['bullets']:
        meta_flag = bool(meta_re.search(b['scored_text']))
        b['_meta'] = meta_flag
    for i, bi in enumerate(cs['bullets']):
        for j, bj in enumerate(cs['bullets']):
            if i < j and bi['_meta'] != bj['_meta']:
                m, o = (bi, bj) if bi['_meta'] else (bj, bi)
                meta_pairs['n'] += 1
                meta_pairs['meta_wins'] += (m['share'] > o['share']) + 0.5 * (m['share'] == o['share'])
    if cs['judge']['pass']:
        n_pass += 1
        for b in cs['bullets']:
            conf[b['label_fine']][codes[b['index']]] += 1
        top = max(cs['bullets'], key=lambda b: b['share'])
        top_c += codes[top['index']] == 'C'
        for i, bi in enumerate(cs['bullets']):
            for j, bj in enumerate(cs['bullets']):
                if codes[i] == 'C' and codes[j] != 'C':
                    pairs['n'] += 1
                    pairs['c_wins_share'] += (bi['share'] > bj['share']) + 0.5 * (bi['share'] == bj['share'])
                    pairs['c_wins_solo'] += (bi['solo'] > bj['solo']) + 0.5 * (bi['solo'] == bj['solo'])
n_c = sum(v['C'] for v in conf.values())
n_all = sum(sum(v.values()) for v in conf.values())
hit_fines = [k for k in conf if k.startswith('hit')]
n_hit = sum(sum(conf[k].values()) for k in hit_fines)
n_hit_c = sum(conf[k]['C'] for k in hit_fines)
n_mpo = sum(conf['miss_pass_other'].values())
summ['passing_readouts_all_bullets'] = dict(
    n_readouts=n_pass, n_bullets=n_all,
    rule_label_vs_reader_code={k: dict(v) for k, v in conf.items()},
    reader_carriers=n_c,
    rule_hit_bullets=n_hit, rule_hit_that_reader_calls_C=n_hit_c,
    miss_pass_other_bullets=n_mpo, miss_pass_other_that_reader_calls_C=conf['miss_pass_other']['C'],
    top_share_bullet_is_reader_carrier=f"{top_c}/{n_pass}", base_rate_carrier=f"{n_c}/{n_all}",
    within_readout_P_carrier_beats_noncarrier_share=round(pairs['c_wins_share'] / pairs['n'], 3) if pairs['n'] else None,
    within_readout_P_carrier_beats_noncarrier_solo=round(pairs['c_wins_solo'] / pairs['n'], 3) if pairs['n'] else None,
    n_pairs=pairs['n'],
    caveat="Sample is stratified on share (A high-share hits, B low-share hits, C2 high-share misses), so these are descriptive only; Combine 32 uses raw shares and Original/Best of 32 are not position-adjusted here.")


def carrier_pairs(other=set('PRWN'), excl_focus=False, lenmatch=False, key='share'):
    n = w = 0
    rds = set()
    for r in recs:
        if r['judge_class'] != 'pass':
            continue
        cs = CASES[r['case_id']]
        codes = R[int(r['case_id'][-2:])]['codes']
        for bi in cs['bullets']:
            for bj in cs['bullets']:
                if codes[bi['index']] != 'C' or codes[bj['index']] not in other:
                    continue
                if excl_focus and r['focus_bullet'] in (bi['index'], bj['index']):
                    continue
                li, lj = len(bi['scored_text'].encode()), len(bj['scored_text'].encode())
                if lenmatch and min(li, lj) < 0.8 * max(li, lj):
                    continue
                n += 1
                w += (bi[key] > bj[key]) + 0.5 * (bi[key] == bj[key])
                rds.add(r['case_id'])
    return dict(P=round(w / n, 3) if n else None, n_pairs=n, n_readouts=len(rds))


summ['passing_readouts_all_bullets']['carrier_pair_rate_variants'] = {
    'all_noncarriers': carrier_pairs(),
    'excluding_focus_bullet': carrier_pairs(excl_focus=True),
    'length_matched_utf8_bytes_0.8': carrier_pairs(lenmatch=True),
    'excluding_focus_and_length_matched': carrier_pairs(excl_focus=True, lenmatch=True),
    'vs_wrong_or_reversed_only': carrier_pairs(other=set('WR')),
    'vs_wrong_or_reversed_only_excluding_focus': carrier_pairs(other=set('WR'), excl_focus=True),
    'vs_partial_or_none_only': carrier_pairs(other=set('PN')),
}
relc = collections.defaultdict(collections.Counter)
for r in recs:
    if r['judge_class'] != 'pass':
        continue
    codes = R[int(r['case_id'][-2:])]['codes']
    for b in CASES[r['case_id']]['bullets']:
        relc[b['label_relaxed']][codes[b['index']]] += 1
summ['passing_readouts_all_bullets']['label_relaxed_vs_reader_code'] = {k: dict(v) for k, v in relc.items()}
summ['meta_wording_all_36_readouts'] = dict(
    regex=meta_re.pattern, n_mixed_pairs=meta_pairs['n'],
    P_meta_bullet_beats_non_meta_share=round(meta_pairs['meta_wins'] / meta_pairs['n'], 3) if meta_pairs['n'] else None,
    caveat="Raw share, no length or position control; descriptive only.")
summ['verdict_legend'] = {
    'correct': 'rule label right; the bullet states the full binding (hit) or the wrong value (wrong_specific)',
    'correct_weak': 'rule label right; the binding is partly stated (one participant implicit, role word off, verb paraphrased) but the direction is recoverable',
    'ambiguous': 'labelled hit, but the bullet gives no direction, is hedged, or is garbled',
    'mixed': 'wrong_specific label defensible only as grammatical subjecthood plus wrong entities',
    'no_wrong_value': 'labelled wrong_specific, but the bullet states no relation at all (only names the person the judge put in the wrong slot)',
    'false_negative': 'labelled miss, but the bullet carries the binding as well as the labelled hit',
    'false_negative_weak': 'labelled miss; it carries the binding with coarse role words'}
summ['reader_code_legend'] = {'C': 'carries binding (direction right)', 'P': 'partial / no direction / hedged',
                              'R': 'reversed', 'W': 'wrong relation or entities', 'N': 'no binding content'}

out = dict(family='role_bound_association (Role-bound association)', source='read_sample.json (seed 0)',
           reader='manual reading, 2026-10-15 (annotations in read_records_build.py)', summary=summ, records=recs)
json.dump(out, open(os.path.join(HERE, 'read_records.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False, indent=1))
