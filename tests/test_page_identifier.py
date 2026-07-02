import pytest

from jira_tools.page_identifier import parse_page_id


def test_bare_digit_string_returned_as_is() -> None:
    assert parse_page_id("12345") == "12345"


def test_pretty_url_with_trailing_title_slug() -> None:
    url = "https://example.atlassian.net/wiki/spaces/ENG/pages/12345/Some+Title"
    assert parse_page_id(url) == "12345"


def test_pretty_url_with_no_trailing_slug() -> None:
    url = "https://example.atlassian.net/wiki/spaces/ENG/pages/12345"
    assert parse_page_id(url) == "12345"


def test_unrecognized_input_raises_naming_the_input() -> None:
    with pytest.raises(ValueError, match="not-a-real-identifier"):
        parse_page_id("not-a-real-identifier")
