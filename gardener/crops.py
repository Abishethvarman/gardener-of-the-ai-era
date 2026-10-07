"""Crop calendar data for monsoon South Asia.

Every window is a number of days relative to the start of a sowing season, and
each region (regions.py) says when its seasons start. There are three kinds of
season:

    wet   warm and rainy: Kharif (India), monsoon sowing (Pakistan),
          Kharif-2 (Bangladesh), Yala and Maha (Sri Lanka), Adi pattam (Tamil Nadu)
    cool  the cool, mostly dry winter after the rains: Rabi
    dry   hot and dry, so plants need watering: Zaid (India), summer vegetables
          (Pakistan), Kharif-1 (Bangladesh), Thai pattam (Tamil Nadu)

Actions:
    nursery     raise seedlings in a tray or nursery bed
    transplant  move nursery seedlings into the bed or grow bag
    sow         sow seed directly where it will grow
    plant       plant cloves, tubers, corms or rhizomes

The offsets were set against published sowing months: Punjab (Pakistan)
agriculture department advisories, Punjab Agricultural University's monthly
operations, Sri Lanka Department of Agriculture crop pages, TNAU season notes
and FAO's homestead calendar for Bangladesh. They are rules of thumb for a home
garden, not a substitute for your local extension office.

`names` are common local names, used for display and by the fact check:
    hi  Hindi / Urdu      bn  Bangla      si  Sinhala
    ta  Tamil             te  Telugu      th  Thai (romanised)
    tl  Tagalog           vi  Vietnamese
`also` lists other English names the fact check should recognise.
`only`, when present, limits a crop to the listed countries.
`days_to_harvest` counts from sowing, or from transplanting for nursery crops
(rules of thumb; varieties differ). `sun` is "full" (6+ hours) or "part"
(3-6 hours). `pot` is the smallest pot that works: small (15 cm deep),
medium (25-30 cm), large (40 cm or more), or None if it needs open ground.
"""

from __future__ import annotations

CROPS: list[dict] = [
    # ---- warm-season crops: monsoon (wet) and summer (dry) ----
    {
        "name": "Okra",
        "days_to_harvest": 50, "sun": "full", "pot": "medium",
        "names": {"hi": "bhindi", "bn": "dherosh", "si": "bandakka", "ta": "vendakkai", "te": "bendakaya", "th": "krachiap mon", "vi": "đậu bắp"},
        "also": ["lady's finger", "ladies finger", "lady finger", "bhendi"],
        "windows": {"wet": {"sow": (-7, 42)}, "dry": {"sow": (0, 42)}},
        "tip": "Soak seed overnight before sowing. Pick pods every two days, while they are finger-length and still snap.",
    },
    {
        "name": "Bottle gourd",
        "days_to_harvest": 60, "sun": "full", "pot": "large",
        "names": {"hi": "lauki", "bn": "lau", "si": "labu", "ta": "surakkai", "te": "sorakaya", "th": "nam tao", "tl": "upo", "vi": "bầu"},
        "also": ["calabash", "dudhi", "ghiya"],
        "windows": {"wet": {"sow": (-7, 42)}, "dry": {"sow": (0, 42)}},
        "tip": "Give it a strong trellis or a roof to climb. Pick the fruit young and glossy.",
    },
    {
        "name": "Bitter gourd",
        "days_to_harvest": 60, "sun": "full", "pot": "large",
        "names": {"hi": "karela", "bn": "korola", "si": "karavila", "ta": "pavakkai", "te": "kakarakaya", "th": "mara", "tl": "ampalaya", "vi": "khổ qua"},
        "also": ["bitter melon"],
        "windows": {"wet": {"sow": (-7, 42)}, "dry": {"sow": (0, 42)}},
        "tip": "Soak seed for a day, because the hard coat slows germination. Train the vine up a trellis.",
    },
    {
        "name": "Ridge gourd",
        "days_to_harvest": 60, "sun": "full", "pot": "large",
        "names": {"hi": "torai", "bn": "jhinga", "si": "wetakolu", "ta": "peerkangai", "te": "beerakaya", "th": "buap liam", "tl": "patola", "vi": "mướp khía"},
        "also": ["turai", "luffa"],
        "windows": {"wet": {"sow": (-7, 42)}, "dry": {"sow": (0, 42)}},
        "tip": "Needs a trellis. Harvest while the ridges are still soft.",
    },
    {
        "name": "Cucumber",
        "days_to_harvest": 50, "sun": "full", "pot": "medium",
        "names": {"hi": "kheera", "bn": "shosha", "si": "pipinna", "ta": "vellarikkai", "te": "dosakaya", "th": "taeng kwa", "tl": "pipino", "vi": "dưa leo"},
        "also": [],
        "windows": {"wet": {"sow": (-7, 35)}, "dry": {"sow": (0, 42)}},
        "tip": "Water at the base in the morning. Wet leaves invite mildew in humid weather.",
    },
    {
        "name": "Pumpkin",
        "days_to_harvest": 100, "sun": "full", "pot": None,
        "names": {"hi": "kaddu", "bn": "mishti kumra", "si": "wattakka", "ta": "parangikai", "te": "gummadikaya", "th": "fak thong", "tl": "kalabasa", "vi": "bí đỏ"},
        "also": [],
        "windows": {"wet": {"sow": (-7, 35)}, "dry": {"sow": (0, 42)}},
        "tip": "Let it sprawl over a fence or a compost heap. Hand-pollinate in the morning if small fruits keep dropping.",
    },
    {
        "name": "Yardlong bean",
        "days_to_harvest": 60, "sun": "full", "pot": "medium",
        "names": {"hi": "lobia", "bn": "borboti", "si": "maekaral", "ta": "karamani", "te": "alasandalu", "th": "thua fak yao", "tl": "sitaw", "vi": "đậu đũa"},
        "also": ["long bean", "cowpea", "snake bean", "asparagus bean"],
        "windows": {"wet": {"sow": (0, 49)}, "dry": {"sow": (0, 42)}},
        "tip": "Climbs fast, so give it a tall trellis. Pick pods before the seeds bulge.",
    },
    {
        "name": "Amaranth",
        "days_to_harvest": 25, "sun": "part", "pot": "small",
        "names": {"hi": "chaulai", "bn": "lal shak", "si": "thampala", "te": "thotakura", "th": "phak khom", "tl": "kulitis", "vi": "rau dền"},
        "also": ["red amaranth"],
        "windows": {"wet": {"sow": (0, 75)}, "dry": {"sow": (0, 75)}},
        "tip": "Scatter the seed thinly and barely cover it. The first cutting is ready in about three weeks.",
    },
    {
        "name": "Water spinach",
        "days_to_harvest": 30, "sun": "part", "pot": "medium",
        "names": {"hi": "kalmi saag", "bn": "kolmi shak", "si": "kankun", "th": "phak bung", "tl": "kangkong", "vi": "rau muống"},
        "also": ["kangkong", "kangkung", "morning glory"],
        "windows": {"wet": {"sow": (0, 75)}, "dry": {"sow": (0, 60)}},
        "tip": "Loves water. Grow it in a tub that stays wet, and cut the tips so it regrows.",
    },
    {
        "name": "Malabar spinach",
        "days_to_harvest": 45, "sun": "part", "pot": "medium",
        "names": {"hi": "poi", "bn": "pui shak", "ta": "pasalai", "te": "bachali", "th": "phak plang", "tl": "alugbati", "vi": "mồng tơi"},
        "also": ["indian spinach", "ceylon spinach", "basella", "vine spinach"],
        "windows": {"wet": {"sow": (-14, 42)}, "dry": {"sow": (0, 42)}},
        "tip": "A climbing green that thrives in heat and rain. Pinch the tips to keep it bushy.",
    },
    {
        "name": "Brinjal",
        "days_to_harvest": 70, "sun": "full", "pot": "medium",
        "names": {"hi": "baingan", "bn": "begun", "si": "wambatu", "ta": "kathirikkai", "te": "vankaya", "th": "makhuea", "tl": "talong", "vi": "cà tím"},
        "also": ["eggplant", "aubergine"],
        "windows": {
            "wet": {"nursery": (-35, -7), "transplant": (0, 35)},
            "dry": {"nursery": (-56, -21), "transplant": (-7, 28)},
        },
        "tip": "Move seedlings at four to six weeks old, in the evening, and water them in well.",
    },
    {
        "name": "Chilli",
        "days_to_harvest": 75, "sun": "full", "pot": "medium",
        "names": {"hi": "mirch", "bn": "morich", "si": "miris", "ta": "milagai", "te": "mirapakaya", "th": "phrik", "tl": "sili", "vi": "ớt"},
        "also": ["chili", "chile", "green chilli", "hot pepper"],
        "windows": {
            "wet": {"nursery": (-42, -7), "transplant": (0, 35)},
            "dry": {"nursery": (-90, -45), "transplant": (-7, 28)},
        },
        "tip": "Seedlings are ready to move at about six weeks. Mulch to keep the roots cool.",
    },
    {
        "name": "Tomato",
        "days_to_harvest": 70, "sun": "full", "pot": "medium",
        "names": {"hi": "tamatar", "si": "thakkali", "ta": "thakkali", "th": "makhuea thet", "tl": "kamatis", "vi": "cà chua"},
        "also": [],
        "windows": {
            "cool": {"nursery": (-21, 7), "transplant": (7, 35)},
            "dry": {"nursery": (-90, -45), "transplant": (-14, 21)},
            "wet": {"nursery": (-28, 0), "transplant": (0, 28)},
        },
        "tip": "Stake early. In wet weather, keep the leaves off the soil to slow blight.",
    },
    {
        "name": "Taro",
        "days_to_harvest": 180, "sun": "part", "pot": "large",
        "names": {"hi": "arbi", "bn": "kochu", "ta": "seppankizhangu", "te": "chamagadda", "th": "phueak", "tl": "gabi", "vi": "khoai môn"},
        "also": ["colocasia", "arvi"],
        "windows": {"wet": {"plant": (-14, 28)}, "dry": {"plant": (0, 42)}},
        "tip": "Plant corms in rich, moist soil. The leaves die back when the tubers are ready.",
    },
    {
        "name": "Ginger",
        "days_to_harvest": 240, "sun": "part", "pot": "large",
        "names": {"hi": "adrak", "bn": "ada", "si": "inguru", "ta": "inji", "te": "allam", "th": "khing", "tl": "luya", "vi": "gừng"},
        "also": [],
        "windows": {"wet": {"plant": (-35, 14)}},
        "tip": "Plant pieces of fresh rhizome with a bud on each, 5 cm deep, in compost-rich soil. Ready in eight to ten months.",
    },
    {
        "name": "Turmeric",
        "days_to_harvest": 270, "sun": "part", "pot": "large",
        "names": {"hi": "haldi", "bn": "holud", "si": "kaha", "ta": "manjal", "te": "pasupu", "th": "khamin", "tl": "luyang dilaw", "vi": "nghệ"},
        "also": [],
        "windows": {"wet": {"plant": (-35, 14)}},
        "tip": "Plant rhizome pieces as the first rains come. Harvest when the leaves turn yellow and dry, in about nine months.",
    },
    {
        "name": "Watermelon",
        "days_to_harvest": 85, "sun": "full", "pot": None,
        "names": {"hi": "tarbooz", "bn": "tormuj", "ta": "tharpoosani", "te": "puchakaya", "th": "taengmo", "tl": "pakwan", "vi": "dưa hấu"},
        "also": [],
        "windows": {"dry": {"sow": (0, 35)}},
        "tip": "Needs full sun, room to spread, and deep watering until the fruit sets.",
    },
    {
        "name": "Muskmelon",
        "days_to_harvest": 80, "sun": "full", "pot": None,
        "names": {"hi": "kharbooza", "bn": "bangi"},
        "also": ["cantaloupe", "melon"],
        "windows": {"dry": {"sow": (0, 35)}},
        "tip": "Sow in warm, well-drained soil. Water less once the fruit starts to ripen, for sweeter melons.",
    },
    {
        "name": "Pak choi",
        "days_to_harvest": 40, "sun": "part", "pot": "small",
        "names": {"tl": "pechay", "vi": "cải thìa"},
        "also": ["bok choy", "bok choi", "pak choy"],
        "only": ["Thailand", "Philippines", "Vietnam"],
        "windows": {"cool": {"sow": (0, 90)}, "wet": {"sow": (0, 60)}, "dry": {"sow": (0, 45)}},
        "tip": "Quick and forgiving. Grow it in part shade in the hot months, and pick whole heads or outer leaves.",
    },
    # ---- cool-season (Rabi) crops ----
    {
        "name": "Cauliflower",
        "days_to_harvest": 70, "sun": "full", "pot": "large",
        "names": {"hi": "phool gobhi", "bn": "phulkopi", "th": "kalam dok", "vi": "bông cải"},
        "also": [],
        "windows": {"cool": {"nursery": (-14, 21), "transplant": (14, 56)}},
        "tip": "Transplant four- to six-week-old seedlings. Tie the leaves over the head once it shows, to keep it white.",
    },
    {
        "name": "Cabbage",
        "days_to_harvest": 80, "sun": "full", "pot": "large",
        "names": {"hi": "patta gobhi", "bn": "bandhakopi", "si": "gova", "ta": "muttaikose", "th": "kalam pli", "tl": "repolyo", "vi": "bắp cải"},
        "also": ["band gobhi"],
        "windows": {"cool": {"nursery": (0, 35), "transplant": (28, 70)}},
        "tip": "Firm the soil around transplants and water steadily so the heads don't split.",
    },
    {
        "name": "Peas",
        "days_to_harvest": 65, "sun": "full", "pot": "medium",
        "names": {"hi": "matar", "bn": "motorshuti", "ta": "pattani", "te": "batani", "th": "thua lantao", "tl": "gisantes", "vi": "đậu hà lan"},
        "also": ["pea", "green peas"],
        "windows": {"cool": {"sow": (14, 50)}},
        "tip": "Sow once the heat breaks. A short trellis or a few twiggy sticks keeps the pods clean.",
    },
    {
        "name": "Spinach",
        "days_to_harvest": 35, "sun": "part", "pot": "small",
        "names": {"hi": "palak", "bn": "palong shak", "te": "palakura"},
        "also": [],
        "windows": {"cool": {"sow": (0, 100)}},
        "tip": "Sow a short row every two weeks for a steady supply of leaves all winter.",
    },
    {
        "name": "Fenugreek",
        "days_to_harvest": 25, "sun": "part", "pot": "small",
        "names": {"hi": "methi", "bn": "methi", "ta": "vendhayam", "te": "menthikura"},
        "also": [],
        "windows": {"cool": {"sow": (0, 75)}},
        "tip": "Ready to cut in about three weeks. Grows happily in a shallow tray or pot.",
    },
    {
        "name": "Coriander",
        "days_to_harvest": 35, "sun": "part", "pot": "small",
        "names": {"hi": "dhaniya", "bn": "dhonepata", "ta": "kothamalli", "te": "kothimeera", "th": "phak chi", "tl": "wansoy", "vi": "ngò"},
        "also": ["cilantro", "dhania"],
        "windows": {"cool": {"sow": (0, 90)}},
        "tip": "Gently crush the round seeds into halves before sowing. They sprout faster.",
    },
    {
        "name": "Mustard greens",
        "days_to_harvest": 35, "sun": "part", "pot": "small",
        "names": {"hi": "sarson", "th": "phak kat", "tl": "mustasa", "vi": "cải bẹ xanh"},
        "also": ["sarson ka saag", "mustard"],
        "windows": {"cool": {"sow": (0, 45)}},
        "tip": "Fast and hardy. Cut young leaves for saag, and let a few plants flower for the bees.",
    },
    {
        "name": "Radish",
        "days_to_harvest": 35, "sun": "part", "pot": "medium",
        "names": {"hi": "mooli", "bn": "mula", "si": "rabu", "ta": "mullangi", "te": "mullangi", "th": "hua chai thao", "tl": "labanos", "vi": "củ cải"},
        "also": [],
        "windows": {"cool": {"sow": (-14, 100)}, "wet": {"sow": (0, 45)}},
        "tip": "Thin the seedlings to a hand's width. Pull them young, because old radishes turn pithy and hot.",
    },
    {
        "name": "Carrot",
        "days_to_harvest": 80, "sun": "part", "pot": "medium",
        "names": {"hi": "gajar", "bn": "gajor", "th": "khae rot", "tl": "karot", "vi": "cà rốt"},
        "also": [],
        "windows": {"cool": {"sow": (0, 60)}},
        "tip": "Sow in loose, stone-free soil and keep it moist until the seedlings show.",
    },
    {
        "name": "Turnip",
        "days_to_harvest": 50, "sun": "part", "pot": "medium",
        "names": {"hi": "shalgam", "bn": "shalgom"},
        "also": [],
        "windows": {"cool": {"sow": (0, 60)}},
        "tip": "Pull them between golf-ball and cricket-ball size, when they are sweetest.",
    },
    {
        "name": "Beetroot",
        "days_to_harvest": 60, "sun": "part", "pot": "medium",
        "names": {"hi": "chukandar"},
        "also": ["beet"],
        "windows": {"cool": {"sow": (7, 70)}},
        "tip": "Each seed is a cluster, so thin the sprouts to about a hand's width apart.",
    },
    {
        "name": "Onion",
        "days_to_harvest": 110, "sun": "full", "pot": "medium",
        "names": {"hi": "pyaz", "bn": "peyaj", "si": "lunu", "ta": "vengayam", "te": "ullipaya", "th": "hom yai", "tl": "sibuyas", "vi": "hành tây"},
        "also": ["pyaaz"],
        "windows": {"cool": {"nursery": (21, 60), "transplant": (75, 115)}},
        "tip": "Raise seedlings in a nursery bed, then transplant them when they are pencil-thick.",
    },
    {
        "name": "Garlic",
        "days_to_harvest": 150, "sun": "full", "pot": "medium",
        "names": {"hi": "lehsun", "bn": "roshun", "si": "sudu lunu", "ta": "poondu", "te": "vellulli", "th": "krathiam", "tl": "bawang", "vi": "tỏi"},
        "also": ["lahsun"],
        "windows": {"cool": {"plant": (7, 45)}},
        "tip": "Plant cloves pointy end up, about 3 cm deep, in loose soil.",
    },
    {
        "name": "Potato",
        "days_to_harvest": 100, "sun": "full", "pot": "large",
        "names": {"hi": "aloo", "bn": "alu", "si": "ala", "ta": "urulaikizhangu", "te": "bangaladumpa", "th": "man farang", "tl": "patatas", "vi": "khoai tây"},
        "also": [],
        "windows": {"cool": {"plant": (7, 45)}},
        "tip": "Plant seed pieces with at least two eyes each, and pile soil up around the stems as they grow.",
    },
    {
        "name": "Lettuce",
        "days_to_harvest": 45, "sun": "part", "pot": "small",
        "names": {"th": "phak kat hom", "tl": "litsugas", "vi": "xà lách"},
        "also": [],
        "windows": {"cool": {"sow": (14, 90)}},
        "tip": "Grows well in pots and part shade. Pick the outer leaves and let the centre keep growing.",
    },
]

# Jobs anchored to the start of the region's main rains instead of a sowing season.
EXTRAS: list[dict] = [
    {
        "name": "Green manure",
        "names": {"hi": "dhaincha"},
        "also": ["sunn hemp", "dhaincha"],
        "kind": "green_manure",
        "days": (-14, 21),
        "tip": "Sow dhaincha or sunn hemp at the first rains. Dig it in after six to eight weeks, before it flowers, to feed the soil.",
    },
    {
        "name": "Tree saplings",
        "names": {},
        "also": ["sapling", "fruit tree", "fruit trees"],
        "kind": "plant_sapling",
        "days": (7, 60),
        "tip": "The rains water new trees for you. Mango, guava, lemon or curry leaf saplings planted now settle in before the dry months.",
    },
]

# Local names that are also ordinary English words. They are still shown in
# the app, but the fact check ignores them so "the season has begun" doesn't
# count as a mention of brinjal.
FACTCHECK_IGNORE = {"begun", "ala", "poi"}
