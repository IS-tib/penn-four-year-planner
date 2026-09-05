"""Seed catalog for the Penn Computer Science BSE.

Course codes, titles, course-unit values and prerequisite expressions are taken
from the Penn course catalog (catalog.upenn.edu/courses/cis, /math, /phys) and
the Computer Science BSE program page. Where the catalog states a prerequisite
as a boolean expression it is transcribed here in the same shape: a list of
OR-groups that are AND'd together.

This is a curated subset, not the whole university catalog. Requirement buckets
that allow hundreds of different courses (technical electives, social science
and humanities) are seeded as explicit placeholder slots instead, one per unit
the degree requires, so a student can lay out a full four years before deciding
exactly which elective fills each hole. Nothing in this file is invented: a
course appears with a real title and real prerequisites, or it appears as a
clearly labelled placeholder.
"""

from __future__ import annotations

from typing import Any

CORE = "CIS Core"
MNS = "Math & Natural Science"
CIS_ELECTIVE = "CIS Elective"
TECH_ELECTIVE = "Technical Elective"
GENERAL = "General Elective"
FREE = "Free Elective"

# Course-unit targets per requirement bucket, added up from the line items the
# Computer Science BSE program page lists inside each bucket:
#   CIS core            the nine named courses, 1 CU each
#   Math & nat. science 2 calculus + CIS 1600 + probability + linear algebra
#                       + 1.5 mechanics + 1.5 electromagnetism + 1 elective
#   the rest            printed as bucket totals on the program page
CATEGORY_TARGETS: dict[str, float] = {
    CORE: 9.0,
    MNS: 9.0,
    CIS_ELECTIVE: 4.0,
    TECH_ELECTIVE: 6.0,
    GENERAL: 7.0,
    FREE: 1.0,
}

CATEGORY_ORDER = [CORE, MNS, CIS_ELECTIVE, TECH_ELECTIVE, GENERAL, FREE]

# What this app tracks, which is the sum of the buckets above.
TRACKED_TOTAL_CU = round(sum(CATEGORY_TARGETS.values()), 2)

# What Penn publishes as the degree total. It is one course unit more than the
# buckets above add up to, and the catalog page does not make clear where that
# unit sits, so the app reports both numbers rather than quietly picking one.
PUBLISHED_DEGREE_TOTAL_CU = 37.0

# The CIS elective bucket allows "a maximum of one course unit from 1000-level
# courses", per the Computer Science BSE program page. The 0.5 CU programming
# language courses are the ones this actually bites on.
CIS_ELECTIVE_LEVEL_CAP = {"category": CIS_ELECTIVE, "level": 1000, "max_credits": 1.0}


def _level(code: str) -> int | None:
    """The thousands band of a course number, or None for a placeholder slot."""
    parts = code.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    return (int(parts[1]) // 1000) * 1000


def _c(
    code: str,
    title: str,
    category: str,
    credits: float = 1.0,
    prereqs: list[dict[str, Any]] | None = None,
    description: str = "",
    placeholder: bool = False,
    min_term: int = 0,
    preferred_term: int | None = None,
    equiv: str | None = None,
) -> dict[str, Any]:
    return {
        "preferred_term": preferred_term,
        "code": code,
        "title": title,
        "category": category,
        "credits": credits,
        "department": code.split()[0] if " " in code else "SLOT",
        "prereqs": prereqs or [],
        "description": description,
        "placeholder": placeholder,
        "min_term": min_term,
        "level": _level(code),
        # Cross-listed courses share this key, which is the undergraduate
        # number of the pair.
        "equiv": equiv,
    }


def _all(*codes: str, concurrent: bool = False) -> list[dict[str, Any]]:
    """Each code becomes its own single-member group, so they are AND'd."""
    return [{"any_of": [code], "concurrent": concurrent} for code in codes]


def _any(*codes: str, concurrent: bool = False) -> dict[str, Any]:
    """One group with several members, which is an OR."""
    return {"any_of": list(codes), "concurrent": concurrent}


COURSES: list[dict[str, Any]] = [
    # ---- CIS core (9 CU) ----------------------------------------------------
    _c("CIS 1100", "Introduction to Computer Programming", CORE, preferred_term=0,
       description="First programming course for students without prior experience. "
                   "No formal prerequisite ties it to CIS 1200, but it is the "
                   "intended entry point, so the autofill seats it first."),
    _c("CIS 1200", "Programming Languages and Techniques I", CORE,
       description="Program design and data structures in OCaml and Java."),
    _c("CIS 1210", "Programming Languages and Techniques II", CORE,
       prereqs=_all("CIS 1200", "CIS 1600"),
       description="Data structures and algorithm analysis in Java."),
    _c("CIS 2400", "Introduction to Computer Systems", CORE,
       prereqs=_all("CIS 1200"),
       description="From transistors and digital logic up to C and assembly."),
    _c("CIS 2620", "Automata, Computability, and Complexity", CORE,
       prereqs=_all("CIS 1600"),
       description="Formal languages, decidability and complexity classes."),
    _c("CIS 3200", "Introduction to Algorithms", CORE,
       prereqs=_all("CIS 1210", "CIS 2620"),
       description="Algorithm design paradigms, correctness proofs, NP-completeness."),
    _c("CIS 4480", "Operating Systems Design and Implementation", CORE, equiv="CIS 4480",
       prereqs=_all("CIS 2400"),
       description="Processes, scheduling, virtual memory and file systems, in C."),
    _c("CIS 4710", "Computer Organization and Design", CORE, equiv="CIS 4710",
       prereqs=_all("CIS 2400"),
       description="Pipelining, caches, and processor microarchitecture."),
    _c("CIS 4000", "Senior Project", CORE, min_term=6,
       description="Capstone. The catalog requires senior standing, so it cannot "
                   "sit earlier than the fourth year."),

    # ---- Math and natural science (8.5 CU) ----------------------------------
    _c("MATH 1400", "Calculus, Part I", MNS),
    _c("MATH 1410", "Calculus, Part II", MNS, prereqs=_all("MATH 1400")),
    _c("MATH 1610", "Calculus for the Mathematical Sciences", MNS,
       prereqs=_all("MATH 1400")),
    _c("MATH 2400", "Calculus, Part III", MNS,
       prereqs=[_any("MATH 1410", "MATH 1610")]),
    _c("CIS 1600", "Mathematical Foundations of Computer Science", MNS,
       description="Logic, proof, induction, counting and discrete probability."),
    _c("CIS 2610", "Discrete Probability, Stochastic Processes, and Statistical Inference",
       MNS, prereqs=_all("CIS 1600")),
    _c("PHYS 0150", "Principles of Physics I: Mechanics and Wave Motion", MNS, credits=1.5,
       prereqs=_all("MATH 1400", concurrent=True),
       description="Catalog allows MATH 1400 to be taken at the same time."),
    _c("PHYS 0151", "Principles of Physics II: Electromagnetism and Radiation", MNS,
       credits=1.5,
       prereqs=[_any("PHYS 0150"), _any("MATH 1410", concurrent=True)],
       description="Catalog allows MATH 1410 to be taken at the same time."),
    _c("PHYS 0170", "Honors Physics I: Mechanics and Wave Motion", MNS, credits=1.5,
       prereqs=[_any("MATH 1400"), _any("MATH 1410", "MATH 1610")]),
    _c("PHYS 0171", "Honors Physics II: Electromagnetism and Radiation", MNS, credits=1.5,
       prereqs=[
           _any("MATH 1410", "MATH 1610"),
           _any("PHYS 0150", "PHYS 0170"),
           _any("MATH 2400"),
       ]),

    # ---- CIS and technical electives (real courses) -------------------------
    _c("CIS 1902", "Python Programming", CIS_ELECTIVE, credits=0.5,
       prereqs=_all("CIS 1200")),
    _c("CIS 1904", "Introduction to Haskell Programming", CIS_ELECTIVE, credits=0.5,
       prereqs=_all("CIS 1200")),
    _c("CIS 1905", "Rust Programming", CIS_ELECTIVE, credits=0.5,
       prereqs=_all("CIS 1200")),
    _c("CIS 1912", "DevOps", CIS_ELECTIVE, credits=0.5),
    _c("CIS 1951", "iOS Programming", CIS_ELECTIVE, credits=0.5,
       prereqs=_all("CIS 1200")),
    _c("CIS 1962", "JavaScript Programming", CIS_ELECTIVE, credits=0.5),
    _c("CIS 2330", "Introduction to Blockchain", CIS_ELECTIVE, prereqs=_all("CIS 1200")),
    _c("CIS 2450", "Big Data Analytics", CIS_ELECTIVE, prereqs=_all("CIS 1200")),
    _c("CIS 3340", "Advanced Topics in Algorithms", TECH_ELECTIVE,
       prereqs=_all("CIS 3200")),
    _c("CIS 3500", "Software Design/Engineering", TECH_ELECTIVE,
       prereqs=_all("CIS 1210")),
    _c("CIS 3900", "Robotics: Planning Perception", TECH_ELECTIVE,
       prereqs=_all("CIS 1210", "MATH 2400")),
    _c("CIS 4120", "Introduction to Human Computer Interaction", TECH_ELECTIVE, equiv="CIS 4120"),
    _c("CIS 4190", "Applied Machine Learning", TECH_ELECTIVE, equiv="CIS 4190", prereqs=_all("CIS 1210")),
    _c("CIS 4210", "Artificial Intelligence", TECH_ELECTIVE, equiv="CIS 4210", prereqs=_all("CIS 1210")),
    _c("CIS 4230", "Ethical Algorithm Design", GENERAL, equiv="CIS 4230", prereqs=_all("CIS 1210"),
       description="Satisfies the BSE ethics requirement."),
    _c("CIS 4300", "Natural Language Processing", TECH_ELECTIVE, equiv="CIS 4300",
       prereqs=_all("CIS 1210", "CIS 1600")),
    _c("CIS 4410", "Embedded Software for Life-Critical Applications", TECH_ELECTIVE, equiv="CIS 4410",
       prereqs=_all("CIS 2400")),
    _c("CIS 4500", "Database and Information Systems", TECH_ELECTIVE, equiv="CIS 4500",
       prereqs=_all("CIS 1210", "CIS 1600"),
       description="Satisfies the databases requirement."),
    _c("CIS 4510", "Computer and Network Security", TECH_ELECTIVE, equiv="CIS 4510",
       prereqs=_all("CIS 1600", "CIS 2400")),
    _c("CIS 4520", "Advanced Programming", TECH_ELECTIVE, equiv="CIS 4520", prereqs=_all("CIS 1210")),
    _c("CIS 4521", "Compilers and Interpreters", TECH_ELECTIVE, equiv="CIS 4521", prereqs=_all("CIS 1210")),
    _c("CIS 4600", "Interactive Computer Graphics", TECH_ELECTIVE, equiv="CIS 4600",
       prereqs=_all("CIS 1210")),
    _c("CIS 4810", "Computer Vision & Computational Photography", TECH_ELECTIVE, equiv="CIS 4810",
       prereqs=_all("CIS 1210", "CIS 1600")),
    _c("CIS 5200", "Machine Learning", TECH_ELECTIVE,
       description="Satisfies the machine learning requirement."),
    _c("CIS 5450", "Big Data Analytics", TECH_ELECTIVE),
    _c("CIS 5530", "Networked Systems", TECH_ELECTIVE, prereqs=_all("CIS 1210"),
       description="Satisfies the networking requirement."),
    _c("CIS 5550", "Internet and Web Systems", TECH_ELECTIVE,
       description="Satisfies the distributed systems requirement."),

    # ---- Cross-listed graduate numbers --------------------------------------
    # Fourteen of the courses above are also listed at the 5000 level with an
    # identical title, which is how Penn cross-lists a course between the
    # undergraduate and masters catalogs. The BSE program page confirms two of
    # them explicitly, writing the operating systems and computer organization
    # core requirements as "CIS 4480/5480" and "CIS 4710/5710". Each pair shares
    # an equivalence key so a plan holding both numbers is caught as counting
    # one course twice, and each twin carries its twin's requirement bucket.
    #
    # The graduate listings state prerequisites loosely, as "CIS 1210 or
    # equivalent knowledge" or as nothing at all. They are transcribed as
    # written: the named course where one is named, and left open otherwise.
    _c("CIS 5120", "Introduction to Human Computer Interaction", TECH_ELECTIVE,
       equiv="CIS 4120"),
    _c("CIS 5190", "Applied Machine Learning", TECH_ELECTIVE, equiv="CIS 4190",
       prereqs=_all("CIS 1210")),
    _c("CIS 5210", "Artificial Intelligence", TECH_ELECTIVE, equiv="CIS 4210"),
    _c("CIS 5230", "Ethical Algorithm Design", GENERAL, equiv="CIS 4230",
       prereqs=_all("CIS 1210")),
    _c("CIS 5300", "Natural Language Processing", TECH_ELECTIVE, equiv="CIS 4300"),
    _c("CIS 5410", "Embedded Software for Life-Critical Applications", TECH_ELECTIVE,
       equiv="CIS 4410", prereqs=_all("CIS 2400")),
    _c("CIS 5480", "Operating Systems Design and Implementation", CORE, equiv="CIS 4480"),
    _c("CIS 5500", "Database and Information Systems", TECH_ELECTIVE, equiv="CIS 4500"),
    _c("CIS 5510", "Computer and Network Security", TECH_ELECTIVE, equiv="CIS 4510",
       prereqs=_all("CIS 1600", "CIS 2400")),
    _c("CIS 5520", "Advanced Programming", TECH_ELECTIVE, equiv="CIS 4520"),
    _c("CIS 5521", "Compilers and Interpreters", TECH_ELECTIVE, equiv="CIS 4521"),
    _c("CIS 5600", "Interactive Computer Graphics", TECH_ELECTIVE, equiv="CIS 4600"),
    _c("CIS 5710", "Computer Organization and Design", CORE, equiv="CIS 4710",
       prereqs=_all("CIS 2400")),
    _c("CIS 5810", "Computer Vision & Computational Photography", TECH_ELECTIVE,
       equiv="CIS 4810"),

    # ---- Placeholder slots, one per course unit the degree requires ---------
    _c("MNS-1", "Math or Natural Science Elective", MNS, placeholder=True),
    _c("CIS-E1", "CIS Elective I", CIS_ELECTIVE, placeholder=True),
    _c("CIS-E2", "CIS Elective II", CIS_ELECTIVE, placeholder=True),
    _c("CIS-E3", "CIS Elective III", CIS_ELECTIVE, placeholder=True),
    _c("CIS-E4", "CIS Elective IV", CIS_ELECTIVE, placeholder=True),
    _c("TECH-1", "Technical Elective I", TECH_ELECTIVE, placeholder=True),
    _c("TECH-2", "Technical Elective II", TECH_ELECTIVE, placeholder=True),
    _c("TECH-3", "Technical Elective III", TECH_ELECTIVE, placeholder=True),
    _c("TECH-4", "Technical Elective IV", TECH_ELECTIVE, placeholder=True),
    _c("TECH-5", "Technical Elective V", TECH_ELECTIVE, placeholder=True),
    _c("TECH-6", "Technical Elective VI", TECH_ELECTIVE, placeholder=True),
    _c("ETH-1", "Ethics Requirement", GENERAL, placeholder=True),
    _c("SSH-1", "Social Science or Humanities I", GENERAL, placeholder=True),
    _c("SSH-2", "Social Science or Humanities II", GENERAL, placeholder=True),
    _c("SSH-3", "Social Science or Humanities III", GENERAL, placeholder=True),
    _c("SSH-4", "Social Science or Humanities IV", GENERAL, placeholder=True),
    _c("SSHT-1", "Social Science, Humanities or Tech in Business & Society I", GENERAL,
       placeholder=True),
    _c("SSHT-2", "Social Science, Humanities or Tech in Business & Society II", GENERAL,
       placeholder=True),
    _c("FREE-1", "Free Elective", FREE, placeholder=True),
]
