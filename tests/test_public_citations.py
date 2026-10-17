from copy import deepcopy

import pytest

from api.ask_ui import public_answer_text


@pytest.mark.parametrize("content,expected", [
    ("A fact [policy#1].", "A fact."),
    ("A fact [policy#1][policy#2].", "A fact."),
    ("A fact [policy#1, policy#2].", "A fact."),
    ("A fact [Sources: policy#1; policy#2].", "A fact."),
    ("One [policy#1] and another [policy#2].", "One and another."),
    ("Eligibility [70+] and [official page](https://example.com).", "Eligibility [70+] and [official page](https://example.com)."),
    ("A [policy#1](https://example.com) link.", "A [policy#1](https://example.com) link."),
])
def test_only_display_citations_are_removed_and_original_is_unchanged(content, expected):
    answer = {"content": content, "sources": ["policy#1"],
              "evidence": [{"chunk_id": "policy#2", "text": "Evidence"}]}
    original = deepcopy(answer)
    assert public_answer_text(answer) == expected
    assert answer == original
