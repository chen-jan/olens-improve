"""Reader 1 for ca: manual reading of read_sample.json cases 12-23 -> read_records_1.json.

Annotations below are hand-written after reading each case (item, stimulus, all four bullets, labels, scores).
Numbers (scores, labels, pool context) are copied from read_sample.json by this script, not by hand.

label_verdict (focal bullet):
  correct        the bullet states the labelled value on the contrast axis, in the right slot
  correct_weak   states it, but truncated / object of the state unclear / another slot also wrong
  borderline     states the label word, but the meaning tilts the other way (e.g. "hollow pride")
  wrong_slot     the label word is present but attached to the wrong role (wrong holder, a living person
                 named in passing, the protagonist instead of the other person); not the value in the gold slot
counts_as: correct (correct, correct_weak) | borderline | wrong (wrong_slot)
"""
import json
from pathlib import Path

HERE = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks/analysis/ca')
SAMPLE = HERE / 'read_sample.json'
OUT = HERE / 'read_records_1.json'

COUNTS = {'correct': 'correct', 'correct_weak': 'correct', 'borderline': 'borderline', 'wrong_slot': 'wrong'}

# reading_index -> annotation
ANN = {
    12: dict(
        label_verdict='correct_weak',
        substance='contrast_state_role_swapped',
        what_bullet_says=('Dana gets "a congratulatory note from her sister Leah" and "suppresses her own recognition to avoid '
                          'overshadowing the celebration. Although she is proud". The contrast state (pride) is stated, but as the '
                          'last scored words; the object of the pride is unclear, the relation is a sister, and Dana is the one '
                          'being recognised (achiever swapped).'),
        frame_vs_filler=('Frame: Dana stays quiet so as not to take attention from someone else\'s success (the story\'s "leaving '
                         'the news unmentioned at Friday\'s dinner"). Filler: state = pride (wrong value); relation wrong (sister); '
                         'roles swapped.'),
        prompt_echo=['Dana (stimulus name)', 'suppresses / avoid overshadowing ~ "leaving the news unmentioned"'],
        fve_driver=('The quiet-concealment frame, which all four bullets share; shares are flat (0.23-0.30). [2] has no state word '
                    '("keeps her own celebration quiet, privately acknowledging her friend\'s success") and scores solo 0.398, the '
                    'same as [1] "conceals her own pride" (0.399). The focal\'s lead (0.489) cannot be put on "proud", which is at '
                    'the tail of the window; it is the one bullet with the stimulus name plus the suppression verb. No bullet says '
                    'envy, so this readout has no within-readout filler test.'),
        sibling_notes=[
            '[0] wrongX_weak (LLM contrast on "silently celebrates her best friend\'s literary success", lex2 frame_only): borderline; '
            'it is the bullet closest to the story (friend\'s literary success, says nothing) and "celebrates" is its only pride cue.',
            '[1] wrongX correct ("conceals her own pride"), but the holder is "her close friend Estela" and Dina is the achiever.',
            '[2] other_axis correct ("Leila\'s promotion"); judge quoted it for distr_wrongX.',
        ],
    ),
    13: dict(
        label_verdict='wrong_slot',
        substance='frame_only_with_spurious_spouse',
        what_bullet_says=('"After an accidental second glance at her phone while driving, Nora ignores her husband\'s warnings and returns '
                          'to the garage, burdened by guilt over the infraction that caused the crash". The husband is alive and warns '
                          'her; nobody dies in the bullet; the guilt is "over the infraction".'),
        frame_vs_filler=('All frame: phone glance, driving, crash, guilt (state and content right). The relation slot (who died) is '
                         'empty. "husband" sits in another slot (the one giving warnings), so it is not a stated wrong victim; both '
                         'labellers took the word.'),
        prompt_echo=['"glance at her phone" ~ "a two-second glance at her phone"', 'Nora', 'crash / driving'],
        fve_driver=('Frame density and length (32 tokens, cut at the window, the most frame words). Siblings with the same frame and '
                    'no relation at all score almost as high: [2] "Nora returns to her car and is consumed by guilt" 0.525, [1] '
                    '"guilt from a recent traffic accident" 0.480. [3], which names "children" (a gold-axis word, also in a wrong '
                    'slot), is lowest (0.375). Combine 32: first greedy pick, no position adjustment.'),
        sibling_notes=[
            '[3] mixed is spurious: "a parent\'s inquiry about the children\'s whereabouts"; neither the parent nor the children are the victim.',
            '[1], [2] frame_only correct.',
            'No bullet names the dead child; the booster seat and school route are not picked up.',
        ],
    ),
    14: dict(
        label_verdict='correct_weak',
        substance='gold_X_relation_collapsed_into_self',
        what_bullet_says=('"面对 potential job loss on his forty-year anniversary, Dan repeatedly reviews his seniority status to ensure he '
                          'qualifies for a pension, while nervously tracking rumors of layoffs." The layoff (gold value) is stated, '
                          'but it is the protagonist\'s own job; the parent with 39 years at the plant and the son are merged into one man.'),
        frame_vs_filler=('X filler right (layoff / job loss); state right ("nervously"); relation filler wrong (self, not his parent).'),
        prompt_echo=['seniority ~ "thirty-nine years of seniority"', 'pension ~ "looked up the pension rules"',
                     'forty-year anniversary ~ thirty-nine years'],
        fve_driver=('Not the filler: all four bullets are gold on X. The focal has the most stimulus details and is the longest (32 '
                    'tokens): solo 0.447, share 0.548, loo 0.124. [0] "Man, concerned about his job security and impending age-based '
                    'layoffs, checks a" (15 tokens, cut mid-phrase) has the same value and scores solo 0.037 (2nd pct). [1] is the '
                    'only bullet with the right relation ("while his father\'s birthday approaches") and scores 0.280.'),
        sibling_notes=[
            '[1] LLM gold / lex2 frame_only: LLM right ("potential job loss").',
            '[3] LLM gold / lex2 none: LLM right ("fearing the loss of his job"); lex2 misses the paraphrase.',
            '[0] gold correct; lowest FVE of the readout.',
        ],
    ),
    15: dict(
        label_verdict='correct',
        substance='contrast_compound_clean',
        what_bullet_says=('"Mark quietly prepares for his wife\'s biopsy while she is distracted by reading. To ease her anxiety," '
                          'This is the contrast compound (medical test, wife) with the right relation and state.'),
        frame_vs_filler=('Frame right (Mark, wife, quiet protective preparation, anxiety); filler wrong (biopsy instead of layoff). '
                         'A clean "same frame, wrong filler" bullet.'),
        prompt_echo=['Mark', 'protective concealment ~ moved the mortgage folder "where she wouldn\'t keep seeing it"'],
        fve_driver=('The whole readout and the whole cell pool are on the medical reading (pool: gold 0, wrong value 95 of 128; judge '
                    'picked contrast). Within the readout the medical word does not separate: [3] with no medical word ("ease his '
                    'wife\'s anxiety before her appointment by quietly replacing the door lock") solo 0.349 vs [1] "his wife waited '
                    'for the biopsy results" 0.360. [2] has "test result"/"medical appointment" with the wrong holder (Jane) and '
                    'scores 0.283. The focal is the shortest (20 tokens) and top, at position 0 of Original. FVE puts the wrong '
                    'compound at the 98th percentile because the lens reads "husband shields anxious wife" and fills in a medical test.'),
        sibling_notes=[
            '[1], [2] wrongX correct.',
            '[3] wrongX_weak (LLM contrast on "wife\'s anxiety", lex2 frame_only): no medical/test word; "her appointment" is the only '
            'cue. Borderline; frame_only is the safer label.',
        ],
    ),
    16: dict(
        label_verdict='wrong_slot',
        substance='unaware_word_on_wrong_person_act_motive_absent',
        what_bullet_says=('"<think> Three years after Elena offered a sandwich to the resentful Julia, she remains oblivious to his '
                          'lingering resentment. Despite". The one who is oblivious is "she" (Elena), and what she is unaware of is '
                          '"his lingering resentment". Gold needs Elena to believe Marcus is unaware of her sabotage. Sabotage, the '
                          'demo and the stolen algorithm are absent.'),
        frame_vs_filler=('Frame: "three years after", interpersonal resentment, a friendly gesture. The unaware-word is present but on '
                         'the wrong person; the act and motive slots are empty.'),
        prompt_echo=['"Three years" ~ "Three years since"', '"offered a sandwich" ~ "waved her ahead" at the coffee line', 'Elena'],
        fve_driver=('Not the filler: [0] "Elena effortlessly enjoys her career success, oblivious to Marcus\'s lingering resentment, '
                    'three years after their" has the same oblivious + resentment content and scores 0.249 vs 0.459. [2] also opens '
                    'with "<think>" and scores 0.215, so the prefix alone does not explain it. The gesture echo is the most visible '
                    'difference; uncertain. q08 is outside the clean-item subset; lex2 calls 99 of 128 pool bullets gold.'),
        sibling_notes=[
            '[0] gold is also wrong slot (Elena is the oblivious one).',
            '[2], [3] none correct ("their professional dynamic remains unchanged", "peaceful professional relationship").',
        ],
    ),
    17: dict(
        label_verdict='borderline',
        substance='contrast_word_envy_meaning',
        what_bullet_says=('"一名 woman named Ruth reacts with hollow pride to her coworker Mary\'s promotion after receiving identical '
                          'news, but her friendship is instantly fractured by the realization that". "hollow pride" plus "friendship is '
                          'instantly fractured" reads as forced pride that hides resentment, which is close to the gold (envy).'),
        frame_vs_filler=('Frame right (a friend/coworker\'s promotion). Filler: the literal word is the contrast value; the meaning '
                         'tilts to gold.'),
        prompt_echo=['promotion ~ "Priya, director, effective the first"', '"hollow" ~ typed "so happy for you," deleted it, retyped it'],
        fve_driver=('The focal dominates (share 0.535, loo 0.127). [3] "Ruth felt a mix of pride and hollow envy as she quietly '
                    'celebrated the news" (same length, 30 tokens; mixed; the judge\'s gold quote) scores 0.212, so adding "envy" does '
                    'not raise FVE. In this cell\'s pool, wrong-value bullets beat gold bullets (P(gold > wrong) = 0.259).'),
        sibling_notes=[
            '[0] other_axis ("numbness and hurt") fine.',
            '[1] other_axis ("quiet devastation"): another value on the state axis, neither envy nor pride; fine.',
            '[3] mixed correct.',
        ],
    ),
    18: dict(
        label_verdict='correct',
        substance='gold_compound_plus_guilt',
        what_bullet_says=('"Haunted by an unresolved accident, Nora passes her familiar intersection daily, burdened by profound guilt '
                          'and grief over a stranger\'s death, even though she was". Stranger\'s death, grief and accident are all right; '
                          'it also adds guilt (the other state value).'),
        frame_vs_filler=('Content and relation right; state right (grief) plus the competitor (guilt).'),
        prompt_echo=['Nora', 'intersection', 'passes daily ~ the flowers at the signpost "new again"',
                     '"even though she was" ~ "no part of it had been hers to prevent"'],
        fve_driver=('Length and scene echo. All four bullets share guilt + accident + passing the site. The three long ones score '
                    '0.53-0.61. The short generic [0] ("a woman repeatedly passes the site of an accident involving a stranger", '
                    '20 tokens) scores 0.259 although it states "stranger". [3] "the accident that killed a neighbor" (neighbor, not '
                    'stranger) scores 0.529, nearly as high as the focal. In this cell\'s pool, P(gold > wrong) = 0.292.'),
        sibling_notes=[
            '[1] LLM gold ("accident she witnessed") / lex2 other_axis (guilt): acceptable as gold, since "witnessed" is the relation.',
            '[3] LLM gold on "killed a neighbor" is generous: a neighbor is not a stranger; better other_value or borderline.',
            '[0] gold correct.',
        ],
    ),
    19: dict(
        label_verdict='correct',
        substance='gold_value_degenerate_format',
        what_bullet_says=('"2: A father waiting for test results while caring for a dog and waiting". Test results (gold content) and '
                          'the father; whose test is not said; invented dog; repeated "waiting".'),
        frame_vs_filler=('Frame: anxious waiting + father. X filler right (test results). Read at the "ize" of "Summarize", 16 tokens '
                         'before the end.'),
        prompt_echo=['waiting (~ "five business days, and this was the fourth")'],
        fve_driver=('Format: a "2:" list-number opener, 15 tokens, repetition. The share winner is a wrong-content bullet, [2] "焦虑 '
                    '(waiting) and dedication of a father named Dan. He\'s waiting for a letter from a judge regarding his daughter '
                    'Molly-Rose." (legal; solo 0.247, share 0.623), which has the right state and relation and is long.'),
        sibling_notes=[
            '[1] other_axis ("waiting for news about his daughter\'s hospital discharge"): medical-adjacent but not test results; label fine.',
            '[2], [3] other_axis (legal news) correct.',
        ],
    ),
    20: dict(
        label_verdict='correct',
        substance='other_value_relation_with_scene_echo',
        what_bullet_says=('"Despite having moved on from a failed marriage, a woman preserves a single receipt as a sentimental relic of '
                          'her deceased father, finding solace in". The dead person is "her deceased father", another value on the '
                          'relation axis. lex2 also matched "marriage", which is not the deceased; the label is right anyway.'),
        frame_vs_filler=('Frame: grief, keeping a small paper memento. Relation filler wrong (father, not the stranger).'),
        prompt_echo=['"preserves a single receipt as a sentimental relic" ~ "The man\'s name, torn from the newspaper, stayed folded '
                     'small in her glovebox"'],
        fve_driver=('The keepsake echo. [0] "secretly preserving a photo of her late husband" (keepsake + husband) 0.174; [3] "comfort '
                    'her deceased husband" 0.208; [2] "attending the funeral of an unknown neighbor", the bullet nearest to gold '
                    '(a stranger-like person), is lowest at 0.098. At layer 36 the whole pool misses gold (gold 0, wrong value 63 of '
                    '123); joint FVE only 0.291.'),
        sibling_notes=[
            '[2] labelled other_axis / frame_only; arguably the closest to gold ("an unknown neighbor"); neither labeller credits it.',
            '[0], [3] wrongX correct (late / deceased husband).',
        ],
    ),
    21: dict(
        label_verdict='correct',
        substance='gold_value_wrong_name_garbled',
        what_bullet_says=('"完成 her late husband\'s task, Lena returns home carrying guilt and resentment, leaving a note about her '
                          'ownership of the keys after returning". Dead husband and guilt (both right); no accident; wrong name; '
                          'garbled ending.'),
        frame_vs_filler=('X filler right (late husband) and state right (guilt); content (accident) missing.'),
        prompt_echo=['"task" ~ "her errand" (weaker than the sibling\'s "errand")', 'keys'],
        fve_driver=('Not the filler. Its near-twin [0] "Nora completed her late husband\'s errand despite being late, keeping the '
                    'apartment\'s key and accepting blame for" has the same filler and frame: solo 0.367 / share 0.625 vs 0.033 / '
                    '0.036 for the focal. Visible differences: the stimulus name "Nora" vs "Lena", the stimulus word "errand" vs '
                    '"task", an English vs a Chinese opener, and position 0 vs 1. That is an 11x solo gap with identical filler.'),
        sibling_notes=[
            '[2] wrongX "the key she borrowed from her father" is wrong slot: the father lends a key, he does not die.',
            '[0] gold correct. [3] none correct.',
        ],
    ),
    22: dict(
        label_verdict='correct_weak',
        substance='gold_X_wrong_state_scene_template',
        what_bullet_says=('"清理 (packing out) a parent\'s home after their death, reflecting a major life transition and grief. Jack is '
                          'now dealing with the reality of his father\'s absence and". The parent died (gold relation), but the state '
                          'is grief instead of guilt; gender swapped (Jack, his father); no driving or accident.'),
        frame_vs_filler=('Frame = the literal scene (emptying a dead parent\'s house). X filler right; Y (state) wrong.'),
        prompt_echo=['clearing the house ~ "the house she had grown up in was hers to empty", "taped another box shut"'],
        fve_driver=('Length within one template. All four bullets are "clearing out a deceased relative\'s home", and solo tracks '
                    'tokens: [1] "2: Clearing out a deceased parent\'s home after a recent death" (14 tokens) 0.348, [2] (26) 0.410, '
                    'focal (32) 0.430, [3] "a deceased person\'s home ... specifically her grandfather\'s" (32) 0.378. The '
                    'grandfather-vs-parent gap (0.05) is within the length spread. Combine 32: first greedy pick.'),
        sibling_notes=[
            '[3] LLM other_axis / lex2 frame_only for "her grandfather\'s": should be other_value (a wrong relation).',
            '[1], [2] gold correct.',
        ],
    ),
    23: dict(
        label_verdict='wrong_slot',
        substance='state_word_on_protagonist_meta_tail',
        what_bullet_says=('"李明 faces disappointment after a college application rejection, returning to old plans. Here are three '
                          'rewritten versions of that moment,". The disappointment is the protagonist\'s own, about a college '
                          'rejection. Gold needs his belief that the SIBLING feels disappointment about the canceled move. The tail is '
                          'meta text.'),
        frame_vs_filler=('Frame: a failed application and returning to old plans (plot). The state word is right but on the wrong '
                         'holder; the order axis (his conclusion about someone else\'s feeling) and the sibling are absent.'),
        prompt_echo=['"returning to old plans" ~ "pulled the appeal forms back out of the drawer"'],
        fve_driver=('Name echo and plot frame, plus a format penalty. The top-share bullet has no state word: [3] "Tom retracts his '
                    'previously hopeful plans after a failed application, returning to familiar, unapproved ideas." (none; solo '
                    '0.229, share 0.478): Tom ~ Tomás, failed application ~ "the posting fell through", plans ~ appeal forms. The '
                    'focal has a wrong name and the "Here are three rewritten versions" tail: 0.037 (3rd pct). Read at the final '
                    '"." of the story, 9 tokens before the end.'),
        sibling_notes=[
            '[0] gold (", disappointed by the rejection, retrieves plans for a canceled trip") also has the wrong holder.',
            '[1], [3] none correct.',
        ],
    ),
}


def main():
    d = json.loads(SAMPLE.read_text())
    recs = []
    for c in d['cases'][12:24]:
        i = c['reading_index']
        a = ANN[i]
        it, fb = c['item'], c['bullets'][c['focal_bullet']]
        rec = {
            'reading_index': i,
            'case_key': c['case_key'],
            'setting': c['setting'],
            'case_type': c['case_type'],
            'item_id': it['id'], 'group': it['group'],
            'gold_label': it['gold_label'], 'contrast_label': it['contrast_label'],
            'contrast_axis': it['contrast_axis'],
            'gold_value': it['gold_value_on_axis'], 'contrast_value': it['contrast_value_on_axis'],
            'layer': c['read_site']['layer'], 'position': c['read_site']['position'],
            'read_site': c['read_site']['site'], 'tokens_from_end': c['read_site']['tokens_from_end'],
            'joint_fve': c['readout']['joint_fve'],
            'judge': c['readout'].get('judge_per_cell'),
            'focal_bullet': c['focal_bullet'],
            'focal_text': fb['text'],
            'focal_label': fb['label'], 'focal_llm_label': fb['llm_label'], 'focal_llm_quote': fb['llm_quote'],
            'focal_lex2_label': fb['lex2_label'],
            'focal_scores': {k: fb[k] for k in ('solo_fve', 'solo_pct_in_setting_layer', 'shapley_share', 'loo_drop',
                                                'scored_tokens', 'truncated')},
            'focal_rank_by_share': c['focal_summary']['rank_by_share_in_readout'],
            'label_verdict': a['label_verdict'],
            'counts_as': COUNTS[a['label_verdict']],
            'substance': a['substance'],
            'what_bullet_says': a['what_bullet_says'],
            'frame_vs_filler': a['frame_vs_filler'],
            'prompt_echo': a['prompt_echo'],
            'fve_driver': a['fve_driver'],
            'sibling_notes': a['sibling_notes'],
            'siblings': [{'index': b['index'], 'label': b['label'], 'llm': b['llm_label'], 'lex2': b['lex2_label'],
                          'solo': b['solo_fve'], 'share': b['shapley_share'], 'tokens': b['scored_tokens'],
                          'text': b['text']} for b in c['bullets']],
            'pool_context_lex2': c['pool_context_lex2'],
        }
        recs.append(rec)

    def tally(rs):
        out = {'n': len(rs), 'correct': 0, 'borderline': 0, 'wrong': 0}
        for r in rs:
            out[r['counts_as']] += 1
        out['precision_strict'] = round(out['correct'] / len(rs), 3) if rs else None
        out['precision_lenient'] = round((out['correct'] + out['borderline']) / len(rs), 3) if rs else None
        return out

    gold = [r for r in recs if r['focal_label'] == 'gold']
    wrong = [r for r in recs if r['focal_label'] == 'wrongX']
    summary = {
        'all_focal': tally(recs),
        'gold_focal': tally(gold),
        'wrongX_focal': tally(wrong),
        'by_case_type': {t: tally([r for r in recs if r['case_type'] == t])
                         for t in ('high_fve_gold', 'low_fve_gold', 'high_fve_wrong_value')},
        'verdict_counts': {v: sum(r['label_verdict'] == v for r in recs)
                           for v in ('correct', 'correct_weak', 'borderline', 'wrong_slot')},
        'sibling_label_issues_noticed': [
            'q01_f.L60.p78 [3] mixed spurious (parent and children are not the victim)',
            'q08_c.L60.p67 [0] gold wrong slot (Elena is the oblivious one)',
            'q01_g.L52.p80 [2] wrongX wrong slot ("the key she borrowed from her father")',
            'q09_i.L60.p67 [0] gold wrong holder (protagonist disappointed)',
            'q01_e.L60.p143 [3] LLM gold on "killed a neighbor" (neighbor is not a stranger)',
            'q01_e.L36.p143 [2] "funeral of an unknown neighbor" (nearest to gold) not credited',
            'q01_h.L44.p87 [3] "her grandfather\'s" should be other_value, labelled other_axis/frame_only',
            'q03_g.L52.p72 [3] wrongX_weak on "wife\'s anxiety" with no medical word',
            'q02_c.L60.p98 [0] wrongX_weak on "silently celebrates her best friend\'s literary success" (borderline)',
        ],
    }
    out = {
        'family': 'conjunctive_association (Conjunctive association)',
        'source': 'analysis/ca/read_sample.json, cases 12-23',
        'reader': 'reader 1, manual reading 2026-10-16 (annotations in read_records_1_build.py)',
        'verdict_definitions': __doc__.split('label_verdict (focal bullet):')[1].strip(),
        'summary': summary,
        'records': recs,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
