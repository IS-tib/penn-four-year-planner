"""Degree programs, transcribed from the Penn catalog's requirement tables.

Ten degrees across two schools. Each one is a list of groups, each group a list
of requirement rows, and each row says how many courses it consumes and what
can fill it. Adding a degree is an edit to this file; no code changes.

Three notes on how the catalog was read.

**Category subtotals mostly are not printed.** With the exception of a couple
of pages, Penn prints a course-unit value per row and a single grand total, and
nothing per heading. So group totals here are summed from their rows rather
than transcribed, and every program's rows add up to the printed grand total.
That arithmetic is checked at seed time and refuses to start if it drifts.

**A row that offers alternatives is one requirement with several options.** The
catalog's "CIS 4480 or CIS 5480" is one row you satisfy once, not two rows.

**Rows that admit hundreds of courses become slots.** "Select 4 Social Science
or Humanities courses" cannot be enumerated, and pretending otherwise would
mean inventing a list Penn did not print. Those rows are filled by labelled
slots a student resolves later, which is also how a real advising worksheet
handles them.
"""

from __future__ import annotations

from typing import Any

SEAS = "SEAS"
COLLEGE = "COLLEGE"

SCHOOLS = [
    {"code": SEAS, "name": "School of Engineering and Applied Science"},
    {"code": COLLEGE, "name": "College of Arts and Sciences"},
]

# Slot tags and the label a student sees. A slot is a requirement the catalog
# leaves open, so the app shows it as a placeholder you can resolve into a real
# course later rather than guessing what Penn would accept.
SLOT_TAGS: dict[str, str] = {
    "ssh": "Social Science or Humanities",
    "sshtbs": "Social Science, Humanities or Technology in Business & Society",
    "ss": "Social Science",
    "hum": "Humanities",
    "free": "Free Elective",
    "mns": "Math or Natural Science Elective",
    "matheg": "Math Elective",
    "nslab": "Natural Science Lab",
    "cis-el": "CIS Elective",
    "cis-proj": "CIS Project Elective",
    "tech": "Technical Elective",
    "eng": "Engineering Elective",
    "prof": "Professional Elective",
    "be-el": "Bioengineering Elective",
    "dmd": "DMD Elective",
    "meam-up": "MEAM Upper Level",
    "ese-adv": "Advanced ESE Elective",
    "ese-mid": "Intermediate or Advanced ESE Elective",
    "gened": "General Education or Free Elective",
    "bio-el": "Biology or Biology-related Elective",
    "math-adv": "Mathematics Elective, 3000 to 5999",
}


def req(*codes: str, credits: float = 1.0, label: str | None = None,
        slots: int = 1, note: str = "") -> dict[str, Any]:
    """A row satisfied by one of the listed courses."""
    if label is None:
        label = codes[0] if len(codes) == 1 else " or ".join(codes)
    return {
        "kind": "explicit", "label": label, "credits": credits,
        "slots": slots, "codes": list(codes), "note": note,
    }


def pattern(label: str, subjects: list[str], min_level: int,
            credits: float = 1.0, slots: int = 1, note: str = "") -> dict[str, Any]:
    """A row satisfied by any course in a subject at or above a level."""
    return {
        "kind": "pattern", "label": label, "credits": credits, "slots": slots,
        "subjects": subjects, "min_level": min_level, "note": note,
    }


def slot(tag: str, count: int = 1, credits_each: float = 1.0,
         label: str | None = None, note: str = "") -> dict[str, Any]:
    """A row the catalog leaves open, filled by labelled placeholders."""
    return {
        "kind": "slot", "label": label or SLOT_TAGS[tag], "tag": tag,
        "credits": credits_each * count, "slots": count, "note": note,
    }


def group(name: str, rows: list[dict[str, Any]], note: str = "") -> dict[str, Any]:
    return {"name": name, "note": note, "rows": rows}


# Shared rows that several SEAS degrees print identically.
_ETHICS = req("EAS 2030", "CIS 4230", "CIS 5230", label="Ethics requirement")
_SENIOR_DESIGN_CIS = [req("CIS 4000", "ESE 4500"), req("CIS 4010", "ESE 4510")]


PROGRAMS: list[dict[str, Any]] = [
    # ==================================================== SEAS: CS BSE ====
    {
        "code": "CIS-BSE", "name": "Computer Science", "degree": "BSE",
        "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/computer-science-bse/",
        "notes": "The classic Penn CS degree. Heavy on theory and systems, with "
                 "six technical electives to point in whatever direction you like.",
        "groups": [
            group("Engineering", [
                req("CIS 1100"), req("CIS 1200"), req("CIS 1210"), req("CIS 2400"),
                req("CIS 2620"), req("CIS 3200"),
                req("CIS 4480", "CIS 5480"), req("CIS 4710", "CIS 5710"),
                req("CIS 4000", "CIS 4100"), req("CIS 4010", "CIS 4110"),
            ]),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410", "MATH 1610"),
                req("MATH 2400", "MATH 2600", "ESE 2030"),
                req("CIS 1600"),
                req("CIS 2610", "ESE 3010", "STAT 4300", label="Probability requirement"),
                req("MEAM 1100", "PHYS 0150", "PHYS 0170", credits=1.5,
                    label="Mechanics requirement"),
                req("PHYS 0151", "PHYS 0171", "ESE 1120", credits=1.5,
                    label="Electromagnetism requirement"),
                slot("mns"),
            ]),
            group("CIS Electives", [slot("cis-el", 4)],
                  note="A CIS or NETS engineering course at the 1000 level or "
                       "above, with at most one course unit from 1000-level work."),
            group("Technical Electives", [slot("tech", 6)]),
            group("General Electives", [_ETHICS, slot("ssh", 4), slot("sshtbs", 2)],
                  note="The social science and humanities set must include a "
                       "Writing Seminar."),
            group("Free Elective", [slot("free", 1)]),
        ],
    },

    # ================================================== SEAS: CMPE BSE ====
    {
        "code": "CMPE-BSE", "name": "Computer Engineering", "degree": "BSE",
        "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/computer-engineering-bse/",
        "notes": "Where software meets the hardware it runs on: circuits, "
                 "embedded systems and computer architecture alongside the CIS core.",
        "groups": [
            group("Engineering", [
                req("ESE 1110", "ESE 3600"), req("CIS 1100"), req("CIS 1200"),
                req("CIS 1210"), req("ESE 2150", credits=1.5), req("CIS 2400"),
                req("ESE 3500", credits=1.5), req("ESE 3700"),
                req("CIS 4480", "CIS 5480"), req("CIS 4710", "CIS 5710"),
            ]),
            group("Intermediate CIS or ESE Elective", [
                pattern("2000 level or above CIS or ESE", ["CIS", "ESE"], 2000),
            ]),
            group("Advanced CIS or ESE Electives", [
                pattern("3000 level or above CIS or ESE", ["CIS", "ESE"], 3000, slots=2,
                        credits=2.0),
            ]),
            group("Senior Design", _SENIOR_DESIGN_CIS),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410", "MATH 1610"),
                req("MATH 2400", "MATH 2600", "ESE 2030"),
                req("ESE 3010", "CIS 2610", "STAT 4300", label="Probability requirement"),
                req("CIS 1600"),
                req("MEAM 1100", "PHYS 0140", "PHYS 0150", "PHYS 0170",
                    label="Mechanics requirement"),
                req("ESE 1120", credits=1.5),
                req("CHEM 1012", "EAS 0091", "BIOL 1101", "BIOL 1121", "PHYS 1240",
                    label="Natural science requirement"),
                slot("mns"), slot("nslab", 1, 0.5),
            ]),
            group("Professional Electives", [slot("prof", 3)],
                  note="At most two freshman-level engineering courses may count."),
            group("General Electives", [
                req("EAS 2030", "CIS 4230", "CIS 5230", label="Ethics requirement"),
                slot("ssh", 4), slot("sshtbs", 2), slot("free", 1),
            ]),
        ],
    },

    # =================================================== SEAS: DMD BSE ====
    {
        "code": "DMD-BSE", "name": "Digital Media Design", "degree": "BSE",
        "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/digital-media-design-bse/",
        "notes": "Computer graphics and animation, with a studio art track "
                 "sitting on top of most of the CS core.",
        "groups": [
            group("Engineering", [
                req("CIS 1100"), req("CIS 1200"), req("CIS 1210"), req("CIS 2400"),
                req("CIS 2620"), req("CIS 3200"), req("CIS 4600", "CIS 5600"),
                req("CIS 4610", "CIS 5610", "CIS 4620", "CIS 5620", "CIS 4550", "CIS 5550",
                    label="Two graphics or web systems courses", slots=2, credits=2.0),
                req("CIS 4970"),
                slot("cis-el", 4),
            ]),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410", "MATH 1610"),
                req("ESE 2030", "ENM 2030", "ENM 2400", label="Linear algebra requirement"),
                req("CIS 1600"),
                req("CIS 2610", "ESE 3010", "STAT 4300", label="Probability requirement"),
                req("MEAM 1100", "PHYS 0150", "PHYS 0170", credits=1.5,
                    label="Mechanics requirement"),
                req("BIOL 1101", "CHEM 1012", "ESE 1120", "PHYS 0151", "PHYS 0171",
                    credits=1.5, label="Natural science requirement"),
                slot("mns"),
            ]),
            group("DMD Electives", [
                req("FNAR 0010", "FNAR 2200", "FNAR 1080", label="Drawing requirement"),
                req("DSGN 1030", "DSGN 2010", label="3-D modeling requirement"),
                req("DSGN 2040", "FNAR 1050", "FNAR 2090", "FNAR 2100",
                    label="Animation requirement"),
                slot("dmd", 3),
            ]),
            group("General Electives", [slot("ssh", 5), slot("sshtbs", 2)]),
            group("Free Elective", [slot("free", 1)]),
        ],
    },

    # =================================================== SEAS: NETS BSE ===
    {
        "code": "NETS-BSE", "name": "Networked and Social Systems Engineering",
        "degree": "BSE", "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/"
                  "networked-social-systems-engineering-bse/",
        "notes": "Networks, markets and game theory. The most economics-adjacent "
                 "engineering degree Penn offers.",
        "groups": [
            group("Engineering", [
                req("CIS 1100"), req("CIS 1200"), req("CIS 1210"), req("CIS 3200"),
                req("ESE 2040", "ESE 5060", "ESE 6050", label="Optimization requirement"),
                req("ESE 3030", "CIS 4190", "CIS 5190", "ESE 5450", "CIS 5200", "CIS 5450",
                    label="Statistics or machine learning requirement"),
                req("ESE 3050"), req("NETS 1120"), req("NETS 1500"), req("NETS 2120"),
                req("NETS 3120"), req("NETS 4120"),
                req("CIS 4000", "CIS 4100", "ESE 4500"),
                req("CIS 4010", "CIS 4110", "ESE 4510"),
            ]),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410", "MATH 1610"),
                req("MATH 2400", "MATH 2600"), req("CIS 1600"),
                req("MATH 3120", "MATH 3130", "MATH 3140",
                    label="Linear algebra requirement"),
                req("CIS 2610", "ESE 3010", "STAT 4300", label="Probability requirement"),
                req("MEAM 1100", "PHYS 0150", "PHYS 0170", credits=1.5,
                    label="Mechanics requirement"),
                req("PHYS 0151", "PHYS 0171", "ESE 1120", credits=1.5,
                    label="Electromagnetism requirement"),
            ]),
            group("Technical Electives", [slot("tech", 6)],
                  note="At least four courses from an approved depth area."),
            group("General Electives", [
                req("ECON 2100"),
                req("ECON 4100", label="Game theory requirement"),
                req("EAS 2030", "CIS 4230", "CIS 5230", label="Ethics requirement"),
                slot("ssh", 2), slot("sshtbs", 2),
            ]),
            group("Free Elective", [slot("free", 1)]),
        ],
    },

    # ===================================================== SEAS: BE BSE ===
    {
        "code": "BE-BSE", "name": "Bioengineering", "degree": "BSE",
        "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/bioengineering-bse/",
        "notes": "The most prescribed SEAS degree: a long chain of BE courses "
                 "on top of a full chemistry and biology sequence.",
        "groups": [
            group("Engineering", [
                req("BE 1000", credits=0.5), req("ENGR 1050"), req("BE 2000"),
                req("BE 2200"), req("BE 2700"), req("BE 3010"), req("BE 3060"),
                req("BE 3090"), req("BE 3100"), req("BE 3500"), req("BE 4950"),
                req("BE 4960"), slot("be-el", 2), slot("eng", 2),
            ]),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410"),
                req("ESE 2030", "ENM 2030", "ENM 2400", label="Linear algebra requirement"),
                req("ENM 3750", "ENGR 3440", label="Biostatistics requirement"),
                req("PHYS 0140"), req("PHYS 0141"),
                req("CHEM 1012", "CHEM 1151"), req("CHEM 1101", credits=0.5),
                req("CHEM 1102", credits=0.5), req("CHEM 1022", "CHEM 1161"),
                req("BIOL 1121"), req("BIOL 1123", credits=0.5), req("BIOL 3310"),
            ]),
            group("General Electives", [
                req("EAS 2030", "BIOE 4010", "BIOE 4020", "HSOC 1330", "HSOC 2457",
                    "LGST 1000", "LGST 2200", "NURS 3300", "PHIL 4330", "PHIL 1342",
                    label="Ethics requirement"),
                slot("ss", 1), slot("hum", 2), slot("ssh", 1), slot("sshtbs", 2),
            ]),
            group("Free Elective", [slot("free", 3)]),
        ],
    },

    # =================================================== SEAS: MEAM BSE ===
    {
        "code": "MEAM-BSE", "name": "Mechanical Engineering and Applied Mechanics",
        "degree": "BSE", "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/"
                  "mechanical-engineering-applied-mechanics-bse/",
        "notes": "Statics, dynamics, thermodynamics and fluids, with a design "
                 "laboratory in every year. Shown here with the General "
                 "Concentration; three other tracks exist.",
        "groups": [
            group("MEAM Core", [
                req("MEAM 2020"), req("MEAM 2030"), req("MEAM 2100"), req("MEAM 2110"),
                req("MEAM 2470", credits=0.5), req("MEAM 2480", credits=0.5),
                req("MEAM 3470"), req("MEAM 3480"), req("MEAM 4450"), req("MEAM 4460"),
            ]),
            group("Concentration", [
                req("MEAM 3020"), req("MEAM 3210"), req("MEAM 3330"), req("MEAM 3540"),
            ], note="The General Concentration. Declaring one of the three named "
                    "tracks swaps two of these rows."),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410"), req("MATH 2400"),
                req("ENM 2510", "MATH 2410", label="Analytical methods requirement"),
                req("MEAM 1100", "PHYS 0150", credits=1.5, label="Mechanics requirement"),
                req("PHYS 0151", "ESE 1120", credits=1.5,
                    label="Electromagnetism requirement"),
                req("CHEM 1012", "BIOL 1121", label="Natural science requirement"),
                slot("matheg"), slot("mns"),
            ]),
            group("Professional Elective", [req("ENGR 1050", "CIS 1100", "CIS 1200")]),
            group("MEAM Upper Level", [slot("meam-up", 2)],
                  note="MEAM 5000-level courses other than MEAM 5990."),
            group("Technical Electives", [slot("tech", 4)]),
            group("General Electives", [
                req("EAS 2030"), slot("ss", 1), slot("hum", 2), slot("ssh", 1),
                slot("sshtbs", 2),
            ]),
        ],
    },

    # ===================================================== SEAS: EE BSE ===
    {
        "code": "EE-BSE", "name": "Electrical Engineering", "degree": "BSE",
        "school": SEAS, "total_units": 37.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/"
                  "electrical-engineering-bse/",
        "notes": "Circuits, devices and signals, with four advanced electives "
                 "chosen from three depth areas.",
        "groups": [
            group("Engineering", [
                req("CIS 1100"), req("ESE 1110"), req("CIS 1200", "CIS 2400"),
                req("ESE 2150", credits=1.5), req("ESE 2180", credits=1.5),
                req("ESE 2240", credits=1.5),
                slot("ese-mid", 1), slot("ese-adv", 4),
            ], note="The catalog prints the advanced elective lists as titles "
                    "without course codes, so they are slots here rather than "
                    "an invented course list."),
            group("Design and Project Courses", [
                req("ESE 2910", "ESE 3190", "ESE 3360", "ESE 3500", "ESE 4210", "BE 4700",
                    credits=1.5, label="Design or project course"),
                req("ESE 4500"), req("ESE 4510"),
            ]),
            group("Math and Natural Science", [
                req("MATH 1400"), req("MATH 1410"), req("MATH 2400", "ESE 2030"),
                req("ESE 3010"),
                req("MEAM 1100", "PHYS 0140", "PHYS 0150", "PHYS 0170",
                    label="Mechanics requirement"),
                req("ESE 1120", credits=1.5),
                req("CHEM 1012", "EAS 0091", "BIOL 1101", "BIOL 1121",
                    label="Natural science requirement"),
                slot("matheg"), slot("mns"), slot("nslab", 1, 0.5),
            ]),
            group("Professional Electives", [slot("prof", 4)]),
            group("General Electives", [
                req("EAS 2030", "CIS 4230", "CIS 5230", label="Ethics requirement"),
                slot("ssh", 4), slot("sshtbs", 2),
            ]),
        ],
    },

    # ================================================= COLLEGE: CS BA =====
    {
        "code": "CIS-BA", "name": "Computer Science", "degree": "BA",
        "school": COLLEGE, "total_units": 12.0, "full_degree": False,
        "source": "https://catalog.upenn.edu/undergraduate/programs/computer-science-ba/",
        "notes": "A second major only. The catalog states it cannot be a "
                 "student's sole major, and prints a major total of 12 course "
                 "units with no degree total, so this program tracks the major "
                 "rather than a whole degree.",
        "groups": [
            group("Major Requirements", [
                req("CIS 1100"), req("CIS 1200"), req("CIS 1600"), req("CIS 1210"),
                req("CIS 2400"), req("CIS 2620"), req("CIS 3200"),
                slot("cis-proj", 2), slot("cis-el", 1),
                pattern("CIS elective, 2000 level or above", ["CIS", "NETS"], 2000,
                        slots=2, credits=2.0),
            ], note="Admission requires a cumulative GPA of 3.0 or above and a "
                    "grade of B or higher in CIS 1200."),
        ],
    },

    # =============================================== COLLEGE: MATH BA =====
    {
        "code": "MATH-BA", "name": "Mathematics", "degree": "BA",
        "school": COLLEGE, "total_units": 33.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/mathematics-ba/",
        "notes": "Analysis, algebra and complex analysis, with the College's "
                 "general education requirements taking up most of the rest.",
        "groups": [
            group("College General Education and Free Electives", [slot("gened", 20)],
                  note="The catalog prints Foundational Approaches, Sectors and "
                       "free electives as one combined figure and gives no "
                       "per-sector unit counts, so this app does not invent them."),
            group("Calculus Requirement", [
                req("MATH 1400"), req("MATH 1410", "MATH 1610"),
            ], note="Starting at MATH 1610 instead reduces this to one course unit."),
            group("Complex Analysis Requirement", [req("MATH 4100")]),
            group("Advanced Linear Algebra Requirement", [
                req("MATH 3000"), req("MATH 3001"),
            ]),
            group("Differential Equations Requirement", [
                req("MATH 2300", "MATH 4200", "MATH 4250",
                    label="Differential equations requirement"),
            ]),
            group("Algebra Requirement", [
                req("MATH 3700", "MATH 5020"), req("MATH 3710", "MATH 5030"),
            ]),
            group("Analysis Requirement", [
                req("MATH 3600", "MATH 5080"), req("MATH 3610", "MATH 5090"),
            ]),
            group("Mathematics Electives", [slot("math-adv", 3)]),
        ],
    },

    # ================================================ COLLEGE: BIOL BA ====
    {
        "code": "BIOL-BA", "name": "Biology", "degree": "BA",
        "school": COLLEGE, "total_units": 36.0,
        "source": "https://catalog.upenn.edu/undergraduate/programs/"
                  "biology-general-biology-ba/",
        "notes": "Introductory biology, a physical sciences base, and paired "
                 "intermediate courses from two groups.",
        "groups": [
            group("College General Education and Free Electives", [slot("gened", 19)]),
            group("Introductory Biology Requirement", [
                req("BIOL 1121"), req("BIOL 1123", credits=0.5),
                req("BIOL 1124", credits=0.5),
                pattern("Additional BIOL course, 2000 level or above", ["BIOL"], 2000),
            ], note="Track 1. Track 2 substitutes BIOL 1101 and BIOL 1102."),
            group("Physical Sciences, Calculus, Statistics and Computer Science", [
                req("CHEM 1011", "CHEM 1021", "CHEM 1012", "CHEM 1022", "CHEM 1101",
                    "CHEM 1102", "PHYS 0101", "PHYS 0102", "PHYS 0150", "PHYS 0151",
                    "MATH 1300", "MATH 1400", "MATH 1410", "BIOL 2510", "STAT 1110",
                    "STAT 1010", "CIS 1200", "CIS 1600",
                    label="Four course units from the approved list",
                    slots=4, credits=4.0),
            ]),
            group("Intermediate Level Biology Courses", [
                req("BIOL 2010", "BIOL 2110", "BIOL 2210", "BIOL 2810", "CHEM 2510",
                    label="Two courses from Group 1", slots=2, credits=2.0),
                req("BIOL 2140", "BIOL 3310", "BIOL 2311", "BIOL 2410", "BIOL 2610",
                    label="Two courses from Group 2", slots=2, credits=2.0),
            ]),
            group("Additional Biology Requirement", [slot("bio-el", 6)]),
        ],
    },
]
