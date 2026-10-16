"""User-modelling bullet labels by string match (no API): which attribute VALUE a bullet names.

Hand-written, word-boundary, case-insensitive. Matching is leftmost-longest and non-overlapping
(one alternation, longest forms first), so "South African" is never read as "African", and
"Latin American" never as "American". Spaces and hyphens inside a form match either.

Per bullet, for the item's attribute class (gold value g, WSB option distractors D, seed 0):
  value match of v          -> gold (v == g) | distractor (v in D) | other_value (any other value of the class)
  coarse term covering set S (a region/group word, or for Continent items a country = finer):
     g in S and S & D empty -> gold_coarse ;  g not in S and S & D -> distractor (coarse)
     g not in S, S & D empty -> other_value (coarse) ;  g in S and S & D -> ambiguous
  cue match (a culture/city/practice word specific to one value) -> as a value match, kind 'cue'
Label, in this order: mixed (a gold match and a wrong match) > gold_exact > gold_coarse >
wrong_value (subtype distractor if any distractor match, else other_value) > ambiguous >
frame_only (frame words of the class, e.g. "nationality", no value) > none.
Flags: in_prompt (a deciding match's surface form or stem occurs in the item's messages: a
verbatim-echo proxy), other_class (names a value of another class, e.g. a gender word in a
country item; kind recorded, pronouns separated).
Analysis groups: right filler = gold_exact|gold_coarse, wrong filler = wrong_value, frame = frame_only.

v2 (2026-10-16, after reading the 150-bullet sample; v1 = logs/um-cpu-backup/um_lexicon.py.orig):
- word-sense fixes: bare "single" / "engaged" / "engagement" / "separation" / "separated" / "full-time" /
  "retirement" / "secular" / "skeptic(al)" are no longer value forms (marital / employment phrases instead;
  "newly single" / "single again" cover divorced|widowed|separated; building contractors are stop forms); Buddhism cues temple / meditation / mindfulness / karma / dharma / monk(s) / bare zen dropped;
  "single parent" etc. and "non-religious" etc. are coarse terms (cover several values).
- forms marked ^ match case-sensitively (US, EU, Polish, Pole(s), Turkey, China, Chile, Cork, Lima);
  "North Pole" / "Arctic" are their own (wrong) location value; "Chile con queso" etc. are excluded.
- stop forms (hot dog, early bird, ...) consume text and label nothing.
- CJK forms (Chinese words for values incl. ~90 country names, matched without word boundaries) for the leading CJK token that
  ~30% of O-lens bullets carry; in_prompt is never true for them (the prompts are English).
- widowed paraphrases (spouse/partner has passed away, loss of a spouse, ...); halal cue Muslim/Islamic.
"""
from __future__ import annotations

import re
from functools import lru_cache

# ----------------------------------------------------------------------------------------------
# Countries: key | name/demonym/adjective forms | cue forms | continent | region tags
# (continents: africa asia europe north_america south_america oceania antarctica)
_COUNTRIES = """
paraguay|paraguay;paraguayan;paraguayans;paraguaya;paraguayo;巴拉圭|guarani;guaraní;asunción;asuncion;chipa;tereré;terere;sopa paraguaya|south_america|south_america,latin_america,hispanic
south_korea|south korea;south korean;south koreans;korea;korean;koreans;republic of korea;韩国;南韩;韩式|k-pop;kpop;k-drama;kimchi;泡菜;韩剧;hangul;seoul;busan;noraebang;tteokbokki;banchan;soju;hanbok;bibimbap;chuseok;jjigae|asia|east_asia
north_korea|north korea;north korean;north koreans;dprk;pyongyang||asia|east_asia
ukraine|ukraine;ukrainian;ukrainians;the ukraine;乌克兰|kyiv;kiev;kharkiv;lviv;odesa;odessa;cossack;cossacks;hopak;pysanky;pysanka;bandura;horilka;vyshyvanka;vyshyvanky;kobzar|europe|eastern_europe,slavic,post_soviet
new_zealand|new zealand;new zealander;new zealanders;aotearoa;新西兰;纽西兰|毛利人;毛利文化;kiwi;kiwis;maori;māori;haka;auckland;wellington;christchurch;pakeha|oceania|oceania,australasia,polynesia,anglophone
south_africa|south africa;south african;south africans;南非|braai;kwaito;afrikaans;afrikaner;afrikaners;zulu;xhosa;johannesburg;cape town;soweto;durban;pretoria;springbok;springboks;boer;biltong;amapiano|africa|southern_africa,sub_saharan,anglophone
costa_rica|costa rica;costa rican;costa ricans;tico;tica;ticos;ticas;哥斯达黎加|pura vida;gallo pinto;san josé|north_america|central_america,latin_america,hispanic
ireland|ireland;irish;irishman;irishwoman;éire;eire;republic of ireland;爱尔兰|dublin;^Cork;galway;emerald isle;shamrock;st. patrick;saint patrick;leprechaun|europe|western_europe,british_isles,celtic,anglophone
japan|japan;japanese;日本|tokyo;kyoto;osaka;sushi;samurai;anime;manga;kimono|asia|east_asia
brazil|brazil;brazilian;brazilians;brasil;巴西|rio de janeiro;são paulo;sao paulo;samba;carnaval|south_america|south_america,latin_america,lusophone
morocco|morocco;moroccan;moroccans;摩洛哥|marrakech;casablanca;rabat;fez;tagine|africa|north_africa,arab,maghreb
finland|finland;finnish;finn;finns;芬兰|helsinki;sauna|europe|northern_europe,nordic
united_states|united states;usa;u.s.;u.s.a.;^US;america;american;americans;african american;african-american;native american;us citizen;美国||north_america|anglophone,north_america_region
canada|canada;canadian;canadians;加拿大|toronto;vancouver;montreal|north_america|anglophone,north_america_region
mexico|mexico;mexican;mexicans;墨西哥|mexico city|north_america|latin_america,hispanic,central_america_wide
united_kingdom|united kingdom;uk;britain;great britain;british;brit;brits;englishman;englishwoman;england;scotland;scottish;scot;scots;wales;welsh;northern ireland;northern irish;英国;北爱尔兰;苏格兰;英格兰;威尔士|london;manchester;edinburgh|europe|western_europe,british_isles,anglophone
australia|australia;australian;australians;aussie;aussies;澳大利亚;澳洲|sydney;melbourne;outback|oceania|oceania,australasia,anglophone
argentina|argentina;argentine;argentinian;argentinians;argentinean;阿根廷|buenos aires;tango|south_america|south_america,latin_america,hispanic
chile|^Chile;chilean;chileans;智利|santiago|south_america|south_america,latin_america,hispanic
colombia|colombia;colombian;colombians;哥伦比亚|bogotá;bogota|south_america|south_america,latin_america,hispanic
peru|peru;peruvian;peruvians;秘鲁|^Lima|south_america|south_america,latin_america,hispanic
bolivia|bolivia;bolivian;bolivians;玻利维亚|la paz|south_america|south_america,latin_america,hispanic
uruguay|uruguay;uruguayan;uruguayans;乌拉圭|montevideo|south_america|south_america,latin_america,hispanic
venezuela|venezuela;venezuelan;venezuelans;委内瑞拉|caracas|south_america|south_america,latin_america,hispanic
ecuador|ecuador;ecuadorian;ecuadorians;厄瓜多尔|quito|south_america|south_america,latin_america,hispanic
guatemala|guatemala;guatemalan;危地马拉|guatemala city|north_america|central_america,latin_america,hispanic
honduras|honduras;honduran;洪都拉斯||north_america|central_america,latin_america,hispanic
nicaragua|nicaragua;nicaraguan;尼加拉瓜||north_america|central_america,latin_america,hispanic
panama|panama;panamanian;巴拿马||north_america|central_america,latin_america,hispanic
el_salvador|el salvador;salvadoran;salvadorian;萨尔瓦多||north_america|central_america,latin_america,hispanic
cuba|cuba;cuban;cubans;古巴|havana|north_america|caribbean,latin_america,hispanic
dominican_republic|dominican republic;dominican;多米尼加||north_america|caribbean,latin_america,hispanic
puerto_rico|puerto rico;puerto rican;波多黎各||north_america|caribbean,latin_america,hispanic
jamaica|jamaica;jamaican;jamaicans;牙买加||north_america|caribbean,anglophone
haiti|haiti;haitian||north_america|caribbean
spain|spain;spaniard;spaniards;西班牙|madrid;barcelona;flamenco|europe|western_europe,mediterranean,hispanic
portugal|portugal;portuguese;葡萄牙|lisbon|europe|western_europe,mediterranean,lusophone
france|france;french;frenchman;frenchwoman;法国|paris|europe|western_europe
germany|germany;german;germans;德国|berlin;munich|europe|western_europe
italy|italy;italian;italians;意大利|rome;milan|europe|western_europe,mediterranean
netherlands|netherlands;dutch;holland;荷兰||europe|western_europe
belgium|belgium;belgian;比利时||europe|western_europe
switzerland|switzerland;swiss;瑞士||europe|western_europe
austria|austria;austrian;奥地利||europe|western_europe
sweden|sweden;swedish;swede;swedes;瑞典||europe|northern_europe,nordic,scandinavia
norway|norway;norwegian;norwegians;挪威||europe|northern_europe,nordic,scandinavia
denmark|denmark;danish;dane;danes;丹麦||europe|northern_europe,nordic,scandinavia
iceland|iceland;icelandic;冰岛||europe|northern_europe,nordic
estonia|estonia;estonian;爱沙尼亚||europe|northern_europe,eastern_europe,post_soviet
latvia|latvia;latvian;拉脱维亚||europe|northern_europe,eastern_europe,post_soviet
lithuania|lithuania;lithuanian;立陶宛||europe|northern_europe,eastern_europe,post_soviet
poland|poland;^Polish;^Pole;^Poles;波兰||europe|eastern_europe,slavic
russia|russia;russian;russians;俄罗斯|moscow|europe|eastern_europe,slavic,post_soviet
belarus|belarus;belarusian;白俄罗斯||europe|eastern_europe,slavic,post_soviet
moldova|moldova;moldovan;摩尔多瓦||europe|eastern_europe,post_soviet
romania|romania;romanian;罗马尼亚||europe|eastern_europe
bulgaria|bulgaria;bulgarian;保加利亚||europe|eastern_europe,slavic
serbia|serbia;serbian;serb;serbs;塞尔维亚||europe|eastern_europe,slavic,balkan
croatia|croatia;croatian;croat;克罗地亚||europe|eastern_europe,slavic,balkan
bosnia|bosnia;bosnian||europe|eastern_europe,slavic,balkan
slovenia|slovenia;slovenian;slovene||europe|eastern_europe,slavic
slovakia|slovakia;slovak;slovakian;斯洛伐克||europe|eastern_europe,slavic
czechia|czech republic;czechia;czech;捷克||europe|eastern_europe,slavic
hungary|hungary;hungarian;匈牙利||europe|eastern_europe
greece|greece;greek;greeks;希腊|athens|europe|mediterranean
georgia|georgian;tbilisi;格鲁吉亚||asia|post_soviet,caucasus
armenia|armenia;armenian;亚美尼亚||asia|post_soviet,caucasus
azerbaijan|azerbaijan;azerbaijani||asia|post_soviet,caucasus
kazakhstan|kazakhstan;kazakh;哈萨克斯坦||asia|central_asia,post_soviet
uzbekistan|uzbekistan;uzbek;乌兹别克斯坦||asia|central_asia,post_soviet
turkey|^Turkey;türkiye;turkish;turks;土耳其|istanbul|asia|middle_east,mediterranean
israel|israel;israeli;israelis;以色列|tel aviv;jerusalem|asia|middle_east
iran|iran;iranian;persian;伊朗||asia|middle_east
iraq|iraq;iraqi;伊拉克||asia|middle_east,arab
saudi_arabia|saudi arabia;saudi;saudis;沙特||asia|middle_east,arab
united_arab_emirates|united arab emirates;uae;emirati;阿联酋|dubai;abu dhabi|asia|middle_east,arab
egypt|egypt;egyptian;egyptians;埃及|cairo|africa|north_africa,arab,middle_east
lebanon|lebanon;lebanese;黎巴嫩||asia|middle_east,arab
syria|syria;syrian;叙利亚||asia|middle_east,arab
jordan|jordanian||asia|middle_east,arab
pakistan|pakistan;pakistani;巴基斯坦||asia|south_asia
india|india;indian;indians;印度|mumbai;delhi;bollywood|asia|south_asia
bangladesh|bangladesh;bangladeshi;孟加拉||asia|south_asia
sri_lanka|sri lanka;sri lankan;斯里兰卡||asia|south_asia
nepal|nepal;nepali;nepalese;尼泊尔||asia|south_asia
afghanistan|afghanistan;afghan;阿富汗||asia|south_asia,central_asia
china|^China;chinese;中国|beijing;shanghai|asia|east_asia
taiwan|taiwan;taiwanese;台湾||asia|east_asia
mongolia|mongolia;mongolian||asia|east_asia,central_asia
vietnam|vietnam;viet nam;vietnamese;越南||asia|southeast_asia
thailand|thailand;thai;泰国||asia|southeast_asia
philippines|philippines;filipino;filipina;filipinos;菲律宾||asia|southeast_asia
indonesia|indonesia;indonesian;印度尼西亚;印尼||asia|southeast_asia
malaysia|malaysia;malaysian;马来西亚||asia|southeast_asia
singapore|singapore;singaporean;新加坡||asia|southeast_asia
cambodia|cambodia;cambodian;柬埔寨||asia|southeast_asia
myanmar|myanmar;burma;burmese;缅甸||asia|southeast_asia
laos|laos;lao;laotian||asia|southeast_asia
nigeria|nigeria;nigerian;nigerians;尼日利亚|lagos|africa|west_africa,sub_saharan
ghana|ghana;ghanaian||africa|west_africa,sub_saharan
senegal|senegal;senegalese;塞内加尔||africa|west_africa,sub_saharan
ivory_coast|ivory coast;côte d'ivoire;ivorian||africa|west_africa,sub_saharan
kenya|kenya;kenyan;kenyans;肯尼亚|nairobi|africa|east_africa,sub_saharan
ethiopia|ethiopia;ethiopian;埃塞俄比亚||africa|east_africa,sub_saharan
tanzania|tanzania;tanzanian;坦桑尼亚||africa|east_africa,sub_saharan
uganda|uganda;ugandan;乌干达||africa|east_africa,sub_saharan
rwanda|rwanda;rwandan;卢旺达||africa|east_africa,sub_saharan
somalia|somalia;somali;索马里||africa|east_africa,sub_saharan
zimbabwe|zimbabwe;zimbabwean;津巴布韦||africa|southern_africa,sub_saharan
zambia|zambia;zambian;赞比亚||africa|southern_africa,sub_saharan
botswana|botswana;motswana;博茨瓦纳||africa|southern_africa,sub_saharan
namibia|namibia;namibian;纳米比亚||africa|southern_africa,sub_saharan
mozambique|mozambique;mozambican;莫桑比克||africa|southern_africa,sub_saharan,lusophone
angola|angola;angolan;安哥拉||africa|southern_africa,sub_saharan,lusophone
lesotho|lesotho;basotho||africa|southern_africa,sub_saharan
eswatini|eswatini;swaziland;swazi||africa|southern_africa,sub_saharan
cameroon|cameroon;cameroonian;喀麦隆||africa|sub_saharan
congo|congo;congolese;刚果||africa|sub_saharan
madagascar|madagascar;malagasy;马达加斯加||africa|sub_saharan
algeria|algeria;algerian;阿尔及利亚||africa|north_africa,arab,maghreb
tunisia|tunisia;tunisian;突尼斯||africa|north_africa,arab,maghreb
libya|libya;libyan||africa|north_africa,arab
sudan|sudan;sudanese||africa|north_africa,arab
fiji|fiji;fijian;斐济||oceania|oceania,polynesia
samoa|samoa;samoan;萨摩亚||oceania|oceania,polynesia
tonga|tonga;tongan||oceania|oceania,polynesia
papua_new_guinea|papua new guinea;papuan||oceania|oceania
"""

# Coarse group words for Country items: term forms -> region tag or continent.
_COARSE = """
south_america|south american;south americans;south america
latin_america|latin american;latin americans;latin america;latino;latina;latinos;latinas;latinx
hispanic|hispanic;hispanics;spanish-speaking;spanish speaking;spanish;castilian
central_america|central american;central americans;central america
caribbean|caribbean
east_asia|east asian;east asians;east asia
southeast_asia|southeast asian;south-east asian;southeast asia
south_asia|south asian;south asians;south asia;desi
middle_east|middle eastern;middle east
arab|arab;arabs;arabic
eastern_europe|eastern european;eastern europeans;eastern europe;east european
slavic|slavic;slav;slavs
post_soviet|post-soviet;soviet;former soviet;ussr
western_europe|western european;western europe
northern_europe|northern european;northern europe
nordic|nordic
scandinavia|scandinavian;scandinavians;scandinavia
celtic|celtic;gaelic;celt;celts
british_isles|british isles
mediterranean|mediterranean
balkan|balkan;balkans
caucasus|caucasus;caucasian region
central_asia|central asian;central asia
southern_africa|southern african;southern africa
sub_saharan|sub-saharan;subsaharan
north_africa|north african;north africa
maghreb|maghreb;maghrebi
west_africa|west african;west africa
east_africa|east african;east africa
polynesia|polynesian;polynesia;pacific islander;pacific islanders;pacific island
australasia|australasian;australasia;antipodean;antipodes
anglophone|anglophone;english-speaking;english speaking
lusophone|lusophone;portuguese-speaking
oceania|oceania;oceanian;south pacific
europe|^EU;european union;欧盟
"""

# Continent value forms (also coarse terms for Country items).
_CONTINENTS = {
    'africa': 'africa;african;africans;非洲',
    'asia': 'asia;asian;asians;亚洲',
    'europe': 'europe;european;europeans;欧洲',
    'north_america': 'north america;north american;north americans;北美;北美洲',
    'south_america': 'south america;south american;south americans;南美;南美洲',
    'oceania': 'oceania;oceanian;australasia;australasian;大洋洲',
    'antarctica': 'antarctica;antarctic;south pole;mcmurdo;polar research station;research station in antarctica;南极;南极洲',
    'arctic': 'arctic;north pole;arctic circle;北极',  # v2: a wrong location for Antarctica items ("North Pole")
}
_REGION_TO_CONTINENT = {
    'south_america': {'south_america'}, 'central_america': {'north_america'}, 'caribbean': {'north_america'},
    'latin_america': {'south_america', 'north_america'}, 'hispanic': {'south_america', 'north_america', 'europe'},
    'east_asia': {'asia'}, 'southeast_asia': {'asia'}, 'south_asia': {'asia'}, 'central_asia': {'asia'},
    'middle_east': {'asia'}, 'arab': {'asia', 'africa'}, 'eastern_europe': {'europe'}, 'slavic': {'europe'},
    'post_soviet': {'europe', 'asia'}, 'western_europe': {'europe'}, 'northern_europe': {'europe'},
    'nordic': {'europe'}, 'scandinavia': {'europe'}, 'celtic': {'europe'}, 'british_isles': {'europe'},
    'mediterranean': {'europe', 'africa', 'asia'}, 'balkan': {'europe'}, 'caucasus': {'asia', 'europe'},
    'southern_africa': {'africa'}, 'sub_saharan': {'africa'}, 'north_africa': {'africa'}, 'maghreb': {'africa'},
    'west_africa': {'africa'}, 'east_africa': {'africa'}, 'polynesia': {'oceania'}, 'australasia': {'oceania'},
    'anglophone': {'europe', 'north_america', 'oceania', 'africa'}, 'lusophone': {'europe', 'south_america', 'africa'},
    'oceania': {'oceania'}, 'europe': {'europe'},
}

# Closed classes: value -> (exact forms, cue forms). Display names follow WSB (underscore -> space).
_CLOSED = {
    'Gender': {
        'male': ('male;males;man;men;masculine;masculinity;guy;guys;gentleman;gentlemen;boy;boys;dude;bloke;lad;'
                 'mr;mr.;sir;husband;father;dad;son;brother;boyfriend;manly;he;him;his;himself;男性;男人;男子', ''),
        'female': ('female;females;woman;women;feminine;femininity;lady;ladies;girl;girls;gal;mrs;mrs.;ms;ms.;'
                   'madam;wife;mother;mom;mum;daughter;sister;girlfriend;bride;womanhood;she;her;hers;herself;女性;女人;女子;女士', ''),
        'nonbinary': ('nonbinary;non-binary;non binary;enby;genderqueer;they/them', ''),
        'genderfluid': ('genderfluid;gender-fluid;gender fluid', ''),
        'agender': ('agender', ''),
    },
    'Occupation': {
        'fisherman': ('fisherman;fishermen;fisherwoman;fisherwomen;fisher;fishers;commercial fishing;'
                      'fishing industry;fishing trade;fishing boat captain;trawlerman;trawlermen;deckhand;fisherfolk;渔民;渔夫',
                      'fishing;fishing boat;fishing nets;nets;trawler;angler;anglers;catch of the day;tides;seafaring;捕鱼;渔船'),
        'locksmith': ('locksmith;locksmiths;locksmithing;lockpicking;lock picking;lockpick;key cutting;keysmith;锁匠',
                      'lock;locks;locked out;keys;key duplication;deadbolt;padlock;开锁;配钥匙'),
        'flight_attendant': ('flight attendant;flight attendants;cabin crew;stewardess;stewardesses;steward;'
                             'air hostess;air steward;airline crew;purser;空乘;空姐;乘务员;空服;空服员',
                             'in-flight;inflight;airline;airlines;aircraft;passengers;passenger;turbulence;cabin service'),
        'anthropologist': ('anthropologist;anthropologists;anthropology;anthropological;ethnographer;ethnographers;'
                           'ethnography;ethnographic;ethnologist;人类学;人类学家', 'fieldwork;cultural research'),
        'nurse': ('nurse;nurses;nursing;护士', ''),
        'electrician': ('electrician;electricians;electrical contractor;电工', 'wiring'),
        'librarian': ('librarian;librarians;library science;图书管理员', 'library'),
        'chef': ('chef;chefs;sous chef;head chef;culinary professional;line cook;厨师', 'culinary;kitchen'),
    },
    'Continent': {},  # filled from _CONTINENTS
    'Country': {},  # filled from _COUNTRIES
    'MaritalStatus': {
        # v2: no bare "single" ("a single sofa", "no single rule"); marital phrases only
        'single': ('being single;single person;single people;single adult;single adults;single man;'
                   'single woman;single men;single women;single guy;single gal;single life;single lifestyle;'
                   'single status;you are single;you\'re single;you’re single;i\'m single;i’m single;i am single;'
                   'still single;stay single;staying single;remain single;remaining single;single living;'
                   'unmarried;never married;never-married;bachelor;bachelorette;unattached;not married;'
                   'spinster;living single;单身;未婚', ''),
        'married': ('married;wedded;newlywed;newlyweds;matrimony;matrimonial;marital bliss;已婚', ''),
        'widowed': ('widowed;widow;widows;widower;widowers;widowhood;late husband;late wife;late spouse;late partner;'
                    'bereaved spouse;lost her husband;lost his wife;lost their spouse;lost my spouse;spouse died;'
                    'spouse passed away;death of a spouse;death of their spouse;'
                    'spouse has passed away;spouse has passed;partner has passed away;partner passed away;'
                    'partner has passed;husband passed away;husband has passed away;wife passed away;'
                    'wife has passed away;husband died;wife died;partner died;partner dies;spouse dies;'
                    'loss of a spouse;loss of my spouse;loss of your spouse;loss of their spouse;losing a spouse;'
                    'losing my spouse;losing your spouse;death of my spouse;death of your spouse;'
                    'death of a partner;death of my partner;death of your partner;'
                    'spouse\'s death;spouse’s death;partner\'s death;partner’s death;husband\'s death;husband’s death;'
                    'wife\'s death;wife’s death;spouse\'s passing;spouse’s passing;partner\'s passing;partner’s passing;'
                    '丧偶;寡妇;鳏夫;遗孀', 'bereavement;bereaved;grieving spouse'),
        'divorced': ('divorced;divorce;divorcee;divorcée;divorces;ex-husband;ex-wife;ex-spouse;ex husband;ex wife;'
                     'marriage ended;failed marriage;post-divorce;离婚;离异', 'custody;alimony'),
        # v2: no bare "engaged" / "engagement" ("stay engaged", "rules of engagement")
        'engaged': ('engaged couple;engaged couples;newly engaged;recently engaged;just got engaged;got engaged;'
                    'getting engaged;engaged to be married;engagement ring;engagement party;'
                    'fiancé;fiancée;fiance;fiancee;betrothed;订婚;未婚夫;未婚妻', ''),
        # v2: no bare "separated" / "separation" ("a separation from your daily routine")
        'separated': ('legally separated;recently separated;newly separated;trial separation;marital separation;'
                      'separated from my spouse;separated from your spouse;separated from their spouse;'
                      'separated from her husband;separated from his wife;estranged spouse;estranged husband;'
                      'estranged wife;分居', ''),
    },
    'PetOwnership': {
        'cat': ('cat;cats;kitten;kittens;kitty;feline;felines;tabby;litter box;catnip;猫;猫咪;小猫;猫砂',
                'purr;purrs;purring;meow;whiskers'),
        'dog': ('dog;dogs;puppy;puppies;pup;canine;canines;pooch;doggy;doggo;hound;狗;狗狗;小狗;遛狗',
                'leash;dog walker;fetch;bark;barking'),
        'bird': ('bird;birds;parrot;parrots;budgie;canary;parakeet;avian;cockatiel;鹦鹉', ''),
        'fish': ('fish;goldfish;aquarium;fish tank;betta;金鱼;鱼缸', ''),
        'rabbit': ('rabbit;rabbits;bunny;bunnies;兔子', ''),
        'horse': ('horse;horses;pony;ponies;equine;equestrian', ''),
    },
    'EmploymentStatus': {
        # v2: no bare "full-time" ("full-time homemaker", "full-time student", "full-time chef")
        'employed_full_time': ('full-time job;full-time jobs;full time job;full-time employee;full-time employees;'
                               'full-time employment;employed full-time;employed full time;working full-time;'
                               'working full time;work full-time;work full time;works full-time;works full time;'
                               'full-time work;full-time worker;full-time workers;full-time position;full-time role;'
                               'full-time career;full-time employed;full time employed;full-time income;'
                               'full-time salary;full-time paycheck;full-time remote employee;full-time remote worker;'
                               'full-time hours;full-time staff;full-time professional;full-time professionals;'
                               'full-time basis;nine-to-five;9-to-5;9 to 5;salaried;office job;全职工作;全职员工', ''),
        # v2: building-trade contractors are stop forms
        'freelancer': ('freelancer;freelancers;freelance;freelancing;independent contractor;independent contractors;'
                       'contractor;contractors;gig worker;gig work;gig economy;contract work;自由职业;自由职业者', ''),
        'homemaker': ('homemaker;homemakers;housewife;househusband;stay-at-home;stay at home parent;'
                      'stay-at-home parent;stay-at-home mom;stay-at-home dad;homemaking;家庭主妇;主妇;全职妈妈;'
                      '全职太太;家庭主夫', 'housekeeping;household management'),
        # v2: no bare "retirement" ("retirement savings")
        'retired': ('retired;retiree;retirees;pensioner;pensioners;in retirement;已退休;退休人员', ''),
        'student': ('student;students;学生;大学生', ''),
        'unemployed': ('unemployed;unemployment;jobless;out of work;between jobs;job seeker;job-seeker;失业', ''),
        'self-employed': ('self-employed;self employed;business owner;small business owner;owns a business;'
                          'runs their own business;entrepreneur', ''),
    },
    'ReligiousAffiliation': {
        # v2: generic or shared cues dropped (temple, meditation, mindfulness, karma, dharma, monk(s), bare zen)
        'buddhism': ('buddhism;buddhist;buddhists;buddha;佛教;佛教徒;佛陀;佛法',
                     'sangha;nirvana;zen practitioner;zen practice;zen temple;zen temples;zen master;zen monk;'
                     'zen monks;zen meditation;zen center;zen centre;zen tradition;zen teacher;zen teachings;'
                     'theravada;mahayana;vipassana;bodhisattva;sutra;sutras;dalai lama;禅宗'),
        'agnostic': ('agnostic;agnostics;agnosticism;不可知论;不可知论者', 'uncertain about god'),
        # v2: "secular" dropped; non-believer etc. are coarse (atheist or agnostic), see _CLASS_COARSE
        'atheist': ('atheist;atheists;atheism;无神论;无神论者', ''),
        'christianity': ('christianity;christian;christians;catholic;protestant;evangelical;church;jesus;christ;bible;'
                         '基督教;基督徒;天主教', ''),
        'islam': ('islam;islamic;muslim;muslims;moslem;quran;koran;mosque;allah;ramadan;imam;伊斯兰;伊斯兰教;穆斯林;清真寺',
                  'eid;hijab;prayer mat'),
        'hinduism': ('hinduism;hindu;hindus;krishna;shiva;vishnu;vedic;印度教;印度教徒', 'diwali;puja'),
    },
    'Religion': {},  # filled from ReligiousAffiliation + judaism / sikhism below
    'Diets': {
        'halal': ('halal;zabiha;dhabiha;pork-free;no pork;islamic dietary;清真', 'muslim;muslims;islamic;穆斯林'),
        'vegan': ('vegan;vegans;veganism;plant-based;纯素;纯素食;纯素食者', ''),
        'vegetarian': ('vegetarian;vegetarians;vegetarianism;meatless;素食;素食者;吃素', ''),
        'kosher': ('kosher;kashrut;洁食;犹太洁食', 'jewish'),
        'pescatarian': ('pescatarian;pescetarian;pescatarians', ''),
    },
    'AgeGroup': {
        '56-65': ('56-65;56–65;late fifties;early sixties;sixties;60s;baby boomer;baby boomers;boomer;boomers;'
                  'senior;seniors;older adult;older adults;elderly;near retirement;retirement age', ''),
        '18-25': ('18-25;18–25;young adult;young adults;early twenties;gen z;college-age;college age', ''),
        '26-35': ('26-35;26–35;late twenties;early thirties;millennial;millennials', ''),
        '36-45': ('36-45;36–45;late thirties;early forties', ''),
        '46-55': ('46-55;46–55;late forties;early fifties', ''),
    },
}
_RELIGION_EXTRA = {
    'judaism': ('judaism;jewish;jew;jews;synagogue;torah;rabbi;shabbat;犹太教', ''),
    'sikhism': ('sikhism;sikh;sikhs;gurdwara;guru nanak', ''),
}
# Ambiguous age terms (cover two buckets) are coarse terms.
_AGE_COARSE = {'fifties;50s': {'46-55', '56-65'}, 'middle-aged;middle aged;middle age': {'36-45', '46-55', '56-65'},
               'forties;40s': {'36-45', '46-55'}, 'thirties;30s': {'26-35', '36-45'}, 'twenties;20s': {'18-25', '26-35'}}
# v2: coarse terms of closed classes (cover several values): gold in cover & a distractor in cover -> ambiguous.
_NONBELIEF = 'non-believer;nonbeliever;non-believers;nonbelievers;irreligious;nonreligious;non-religious;no religion;not religious'
_CLASS_COARSE = {
    'MaritalStatus': {'single parent;single parents;single mother;single mothers;single father;single fathers;'
                      'single mom;single moms;single dad;single dads;single-parent;single parenthood;solo parent':
                      {'single', 'divorced', 'widowed', 'separated'},
                      # a partnership that ended: not the never-partnered "single"
                      'newly single;single again;recently single;suddenly single': {'divorced', 'widowed', 'separated'}},
    'ReligiousAffiliation': {_NONBELIEF: {'atheist', 'agnostic'}},
    'Religion': {_NONBELIEF: {'atheist', 'agnostic'}},
}
# v2: stop forms: matched (leftmost-longest) and ignored, so their parts are not read as values.
_STOP = ('hot dog;hot dogs;early bird;early birds;bird\'s-eye;bird’s-eye;birds-eye;fish and chips;fish tacos;fish taco;'
         'fish sauce;fish oil;general contractor;general contractors;building contractor;roofing contractor;'
         'plumbing contractor;licensed contractor;hire a contractor;hiring a contractor;熊猫;猫头鹰;夜猫子;热狗;狗仔;仿佛')
# v2: context exclusions on the normalized surface: (surface regex, previous-text regex, next-text regex)
_CONTEXT_EXCLUDE = [
    (re.compile(r'^single\b'), re.compile(r'(?:\bevery|\bnot\s+a|\bno|\bany|\bwithout\s+a)\s+$', re.I), None),
    (re.compile(r'single$'), None, re.compile(r'^-')),
    (re.compile(r'^chile$'), None, re.compile(r'^\s+(?:con|relleno|rellenos|pepper|peppers|peperadas|powder|sauce|verde|'
                                              r'colorado|de\s+arbol)\b', re.I)),
]
CASE_SENSITIVE: set = set()  # normalized forms written with a leading ^ (filled by tables())

_FRAMES = {
    'Country': 'nationality;nationalities;national identity;country;countries;home country;homeland;country of origin;'
               'heritage;cultural background;cultural heritage;ethnicity;ethnic;ancestry;ancestral;origin;origins;'
               'native;citizenship;citizen;immigrant;expat;expatriate;birthplace;born in;hometown',
    'Continent': 'continent;continents;region;regional;geographic;geography;location;locale;hemisphere;'
                 'where the user lives;place of residence;residence;lives in',
    'Gender': 'gender;genders;gendered;sex;pronoun;pronouns;gender identity',
    'Occupation': 'occupation;occupational;profession;professional;job;jobs;career;careers;works as;worker;'
                  'trade;vocation;livelihood;employment;employed;employer;workplace',
    'MaritalStatus': 'marital status;marital;relationship status;relationship;relationships;partner;spouse;'
                     'husband;wife;romantic;dating;love life',
    'PetOwnership': 'pet;pets;pet owner;pet ownership;animal companion;companion animal;animal;animals;'
                    'veterinarian;vet;pet care',
    'EmploymentStatus': 'employment status;employment;work status;job status;working;job;career;occupation;'
                        'profession;workplace;employer;income',
    'ReligiousAffiliation': 'religion;religious;religiosity;faith;faiths;spiritual;spirituality;belief;beliefs;'
                            'worship;sacred;devout;creed;belief system;worldview',
    'Religion': 'religion;religious;faith;spiritual;spirituality;belief;beliefs;worship;sacred;devout;prayer;pray;'
                'praying',
    'Diets': 'diet;diets;dietary;dietary restrictions;food restrictions;eating habits;food choices;cuisine;'
             'meal;meals;food',
    'AgeGroup': 'age;aged;ages;years old;year-old;generation;generational;life stage;older;younger;age group',
}
PRONOUNS = {'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself', 'they/them'}
# Other values of the open-ish classes (wrong filler = other_value when named instead of the gold).
_OTHER_OCCUPATIONS = (
    'teacher;teachers;professor;lecturer;tutor;doctor;physician;surgeon;dentist;pharmacist;veterinarian;paramedic;'
    'engineer;software engineer;software developer;programmer;developer;data scientist;scientist;researcher;'
    'biologist;chemist;physicist;geologist;archaeologist;historian;sociologist;psychologist;economist;linguist;'
    'lawyer;attorney;judge;accountant;banker;financial analyst;consultant;manager;executive;ceo;entrepreneur;'
    'salesperson;sales representative;marketer;cashier;clerk;secretary;receptionist;administrator;'
    'farmer;rancher;cowboy;gardener;landscaper;florist;miner;logger;lumberjack;hunter;forester;park ranger;'
    'carpenter;plumber;mechanic;welder;builder;construction worker;bricklayer;roofer;painter;handyman;technician;'
    'pilot;sailor;captain;boat captain;sea captain;mariner;navigator;dockworker;longshoreman;truck driver;'
    'taxi driver;driver;courier;delivery driver;bus driver;train conductor;'
    'soldier;police officer;policeman;detective;firefighter;security guard;guard;bodyguard;'
    'writer;author;novelist;poet;journalist;reporter;editor;photographer;filmmaker;director;actor;actress;'
    'musician;singer;songwriter;composer;dancer;artist;sculptor;designer;architect;illustrator;'
    'cook;baker;butcher;waiter;waitress;bartender;barista;sommelier;caterer;'
    'athlete;coach;personal trainer;fitness trainer;bodybuilder;'
    'priest;pastor;minister;monk;nun;missionary;imam;rabbi;'
    'social worker;counselor;therapist;caregiver;nanny;babysitter;housekeeper;janitor;cleaner;'
    'tour guide;travel agent;hotel manager;diplomat;politician;civil servant;translator;interpreter;'
    'fishmonger;shopkeeper;merchant;trader;tailor;seamstress;blacksmith;jeweler;watchmaker;'
    'security consultant;burglar;thief;safecracker;inventor;explorer;adventurer;archivist;curator;'
    'museum curator;flight engineer;air traffic controller;astronaut;sailor;fisheries officer;marine biologist;'
    'oceanographer;ship captain;boatswain;stevedore')
_OTHER_EMPLOYMENT = 'part-time;part time;employed part-time;seasonal worker;intern;internship;on leave;disabled'
_OTHER_PETS = 'hamster;hamsters;guinea pig;guinea pigs;reptile;snake;lizard;turtle;tortoise;ferret;parrot owner'
_OTHER_DIETS = 'keto;ketogenic;paleo;gluten-free;gluten free;low-carb;low carb;dairy-free;lactose-free'


def _split(s):
    out = []
    for x in s.split(';'):
        x = x.strip()
        if x.startswith('^'):  # v2: case-sensitive form
            x = x[1:]
            CASE_SENSITIVE.add(_norm(x))
        if x:
            out.append(x)
    return out


def _is_cjk(form: str) -> bool:
    return any('\u3400' <= ch <= '\u9fff' for ch in form)


@lru_cache(maxsize=1)
def tables():
    """-> (values, coarse, countries): values[class][value] = [(form, kind)], coarse[class] = [(form, cover set)]."""
    countries = {}
    for line in _COUNTRIES.strip().splitlines():
        key, forms, cues, cont, tags = line.split('|')
        countries[key] = {'forms': _split(forms), 'cues': _split(cues), 'continent': cont,
                          'tags': set(t for t in tags.split(',') if t)}
    values = {cls: {} for cls in _CLOSED}
    for cls, d in _CLOSED.items():
        for v, (exact, cue) in d.items():
            values[cls][v] = ([(f, 'pronoun' if f in PRONOUNS else 'exact') for f in _split(exact)]
                              + [(f, 'cue') for f in _split(cue)])
    for v in _split(_OTHER_OCCUPATIONS):
        values['Occupation'].setdefault(v, [(v, 'exact')])
    for v in _split(_OTHER_EMPLOYMENT):
        values['EmploymentStatus'].setdefault(v, [(v, 'exact')])
    for v in _split(_OTHER_PETS):
        values['PetOwnership'].setdefault(v, [(v, 'exact')])
    for v in _split(_OTHER_DIETS):
        values['Diets'].setdefault(v, [(v, 'exact')])
    for v, d in _RELIGION_EXTRA.items():
        values['Religion'][v] = [(f, 'exact') for f in _split(d[0])]
    for v, forms in values['ReligiousAffiliation'].items():
        values['Religion'].setdefault(v, forms)
    for v, c in countries.items():
        values['Country'][v] = [(f, 'exact') for f in c['forms']] + [(f, 'cue') for f in c['cues']]
    for v, forms in _CONTINENTS.items():
        values['Continent'][v] = [(f, 'exact') for f in _split(forms)]
    coarse = {cls: [] for cls in values}
    by_tag = {}
    for v, c in countries.items():
        for t in c['tags'] | {c['continent']}:
            by_tag.setdefault(t, set()).add(v)
    for line in _COARSE.strip().splitlines():
        tag, forms = line.split('|')
        for f in _split(forms):
            coarse['Country'].append((f, frozenset(by_tag.get(tag, set()))))
            coarse['Continent'].append((f, frozenset(_REGION_TO_CONTINENT.get(tag, set()))))
    for cont, forms in _CONTINENTS.items():
        for f in _split(forms):
            coarse['Country'].append((f, frozenset(by_tag.get(cont, set()))))
    # countries are finer, consistent-or-not terms for Continent items
    for v, c in countries.items():
        for f in c['forms'] + c['cues']:
            coarse['Continent'].append((f, frozenset({c['continent']})))
    for forms, cover in _AGE_COARSE.items():
        for f in _split(forms):
            coarse['AgeGroup'].append((f, frozenset(cover)))
    for cls, d in _CLASS_COARSE.items():
        for forms, cover in d.items():
            for f in _split(forms):
                coarse[cls].append((f, frozenset(cover)))
    return values, coarse, countries


def _norm(form: str) -> str:
    return re.sub(r'[\s\-]+', ' ', form.lower()).strip()


def _pattern(form: str, lower: bool = True) -> str:
    form = form.lower().strip() if lower else form.strip()
    return r'[\s\-]+'.join(re.escape(part) for part in re.split(r'[\s\-]+', form))


@lru_cache(maxsize=None)
def compiled(cls: str):
    """One leftmost-longest alternation over every form relevant to an item of class `cls`.
    -> (regex, lookup normalized-surface -> (kind, payload))."""
    values, coarse, _ = tables()
    entries = []
    for c, vals in values.items():
        for v, forms in vals.items():
            for f, kind in forms:
                if c == cls:
                    entries.append((f, 'value', (v, kind)))
                elif not (c == 'Religion' and cls == 'ReligiousAffiliation') and \
                        not (c == 'ReligiousAffiliation' and cls == 'Religion') and \
                        not (c in ('Country', 'Continent') and cls in ('Country', 'Continent')):
                    entries.append((f, 'other_class', (c, v, 'pronoun' if f in PRONOUNS else kind)))
    for f, cover in coarse.get(cls, []):
        entries.append((f, 'coarse', cover))
    for f in _split(_FRAMES.get(cls, '')):
        entries.append((f, 'frame', None))
    for f in _split(_STOP):
        entries.append((f, 'stop', None))
    # same surface listed twice: stop beats value beats coarse beats the class's own frame beats another class's value
    rank = {'stop': -1, 'value': 0, 'coarse': 1, 'frame': 2, 'other_class': 3}
    best = {}
    for f, kind, payload in entries:
        k = _norm(f)
        if k not in best or rank[kind] < rank[best[k][1]]:
            best[k] = (f, kind, payload)
    forms = sorted(best.values(), key=lambda e: -len(e[0]))
    ci = [f for f, _, _ in forms if not _is_cjk(f) and _norm(f) not in CASE_SENSITIVE]
    cs = [f for f, _, _ in forms if not _is_cjk(f) and _norm(f) in CASE_SENSITIVE]
    cj = [f for f, _, _ in forms if _is_cjk(f)]
    # word boundary = not next to a non-CJK word character (v2: a CJK character next to an English form is a boundary,
    # e.g. "宠物dog")
    lb, la = r'(?<![^\W\u3400-\u9fff])', r'(?![^\W\u3400-\u9fff])'
    rxs = [re.compile(lb + r'(?:' + '|'.join(_pattern(f) for f in ci) + r')' + la, re.I)]
    if cs:
        rxs.append(re.compile(lb + r'(?:' + '|'.join(_pattern(f, lower=False) for f in cs) + r')' + la))
    if cj:  # CJK has no word boundaries; longest first
        rxs.append(re.compile('|'.join(re.escape(f) for f in cj)))
    return rxs, {k: (kind, payload) for k, (f, kind, payload) in best.items()}


def _excluded(text: str, s: int, e: int, norm: str) -> bool:
    for surf_rx, prev_rx, next_rx in _CONTEXT_EXCLUDE:
        if surf_rx.search(norm) and ((prev_rx and prev_rx.search(text[max(0, s - 24):s]))
                                     or (next_rx and next_rx.search(text[e:e + 24]))):
            return True
    return False


def find_matches(text: str, cls: str):
    """Leftmost-longest, non-overlapping matches over the case-insensitive, case-sensitive and CJK
    alternations: [(start, end, surface, kind, payload)]. Stop forms consume text and are dropped."""
    rxs, lookup = compiled(cls)
    cands = []
    for rx in rxs:
        for m in rx.finditer(text):
            norm = _norm(m.group(0))
            if not _excluded(text, m.start(), m.end(), norm):
                cands.append((m.start(), m.end(), m.group(0), norm))
    cands.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    out, last = [], 0
    for s, e, surf, norm in cands:
        if s < last:
            continue
        last = e
        kind, payload = lookup[norm]
        if kind != 'stop':
            out.append((s, e, surf, kind, payload))
    return out


def _fold(text: str) -> str:
    """Lower case without diacritics (Maori == M\u0101ori), for the in-prompt echo check only."""
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(ch))


def _stem_in(surface: str, prompt_low: str) -> bool:
    """The matched surface, or its stem (drop up to 3 final chars, keep >= 5), occurs in the prompt.
    `prompt_low` is the _fold()ed prompt; the surface is folded the same way."""
    s = _fold(surface)
    cands = {s}
    if len(s) >= 6:
        cands.add(s[:max(5, len(s) - 3)])
    return any(c in prompt_low for c in cands)


def label_bullet(text: str, cls: str, gold: str, distractors, prompt: str) -> dict:
    """Label one bullet for an item: see the module docstring."""
    keys = tables()[0][cls]
    canon = lambda v: v if v in keys else v.replace(' ', '_')  # noqa: E731  WSB displays snake_case ids with spaces
    gold, dset = canon(gold), {canon(d) for d in distractors}
    missing = ({gold} | dset) - set(keys)
    if missing:
        raise KeyError(f'{cls}: values without lexicon entries: {sorted(missing)}')
    prompt_low = _fold(prompt)
    gold_hits, wrong_hits, amb, frames, other_class = [], [], [], [], []
    for s, e, surf, kind, payload in find_matches(text, cls):
        if kind == 'value':
            v, vkind = payload
            hit = {'surface': surf, 'value': v, 'kind': vkind, 'span': [s, e],
                   'in_prompt': _stem_in(surf, prompt_low)}
            if v == gold:
                gold_hits.append(hit | {'match': vkind})
            else:
                wrong_hits.append(hit | {'subtype': 'distractor' if v in dset else 'other_value'})
        elif kind == 'coarse':
            cover = payload
            hit = {'surface': surf, 'cover': sorted(cover)[:12], 'kind': 'coarse', 'span': [s, e],
                   'in_prompt': _stem_in(surf, prompt_low)}
            if gold in cover and not (cover & dset):
                gold_hits.append(hit | {'match': 'coarse'})
            elif gold not in cover and cover & dset:
                wrong_hits.append(hit | {'subtype': 'distractor'})
            elif gold not in cover:
                wrong_hits.append(hit | {'subtype': 'other_value'})
            else:
                amb.append(hit)
        elif kind == 'frame':
            frames.append({'surface': surf, 'span': [s, e]})
        else:
            c, v, okind = payload
            other_class.append({'surface': surf, 'class': c, 'value': v, 'kind': okind})
    exact = [h for h in gold_hits if h['match'] == 'exact']
    if gold_hits and wrong_hits:
        label, sub, deciding = 'mixed', None, gold_hits + wrong_hits
    elif exact:
        label, sub, deciding = 'gold_exact', None, exact
    elif gold_hits:
        label, sub, deciding = 'gold_coarse', '+'.join(sorted({h['match'] for h in gold_hits})), gold_hits
    elif wrong_hits:
        label = 'wrong_value'
        sub = 'distractor' if any(h['subtype'] == 'distractor' for h in wrong_hits) else 'other_value'
        deciding = wrong_hits
    elif amb:
        label, sub, deciding = 'ambiguous', None, amb
    elif frames:
        label, sub, deciding = 'frame_only', None, []
    else:
        label, sub, deciding = 'none', None, []
    return {'label': label, 'subtype': sub,
            'match_kinds': sorted({h.get('match') or h.get('kind') for h in deciding}),
            'group': {'gold_exact': 'right', 'gold_coarse': 'right', 'wrong_value': 'wrong',
                      'frame_only': 'frame', 'none': 'none'}.get(label, label),
            'in_prompt': any(h.get('in_prompt') for h in deciding),
            'other_class': bool([o for o in other_class if o['kind'] != 'pronoun']),
            'other_class_pronoun': bool([o for o in other_class if o['kind'] == 'pronoun']),
            'gold_hits': gold_hits, 'wrong_hits': wrong_hits, 'ambiguous': amb, 'frames': frames,
            'other_class_hits': other_class}


def item_context(item: dict, options: tuple[list[str], int]) -> dict:
    """Gold, the 4 WSB distractors and the prompt text for one bank item."""
    opts, gold_pos = options
    distractors = [o for i, o in enumerate(opts) if i + 1 != gold_pos]
    prompt = '\n'.join(m['content'] for m in item['messages'])
    return {'cls': item['attr_class'], 'gold': item['attr'], 'distractors': distractors, 'prompt': prompt}
