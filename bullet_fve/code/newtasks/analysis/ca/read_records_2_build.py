"""Reader 2 for conjunctive association (ca): manual reading of read_sample.json cases 24-35.

Builds analysis/ca/read_records_2.json from read_sample.json plus the annotations below. Bullet text and scores are
copied from read_sample.json, and every quoted snippet is asserted to be a substring of its bullet, so quotes stay
verbatim. Pool quotes (bullets from the cell's 32-sample pool, shown with `analysis.py show KEY --pool`) are checked
against the cache tables with --verify-pool (loads tables.pkl; run it as a short mit_quicktest job).

Reader codes (per bullet, my reading, independent of the labellers):
  G   states gold's value on the contrast axis X, in the gold slot (right holder / agent / object)
  Gp  states gold's X value only by paraphrase (no X word the labellers credit), right slot
  Gs  states gold's X value, but in the wrong slot: wrong agent (she did it herself), wrong object or wrong event
  W   states a wrong value on X (the contrast's or another bank value) in the item's frame
  Ws  holds a contrast-axis word, but the word is story-consistent or sits in the wrong slot (not a wrong filler)
  F   frame only: shared content (event, object, relation, evidence paraphrase) and no X value
  O   other content (different event or object), no X value
Label verdicts (focal bullet): correct | borderline | wrong.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / 'read_sample.json'
OUT = HERE / 'read_records_2.json'
FIRST, LAST = 24, 35
G_LIKE = ('G', 'Gp')

# ------------------------------------------------------------------------------------------------ annotations
# codes: one reader code per bullet index; quotes: (bullet index, verbatim snippet) used in the prose.
ANN = {
    24: dict(
        label_verdict='correct',
        label_note='"deliberate erasure" states gold\'s X value (deliberate). "the wife" fills the spouse slot, with the '
                   'gender flipped: in the story the husband (Sasha) did it and Vera is the wife.',
        what_bullet_says='Request echo around one content phrase: [3] "summarize it in one sentence, capturing the '
                         'wife\'s deliberate erasure of her reminders. Here\'s a concise summary". Object is '
                         '"reminders", not the book.',
        frame_vs_filler='filler right (deliberate, spouse) inside a prompt echo; siblings carry only the frame '
                        '(deletion, wife, simultaneity).',
        prompt_echo=True,
        fve_driver='The whole readout is weak (L20, "ize" site 16 tokens before the end; joint 0.103, every bullet '
                   'below the 40th percentile). The top bullet [0] has no X value but paraphrases the story\'s '
                   'evidence ("the simultaneous disappearance of her records", the three copies cleared in the same '
                   'twenty minutes): solo 0.069 vs 0.021 for the gold bullet. FVE follows the evidence paraphrase, '
                   'not the inferred conclusion ("deliberate").',
        codes={0: 'F', 1: 'F', 2: 'F', 3: 'G'},
        quotes=[(3, "capturing the wife's deliberate erasure of her reminders"),
                (3, 'summarize it in one sentence'),
                (0, 'focusing on the simultaneous disappearance of her records'),
                (1, 'The wife deleted everything at once')],
    ),
    25: dict(
        label_verdict='correct',
        label_note='"assumed her apartment was rented out" is the gold state (an unconfirmed but correct suspicion '
                   'that it is settled). The LLM quote is the right one. lex2 fired on "suspicious", which here '
                   'describes the silence (evidence), not her belief: right label, weak lexicon reason.',
        what_bullet_says='[0] "Noticing suspicious silence and a disappeared listing, Nadine assumed her apartment was '
                         'rented out and resigned herself to a likely rejection". Evidence paraphrase plus the '
                         'gold conclusion; wrong name (Talia in the story).',
        frame_vs_filler='frame (apartment, vanished listing, silence) plus right filler.',
        prompt_echo=False,
        fve_driver='The apartment frame. The three apartment bullets sit at 0.43-0.48 whether or not they state the '
                   'conclusion: [1] (frame_only, "adopted a wait-and-see approach") 0.428, [3] (lex2 gold only '
                   'through "suspicious changes") 0.437, [0] 0.483. The bullet that swaps the object to a job search '
                   '[2] drops to 0.176. Pool: 48 gold, 0 wrong-value bullets, so no filler contrast is available.',
        codes={0: 'G', 1: 'F', 2: 'O', 3: 'F'},
        quotes=[(0, 'assumed her apartment was rented out'),
                (0, 'Noticing suspicious silence'),
                (1, 'adopted a wait-and-see approach'),
                (3, 'observes suspicious changes to the apartment listing'),
                (2, 'abandoned her job search plans')],
        sibling_label_issues=['[3] combined gold rests on lex2 "suspicious changes" (evidence word); the LLM says '
                              'none. I read it as frame only.'],
    ),
    26: dict(
        label_verdict='correct',
        label_note='"believing her friend deliberately destroyed it" is the contrast value (deliberate) in exactly '
                   'the gold frame (her belief that someone else destroyed her writing). Relation is wrong too '
                   '(friend, not sibling).',
        what_bullet_says='[2] "Lena mourns the loss of a sentimental notebook she discarded, believing her friend '
                         'deliberately destroyed it", then a template tail "**Option 2: Concise and Direct".',
        frame_vs_filler='clean minimal pair with gold: same frame, wrong filler.',
        prompt_echo=False,
        fve_driver='The trash-checking / lost-notebook frame. [0] (belief that a boyfriend destroyed it, no X value) '
                   '0.465, [2] (contrast) 0.450, [1] (story echo: "Vera ... checking the trash") 0.428. The only '
                   'combined-gold bullet [3] puts "accidentally" on the wrong agent (her own remorse) and opens with '
                   'Chinese: 0.087. In the cell pool, friend-did-it-accidentally bullets (s26.0 0.382, s31.1 0.382, '
                   's22.1 0.375) and the full gold s30.3 (sister accidentally threw it away, 0.363) score no higher '
                   'than friend-did-it-deliberately bullets (s13.2 0.450, s11.1 0.441, s7.3 0.397). Most pool '
                   '"gold" bullets make her the one who accidentally discarded it (s15.2, s10.1, s2.1, ...).',
        codes={0: 'F', 1: 'F', 2: 'W', 3: 'Gs'},
        quotes=[(2, 'believing her friend deliberately destroyed it'),
                (0, 'she believed her boyfriend destroyed'),
                (1, 'Vera mourns the loss of her best friend by secretly checking the trash'),
                (3, '悔恨 (remorse) over accidentally destroying a cherished gift')],
        pool_quotes=[
            ('s13.2', 'contrast', 0.4504, 'believing her friend deliberately destroyed it'),
            ('s11.1', 'contrast', 0.441, 'suspects her friend deleted it intentionally'),
            ('s7.3', 'contrast', 0.3968, 'suspects the disposal was intentional'),
            ('s26.0', 'gold', 0.3821, "Vera mourns her friend's accidental destruction of her diary"),
            ('s31.1', 'gold', 0.3817, 'After her friend Maya accidentally destroyed her notebook'),
            ('s22.1', 'gold', 0.3746, 'After sending her journal to a friend, who inadvertently destroyed it'),
            ('s30.3', 'gold', 0.3631, 'After her sister accidentally threw away a diary containing their shared memories'),
            ('s15.2', 'gold', 0.4016, "After accidentally discarding her father's love letter, remorseful Maya"),
            ('s10.1', 'gold', 0.3987, 'a memory box she accidentally discarded by pouring a glass of wine'),
        ],
        sibling_label_issues=['[3] combined gold (lex2 gold, LLM other_axis): "accidentally" sits on the wrong agent '
                              '(she destroyed a gift herself; the sister appears only as the house she searches). '
                              'The LLM is right. Same pattern across most pool "gold" bullets of this cell.'],
    ),
    27: dict(
        label_verdict='correct',
        label_note='"hiding the news" states gold\'s X value (keeping it hidden).',
        what_bullet_says='[1] "行为 (Action) and Emotional Suppression: Sarah is meticulously hiding the news, wiping '
                         'tears, and dismissing the". It has the X value, but not the shared state (relief), and '
                         'adds a wrong detail ("wiping tears"; in the story she laughed).',
        frame_vs_filler='filler right, the shared frame component (relief) missing.',
        prompt_echo=False,
        fve_driver='All four bullets state hiding. The three that also name relief, the component gold and contrast '
                   'share, score 0.185-0.233 ([0] "Quick relief ... hides the bad news", [2] "quick relief. She '
                   'hides", [3] "rapid relief"); the one without relief scores 0.028. FVE tracks the shared state, '
                   'not the X value. Pool: 33 gold, 0 wrong-value bullets.',
        codes={0: 'G', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(1, 'Sarah is meticulously hiding the news, wiping tears'),
                (0, 'Quick relief and suppression of emotional response. The protagonist hides the bad news'),
                (2, 'quick relief. She hides a major life event'),
                (3, 'rapid relief after a difficult event')],
        sibling_label_issues=['[0], [2], [3]: lex2 frame_only, LLM gold. lex2 misses "hides" and "covering up" '
                              '(it matched only "hiding" in [1]); the combined label (gold) is right.'],
    ),
    28: dict(
        label_verdict='borderline',
        label_note='The lexicon fired on "mother" and "daughter", but those name the griever (Lucy, a mother) and a '
                   'living daughter, not the deceased: wrong slot. The LLM\'s reason, "miscarriage", is only an '
                   'inferred "own child" value, and the explicit deceased is a dog. The bullet does not name the '
                   'mentor, so it is off gold, but the wrong X value is inferred, not stated.',
        what_bullet_says='[2] "A grieving mother named Lucy and her daughter Emily quietly disposed of a deceased dog '
                         'and moved out of their home after a devastating miscarriage". Grief, not guilt; no '
                         'mentor, lab or site visit.',
        frame_vs_filler='generic bereavement frame (death, disposal, moving out) with a muddled wrong deceased; the '
                        'kinship words the lexicon counts are in the griever slot.',
        prompt_echo=False,
        fve_driver='No bullet in this readout (or in the 126-bullet pool: 0 gold, 86 lex2 other-value) names the '
                   'mentor or guilt. The four bullets are all wrong deceased (fiancé, ex-lover, dog/miscarriage, '
                   'husband) and score 0.13-0.29; the two longest truncated ones score highest. Across settings and '
                   'in the pool the top bullets open with the response template: Best of 32 [2] "Here is a single '
                   'sentence summary of the passage: ... two sisters discover that the" solo 0.507 (100th pct, share '
                   '0.73), pool s8.2 "Here is a one-sentence summary of the text: ..." 0.500. The template, not '
                   'the filler, gets the FVE.',
        codes={0: 'W', 1: 'W', 2: 'Ws', 3: 'W'},
        quotes=[(2, 'A grieving mother named Lucy and her daughter Emily quietly disposed of a deceased dog'),
                (2, 'after a devastating miscarriage'),
                (0, "attends her fiancé's funeral"),
                (1, "attends her ex-lover's funeral"),
                (3, "After her husband's death")],
        pool_quotes=[
            ('s8.2', 'other_value', 0.4997, 'Here is a one-sentence summary of the text: After the tragic loss of their home and loved one, Lorraine and her mother attend the funeral of'),
            ('s19.2', 'other_value', 0.4727, 'Here is a one-sentence summary of the paragraph: In the wake of a devastating cancer diagnosis, Mara and her husband, Will, decide to remain together'),
        ],
        other_setting_quotes=[
            ('Best of 32', 2, 'other_axis', 0.5074, 'Here is a single sentence summary of the passage: While preparing to return to their town after a devastating tornado, two sisters discover that the'),
        ],
        sibling_label_issues=['[0] fiancé and [1] ex-lover are wrong deceased on the relation axis but fall outside '
                              'the bank\'s five values (own child, spouse, parent, mentor, stranger), so they are '
                              'other_axis; [3] "husband\'s death" is the one clean wrong value here.',
                              'Pool top other-value bullets s8.2 ("Lorraine and her mother attend the funeral") and '
                              's19.2 ("Mara and her husband, Will, decide to remain together") hit kinship words for '
                              'living people: lex2 other_value is slot-blind on the relation axis.'],
    ),
    29: dict(
        label_verdict='correct',
        label_note='"accidentally erasing a woman\'s legal documents" states gold\'s X value (accidental). It is the '
                   'only bullet of the four with the story\'s role layout (a man erases a woman\'s files).',
        what_bullet_says='[2] "A grieving man resolved a legal dispute with a clerk while accidentally erasing a '
                         'woman\'s legal documents, a mistake that inadvertently saved his family\'s financial '
                         'status". Object wrong (legal documents, not chapters); "colleague" not named.',
        frame_vs_filler='filler right; frame partly wrong (legal documents, legal dispute).',
        prompt_echo=False,
        fve_driver='The X value is saturated: all four bullets say "accidentally deleted/erasing" and the pool has '
                   '102 gold and 0 wrong-value bullets. Solo FVE among them follows length and opener: the 32-token '
                   'bullet [2] 0.343 and [3] 0.322 lead, [0] 0.264, and [1], which opens with a Chinese name '
                   '("艾德"), drops to 0.093. [0] and [3] put the protagonist-like figure ("A woman", "An unnamed '
                   'narrator") as the one who deleted. The right-slot bullet [2] is also the top one, but it leads '
                   '[3] by only 0.02, so this is weak evidence for slot sensitivity.',
        codes={0: 'Gs', 1: 'Gs', 2: 'G', 3: 'Gs'},
        quotes=[(2, "accidentally erasing a woman's legal documents"),
                (0, "A woman accidentally deleted a stranger's legal documents"),
                (1, "艾德 accidentally deleted a man's legal documents"),
                (3, 'An unnamed narrator accidentally deleted Kevin’s legal files')],
    ),
    30: dict(
        label_verdict='correct',
        label_note='"proudly displays" states pride. Relation is "her sister", not her closest friend (relation is '
                   'not varied in q02, so this does not affect the label).',
        what_bullet_says='[0] "Dana proudly displays the recognition her sister received, hanging a photocopy of her '
                         'name in the office lobby". Right name (Dana), pride, display of someone else\'s honour.',
        frame_vs_filler='frame (someone else\'s honour, Dana displays a copy) plus right filler (pride).',
        prompt_echo=False,
        fve_driver='The one case where gold bullets clearly beat their siblings: [0] 0.565 and [2] 0.520 vs [1] 0.289 '
                   'and [3] 0.253. But the gap is confounded with roles: in [1] and [3] Dana herself receives the '
                   'award or title ("After being named Editor-in-Chief, Dana eagerly purchased a framed copy"), so '
                   'they lose both pride and the other-person-achieved frame. The pool has 75 gold and 0 envy '
                   'bullets, so this says nothing about pride vs envy.',
        codes={0: 'G', 1: 'F', 2: 'G', 3: 'F'},
        quotes=[(0, 'Dana proudly displays the recognition her sister received'),
                (2, "Prideful and eager to display her sister Sarah's professional achievement"),
                (1, 'After a prominent colleague named Dana receives an award'),
                (3, 'After being named Editor-in-Chief, Dana eagerly purchased a framed copy')],
    ),
    31: dict(
        label_verdict='correct',
        label_note='"pride in" states pride. The bullet begins mid-correction ("(or rather, pride in)"), so the '
                   'word it corrects is not visible.',
        what_bullet_says='[2] "(or rather, pride in) Nancy’s achievement based on the provided text, highlighting how '
                         'each friend preserves the news differently." Pride plus task meta ("based on the provided '
                         'text") and a "**Diane’s" header tail.',
        frame_vs_filler='filler right, wrapped in analysis meta.',
        prompt_echo=True,
        fve_driver='All four bullets say pride (pool 92 gold, 0 wrong-value), and all score low (L52 "ize" site; '
                   '0.07-0.17, below the 15th percentile). The focal is the fragment that opens with a parenthetical '
                   'and carries the most meta; the short "2: Dana\'s reaction and pride in keeping the clipping" '
                   '(verbatim story detail) scores 0.128. Differences are about form, not content.',
        codes={0: 'G', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(2, '(or rather, pride in) Nancy’s achievement based on the provided text'),
                (1, "2: Dana's reaction and pride in keeping the clipping"),
                (0, "黛安’s pride in Lena's achievement")],
    ),
    32: dict(
        label_verdict='borderline',
        label_note='"to hide her" is the contrast-axis word (concealing / hiding something), so it is right by the '
                   'axis definition. But concealment is part of the gold story (she "archived the call recording to '
                   'the tier nobody audited"), and the rest of the bullet is the credit-taking scenario ("submitted '
                   'an uncredited architectural drawing ... anonymously"). The contrast\'s own content, concealing '
                   'HER OWN MISTAKE, appears nowhere. This is not a wrong filler.',
        what_bullet_says='[0] "Renata submitted an uncredited architectural drawing to the board anonymously, '
                         'exploiting the director\'s absence to hide her" (truncated at 21 tokens).',
        frame_vs_filler='gold frame (submitting someone\'s uncredited work) with a story-consistent concealment word '
                        'that the labellers read as the contrast value.',
        prompt_echo=False,
        fve_driver='Every bullet in the readout and most of the pool describe submitting work while concealing '
                   'its source or authorship ("concealed her contribution", "concealed her authorship", "hiding its '
                   'source"). FVE is high for the whole frame: pool contrast s30.1 0.358, mixed s11.0 0.376, gold '
                   's11.3 0.394, all within 0.04. The focal leads the readout (share 0.42, drop 0.067) as the '
                   'cleanest version of the frame, with the right name (Renata) and the scenario (uncredited, '
                   'anonymous, absent superior).',
        codes={0: 'Ws', 1: 'Ws', 2: 'Ws', 3: 'Ws'},
        quotes=[(0, 'submitted an uncredited architectural drawing to the board anonymously'),
                (0, 'to hide her'),
                (1, 'concealed her contribution from a superior'),
                (2, 'An uncredited intern secretly submitted the final draft'),
                (3, 'concealed her authorship by submitting her work')],
        pool_quotes=[
            ('s30.1', 'contrast', 0.3575, 'Renata concealed the origin of an innovative design by submitting it alone and hiding its source'),
            ('s11.0', 'mixed', 0.3759, "Renata concealed an original idea within the competition's internal submissions to claim sole credit"),
            ('s11.3', 'gold', 0.3942, 'omitting the signature of a senior colleague to secure sole credit'),
            ('s20.1', 'contrast', 0.3784, "concealed its source, hiding her work under her supervisor's name"),
        ],
        sibling_label_issues=['All four are labelled wrong value (three wrongX, one wrongX_weak), but each conceals '
                              'authorship or the source of the work, which is part of the gold story (or its mirror '
                              'image). [2] "An uncredited intern" is close to the gold scenario. In q04_j, '
                              '"contrast" means "concealment word present", not "wrong filler".'],
    ),
    33: dict(
        label_verdict='correct',
        label_note='"Proud" states pride; it is also the only bullet that keeps the right content (the engagement '
                   'news) and the right name.',
        what_bullet_says='[2] "1. Proud and boastful, Dana received the engagement news a week after her promotion '
                         'and immediately began celebrating with her coworkers at their office." Pride, engagement, '
                         'Dana, coworkers ("told the story at work all week").',
        frame_vs_filler='frame and filler both right; the most story-faithful bullet in the readout.',
        prompt_echo=False,
        fve_driver='Inverse of content fidelity. The focal scores 0.0067 (0.3rd pct; share 0.004, drop 0, coef 0). '
                   'The siblings attach pride to the wrong object: her own promotion or new job ([3] "Pridefully '
                   'boasting about her new job" 0.371, share 0.606; [0] "recounting her new job announcement" 0.254; '
                   '[1] "elated by her promotion" 0.086). Nothing in the content explains the focal\'s near-zero '
                   'score; the "1." list opener is the most visible formal difference. Pool: 69 gold, 0 envy '
                   'bullets.',
        codes={0: 'Gs', 1: 'Gs', 2: 'G', 3: 'Gs'},
        quotes=[(2, '1. Proud and boastful, Dana received the engagement news'),
                (3, 'Pridefully boasting about her new job in a magazine'),
                (0, 'Dana is beaming with pride, recounting her new job announcement'),
                (1, 'Daniella, elated by her promotion, proudly shares the news')],
        sibling_label_issues=['[3] lex2 other_axis (promotion), LLM gold: pride is stated, about the wrong content. '
                              'Combined gold is right by the definition (X value stated).'],
    ),
    34: dict(
        label_verdict='correct',
        label_note='"deliberate sabotage by her neighbor" plus "interprets" is the full gold compound except the '
                   'book.',
        what_bullet_says='[2] "冲突 (Conflict) and Interpretation: Alice interprets a series of minor electrical '
                         'failures as deliberate sabotage by her neighbor. Here is a breakdown of". Belief, '
                         'deliberate, neighbor, electrical cause (breaker), plus a meta tail.',
        frame_vs_filler='frame and filler both right; the most complete statement of the four.',
        prompt_echo=True,
        fve_driver='All four bullets state sabotage (pool 63 gold, 2 wrong-value). The most complete one scores '
                   'lowest (0.036, coef 0.145); [3] "恶意 (malice) ... concluding that Jane’s garage light going '
                   'out was deliberate sabotage" scores 0.243 (share 0.55). Same-format bullets in the pool score '
                   'much higher ("冲突 (Conflict) and Suspicion: ... deliberate sabotage" 0.148; "冲突 escalation and '
                   'sabotage ... intentional sabotage by her neighbor" 0.225), so the focal\'s score is a '
                   'sample-level outlier with no content reason.',
        codes={0: 'G', 1: 'G', 2: 'G', 3: 'G'},
        quotes=[(2, 'Alice interprets a series of minor electrical failures as deliberate sabotage by her neighbor'),
                (2, 'Here is a breakdown of'),
                (3, 'concluding that Jane’s garage light going out was deliberate sabotage'),
                (1, 'Sarah believes her solar garden was sabotaged by her neighbor'),
                (0, 'Conclusion of Sabotage')],
        pool_quotes=[
            ('s14.1', 'contrast', 0.1503, 'It shifts from accident to sabotage'),
            ('s12.1', 'gold', 0.225, 'interpreting recent events as intentional sabotage by her neighbor'),
            ('s0.2', 'gold', 0.1477, '冲突 (Conflict) and Suspicion: Interpretation of Elena’s actions as deliberate sabotage'),
        ],
        sibling_label_issues=['[1] "believes her solar garden was sabotaged by her neighbor" is labelled frame_only '
                              '(LLM none, lex2 frame): a gold false negative. "sabotage" is not a lex2 credit word, '
                              'so [0] is lex2 none.',
                              'Pool s14.1 "It shifts from accident to sabotage" is lex2 contrast but states gold: '
                              'the negation rule does not catch "from accident to". At least one of this cell\'s two '
                              'wrong-value bullets is a false positive.'],
    ),
    35: dict(
        label_verdict='correct',
        label_note='"to conceal a" states the gold X value (concealing), with the object cut off at 19 tokens; '
                   '"fearing exposure after failing her annual review" supplies her own failure.',
        what_bullet_says='[0] "Renata, fearing exposure after failing her annual review, meticulously destroys her '
                         'employee handbook to conceal a". Right name, the review, destroying a document.',
        frame_vs_filler='frame (fear of exposure at a review, destroying documents) plus right filler.',
        prompt_echo=False,
        fve_driver='The destroy-the-evidence frame. Two bullets the labellers call none, because they never say '
                   'conceal or hide, score almost as high: [2] "sought to destroy evidence of her embezzlement" '
                   '0.473 and [3] "attempts to erase the evidence of her fraud by shredding the" 0.371. The most '
                   'faithful bullet [1] ("discovery of her errors ... to hide the evidence", own mistake plus hiding) '
                   'scores 0.299, with a Chinese opener ("害怕"). Pool: 66 gold, 0 wrong-value.',
        codes={0: 'G', 1: 'G', 2: 'Gp', 3: 'Gp'},
        quotes=[(0, 'fearing exposure after failing her annual review, meticulously destroys her employee handbook to conceal a'),
                (1, 'discovery of her errors'),
                (1, 'to hide the evidence'),
                (2, 'sought to destroy evidence of her embezzlement'),
                (3, 'attempts to erase the evidence of her fraud by shredding the')],
        sibling_label_issues=['[2], [3] labelled none (both labellers): they describe concealing her own wrongdoing '
                              'by destroying evidence, a paraphrase of the gold X value (weak false negatives; the '
                              'wrongdoing is embezzlement/fraud, not a mistake).'],
    ),
}

PATTERNS = [
    dict(
        name='Frame, not filler: the X value moves FVE little, and shared content moves it a lot',
        text='Where a readout or pool holds the same frame with different X values, FVE does not follow the value. '
             'Where all bullets share the value, FVE follows the shared frame component or the story-evidence '
             'paraphrase.',
        examples=[
            'q10_g.L52.p112 (Combine 32 and pool): friend-did-it-DELIBERATELY [2] "believing her friend deliberately '
            'destroyed it" 0.450, pool s11.1 "suspects her friend deleted it intentionally" 0.441 vs friend-did-it-'
            'ACCIDENTALLY s26.0 "Vera mourns her friend\'s accidental destruction of her diary" 0.382, s31.1 0.382; '
            'full gold s30.3 "After her sister accidentally threw away a diary" 0.363.',
            'q07_b.L60.p94 (Original): all four say hiding; with the shared "relief" 0.185-0.233 ([2] "quick relief. '
            'She hides a major life event"), without it 0.028 ([1] "Sarah is meticulously hiding the news, wiping '
            'tears").',
            'q04_b.L60.p87 (Original): gold [0] "to conceal a" 0.506 vs label-none [2] "sought to destroy evidence of '
            'her embezzlement" 0.473; the most faithful gold [1] ("discovery of her errors ... to hide the '
            'evidence") 0.299.',
            'q06_g.L52.p100 (Combine 32): apartment bullets 0.43-0.48 with or without the conclusion; the one that '
            'switches to "abandoned her job search plans" 0.176.',
        ],
    ),
    dict(
        name='Right value, wrong slot inflates gold labels (lexicon), and slot errors make the "wrong value" labels '
             'noisy',
        text='lex2 credits an X word anywhere in the bullet. On state axes the value often lands on the wrong agent '
             '(she did it herself); on the relation axis the kinship word often names the griever or a living '
             'companion. The LLM catches some of these (other_axis), and the combined "either says gold" rule '
             're-admits them.',
        examples=[
            'q10_g.L52.p112 [3] "悔恨 (remorse) over accidentally destroying a cherished gift, Julia scans her '
            'sister\'s home" combined gold (lex2), LLM other_axis; solo 0.087. Pool "gold" is mostly self-as-agent: '
            's15.2 "After accidentally discarding her father\'s love letter, remorseful Maya" 0.402.',
            'q01_i.L36.p95 [2] "A grieving mother named Lucy and her daughter Emily quietly disposed of a deceased dog" '
            '(lex2 other_value via mother/daughter, both living); pool s19.2 "Mara and her husband, Will, decide to '
            'remain together" lex2 other_value 0.473.',
            'q10_e pool s14.1 "It shifts from accident to sabotage" lex2 contrast, but it states gold (the negation '
            'rule misses "from ... to").',
            'q02_g.L60.p80 [3] "Pridefully boasting about her new job in a magazine": pride about her own promotion, '
            'not the friend\'s engagement; combined gold; top FVE in its readout (0.371, share 0.606).',
        ],
    ),
    dict(
        name='q04 "contrast" bullets describe the gold story: concealment is part of credit theft',
        text='In q04_j the contrast-axis words (conceal, hide) describe how Renata hid the source of the stolen '
             'work, which the story contains ("archived the call recording to the tier nobody audited"). None of the '
             'four readout bullets or the pool quotes mention her own mistake, so q04 gold-vs-wrong-value pairs '
             'compare credit theft with credit theft.',
        examples=[
            'q04_j.L60.p77 [0] "Renata submitted an uncredited architectural drawing to the board anonymously, '
            'exploiting the director\'s absence to hide her" (LLM and lex2 contrast) 0.384.',
            'q04_j pool s30.1 "Renata concealed the origin of an innovative design by submitting it alone and hiding '
            'its source" contrast 0.358 vs s11.3 "omitting the signature of a senior colleague to secure sole credit" '
            'gold 0.394.',
        ],
    ),
    dict(
        name='Low-FVE gold bullets are often the most faithful; form drives the low score',
        text='In 3 of the 5 low-FVE gold cases the focal is the most story-faithful bullet in its readout (q02_g, '
             'q10_e, and q10_a apart from its echo). The low scores come with list or header openers, meta tails '
             '("Here is a breakdown of"), request echo at the "ize" site, or fragments. The top bullets often open '
             'with the response template. This sample is selected on FVE, so it shows that the pattern exists, not '
             'how common it is.',
        examples=[
            'q02_g.L60.p80 [2] "1. Proud and boastful, Dana received the engagement news a week after her promotion '
            'and immediately began celebrating with her coworkers" solo 0.0067 (coef 0) vs [3] "Pridefully boasting '
            'about her new job" 0.371.',
            'q10_e.L52.p115 [2] "Alice interprets a series of minor electrical failures as deliberate sabotage by her '
            'neighbor. Here is a breakdown of" 0.036, the most complete gold statement.',
            'q10_a.L20.p82 [3] "summarize it in one sentence, capturing the wife\'s deliberate erasure of her '
            'reminders. Here\'s a concise summary" 0.021.',
            'q01_i.L36.p95 Best of 32 [2] "Here is a single sentence summary of the passage: ... two sisters discover '
            'that the" 0.507 (100th pct, share 0.73), with no X value.',
        ],
    ),
]


def check_quotes(case, ann):
    texts = {b['index']: b['text'] for b in case['bullets']}
    for i, q in ann['quotes']:
        assert q in texts[i], (case['case_key'], i, q)
    assert set(ann['codes']) == set(texts), case['case_key']


def pair_rate(bs, a_codes, b_codes, exclude=None):
    """P(solo of a code-A bullet > solo of a code-B bullet), pairs within one readout; ties 1/2."""
    n = w = 0.0
    for x, y in itertools.product(bs, bs):
        if x['index'] == y['index'] or exclude in (x['index'], y['index']):
            continue
        if x['reader_code'] in a_codes and y['reader_code'] in b_codes:
            n += 1
            w += 1.0 if x['solo_fve'] > y['solo_fve'] else 0.5 if x['solo_fve'] == y['solo_fve'] else 0.0
    return w, n


def build():
    src = json.loads(SRC.read_text())
    recs = []
    for case in src['cases'][FIRST:LAST + 1]:
        ri = case['reading_index']
        ann = ANN[ri]
        check_quotes(case, ann)
        it, f = case['item'], case['focal_bullet']
        fb = case['bullets'][f]
        bullets = [{
            'index': b['index'], 'text': b['text'], 'label': b['label'], 'llm_label': b['llm_label'],
            'llm_quote': b['llm_quote'], 'lex2_label': b['lex2_label'], 'lex2_words': b['lex2_words'],
            'reader_code': ann['codes'][b['index']], 'solo_fve': b['solo_fve'],
            'solo_pct_in_setting_layer': b['solo_pct_in_setting_layer'], 'shapley_share': b['shapley_share'],
            'loo_drop': b['loo_drop'], 'coefficient': b['coefficient'], 'scored_tokens': b['scored_tokens'],
            'truncated': b['truncated'], 'focal': b['index'] == f,
        } for b in case['bullets']]
        recs.append({
            'reading_index': ri, 'case_key': case['case_key'], 'setting': case['setting'],
            'case_type': case['case_type'], 'item_id': it['id'], 'group': it['group'],
            'layer': case['read_site']['layer'], 'position': case['read_site']['position'],
            'site': case['read_site']['site'], 'gold_label': it['gold_label'], 'contrast_label': it['contrast_label'],
            'contrast_axis': it['contrast_axis'], 'gold_value_on_axis': it['gold_value_on_axis'],
            'contrast_value_on_axis': it['contrast_value_on_axis'], 'joint_fve': case['readout']['joint_fve'],
            'judge_per_cell': case['readout'].get('judge_per_cell'),
            'focal_bullet': f, 'focal_text': fb['text'], 'focal_label': fb['label'],
            'focal_llm': [fb['llm_label'], fb['llm_quote']], 'focal_lex2': [fb['lex2_label'], fb['lex2_words']],
            'focal_scores': case['focal_summary'],
            'label_verdict': ann['label_verdict'], 'label_note': ann['label_note'],
            'what_bullet_says': ann['what_bullet_says'], 'frame_vs_filler': ann['frame_vs_filler'],
            'prompt_echo': ann['prompt_echo'], 'fve_driver': ann['fve_driver'],
            'sibling_label_issues': ann.get('sibling_label_issues', []),
            'pool_context_lex2': case['pool_context_lex2'],
            'pool_quotes': [dict(zip(('sample.bullet', 'lex2', 'solo', 'quote'), q)) for q in ann.get('pool_quotes', [])],
            'other_setting_quotes': [dict(zip(('setting', 'index', 'label', 'solo', 'quote'), q))
                                     for q in ann.get('other_setting_quotes', [])],
            'bullets': bullets,
        })

    # ---------------------------------------------------------------------------------------------- summary
    by_type = collections.defaultdict(collections.Counter)
    for r in recs:
        by_type[r['case_type']][r['label_verdict']] += 1
    gold_focal = [r for r in recs if r['focal_label'] == 'gold']
    wrong_focal = [r for r in recs if r['focal_label'] == 'wrongX']
    allb = [(r, b) for r in recs for b in r['bullets']]
    lab_x_code = collections.defaultdict(collections.Counter)
    for _, b in allb:
        lab_x_code[b['label']][b['reader_code']] += 1
    code_solo = collections.defaultdict(list)
    for _, b in allb:
        code_solo[b['reader_code']].append(b['solo_fve'])
    w = n = w2 = n2 = 0.0
    readouts_both = 0
    for r in recs:
        a, b = pair_rate(r['bullets'], G_LIKE, ('Gs', 'W', 'Ws', 'F', 'O'))
        a2, b2 = pair_rate(r['bullets'], G_LIKE, ('Gs', 'W', 'Ws', 'F', 'O'), exclude=r['focal_bullet'])
        w, n, w2, n2 = w + a, n + b, w2 + a2, n2 + b2
        readouts_both += b > 0
    top_is_g = sum(max(r['bullets'], key=lambda b: b['shapley_share'])['reader_code'] in G_LIKE for r in recs)
    base_g = sum(b['reader_code'] in G_LIKE for _, b in allb)
    summary = {
        'n_cases': len(recs),
        'focal_label_precision': {
            'gold': {'n': len(gold_focal), 'correct': sum(r['label_verdict'] == 'correct' for r in gold_focal),
                     'borderline': sum(r['label_verdict'] == 'borderline' for r in gold_focal),
                     'wrong': sum(r['label_verdict'] == 'wrong' for r in gold_focal)},
            'wrong_value': {'n': len(wrong_focal),
                            'correct': sum(r['label_verdict'] == 'correct' for r in wrong_focal),
                            'borderline': sum(r['label_verdict'] == 'borderline' for r in wrong_focal),
                            'wrong': sum(r['label_verdict'] == 'wrong' for r in wrong_focal)},
            'all': {'correct': sum(r['label_verdict'] == 'correct' for r in recs), 'n': len(recs)},
        },
        'verdict_by_case_type': {k: dict(v) for k, v in by_type.items()},
        'all_bullets_label_vs_reader_code': {k: dict(v) for k, v in lab_x_code.items()},
        'reader_code_mean_solo': {k: {'n': len(v), 'mean_solo': round(sum(v) / len(v), 4)}
                                  for k, v in sorted(code_solo.items())},
        'within_readout_P_readerG_solo_gt_rest': {
            'all_pairs': {'P': round(w / n, 3) if n else None, 'n_pairs': int(n), 'n_readouts': int(readouts_both)},
            'excluding_focal': {'P': round(w2 / n2, 3) if n2 else None, 'n_pairs': int(n2)},
        },
        'top_share_bullet_is_readerG': f'{top_is_g}/{len(recs)}', 'base_rate_readerG': f'{base_g}/{len(allb)}',
        'pools_with_zero_wrong_value': f"{sum(r['pool_context_lex2']['wrong_value'] == 0 for r in recs)}/{len(recs)}",
        'caveat': ('12 cases, stratified on the focal bullet\'s solo FVE (4 high-FVE gold, 5 low-FVE gold, 3 '
                   'high-FVE wrong value), so FVE statistics here are descriptive only. Solo FVE is raw: not '
                   'position- or length-adjusted (Original / Best of 32 would need position adjustment; Combine 32 '
                   'order is the greedy FVE order).'),
    }
    out = {
        'family': 'conjunctive_association (Conjunctive association)',
        'source': 'analysis/ca/read_sample.json, cases 24-35 (reading_index)',
        'reader': 'reader 2, manual reading 2026-10-16 (annotations in read_records_2_build.py)',
        'reader_codes': __doc__.split('Reader codes')[1].split('Label verdicts')[0].strip(),
        'summary': summary,
        'patterns': PATTERNS,
        'records': recs,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def verify_pool():
    import sys
    sys.path.insert(0, str(HERE))
    import analysis as A  # noqa: E402  (imports ntcommon and sets paths)
    T = A.load_tables()
    p = A.pool_frame(T['pool'])
    src = json.loads(SRC.read_text())
    keys = {c['reading_index']: c['case_key'] for c in src['cases']}
    bad = 0
    for ri, ann in ANN.items():
        for sb, lab, solo, q in ann.get('pool_quotes', []):
            si, pos = (int(x) for x in sb[1:].split('.'))
            d = p[(p.key == keys[ri]) & (p.sample_index == si) & (p.pos == pos)] if 'key' in p else \
                p[(p.cell_id.map(A.case_key) == keys[ri]) & (p.sample_index == si) & (p.pos == pos)]
            ok = len(d) == 1 and q in d.text.iloc[0] and abs(float(d.solo.iloc[0]) - solo) < 6e-4 \
                and d.lex2.iloc[0] == lab
            bad += not ok
            print('OK ' if ok else 'BAD', keys[ri], sb, lab, solo, '|', q[:70],
                  '' if ok else f'-> {len(d)} rows {d[["lex2", "solo"]].to_dict("records") if len(d) else ""}')
    print('pool quotes bad:', bad)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify-pool', action='store_true')
    a = ap.parse_args()
    verify_pool() if a.verify_pool else build()
