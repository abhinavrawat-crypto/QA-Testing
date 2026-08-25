"""Gherkin .feature file parser.

Parses Feature files into structured scenario objects without external deps.
Handles: Feature, Background, Scenario, Scenario Outline, Examples, Tags, Steps.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GherkinStep:
    keyword: str   # Given / When / Then / And / But
    text: str


@dataclass
class GherkinScenario:
    title: str
    description: str
    steps: List[GherkinStep]
    tags: List[str] = field(default_factory=list)
    is_outline: bool = False
    examples: List[dict] = field(default_factory=list)


@dataclass
class GherkinFeature:
    name: str
    description: str
    scenarios: List[GherkinScenario]
    tags: List[str] = field(default_factory=list)


STEP_KEYWORDS = re.compile(r"^(Given|When|Then|And|But)\s+(.+)$")
TAG_RE = re.compile(r"@\S+")
SCENARIO_KW = re.compile(r"^(Scenario(?: Outline)?|Example):\s*(.*)$")
FEATURE_KW = re.compile(r"^Feature:\s*(.*)$")
BACKGROUND_KW = re.compile(r"^Background:")
EXAMPLES_KW = re.compile(r"^Examples?:")


def parse_gherkin(content: str) -> GherkinFeature:
    lines = content.splitlines()
    feature_name = ""
    feature_desc_lines = []
    feature_tags: List[str] = []
    scenarios: List[GherkinScenario] = []

    current_tags: List[str] = []
    current_scenario: Optional[GherkinScenario] = None
    in_feature_desc = False
    in_examples = False

    def flush_scenario():
        nonlocal current_scenario
        if current_scenario is not None:
            scenarios.append(current_scenario)
        current_scenario = None

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        # Tags
        if line.startswith("@"):
            current_tags.extend(TAG_RE.findall(line))
            i += 1
            continue

        # Feature
        m = FEATURE_KW.match(line)
        if m:
            feature_name = m.group(1).strip()
            feature_tags = current_tags[:]
            current_tags = []
            in_feature_desc = True
            i += 1
            continue

        # Feature description (lines before first Scenario)
        if in_feature_desc and not SCENARIO_KW.match(line) and not BACKGROUND_KW.match(line) and line:
            feature_desc_lines.append(line)

        # Background — skip steps, treat as implicit
        if BACKGROUND_KW.match(line):
            in_feature_desc = False
            i += 1
            continue

        # Scenario / Scenario Outline
        m = SCENARIO_KW.match(line)
        if m:
            in_feature_desc = False
            in_examples = False
            flush_scenario()
            is_outline = "Outline" in m.group(1) or "Outline" in m.group(0)
            current_scenario = GherkinScenario(
                title=m.group(2).strip(),
                description="",
                steps=[],
                tags=current_tags[:],
                is_outline=is_outline,
            )
            current_tags = []
            i += 1
            continue

        # Examples table
        if EXAMPLES_KW.match(line):
            in_examples = True
            i += 1
            continue

        if in_examples and current_scenario and line.startswith("|"):
            current_scenario.examples.append({"row": line})
            i += 1
            continue

        # Steps
        m = STEP_KEYWORDS.match(line)
        if m and current_scenario:
            current_scenario.steps.append(GherkinStep(keyword=m.group(1), text=m.group(2).strip()))
            i += 1
            continue

        i += 1

    flush_scenario()

    return GherkinFeature(
        name=feature_name,
        description=" ".join(feature_desc_lines),
        scenarios=scenarios,
        tags=feature_tags,
    )


def scenarios_to_index_items(feature: GherkinFeature, file_path: str, commit_sha: str) -> list:
    """Convert parsed GherkinFeature into list of dicts ready for DB upsert."""
    items = []
    for sc in feature.scenarios:
        steps_text = " | ".join(f"{s.keyword} {s.text}" for s in sc.steps)
        raw_content = f"Feature: {feature.name}\nScenario: {sc.title}\n{steps_text}"
        items.append({
            "file_path": file_path,
            "test_type": "gherkin",
            "feature_name": feature.name,
            "title": sc.title,
            "description": feature.description,
            "steps": [{"keyword": s.keyword, "text": s.text} for s in sc.steps],
            "tags": sc.tags,
            "raw_content": raw_content,
            "commit_sha": commit_sha,
            "embed_text": f"{feature.name} {sc.title} {steps_text}",
        })
    return items
