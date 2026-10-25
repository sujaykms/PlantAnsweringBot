"""Label descriptions and few-shot examples for the router."""

DESCRIPTIONS: dict[str, str] = {
    "safety": (
        "Hazards and protecting people: PPE, lockout/tagout, confined space, hot work, "
        "chemicals/SDS, machine guarding, emergency response, incidents, permits."
    ),
    "maintenance": (
        "Keeping equipment running: PM schedules, fault codes, troubleshooting, repair steps, "
        "torque/specs, lubrication, spare parts."
    ),
    "quality": (
        "Product meets spec: inspection criteria, tolerances, defects, AQL sampling, SPC, "
        "NCR/hold decisions."
    ),
    "analytics": (
        "Numeric questions over plant data tables (counts, trends, KPIs). Not routed yet (Phase 3)."
    ),
    "none": "Not about plant operations or documentation (small talk, off-topic).",
}

RULE = "Rule of thumb: person -> safety, machine -> maintenance, product -> quality."

# (question, expected labels) -- also used by scripts/route_cli.py
EXAMPLES: list[tuple[str, list[str]]] = [
    ("What PPE do I need on the paint line?", ["safety"]),
    ("Someone got solvent in their eye, what now?", ["safety"]),
    ("Do I need a permit to weld near the tank farm?", ["safety"]),
    ("Conveyor 3 is showing fault E42", ["maintenance"]),
    ("Torque spec for the P-101 motor mount bolts?", ["maintenance"]),
    ("How often do we grease the pump bearings?", ["maintenance"]),
    ("What's the max allowable porosity on BRK-200 welds?", ["quality"]),
    ("We found 3 bad parts in a lot of 500, do we hold it?", ["quality"]),
    ("Control chart shows 7 points above the mean, what do I do?", ["quality"]),
    ("How do I replace the compressor filter?", ["maintenance", "safety"]),
    ("Parts have burrs since the die change", ["quality", "maintenance"]),
    ("Can I bypass the light curtain to clear a jam?", ["safety"]),
    ("What's on the cafeteria menu?", ["none"]),
    ("Someone is bleeding badly from the hand, what do I do?", ["safety"]),
    ("There's smoke coming from the MCC panel", ["safety", "maintenance"]),
    ("Acid splashed into a coworker's eyes", ["safety"]),
    ("Gas alarm just went off in the pump room", ["safety"]),
    ("A guy got electrocuted at the junction box", ["safety"]),
    ("Operator is trapped inside the baler", ["safety"]),
]
# questions (from EXAMPLES) that must set emergency=True; all others must be False
EMERGENCY_EXAMPLES: set[str] = {
    "Someone got solvent in their eye, what now?",
    "Someone is bleeding badly from the hand, what do I do?",
    "There's smoke coming from the MCC panel",
    "Acid splashed into a coworker's eyes",
    "Gas alarm just went off in the pump room",
    "A guy got electrocuted at the junction box",
    "Operator is trapped inside the baler",
}
# extra labels tolerated (not required) for a given example
EXTRA_OK: dict[str, set[str]] = {"Can I bypass the light curtain to clear a jam?": {"maintenance"}}


def build_system_prompt() -> str:
    labels = "\n".join(f"- {k}: {v}" for k, v in DESCRIPTIONS.items() if k != "analytics")
    shots = []
    for q, ls in EXAMPLES:
        rs = ",".join(
            f'{{"label":"{l}","confidence":{0.9 if i == 0 else 0.6}}}' for i, l in enumerate(ls)
        )
        em = "true" if q in EMERGENCY_EXAMPLES else "false"
        shots.append(f'Q: {q}\nA: {{"routes":[{rs}],"reason":"...","emergency":{em}}}')
    return (
        "You route questions from plant floor supervisors to documentation sources.\n"
        f"Labels:\n{labels}\n{RULE}\n"
        "Return ONLY a JSON object: "
        '{"routes":[{"label":"safety|maintenance|quality|none","confidence":0..1}],"reason":"short","emergency":true|false}. '
        "Set emergency=true ONLY when the question describes a situation happening now that endangers people: "
        "injury, bleeding, burn, unconscious person, fire or smoke, chemical spill/exposure/eye contact, "
        "gas leak or gas alarm, electrocution, someone trapped. Emergency questions are still routed normally "
        "(usually safety). Planned-work or general-information questions are emergency=false.\n"
        "List the 1-2 most relevant labels, highest confidence first. Use 'none' alone for off-topic.\n"
        "Examples:\n" + "\n".join(shots)
    )


ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "routes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": ["safety", "maintenance", "quality", "none"]},
                    "confidence": {"type": "number"},
                },
                "required": ["label", "confidence"],
                "additionalProperties": False,
            },
        },
        "reason": {"type": "string"},
        "emergency": {"type": "boolean"},
    },
    "required": ["routes", "reason", "emergency"],
    "additionalProperties": False,
}
