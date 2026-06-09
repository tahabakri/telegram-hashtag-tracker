"""Tests for the hashtag matcher — run with: python -m pytest"""
from bot import find_hashtags

TRACKED = ["#entry", "#proof", "#prediction"]


def test_plain_match():
    assert find_hashtags("counting me in #entry", TRACKED) == ["#entry"]


def test_case_insensitive():
    assert find_hashtags("MY #Entry here", TRACKED) == ["#entry"]
    assert find_hashtags("#ENTRY", TRACKED) == ["#entry"]


def test_no_substring_false_positive():
    # lookalike tags must NOT count
    assert find_hashtags("#entryfinal should not count", TRACKED) == []
    assert find_hashtags("#proofs", TRACKED) == []


def test_trailing_punctuation_ignored():
    assert find_hashtags("done #entry!", TRACKED) == ["#entry"]
    assert find_hashtags("(#prediction)", TRACKED) == ["#prediction"]


def test_multiple_hashtags_in_one_message():
    assert find_hashtags("#entry and #proof", TRACKED) == ["#entry", "#proof"]


def test_repeats_are_deduplicated():
    assert find_hashtags("#entry #entry #entry", TRACKED) == ["#entry"]


def test_untracked_hashtags_ignored():
    assert find_hashtags("#random #other", TRACKED) == []


def test_empty_or_none():
    assert find_hashtags("", TRACKED) == []
    assert find_hashtags(None, TRACKED) == []
