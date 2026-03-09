"""Fix broken synthetic puzzles - repaired groups hardcoded where known, Sonnet for rest."""
import asyncio
import csv
import json
import sys
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Fully fixed puzzles (all 4 groups verified correct)
# ---------------------------------------------------------------------------
FIXED_PUZZLES = [
    {
        "id": "syn-8",
        "groups": [
            {"level": 0, "name": "TYPES OF BERRIES", "words": ["STRAW", "BLUE", "RASP", "CRAN"]},
            {"level": 1, "name": "THINGS THAT CAN BE CRUSHED", "words": ["VELVET", "HOPES", "ICE", "DREAMS"]},
            {"level": 2, "name": "WORDS HIDING A GEMSTONE", "words": ["PEARLESCENT", "JADEITE", "TOPAZITE", "RUBICUND"]},
            {"level": 3, "name": "___ KINGDOM", "words": ["ANIMAL", "PLANT", "FUNGI", "MONERA"]},
        ]
    },
    {
        "id": "syn-27",
        "groups": [
            {"level": 0, "name": "THINGS THAT ARE SLICED", "words": ["BREAD", "PIZZA", "CHEESE", "TOMATO"]},
            {"level": 1, "name": "WORDS THAT FOLLOW 'STRAWBERRY'", "words": ["JAM", "SHORTCAKE", "FIELDS", "BLONDE"]},
            {"level": 2, "name": "COUNTRIES WITH CONSECUTIVE DOUBLE LETTERS IN NAME", "words": ["GREECE", "MOROCCO", "CAMEROON", "PHILIPPINES"]},
            {"level": 3, "name": "DRAG QUEENS KNOWN BY FIRST NAME ONLY", "words": ["TAMMIE", "ALASKA", "DETOX", "MANILA"]},
        ]
    },
    {
        "id": "syn-39",
        "groups": [
            {"level": 0, "name": "SYNONYMS FOR SHABBY", "words": ["TATTY", "WORN", "DINGY", "TATTERED"]},
            {"level": 1, "name": "THINGS THAT COME IN PODS", "words": ["COCOA", "VANILLA", "PEAS", "COFFEE"]},
            {"level": 2, "name": "SURNAMES THAT ARE JOBS WITH DOUBLE LETTERS", "words": ["MILLER", "POTTER", "TANNER", "LOGGER"]},
            {"level": 3, "name": "WORDS THAT FOLLOW 'SLEEPING'", "words": ["BAG", "GIANT", "BEAUTY", "CAR"]},
        ]
    },
    {
        "id": "syn-72",
        "groups": [
            {"level": 0, "name": "BODY PARTS OF A CHICKEN", "words": ["BREAST", "WING", "THIGH", "LEG"]},
            {"level": 1, "name": "THINGS THAT CAN BE 'HARD'", "words": ["CIDER", "CANDY", "LABOR", "DRIVE"]},
            {"level": 2, "name": "WORDS THAT FOLLOW 'UPPER'", "words": ["CRUST", "HAND", "CUT", "DECK"]},
            {"level": 3, "name": "ANAGRAMS OF SPANISH NUMBERS", "words": ["REST", "CONE", "CODE", "ERECT"]},
        ]
    },
    {
        "id": "syn-76",
        "groups": [
            {"level": 0, "name": "SHAKESPEARE PLAYS", "words": ["HAMLET", "MACBETH", "OTHELLO", "TEMPEST"]},
            {"level": 1, "name": "HIDDEN KING", "words": ["KINGPIN", "KINGDOM", "KINGFISH", "KINGLET"]},
            {"level": 2, "name": "FAMOUS WILLIAMS (LAST NAMES)", "words": ["VENUS", "PHARRELL", "HANK", "ROBIN"]},
            {"level": 3, "name": "ADD 'T' TO START TO MAKE A NEW WORD", "words": ["RAIN", "ANGLE", "RUST", "RACK"]},
        ]
    },
    {
        "id": "syn-79",
        "groups": [
            {"level": 0, "name": "THINGS THAT MELT", "words": ["ICE", "CHOCOLATE", "BUTTER", "SNOW"]},
            {"level": 1, "name": "FAMOUS DAVIDS", "words": ["BOWIE", "LETTERMAN", "BECKHAM", "COPPERFIELD"]},
            {"level": 2, "name": "WORDS HIDING A FISH", "words": ["BASSINET", "CODEINE", "SALMONELLA", "FLOUNDERING"]},
            {"level": 3, "name": "THINGS THAT PRECEDE 'WOOD'", "words": ["PLYWOOD", "DOGWOOD", "REDWOOD", "DEADWOOD"]},
        ]
    },
    {
        "id": "syn-82",
        "groups": [
            {"level": 0, "name": "THINGS THAT SPARKLE", "words": ["GLITTER", "SEQUIN", "RHINESTONE", "MICA"]},
            {"level": 1, "name": "FAMOUS DONS", "words": ["CHEADLE", "JOHNSON", "DRAPER", "CORLEONE"]},
            {"level": 2, "name": "WORDS HIDING A COMPOSER'S NAME", "words": ["BACHELOR", "MISHANDLED", "VERDICT", "UPHOLSTERY"]},
            {"level": 3, "name": "___ 'S LAW", "words": ["MURPHY", "COULOMB", "BOYLE", "NEWTON"]},
        ]
    },
    {
        "id": "syn-83",
        "groups": [
            {"level": 0, "name": "LITERARY DEVICES", "words": ["METAPHOR", "SIMILE", "IRONY", "PERSONIFICATION"]},
            {"level": 1, "name": "FAMOUS POPES", "words": ["JOHN", "GREGORY", "CLEMENT", "INNOCENT"]},
            {"level": 2, "name": "WORDS HIDING A CHESS PIECE", "words": ["WORKING", "PAWNSHOP", "ROOKERY", "ARCHBISHOP"]},
            {"level": 3, "name": "PRECEDED BY DRUG SLANG", "words": ["SNOW", "GRASS", "ROCK", "ACID"]},
        ]
    },
    {
        "id": "syn-93",
        "groups": [
            {"level": 0, "name": "BOARD GAME PIECES", "words": ["PAWN", "ROOK", "TOKEN", "DIE"]},
            {"level": 1, "name": "THINGS THAT FLIP", "words": ["PANCAKE", "SWITCH", "COIN", "MATTRESS"]},
            {"level": 2, "name": "WORDS HIDING A CARD SUIT", "words": ["SWEETHEART", "NIGHTCLUB", "DIAMONDBACK", "SPADEWORK"]},
            {"level": 3, "name": "HARRY POTTER SPELLS", "words": ["STUPEFY", "EXPELLIARMUS", "ACCIO", "LUMOS"]},
        ]
    },
    {
        "id": "syn-33",
        "groups": [
            {"level": 0, "name": "BREAKFAST ITEMS", "words": ["BACON", "TOAST", "EGGS", "PANCAKES"]},
            {"level": 1, "name": "SYNONYMS FOR TIRED", "words": ["BEAT", "WIPED", "DRAINED", "SPENT"]},
            {"level": 2, "name": "THINGS THAT CAN FOLLOW 'COLD'", "words": ["SNAP", "SHOULDER", "BREW", "CASE"]},
            {"level": 3, "name": "FAMOUS DANNYS (LAST NAMES)", "words": ["DEVITO", "GLOVER", "TREJO", "AIELLO"]},
        ]
    },
]

# ---------------------------------------------------------------------------
# Puzzles needing Sonnet to fix one or more groups
# good groups are kept; broken groups have "broken": True with a short hint
# ---------------------------------------------------------------------------
NEEDS_FIXING = [
    {
        "id": "syn-3",
        "groups": [
            {"level": 0, "name": "TYPES OF PASTA", "words": ["PENNE", "RIGATONI", "FUSILLI", "LINGUINE"]},
            {"level": 1, "name": "WORDS THAT CAN FOLLOW 'HARD'", "words": ["DRIVE", "COPY", "WEAR", "WIRE"]},
            {"level": 2, "name": "WORDS HIDING A FRUIT", "words": [], "broken": True,
             "hint": "4 common English words that each contain a fruit name as a substring. E.g. PLUMBER(PLUM), PEACHY(PEACH), LIMELIGHT(LIME), FIGMENT(FIG). Do NOT use the fruit names themselves."},
            {"level": 3, "name": "ANAGRAMS OF GREEK LETTER NAMES", "words": [], "broken": True,
             "hint": "4 common English words that are anagrams of Greek letter names. BETA->BEAT, DELTA->DEALT are valid. Find 4 total. Only use real Greek letters and verify letter counts match exactly."},
        ]
    },
    {
        "id": "syn-9",
        "groups": [
            {"level": 0, "name": "THINGS THAT ARE CIRCULAR", "words": ["PIZZA", "PLATE", "WHEEL", "COIN"]},
            {"level": 1, "name": "TYPES OF DANCES", "words": ["TANGO", "WALTZ", "JIVE", "FOXTROT"]},
            {"level": 2, "name": "ANAGRAMS OF COUNTRY NAMES", "words": [], "broken": True,
             "hint": "4 common English words that are anagrams of country names. Verify letter counts exactly. E.g. SPAIN(5)->PAINS ✓, CHILE(5)->? ITALY(5)->LAITY ✓, CHINA(5)->NAICH? No. IRAN(4)->RAIN ✓, PERU(4)->PURE ✓, CUBA(4)->? Find 4 that work."},
            {"level": 3, "name": "WORDS ENDING IN 'NET' WHERE REMOVING 'NET' GIVES A COMMON WORD", "words": [], "broken": True,
             "hint": "4 words ending in NET where what remains before NET is a common English word. E.g. DRAGNET(DRAG+NET), FISHNET(FISH+NET), HAIRNET(HAIR+NET), BAYONET? (BAYO not a word). Find 4 where the prefix is a common standalone word."},
        ]
    },
    {
        "id": "syn-20",
        "groups": [
            {"level": 0, "name": "SWIMMING STROKES", "words": ["BUTTERFLY", "BACKSTROKE", "BREASTSTROKE", "FREESTYLE"]},
            {"level": 1, "name": "THINGS THAT ARE LIQUID AT ROOM TEMPERATURE", "words": ["MERCURY", "BROMINE", "WATER", "GASOLINE"]},
            {"level": 2, "name": "WORDS THAT FOLLOW 'RUBBER'", "words": ["BAND", "STAMP", "DUCKY", "MALLET"]},
            {"level": 3, "name": "ANAGRAMS OF FAMOUS PHILOSOPHER NAMES", "words": [], "broken": True,
             "hint": "4 common English words that are exact anagrams of famous philosopher last names. Verify letter counts exactly. PLATO(5:P,L,A,T,O)->? HEGEL(5)->? LOCKE(5)->? HUME(4)->? KANT(4)->TANK ✓, MARX(4)->? Find ones where a real common English word uses the exact same letters."},
        ]
    },
    {
        "id": "syn-26",
        "groups": [
            {"level": 0, "name": "TOOLS FOR BUILDING/REPAIR", "words": ["HAMMER", "WRENCH", "DRILL", "SAW"]},
            {"level": 1, "name": "FRUITS WITH PITS", "words": ["PEACH", "PLUM", "CHERRY", "APRICOT"]},
            {"level": 2, "name": "THINGS THAT CAN PRECEDE 'WOOD'", "words": ["DOGWOOD", "HARDWOOD", "DRIFTWOOD", "DEADWOOD"]},
            {"level": 3, "name": "WORDS HIDING A UNIT OF MEASUREMENT", "words": [], "broken": True,
             "hint": "4 common English words that contain a measurement unit as a substring. E.g. WRENCHING(INCH), YARDAGE(YARD), FOOTAGE(FOOT), MILEAGE(MILE). Don't use HAMMER, WRENCH, DRILL, SAW, PEACH, PLUM, CHERRY, APRICOT, DOGWOOD, HARDWOOD, DRIFTWOOD, DEADWOOD."},
        ]
    },
    {
        "id": "syn-30",
        "groups": [
            {"level": 0, "name": "LARGE BODIES OF WATER", "words": ["OCEAN", "SEA", "GULF", "STRAIT"]},
            {"level": 1, "name": "WORDS THAT FOLLOW 'SOUND'", "words": ["BARRIER", "CHECK", "BITE", "BOARD"]},
            {"level": 2, "name": "COFFEE SHOP ORDERS", "words": ["LATTE", "MOCHA", "AMERICANO", "CORTADO"]},
            {"level": 3, "name": "WORDS CONTAINING 'CLOSE'", "words": [], "broken": True,
             "hint": "4 common English words that contain the word CLOSE as a substring. E.g. CLOSER, ENCLOSED, DISCLOSE, FORECLOSE. Don't repeat OCEAN, SEA, GULF, STRAIT, BARRIER, CHECK, BITE, BOARD, LATTE, MOCHA, AMERICANO, CORTADO."},
        ]
    },
    {
        "id": "syn-45",
        "groups": [
            {"level": 0, "name": "THINGS YOU STIR", "words": ["COFFEE", "SOUP", "PAINT", "TROUBLE"]},
            {"level": 1, "name": "VARIETIES OF LETTUCE", "words": ["ROMAINE", "ICEBERG", "BUTTER", "LOOSE LEAF"]},
            {"level": 2, "name": "MICHAEL ___ (FAMOUS PEOPLE NAMED MICHAEL)", "words": ["JORDAN", "JACKSON", "PHELPS", "SCOTT"]},
            {"level": 3, "name": "ADD ONE LETTER TO START TO MAKE AN ANIMAL", "words": [], "broken": True,
             "hint": "4 words where adding exactly one letter to the START makes an animal name. The original word must NOT be an animal. E.g. OAT->GOAT(+G), OX->FOX(+F), OAR->BOAR(+B), EWE->? (already animal). Find 4 that work. Avoid: COFFEE, SOUP, PAINT, TROUBLE, ROMAINE, ICEBERG, BUTTER, JORDAN, JACKSON, PHELPS, SCOTT."},
        ]
    },
    {
        "id": "syn-53",
        "groups": [
            {"level": 0, "name": "TYPES OF CAKE", "words": ["CARROT", "POUND", "LAYER", "ANGEL"]},
            {"level": 1, "name": "THINGS THAT ARE DIVIDED INTO ACTS", "words": ["PLAY", "OPERA", "CIRCUS", "BALLET"]},
            {"level": 2, "name": "ROCK BANDS FRONTED BY SOMEONE NAMED CHRIS", "words": [], "broken": True,
             "hint": "4 rock/pop bands whose lead singer is named Chris. Chris Martin=COLDPLAY, Chris Cornell=SOUNDGARDEN, Chris Robinson=BLACK CROWES, Chris Frantz? No. Chris Rea? Solo. Use band names only. Find 4 real verified ones."},
            {"level": 3, "name": "WORDS THAT BECOME A BUILDING WHEN 'E' IS ADDED TO THE END", "words": [], "broken": True,
             "hint": "4 words where adding E to the end creates a type of building or structure. E.g. CASTL->CASTLE, PALAC->PALACE, COTTAG->COTTAGE, GARAG->GARAGE, BRIDG->BRIDGE. The base word must be recognizable without the E."},
        ]
    },
    {
        "id": "syn-55",
        "groups": [
            {"level": 0, "name": "TYPES OF NUTS", "words": ["ALMOND", "WALNUT", "CASHEW", "PECAN"]},
            {"level": 1, "name": "THINGS THAT CAN BE BLIND", "words": ["SPOT", "AMBITION", "RAGE", "SIDE"]},
            {"level": 2, "name": "WORDS THAT FOLLOW 'CALL'", "words": ["CENTER", "GIRL", "BACK", "SIGN"]},
            {"level": 3, "name": "ANAGRAMS OF CARIBBEAN ISLAND NAMES", "words": [], "broken": True,
             "hint": "4 common English words that are exact anagrams of Caribbean island names. Check letter counts exactly. CUBA(4:C,U,B,A)->? ARUBA(5)->? HAITI(5:H,A,I,T,I)->? Try island names and verify each anagram is a real common English word."},
        ]
    },
    {
        "id": "syn-61",
        "groups": [
            {"level": 0, "name": "THINGS THAT STICK TO SURFACES", "words": ["MAGNET", "TAPE", "GLUE", "STICKER"]},
            {"level": 1, "name": "HARRY POTTER LOCATIONS", "words": ["HOGWARTS", "DIAGON", "GRINGOTTS", "AZKABAN"]},
            {"level": 2, "name": "WORDS CONTAINING A SNEAKER BRAND", "words": [], "broken": True,
             "hint": "4 common English words containing a sneaker brand as substring. Brands: NIKE, PUMA, VANS, FILA, KEDS, AVIA. E.g. VANISH(VAN/VANS), FILAGREE? Try to find real examples where the brand name is clearly embedded."},
            {"level": 3, "name": "WORDS FOLLOWING 'SUGAR'", "words": ["PLUM", "CANE", "RUSH", "COAT"]},
        ]
    },
    {
        "id": "syn-63",
        "groups": [
            {"level": 0, "name": "TOOLS FOR CUTTING", "words": ["KNIFE", "SCISSORS", "AXE", "SAW"]},
            {"level": 1, "name": "THINGS THAT CAN BE BLUE", "words": ["MOON", "WHALE", "JAY", "CHEESE"]},
            {"level": 2, "name": "WORDS FOLLOWING 'ORANGE'", "words": ["PEEL", "JUICE", "BLOSSOM", "COUNTY"]},
            {"level": 3, "name": "FOOD WORDS THAT CONTAIN A US PRESIDENT'S NAME", "words": [], "broken": True,
             "hint": "4 food words that contain a US president's surname as a substring. E.g. GRANT in POMEGRANATE? P-O-M-E-G-R-A-N-A-T-E contains G-R-A-N-T? G-R-A-N yes but not G-R-A-N-T. LINZER cookie contains LINCOLN? No. Try: FILLMORE in? POLK in? TAFT in TAFFY? T-A-F-F-Y vs T-A-F-T different. Find real ones."},
        ]
    },
    {
        "id": "syn-67",
        "groups": [
            {"level": 0, "name": "THINGS THAT ARE WARM", "words": ["BLANKET", "COCOA", "FIRE", "SWEATER"]},
            {"level": 1, "name": "WORDS THAT FOLLOW 'STRAW'", "words": ["BERRY", "MAN", "POLL", "WEIGHT"]},
            {"level": 2, "name": "FICTIONAL CHARACTERS WHOSE NAME IS A COLOR", "words": [], "broken": True,
             "hint": "4 fictional characters whose given name is literally a color word. E.g. VIOLET (Incredibles), SCARLETT (Gone with the Wind / G.I. Joe), BLUE (Blue's Clues), JADE (various). The character's actual name must be the color itself."},
            {"level": 3, "name": "REMOVE 'S' TO GET A VERB ENDING IN 'Y'", "words": ["STAYS", "PLAYS", "SPRAYS", "GRAYS"]},
        ]
    },
    {
        "id": "syn-68",
        "groups": [
            {"level": 0, "name": "BECOME ANGRY", "words": ["SEETHE", "FUME", "BOIL", "RAGE"]},
            {"level": 1, "name": "THINGS WITH LACES", "words": ["CORSET", "SHOE", "CURTAIN", "DOILY"]},
            {"level": 2, "name": "EDIBLE ___ CANDY", "words": ["ROCK", "COTTON", "HARD", "BARLEY"]},
            {"level": 3, "name": "ANAGRAMS OF ANIMAL NAMES", "words": [], "broken": True,
             "hint": "4 common English words that are exact anagrams of animal names. Verify letter counts. LION(4)->LOIN ✓, COBRA(5)->CAROB ✓, VIPER(5)->? STEAK(5)->SKATE(fish) ✓. Find a 4th. Avoid: SEETHE, FUME, BOIL, RAGE, CORSET, SHOE, CURTAIN, DOILY, ROCK, COTTON, HARD, BARLEY."},
        ]
    },
    {
        "id": "syn-70",
        "groups": [
            {"level": 0, "name": "SHADES OF ORANGE", "words": ["APRICOT", "PEACH", "CORAL", "TANGERINE"]},
            {"level": 1, "name": "THINGS THAT CAN BE 'LEGAL'", "words": ["EAGLE", "TENDER", "BRIEF", "PAD"]},
            {"level": 2, "name": "SANDWICHES NAMED FOR PLACES", "words": ["CUBAN", "REUBEN", "MONTE CRISTO", "PHILLY"]},
            {"level": 3, "name": "WORDS CONTAINING 'JUST'", "words": [], "broken": True,
             "hint": "4 common English words that contain the word JUST as a substring. E.g. JUSTICE, JUSTIFY, UNJUST, ADJUST, JUSTLY, UNJUSTLY. Avoid: APRICOT, PEACH, CORAL, TANGERINE, EAGLE, TENDER, BRIEF, PAD, CUBAN, REUBEN, PHILLY."},
        ]
    },
    {
        "id": "syn-77",
        "groups": [
            {"level": 0, "name": "NOBEL PEACE PRIZE WINNERS", "words": ["MALALA", "MANDELA", "OBAMA", "SUU KYI"]},
            {"level": 1, "name": "CONTAINS A CURRENCY", "words": ["DRACHMA", "TUGBOAT", "RUPTURE", "YENNING"]},
            {"level": 2, "name": "WORDS ENDING WITH A PLAYING CARD SUIT", "words": [], "broken": True,
             "hint": "4 common English words that end with HEART, CLUB, DIAMOND, or SPADE (one of each). E.g. SWEETHEART(HEART), NIGHTCLUB(CLUB), DIAMONDBACK? ends in BACK not DIAMOND. SPADE: ESCAPADE? ends in ADE not SPADE. Find words that literally end in the full suit name. Each suit used once."},
            {"level": 3, "name": "WORDS CONTAINING 'CLOSE'", "words": [], "broken": True,
             "hint": "4 common words containing CLOSE as substring: CLOSER, ENCLOSED, DISCLOSE, FORECLOSE, CLOSET, CLOSELY, ENCLOSE. Pick 4, avoiding: MALALA, MANDELA, OBAMA, DRACHMA, TUGBOAT, RUPTURE, YENNING and the card suit words."},
        ]
    },
    {
        "id": "syn-78",
        "groups": [
            {"level": 0, "name": "SHAKESPEAREAN TRAGEDIES", "words": ["HAMLET", "MACBETH", "OTHELLO", "KING LEAR"]},
            {"level": 1, "name": "ELEMENTS OF A CRIME SCENE", "words": ["EVIDENCE", "MOTIVE", "WITNESS", "ALIBI"]},
            {"level": 2, "name": "COMPOUND WORDS STARTING WITH A TOOL NAME", "words": [], "broken": True,
             "hint": "4 single compound words that begin with a tool name. E.g. SAWDUST(SAW), PICKPOCKET(PICK), SCREWBALL(SCREW), HAMMERHEAD(HAMMER), CHISELBEARER? No. Find 4 real single-word compounds. Avoid: HAMLET, MACBETH, OTHELLO, KING LEAR, EVIDENCE, MOTIVE, WITNESS, ALIBI."},
            {"level": 3, "name": "WORDS THAT SOUND LIKE FAMOUS PAINTERS' SURNAMES", "words": [], "broken": True,
             "hint": "4 common words that sound like (are homophones or very close sound-alikes of) famous painters' surnames. E.g. MONEY sounds like MONET, CLAY sounds like KLEE (Paul Klee pronounced KLAY), HALLS sounds like HALS (Frans Hals). Find 4 clear ones."},
        ]
    },
    {
        "id": "syn-80",
        "groups": [
            {"level": 0, "name": "JANE AUSTEN HEROINES", "words": ["EMMA", "ANNE", "ELIZABETH", "CATHERINE"]},
            {"level": 1, "name": "WORDS THAT RHYME WITH 'RING'", "words": [], "broken": True,
             "hint": "4 common single-syllable words that rhyme with RING (ending in -ING sound). E.g. KING, SING, BRING, STING, FLING, SWING, CLING, SLING. Avoid EMMA, ANNE, ELIZABETH, CATHERINE, MADISON, MONROE, POLK, GARFIELD."},
            {"level": 2, "name": "PRESIDENTS FIRST NAME 'JAMES'", "words": ["MADISON", "MONROE", "POLK", "GARFIELD"]},
            {"level": 3, "name": "WORDS HIDING A TOOL", "words": [], "broken": True,
             "hint": "4 common English words that contain a tool name as a substring (NOT the tool itself as a standalone). E.g. SAWYER(SAW), SCREWBALL(SCREW), DRILLER(DRILL), CHISELED(CHISEL), HAMMERED(HAMMER), PICKPOCKET(PICK). Find 4 where both the compound word AND the embedded tool are clearly recognizable."},
        ]
    },
    {
        "id": "syn-81",
        "groups": [
            {"level": 0, "name": "THINGS THAT HOOT", "words": ["OWL", "HORN", "SIREN", "WHISTLE"]},
            {"level": 1, "name": "FAMOUS STEPHENS", "words": ["KING", "COLBERT", "CURRY", "HAWKING"]},
            {"level": 2, "name": "WORDS HIDING A MUSICAL INSTRUMENT", "words": [], "broken": True,
             "hint": "4 common words that contain a musical instrument as a substring (NOT the instrument itself). E.g. HARPING(HARP), DRUMMING(DRUM), FIDDLER(FIDDLE), TROMBONIST(TROMBONE), VIOLINIST(VIOLIN), GUITARIST(GUITAR). Pick 4 where the instrument is clearly embedded."},
            {"level": 3, "name": "___ PARADOX", "words": ["ZENO", "RUSSELL", "ARROW", "GALILEO"]},
        ]
    },
    {
        "id": "syn-89",
        "groups": [
            {"level": 0, "name": "THINGS THAT FLOAT", "words": ["BOAT", "BALLOON", "RAFT", "BUOY"]},
            {"level": 1, "name": "SCIENTIFIC UNITS NAMED AFTER PEOPLE", "words": ["VOLT", "WATT", "JOULE", "HERTZ"]},
            {"level": 2, "name": "US STATES CONTAINING A COLOR WORD", "words": [], "broken": True,
             "hint": "4 US state names that contain a color word as a substring. E.g. RHODE ISLAND(no), COLORADO(no English color), GOLDEN(not a state). Actually: VERMONT contains... V-E-R-M-O-N-T no. Try: CONNECTICUT? No. DELAWARE? No. OREGON? No. HAWAII? No. INDIGO-ANA? INDIANA? I-N-D-I-A-N-A no. GREENLAND is not a state. Hmm. Maybe: states with colors in alternate form... Or change theme to: WORDS CONTAINING A COLOR: SCARLET, BLUEPRINT, GREENERY, GOLDEN — use common words hiding colors."},
            {"level": 3, "name": "FAMOUS MATTHEWS (LAST NAMES)", "words": ["BROCK", "PERRY", "MCCONAUGHEY", "GRAY"]},
        ]
    },
    {
        "id": "syn-94",
        "groups": [
            {"level": 0, "name": "FILMS ABOUT OR FEATURING DREAMS", "words": ["INCEPTION", "NIGHTMARE", "DREAMSCAPE", "PAPRIKA"]},
            {"level": 1, "name": "NORTH AMERICAN CAPITALS", "words": ["OTTAWA", "MEXICO", "NASSAU", "BELMOPAN"]},
            {"level": 2, "name": "COMMON WORDS THAT ARE ANAGRAMS OF SHAKESPEARE PLAY TITLES", "words": [], "broken": True,
             "hint": "4 common English words that are exact anagrams of Shakespeare play titles. LEAR(4)->EARL ✓, TITUS(5)->? Shorter plays: LEAR, PUCK? (not a play title). Check carefully. Try: LEAR->EARL, and single-word play titles that have anagrams. Verify letter counts exactly."},
            {"level": 3, "name": "WORDS THAT PRECEDE 'STREET' IN FAMOUS SONG OR SHOW TITLES", "words": ["WALL", "BAKER", "EASY", "SESAME"]},
        ]
    },
    {
        "id": "syn-99",
        "groups": [
            {"level": 0, "name": "SYNONYMS FOR MESSY", "words": ["DISHEVELED", "UNKEMPT", "SCRUFFY", "RUMPLED"]},
            {"level": 1, "name": "THINGS THAT ARE KNOCKED DOWN", "words": ["PINS", "DOMINOES", "BLOCKS", "WALLS"]},
            {"level": 2, "name": "CELEBRITIES NAMED MARK", "words": ["ZUCKERBERG", "WAHLBERG", "RUFFALO", "HAMILL"]},
            {"level": 3, "name": "WORDS WHERE ADDING 'A' TO THE END MAKES A NEW WORD", "words": [], "broken": True,
             "hint": "4 common English words where appending the letter A creates a different common word. E.g. PAST->PASTA, SOFA? (SOF not a word), AURA? (AUR not a word). Try: PAST->PASTA ✓, PIZZA (PIZ not a word). How about: ALFALFA? SODA(SOD+A ✓ SOD is a word!), AREA(ARE+A ✓), YOGA(YOG?). Find 4 where the base word is a common English word and base+A is also a common word."},
        ]
    },
    # Fully new puzzles (replacing duplicates)
    {
        "id": "syn-75",
        "groups": [
            {"level": 0, "name": "DESSERT TOPPINGS", "words": [], "broken": True,
             "hint": "4 common dessert toppings. Single words preferred: SPRINKLES, CARAMEL, FUDGE, WHIPPED, NUTS, GANACHE, GLAZE."},
            {"level": 1, "name": "WORDS THAT FOLLOW 'HEAD'", "words": [], "broken": True,
             "hint": "4 words that follow HEAD: BAND, LIGHT, STONE, BOARD, MASTER, PHONES, SET, STRONG, QUARTERS, COUNT. Pick 4 single words."},
            {"level": 2, "name": "FAMOUS PEOPLE WITH FIRST NAME JAMES (LAST NAMES)", "words": [], "broken": True,
             "hint": "4 last names of famous real people named James. James BROWN(musician), James DEAN(actor), James CAMERON(director), James FRANCO(actor), James WOODS(actor), James MAY(TV). Avoid fictional characters."},
            {"level": 3, "name": "REMOVE FIRST TWO LETTERS TO GET A NEW WORD", "words": [], "broken": True,
             "hint": "4 words where removing the first 2 letters gives a common English word. E.g. BEFORE(FORE), BELOW(LOW), BECAUSE(CAUSE), BEHIND(HIND) — all start with BE. Or RETURN(TURN), REFORM(FORM) — RE prefix. Pick 4 with consistent prefix if possible."},
        ]
    },
    {
        "id": "syn-95",
        "groups": [
            {"level": 0, "name": "TYPES OF CLOUDS", "words": [], "broken": True,
             "hint": "4 well-known cloud types: CUMULUS, STRATUS, CIRRUS, NIMBUS, CUMULONIMBUS. Pick 4."},
            {"level": 1, "name": "THINGS IN A TOOLBOX", "words": [], "broken": True,
             "hint": "4 single-word things found in a toolbox. E.g. WRENCH, PLIERS, LEVEL, CHISEL, CLAMP, MALLET. Avoid words used in other groups."},
            {"level": 2, "name": "WORDS THAT PRECEDE 'FISH'", "words": [], "broken": True,
             "hint": "4 words that go before FISH to make a compound word: SWORD, CAT, GOLD, STAR, JELLY, BLOW, CLOWN, CUTTLE, ANGLER, SWORD. Pick 4 where the compound is a single word."},
            {"level": 3, "name": "WORDS THAT PRECEDE 'STONE'", "words": [], "broken": True,
             "hint": "4 words that go before STONE: COBBLE, CORNER, LIME, MILE, SAND, FLAG, GEM, BROWN, TOMB, KEY. Pick 4."},
        ]
    },
    {
        "id": "syn-97",
        "groups": [
            {"level": 0, "name": "THINGS ON A FARM", "words": [], "broken": True,
             "hint": "4 things found on a farm: BARN, TRACTOR, SILO, FENCE, PLOW, SCARECROW, HAYSTACK, PITCHFORK. Pick 4 single words."},
            {"level": 1, "name": "WORDS THAT FOLLOW 'BOOK'", "words": [], "broken": True,
             "hint": "4 words that follow BOOK: MARK, SHELF, WORM, STORE, KEEPER, CASE, LET, END. Pick 4."},
            {"level": 2, "name": "WORDS THAT PRECEDE 'BREAK'", "words": [], "broken": True,
             "hint": "4 words that precede BREAK: DAY, JAIL, HEART, WIND, OUT, TIE, LUNCH, NEWS, GROUND. Pick 4 common ones."},
            {"level": 3, "name": "FAMOUS PEOPLE WITH LAST NAME YOUNG (FIRST NAMES)", "words": [], "broken": True,
             "hint": "4 first names of famous people with last name YOUNG: NEIL(musician), BRIGHAM(Mormon leader), LORETTA(actress), ANGUS(AC/DC), LESTER(jazz). Pick 4."},
        ]
    },
]

FIX_SYSTEM = "You are a NYT Connections puzzle designer. Given a group name and guidance, output exactly 4 words that fit. Output ONLY valid JSON: {\"words\": [\"W1\", \"W2\", \"W3\", \"W4\"]}"

async def fix_group(client, name: str, level: int, hint: str, avoid: list[str]) -> list[str] | None:
    prompt = (
        f"Group: {name}\nLevel: {level}\nGuidance: {hint}\n"
        f"Do NOT use these words: {', '.join(avoid)}\n"
        "Output ONLY: {\"words\": [\"W1\", \"W2\", \"W3\", \"W4\"]}"
    )
    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=256,
            system=FIX_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        start = text.find("{")
        if start == -1:
            return None
        data = json.loads(text[start:])
        words = [w.upper() for w in data["words"]]
        return words if len(words) == 4 else None
    except Exception as e:
        print(f"[fix error] {e}", file=sys.stderr)
        return None


CSV_FIELDS = ["Game ID", "Puzzle Date", "Group Name", "Group Level", "Word"]

def write_puzzle(out_path: Path, game_id: str, groups: list[dict]):
    num = int(game_id.split("-")[1])
    date = f"2022-01-{(num % 28) + 1:02d}"
    write_header = not out_path.exists() or out_path.stat().st_size == 0
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        for g in groups:
            for word in g["words"]:
                writer.writerow({
                    "Game ID": game_id, "Puzzle Date": date,
                    "Group Name": g["name"], "Group Level": g["level"],
                    "Word": word.upper(),
                })


async def main():
    out_path = Path(__file__).parent.parent / "environments" / "connections" / "synthetic_puzzles.csv"
    client = anthropic.AsyncAnthropic()
    written = 0

    # Write hardcoded fixed puzzles directly
    print("=== Writing hardcoded fixed puzzles ===")
    for p in FIXED_PUZZLES:
        write_puzzle(out_path, p["id"], p["groups"])
        print(f"  {p['id']}: written")
        written += 1

    # Fix remaining puzzles with Sonnet
    print("\n=== Fixing remaining puzzles with Sonnet ===")
    for puzzle in NEEDS_FIXING:
        gid = puzzle["id"]
        print(f"\n{gid}:")
        final_groups = []
        all_words = []
        ok = True

        for g in puzzle["groups"]:
            if not g.get("broken"):
                final_groups.append(g)
                all_words.extend(g["words"])
                print(f"  L{g['level']} KEPT: {g['words']}")
            else:
                print(f"  L{g['level']} {g['name']}: ", end="", flush=True)
                words = await fix_group(client, g["name"], g["level"], g["hint"], all_words)
                if not words:
                    print("FAILED")
                    ok = False
                    break
                overlap = set(words) & set(all_words)
                if overlap:
                    print(f"CONFLICT {overlap}")
                    ok = False
                    break
                all_words.extend(words)
                final_groups.append({"level": g["level"], "name": g["name"], "words": words})
                print(f"FIXED: {words}")

        if ok and len(final_groups) == 4:
            write_puzzle(out_path, gid, final_groups)
            print(f"  -> Written.")
            written += 1
        else:
            print(f"  -> SKIPPED.")

    print(f"\nDone. Wrote {written} puzzles total.")


if __name__ == "__main__":
    asyncio.run(main())
