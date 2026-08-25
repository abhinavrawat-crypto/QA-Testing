"""Playwright spec parser (.spec.ts / .spec.js).

Regex-based extraction of test() and describe() blocks — no Node.js required.
Extracts: test name, parent describe name, locators, assertions found in the block.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlaywrightTest:
    title: str
    describe_context: str
    assertions: List[str] = field(default_factory=list)
    locators: List[str] = field(default_factory=list)


# Regex patterns
DESCRIBE_RE = re.compile(r"""(?:describe|test\.describe)\s*\(\s*['"`]([^'"`]+)['"`]""")
TEST_RE = re.compile(r"""(?:^|\s)(?:test|it)\s*\(\s*['"`]([^'"`]+)['"`]""", re.MULTILINE)
EXPECT_RE = re.compile(r"""expect\s*\([^)]+\)\s*\.\s*(\w+)\s*\(([^)]*)\)""")
LOCATOR_RE = re.compile(r"""(?:getByRole|getByText|getByLabel|getByPlaceholder|getByTestId|locator|page\.)\s*\(\s*['"`]([^'"`]+)['"`]""")


def _extract_block(content: str, start_idx: int) -> str:
    """Extract the body of a function block starting at start_idx."""
    depth = 0
    in_str = False
    str_char = None
    i = start_idx
    block_start = -1

    while i < len(content):
        ch = content[i]
        if in_str:
            if ch == str_char and content[i - 1] != "\\":
                in_str = False
        elif ch in ('"', "'", "`"):
            in_str = True
            str_char = ch
        elif ch == "{":
            depth += 1
            if block_start == -1:
                block_start = i
        elif ch == "}":
            depth -= 1
            if depth == 0 and block_start != -1:
                return content[block_start: i + 1]
        i += 1
    return ""


def parse_playwright(content: str) -> List[PlaywrightTest]:
    tests: List[PlaywrightTest] = []

    # Find describe contexts
    describe_contexts: List[tuple[int, int, str]] = []  # (start, end, name)
    for m in DESCRIBE_RE.finditer(content):
        desc_name = m.group(1)
        block = _extract_block(content, m.end())
        if block:
            block_start = content.index(block, m.end())
            describe_contexts.append((block_start, block_start + len(block), desc_name))

    # Find all tests
    for m in TEST_RE.finditer(content):
        test_name = m.group(1)
        # Determine describe context
        describe_name = ""
        for (ds, de, dn) in describe_contexts:
            if ds <= m.start() <= de:
                describe_name = dn
                break

        # Extract test body
        body = _extract_block(content, m.end())

        # Extract assertions
        assertions = [
            f"{em.group(1)}({em.group(2).strip()[:60]})"
            for em in EXPECT_RE.finditer(body)
        ]

        # Extract locators
        locators = list(set(LOCATOR_RE.findall(body)))[:8]

        tests.append(PlaywrightTest(
            title=test_name,
            describe_context=describe_name,
            assertions=assertions[:8],
            locators=locators,
        ))

    return tests


def tests_to_index_items(tests: List[PlaywrightTest], file_path: str, commit_sha: str) -> list:
    items = []
    for t in tests:
        context = f"{t.describe_context} > " if t.describe_context else ""
        full_title = f"{context}{t.title}"
        assertions_text = " | ".join(t.assertions)
        locators_text = " | ".join(t.locators)
        raw = f"Test: {full_title}\nAssertions: {assertions_text}\nLocators: {locators_text}"
        items.append({
            "file_path": file_path,
            "test_type": "playwright_spec",
            "feature_name": t.describe_context or None,
            "title": full_title,
            "description": t.describe_context,
            "steps": [
                {"keyword": "assert", "text": a} for a in t.assertions
            ],
            "tags": [],
            "raw_content": raw,
            "commit_sha": commit_sha,
            "embed_text": f"{full_title} {assertions_text} {locators_text}",
        })
    return items
