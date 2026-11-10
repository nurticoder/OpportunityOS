import re

TOPICS = {
    "ai": r"\b(ai|artificial intelligence|machine learning|ml|deep learning|llm)\b",
    "robotics": r"robotics|autonomous|simulation|perception",
    "software engineering": r"software|engineering|developer|infrastructure",
    "research": r"research|scientist",
    "data science": r"data (science|engineer|analyst)|analytics",
    "entrepreneurship": r"product manag|founder|startup|entrepreneur",
    "public policy": r"public policy|government affairs|diplomacy",
    "leadership": r"leadership|fellowship",
}


def evaluate(item, facts, weights):
    text = item["description"]
    title = item["title"]
    interests = " ".join(facts[key]["value"].lower() for key in ("interests", "program"))
    matches = [topic for topic, pattern in TOPICS.items()
               if topic in interests and re.search(pattern, title, re.I)]
    academic = facts["academic_level"]
    graduate = bool(re.search(r"\b(?:ms|ph\.?d\.?|master[’']?s|doctoral)\b", title, re.I))
    undergrad_allowed = bool(re.search(r"\b(bs|bachelor|undergraduate)\b", title, re.I))
    graduate_only = graduate and not undergrad_allowed
    excluded = graduate_only and academic["verified"] and academic["value"].lower() == "undergraduate"
    unknown = ["Work authorization and sponsorship", "Citizenship and age rules",
               "Skills, availability and travel requirements"]
    if not academic["verified"] or not undergrad_allowed:
        unknown.append("Required degree and enrollment dates")
    location = item["location"]
    pay = next((line[:280] for line in text.splitlines()
                if re.search(r"(?:\$|€|£)\s*\d", line) and re.search(r"pay|salary|stipend|compensation|hour|range", line, re.I)), None)
    signals = {"alignment": min(1, len(matches) * .45), "eligibility": .55 if undergrad_allowed else 0 if graduate_only else .15,
               "credibility": 1, "funding": .7 if pay else 0}
    score = round(sum(weights[k] * signals[k] for k in signals) * 100 / sum(weights.values()))
    return {
        "score": 0 if excluded else score,
        "eligibility": "Ineligible" if excluded else "Needs review",
        "group": "Ineligible" if excluded else ("Needs eligibility review" if graduate_only else
                 "Strong fit" if matches and undergrad_allowed else "Needs eligibility review" if matches else "Unexpected"),
        "matches": matches, "unknown": unknown,
        "reason": ("Listing title specifies graduate study and your verified level is undergraduate." if excluded else
                   "Bachelor’s level appears in the listing title." if undergrad_allowed else
                   "The title specifies graduate study. Verify the degree requirement." if graduate_only else
                   "Check the degree and enrollment requirements in the official listing."),
        "funding": pay or "Unknown", "location": location,
    }
