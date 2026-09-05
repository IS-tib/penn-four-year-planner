"""The seeded course catalog.

Every course below is transcribed from catalog.upenn.edu: the subject course
pages for titles, course-unit values and prerequisites, and the program pages
for how each degree uses them. Nothing here is invented. Where the catalog
prints something this app cannot model, the course carries a note saying so
rather than the gap being quietly filled in.

Three transcription decisions worth knowing about.

**Prerequisites go in as conjunctive normal form.** Groups are AND'd, courses
inside a group are OR'd. Most catalog lines are already in that shape. A few
are not: Biology prints "(BIOL 1101 AND BIOL 1102) OR BIOL 1121", which is a
disjunction of a conjunction. Distributing it gives
"(BIOL 1101 OR BIOL 1121) AND (BIOL 1102 OR BIOL 1121)", which is CNF and means
exactly the same thing, so it is stored that way. Every prerequisite in this
file converts; none needed an expression evaluator.

**Placement scores are not modelled as prerequisites.** MATH 1400 prints
"Students must take MATH 1300 or have a placement score of 10+". Most students
arrive with the placement, so treating MATH 1300 as a hard prerequisite would
flag almost every real plan as broken. Those cases are left as notes.

**Corequisite cycles are broken on one side.** MEAM 1100 lists MEAM 1470 as a
prerequisite that may be taken concurrently, and MEAM 1470 lists MEAM 1100 as a
corequisite. Encoding both directions makes a cycle that no scheduler can
order, so the concurrent edge is kept on MEAM 1100 only. The constraint that
matters, that they share a term, still holds.
"""

from __future__ import annotations

from typing import Any


def _level(code: str) -> int | None:
    parts = code.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    return (int(parts[1]) // 1000) * 1000


def c(
    code: str,
    title: str,
    credits: float = 1.0,
    prereqs: list[dict[str, Any]] | None = None,
    note: str = "",
    min_term: int = 0,
    preferred_term: int | None = None,
    equiv: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "credits": credits,
        "subject": code.split()[0],
        "prereqs": prereqs or [],
        "description": note,
        "min_term": min_term,
        "preferred_term": preferred_term,
        "level": _level(code),
        "equiv": equiv,
    }


def all_of(*codes: str, concurrent: bool = False) -> list[dict[str, Any]]:
    """Each code becomes its own single-member group, so they are AND'd."""
    return [{"any_of": [code], "concurrent": concurrent} for code in codes]


def one_of(*codes: str, concurrent: bool = False) -> dict[str, Any]:
    """One group with several members, which is an OR."""
    return {"any_of": list(codes), "concurrent": concurrent}


def groups(*entries: dict[str, Any]) -> list[dict[str, Any]]:
    return list(entries)


# Biology's "(A AND B) OR C" distributed into CNF, used three times below.
def _bio_intro() -> list[dict[str, Any]]:
    return groups(
        one_of("BIOL 1101", "BIOL 1121"),
        one_of("BIOL 1102", "BIOL 1121"),
    )


COURSES: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- CIS --
    c("CIS 1100", "Introduction to Computer Programming", preferred_term=0,
      note="The intended entry point. No catalog prerequisite ties it to "
           "CIS 1200, but advising places it first, so the scheduler does too."),
    c("CIS 1200", "Programming Languages and Techniques I",
      note="Program design and data structures in OCaml and Java."),
    c("CIS 1210", "Programming Languages and Techniques II",
      prereqs=all_of("CIS 1200", "CIS 1600"),
      note="Data structures and algorithm analysis."),
    c("CIS 1600", "Mathematical Foundations of Computer Science",
      note="Logic, proof, induction, counting and discrete probability."),
    c("CIS 1902", "Python Programming", 0.5, all_of("CIS 1200")),
    c("CIS 1904", "Introduction to Haskell Programming", 0.5, all_of("CIS 1200")),
    c("CIS 1905", "Rust Programming", 0.5, all_of("CIS 1200")),
    c("CIS 1912", "DevOps", 0.5),
    c("CIS 1951", "iOS Programming", 0.5, all_of("CIS 1200")),
    c("CIS 1962", "JavaScript Programming", 0.5),
    c("CIS 2330", "Introduction to Blockchain", 1.0, all_of("CIS 1200")),
    c("CIS 2400", "Introduction to Computer Systems", 1.0, all_of("CIS 1200"),
      note="Transistors and digital logic up through C and assembly."),
    c("CIS 2450", "Big Data Analytics", 1.0, all_of("CIS 1200")),
    c("CIS 2610", "Discrete Probability, Stochastic Processes, and Statistical Inference",
      1.0, all_of("CIS 1600")),
    c("CIS 2620", "Automata, Computability, and Complexity", 1.0, all_of("CIS 1600")),
    c("CIS 3200", "Introduction to Algorithms", 1.0, all_of("CIS 1210", "CIS 2620")),
    c("CIS 3340", "Advanced Topics in Algorithms", 1.0, all_of("CIS 3200")),
    c("CIS 3500", "Software Design/Engineering", 1.0, all_of("CIS 1210")),
    c("CIS 3900", "Robotics: Planning Perception", 1.0, all_of("CIS 1210", "MATH 2400")),
    c("CIS 4000", "Senior Project", 1.0, min_term=6,
      note="Catalog requires senior standing."),
    c("CIS 4010", "Senior Project", 1.0, all_of("CIS 4000"), min_term=7),
    c("CIS 4100", "CIS Senior Thesis", 1.0, min_term=6),
    c("CIS 4110", "CIS Senior Thesis", 1.0, all_of("CIS 4100"), min_term=7),
    c("CIS 4120", "Introduction to Human Computer Interaction", 1.0, equiv="CIS 4120"),
    c("CIS 4190", "Applied Machine Learning", 1.0, all_of("CIS 1210"), equiv="CIS 4190"),
    c("CIS 4210", "Artificial Intelligence", 1.0, all_of("CIS 1210"), equiv="CIS 4210"),
    c("CIS 4230", "Ethical Algorithm Design", 1.0, all_of("CIS 1210"), equiv="CIS 4230"),
    c("CIS 4300", "Natural Language Processing", 1.0,
      all_of("CIS 1210", "CIS 1600"), equiv="CIS 4300"),
    c("CIS 4410", "Embedded Software for Life-Critical Applications", 1.0,
      all_of("CIS 2400"), equiv="CIS 4410"),
    c("CIS 4480", "Operating Systems Design and Implementation", 1.0,
      all_of("CIS 2400"), equiv="CIS 4480"),
    c("CIS 4500", "Database and Information Systems", 1.0,
      all_of("CIS 1210", "CIS 1600"), equiv="CIS 4500"),
    c("CIS 4510", "Computer and Network Security", 1.0,
      all_of("CIS 1600", "CIS 2400"), equiv="CIS 4510"),
    c("CIS 4520", "Advanced Programming", 1.0, all_of("CIS 1210"), equiv="CIS 4520"),
    c("CIS 4521", "Compilers and Interpreters", 1.0, all_of("CIS 1210"), equiv="CIS 4521"),
    c("CIS 4550", "Internet and Web Systems", 1.0, equiv="CIS 4550",
      note="Catalog states familiarity with threads, concurrency and Java "
           "rather than a course prerequisite."),
    c("CIS 4600", "Interactive Computer Graphics", 1.0, all_of("CIS 1210"), equiv="CIS 4600"),
    c("CIS 4610", "Advanced Rendering", 1.0, equiv="CIS 4610"),
    c("CIS 4620", "Computer Animation", 1.0, equiv="CIS 4620"),
    c("CIS 4710", "Computer Organization and Design", 1.0,
      all_of("CIS 2400"), equiv="CIS 4710"),
    c("CIS 4810", "Computer Vision & Computational Photography", 1.0,
      all_of("CIS 1210", "CIS 1600"), equiv="CIS 4810"),
    c("CIS 4970", "DMD Senior Project", 1.0, min_term=6,
      note="Catalog requires senior standing."),
    c("CIS 5050", "Software Systems", 1.0),
    c("CIS 5120", "Introduction to Human Computer Interaction", 1.0, equiv="CIS 4120"),
    c("CIS 5190", "Applied Machine Learning", 1.0, all_of("CIS 1210"), equiv="CIS 4190"),
    c("CIS 5200", "Machine Learning", 1.0),
    c("CIS 5210", "Artificial Intelligence", 1.0, equiv="CIS 4210"),
    c("CIS 5230", "Ethical Algorithm Design", 1.0, all_of("CIS 1210"), equiv="CIS 4230"),
    c("CIS 5300", "Natural Language Processing", 1.0, equiv="CIS 4300"),
    c("CIS 5410", "Embedded Software for Life-Critical Applications", 1.0,
      all_of("CIS 2400"), equiv="CIS 4410"),
    c("CIS 5450", "Big Data Analytics", 1.0),
    c("CIS 5480", "Operating Systems Design and Implementation", 1.0, equiv="CIS 4480"),
    c("CIS 5500", "Database and Information Systems", 1.0, equiv="CIS 4500"),
    c("CIS 5510", "Computer and Network Security", 1.0,
      all_of("CIS 1600", "CIS 2400"), equiv="CIS 4510"),
    c("CIS 5520", "Advanced Programming", 1.0, equiv="CIS 4520"),
    c("CIS 5521", "Compilers and Interpreters", 1.0, equiv="CIS 4521"),
    c("CIS 5530", "Networked Systems", 1.0, all_of("CIS 1210")),
    c("CIS 5550", "Internet and Web Systems", 1.0, equiv="CIS 4550"),
    c("CIS 5600", "Interactive Computer Graphics", 1.0, equiv="CIS 4600"),
    c("CIS 5610", "Advanced Computer Graphics", 1.0, equiv="CIS 4610",
      note="Cross-listed with CIS 4610 per the catalog's mutually exclusive "
           "line, though the two entries print different titles."),
    c("CIS 5620", "Computer Animation", 1.0, equiv="CIS 4620"),
    c("CIS 5710", "Computer Organization and Design", 1.0,
      all_of("CIS 2400"), equiv="CIS 4710"),
    c("CIS 5810", "Computer Vision & Computational Photography", 1.0, equiv="CIS 4810"),

    # --------------------------------------------------------------- NETS --
    c("NETS 1120", "Networked Life"),
    c("NETS 1500", "Market and Social Systems on the Internet"),
    c("NETS 2120", "Scalable and Cloud Computing"),
    c("NETS 3120", "Theory of Networks"),
    c("NETS 4120", "Algorithmic Game Theory"),

    # --------------------------------------------------------------- MATH --
    c("MATH 1300", "Introduction to Calculus"),
    c("MATH 1400", "Calculus, Part I",
      note="Catalog allows MATH 1300 or a placement score of 10 or above. "
           "Placement is not modelled."),
    c("MATH 1410", "Calculus, Part II", 1.0, all_of("MATH 1400"),
      note="A placement score of 16 or above also satisfies this."),
    c("MATH 1610", "Calculus for the Mathematical Sciences", 1.0, all_of("MATH 1400"),
      note="Some program tables print this course as Honors Calculus."),
    c("MATH 2300", "Introduction to Ordinary and Partial Differential Equations",
      note="The catalog's prerequisite line was truncated in every retrieval, "
           "so it is not modelled."),
    c("MATH 2400", "Calculus, Part III", 1.0, groups(one_of("MATH 1410", "MATH 1610"))),
    c("MATH 2410", "Calculus, Part IV", 1.0, all_of("MATH 2400"),
      note="Title taken from the MEAM program table. No entry for this course "
           "was found on the MATH course page."),
    c("MATH 2600", "Honors Calculus, Part II", 1.0, all_of("MATH 1410")),
    c("MATH 3000", "Introduction to Proofs and Linear Algebra", 1.0, all_of("MATH 1400")),
    c("MATH 3001", "Advanced linear algebra", 1.0, all_of("MATH 3000")),
    c("MATH 3120", "Linear Algebra", 1.0, all_of("MATH 2400")),
    c("MATH 3130", "Computational Linear Algebra", 1.0, all_of("MATH 2400")),
    c("MATH 3140", "Advanced Linear Algebra", 1.0, all_of("MATH 2400")),
    c("MATH 3600", "Real Analysis", 1.0, all_of("MATH 2400")),
    c("MATH 3610", "Real Analysis II", 1.0, all_of("MATH 3600")),
    c("MATH 3700", "Algebra", 1.0, groups(one_of("MATH 2400", "MATH 2600"))),
    c("MATH 3710", "Algebra", 1.0, groups(one_of("MATH 3700", "MATH 5020"))),
    c("MATH 4100", "Complex Analysis", 1.0, all_of("MATH 2400")),
    c("MATH 4200", "Ordinary Differential Equations", 1.0, all_of("MATH 2400")),
    c("MATH 4250", "Partial Differential Equations", 1.0, all_of("MATH 2400")),
    c("MATH 5020", "Abstract Algebra", 1.0,
      groups(one_of("MATH 2400", "MATH 2600"), one_of("MATH 3140")),
      note="Catalog also allows MATH 5140, which is not in this catalog."),
    c("MATH 5030", "Abstract Algebra", 1.0, all_of("MATH 5020")),
    c("MATH 5080", "Advanced Analysis", 1.0, all_of("MATH 2400", "MATH 2410")),
    c("MATH 5090", "Advanced Analysis", 1.0, all_of("MATH 5080")),

    # --------------------------------------------------------------- PHYS --
    c("PHYS 0050", "Physics Laboratory I", 0.5),
    c("PHYS 0101", "General Physics: Mechanics, Heat and Sound", 1.5),
    c("PHYS 0102", "General Physics: Electromagnetism, Optics, and Modern Physics", 1.5,
      groups(one_of("PHYS 0101", "PHYS 0150", "PHYS 0170"))),
    c("PHYS 0140", "Principles of Physics I (without laboratory)", 1.0, all_of("MATH 1400")),
    c("PHYS 0141", "Principles of Physics II (without laboratory)", 1.0,
      all_of("PHYS 0140", "MATH 1410")),
    c("PHYS 0150", "Principles of Physics I: Mechanics and Wave Motion", 1.5,
      all_of("MATH 1400", concurrent=True),
      note="Catalog allows MATH 1400 to be taken at the same time."),
    c("PHYS 0151", "Principles of Physics II: Electromagnetism and Radiation", 1.5,
      groups(one_of("PHYS 0150"), one_of("MATH 1410", concurrent=True)),
      note="Catalog allows MATH 1410 to be taken at the same time."),
    c("PHYS 0170", "Honors Physics I: Mechanics and Wave Motion", 1.5,
      groups(one_of("MATH 1400"), one_of("MATH 1410", "MATH 1610"))),
    c("PHYS 0171", "Honors Physics II: Electromagnetism and Radiation", 1.5,
      groups(
          one_of("MATH 1410", "MATH 1610"),
          one_of("PHYS 0150", "PHYS 0170"),
          one_of("MATH 2400", "MATH 2600"),
      )),
    c("PHYS 1240", "Principles of Physics IV: Modern Physics (without laboratory)", 1.0,
      groups(
          one_of("PHYS 0150", "PHYS 0151", "PHYS 0170", "PHYS 0171"),
          one_of("MATH 2400"),
      )),

    # --------------------------------------------------------------- CHEM --
    c("CHEM 1011", "Introduction to General Chemistry I"),
    c("CHEM 1012", "General Chemistry I"),
    c("CHEM 1021", "Introduction to General Chemistry II", 1.0, all_of("CHEM 1011"),
      note="The catalog also lists MATH 1300, which placement satisfies for "
           "most students, so it is not modelled here."),
    c("CHEM 1022", "General Chemistry II", 1.0, all_of("CHEM 1012"),
      note="The catalog also lists MATH 1300, which placement satisfies for "
           "most students, so it is not modelled here."),
    c("CHEM 1101", "General Chemistry Laboratory I", 0.5),
    c("CHEM 1102", "General Chemistry Laboratory II", 0.5),
    c("CHEM 1151", "Honors Chemistry I", 1.0,
      note="Catalog prerequisite is an AP Chemistry score of 5, not a course."),
    c("CHEM 1161", "Honors Chemistry II", 1.0, all_of("CHEM 1151")),
    c("CHEM 2510", "Principles of Biological Chemistry", 1.0, all_of("CHEM 1021"),
      note="Catalog also requires CHEM 2410 and CHEM 2420 or CHEM 2425, which "
           "are not in this catalog, so those parts are not modelled."),

    # --------------------------------------------------------------- BIOL --
    c("BIOL 1101", "Introduction to Biology A", 1.5),
    c("BIOL 1102", "Introduction to Biology B", 1.5, all_of("BIOL 1101")),
    c("BIOL 1121", "Introduction to Biology - The Molecular Biology of Life"),
    c("BIOL 1123", "Introductory Molecular Biology Laboratory", 0.5, all_of("BIOL 1121")),
    c("BIOL 1124", "Introductory Organismal Biology Lab", 0.5,
      all_of("BIOL 1121", "BIOL 1123")),
    c("BIOL 2010", "Cell Biology", 1.0, _bio_intro(),
      note="Catalog prints (BIOL 1101 AND BIOL 1102) OR BIOL 1121, stored here "
           "as its equivalent conjunctive normal form."),
    c("BIOL 2110", "Molecular and Cellular Neurobiology", 1.0, _bio_intro()),
    c("BIOL 2140", "Evolution of Behavior: Animal Behavior", 1.0,
      groups(one_of("BIOL 1102", "BIOL 1121")),
      note="Catalog also allows PSYC 0001, which is not in this catalog."),
    c("BIOL 2210", "Molecular Biology and Genetics", 1.0,
      groups(one_of("BIOL 1101", "BIOL 1121"))),
    c("BIOL 2311", "Human Physiology"),
    c("BIOL 2410", "Evolutionary Biology", 1.0, _bio_intro()),
    c("BIOL 2510", "Statistics for Biologists", 1.0, all_of("MATH 1400")),
    c("BIOL 2610", "Ecology: From individuals to ecosystems", 1.0,
      groups(one_of("BIOL 1102", "BIOL 1121"))),
    c("BIOL 2810", "Biochemistry", 1.0, _bio_intro(),
      note="Catalog also requires CHEM 2410, which is not in this catalog."),
    c("BIOL 3310", "Principles of Human Physiology", 1.0,
      groups(one_of("BIOL 1102", "BIOL 1121"))),

    # ----------------------------------------------------------------- BE --
    c("BE 1000", "Introduction to Bioengineering", 0.5, preferred_term=0),
    c("BE 2000", "Introduction to Biomechanics", 1.0,
      groups(one_of("MATH 1410"), one_of("PHYS 0140", "PHYS 0150"))),
    c("BE 2200", "Biomaterials", 1.0, all_of("BE 2000", "CHEM 1022")),
    c("BE 2700", "Bioengineering Laboratory Principles", 1.0,
      groups(one_of("BE 2000"), one_of("ENGR 1050", "CIS 1200", "CIS 1210"))),
    c("BE 3010", "Bioengineering Signals and Systems", 1.0,
      groups(one_of("MATH 2400", "ENM 2400"), one_of("PHYS 0141", "PHYS 0151"))),
    c("BE 3060", "Cellular Engineering", 1.0,
      groups(
          one_of("CHEM 1022"),
          one_of("MATH 2400", "ENM 2400"),
          one_of("PHYS 0140", "PHYS 0150"),
          one_of("PHYS 0141", "PHYS 0151"),
          one_of("BIOL 1121"),
          one_of("ENGR 1050", "CIS 1200", "CIS 1210"),
      )),
    c("BE 3090", "Bioengineering Modeling, Analysis and Design Laboratory I", 1.0,
      groups(
          one_of("ENGR 1050", "CIS 1200", "CIS 1210"),
          one_of("PHYS 0141", "PHYS 0151"),
          one_of("MATH 2400", "ENM 2400"),
          one_of("BE 2000"), one_of("BE 2200"), one_of("BE 2700"),
          one_of("ENM 3750", "ENGR 3440"),
      ),
      note="Catalog also allows STAT 4310 for the statistics requirement."),
    c("BE 3100", "Bioengineering Modeling, Analysis and Design Laboratory II", 1.0,
      groups(
          one_of("ENGR 1050", "CIS 1200", "CIS 1210"),
          one_of("PHYS 0141", "PHYS 0151"),
          one_of("MATH 2400", "ENM 2400"),
          one_of("BE 2000"), one_of("BE 2200"), one_of("BE 2700"), one_of("BE 3010"),
          one_of("ENM 3750", "ENGR 3440"),
      )),
    c("BE 3500", "Introduction to Biotransport Processes", 1.0,
      groups(
          one_of("MATH 2400", "ENM 2400"),
          one_of("PHYS 0140", "PHYS 0150"),
          one_of("BE 2000"),
      )),
    c("BE 4700", "Medical Devices"),
    c("BE 4950", "Senior Design Project", 1.0, min_term=6),
    c("BE 4960", "Senior Design Project", 1.0, all_of("BE 4950"), min_term=7),
    c("BE 5210", "Brain-Computer Interfaces"),

    # ------------------------------------------------------- ENGR and ENM --
    c("ENGR 1050", "Introduction to Scientific Computing"),
    c("ENGR 3440", "Answering Questions with Data, for Everyone"),
    c("ENM 2030", "Linear Algebra with Applications to Engineering and AI", 1.0,
      all_of("MATH 1410"), equiv="ESE 2030",
      note="Also offered as ESE 2030."),
    c("ENM 2400", "Differential Equations and Linear Algebra", 1.0, all_of("MATH 1410")),
    c("ENM 2510", "Analytical Methods for Engineering", 1.0, all_of("MATH 2400")),
    c("ENM 3750", "Biological Data Science I - Fundamentals of Biostatistics"),

    # ---------------------------------------------------------------- ESE --
    c("ESE 1110", "Atoms, Bits, Circuits and Systems", 1.0, preferred_term=0),
    c("ESE 1120", "Engineering Electromagnetics", 1.5,
      groups(
          one_of("MATH 1400"),
          one_of("PHYS 0140", "PHYS 0150", "PHYS 0170", "MEAM 1100"),
      )),
    c("ESE 2030", "Linear Algebra with Applications to Engineering and AI", 1.0,
      all_of("MATH 1410"), equiv="ESE 2030"),
    c("ESE 2040", "Decision Models", 1.0, all_of("MATH 1400")),
    c("ESE 2150", "Electrical Circuits and Systems", 1.5, all_of("ESE 1120")),
    c("ESE 2180", "Electronic, Photonic, and Electromechanical Devices", 1.5,
      all_of("ESE 1120")),
    c("ESE 2240", "Signal and Information Processing", 1.5, all_of("MATH 1400")),
    c("ESE 2900", "Introduction to Electrical and Systems Engineering Research Methodology",
      0.5),
    c("ESE 2910", "Introduction to Electrical and Systems Engineering Research and Design",
      1.0, all_of("ESE 2900")),
    c("ESE 3010", "Engineering Probability", 1.0, all_of("MATH 1410")),
    c("ESE 3030", "Stochastic Systems Analysis and Simulation", 1.0, all_of("ESE 3010")),
    c("ESE 3050", "Foundations of Data Science", 1.0, all_of("ESE 3010")),
    c("ESE 3190", "Fundamentals of Solid-State Circuits", 1.5, all_of("ESE 2150")),
    c("ESE 3360", "Nanofabrication of Electrical Devices", 1.5, all_of("ESE 2180")),
    c("ESE 3500", "Embedded Systems/Microcontroller Laboratory", 1.5,
      all_of("ESE 2150", "CIS 1200")),
    c("ESE 3600", "TinyML: Tiny Machine Learning for Embedded Systems", 1.0,
      all_of("CIS 1200")),
    c("ESE 3700",
      "Circuit-Level Modeling, Design, and Optimization for Digital Systems", 1.0,
      all_of("ESE 2150")),
    c("ESE 4210", "Control For Autonomous Robots", 1.5,
      groups(one_of("ESE 2240", "MEAM 2110"))),
    c("ESE 4500", "Senior Design Project I - EE and SSE", 1.0, min_term=6),
    c("ESE 4510", "Senior Design Project II - EE and SSE", 1.0,
      all_of("ESE 4500"), min_term=7),
    c("ESE 5060", "Introduction to Optimization Theory"),
    c("ESE 5450", "Data Mining: Learning from Massive Datasets"),
    c("ESE 6050", "Modern Convex Optimization"),

    # --------------------------------------------------------------- MEAM --
    c("MEAM 1100", "Introduction to Mechanics", 1.0,
      groups(one_of("MATH 1400"), one_of("MEAM 1470", concurrent=True)),
      note="MEAM 1470 may be taken concurrently. The reverse corequisite is "
           "not encoded, because two mutual edges are a cycle no schedule "
           "can order."),
    c("MEAM 1470", "Introduction to Mechanics Lab", 0.5),
    c("MEAM 2020", "Introduction to Thermal-Fluids Engineering", 1.0,
      groups(one_of("MATH 1400"), one_of("MEAM 1100", "PHYS 0150"), one_of("MATH 1410"))),
    c("MEAM 2030", "Thermodynamics", 1.0, all_of("MATH 1400", "MATH 1410", "MEAM 2020")),
    c("MEAM 2100", "Statics and Strength of Materials", 1.0,
      groups(
          one_of("MEAM 1100", "PHYS 0150", "PHYS 0170"),
          one_of("MATH 2400"),
          one_of("MEAM 2470", concurrent=True),
      )),
    c("MEAM 2110", "Engineering Mechanics: Dynamics", 1.0,
      groups(
          one_of("MEAM 2100"),
          one_of("MATH 2400"),
          one_of("ENGR 1050", "CIS 1100", "CIS 1200"),
          one_of("MATH 2410", "ENM 2510"),
      )),
    c("MEAM 2470", "Mechanical Engineering Laboratory I", 0.5,
      all_of("MEAM 2020"),
      note="The catalog also lists MEAM 2100, which lists MEAM 2470 back as a "
           "concurrent prerequisite. Encoding both directions is a cycle no "
           "schedule can order, so the edge is kept on MEAM 2100 only."),
    c("MEAM 2480", "Mechanical Engineering Lab I", 0.5,
      groups(one_of("MEAM 2030", concurrent=True), one_of("MEAM 2110", concurrent=True))),
    c("MEAM 3020", "Fluid Mechanics", 1.0,
      groups(
          one_of("MATH 2410", "ENM 2510"),
          one_of("PHYS 0150", "MEAM 1100", "PHYS 0170"),
      )),
    c("MEAM 3200", "Intro to Mechanical and Mechatronic Systems", 1.0, all_of("MEAM 3470")),
    c("MEAM 3210", "Dynamic Systems and Control", 1.0,
      groups(one_of("MATH 2410", "ENM 2510"), one_of("MEAM 2110"))),
    c("MEAM 3330", "Heat and Mass Transfer", 1.0, all_of("MEAM 2030", "MEAM 3020")),
    c("MEAM 3470", "Mechanical Engineering Design Laboratory"),
    c("MEAM 3480", "Mechanical Engineering Design Laboratory", 1.0, all_of("MEAM 3470")),
    c("MEAM 3540", "Mechanics of Solids", 1.0, groups(one_of("MEAM 2100", "BE 2000"))),
    c("MEAM 4450", "Mechanical Engineering Design Projects", 1.0, min_term=4,
      note="Catalog requires junior standing."),
    c("MEAM 4460", "Mechanical Engineering Design Projects", 1.0,
      all_of("MEAM 4450"), min_term=5),

    # ------------------------------------------------- ethics and others --
    c("EAS 0091",
      "Chemistry Advanced Placement/International Baccalaureate Credit "
      "(Engineering Students Only)"),
    c("EAS 2030", "Engineering Ethics"),
    c("BIOE 4010", "Introduction to Bioethics"),
    c("BIOE 4020", "Conceptual Foundations of Bioethics"),
    c("HSOC 1330", "Bioethics"),
    c("HSOC 2457", "History of Bioethics"),
    c("LGST 1000", "Ethics and Social Responsibility"),
    c("LGST 2200", "International Business Ethics"),
    c("NURS 3300", "Theoretical Foundations of Health Care Ethics"),
    c("PHIL 1342", "Bioethics"),
    c("PHIL 4330", "Metaethics"),
    c("ECON 2100", "Intermediate Microeconomics", 1.0, all_of("MATH 1400", "MATH 1410"),
      note="Catalog also requires ECON 0100 and ECON 0200, which are not in "
           "this catalog."),
    c("ECON 4100", "Game Theory", 1.0, all_of("ECON 2100", "MATH 1400", "MATH 1410")),
    c("STAT 1010", "Introductory Business Statistics", 1.0, all_of("MATH 1400")),
    c("STAT 1110", "Introductory Statistics"),
    c("STAT 4300", "Probability", 1.0, groups(one_of("MATH 1410", "MATH 1610"))),

    # ----------------------------------------------------- DMD art track --
    c("FNAR 0010", "Drawing I"),
    c("FNAR 1050", "Mixed Media Animation"),
    c("FNAR 1080", "Figure Drawing I", 1.0, all_of("FNAR 0010")),
    c("FNAR 2090", "Hand-Drawn Computer Animation", 1.0,
      note="Catalog prerequisite DSGN 0010 is not in this catalog."),
    c("FNAR 2100", "Computer Animation"),
    c("FNAR 2200", "Drawing Investigations", 1.0, all_of("FNAR 0010")),
    c("DSGN 1030", "3-D Computer Modeling"),
    c("DSGN 2010", "Digital Figure Modeling", 1.0,
      note="Catalog prerequisite DSGN 1020 is not in this catalog."),
    c("DSGN 2040", "Environmental Animation"),
]
