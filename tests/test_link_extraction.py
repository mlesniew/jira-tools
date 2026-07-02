from jira_tools.adf import ADFNode
from jira_tools.atlassian_client import ConfluencePage, JiraComment, JiraIssueLink, JiraTicket
from jira_tools.link_extraction import (
    extract_page_links,
    extract_ticket_links,
    is_jira_key,
)

SITE_URL = "https://example.atlassian.net"


def _doc(*content: dict[str, object]) -> ADFNode:
    return ADFNode.model_validate({"type": "doc", "content": list(content)})


def _text(text: str, href: str | None = None) -> dict[str, object]:
    node: dict[str, object] = {"type": "text", "text": text}
    if href is not None:
        node["marks"] = [{"type": "link", "attrs": {"href": href}}]
    return node


def _paragraph(*content: dict[str, object]) -> dict[str, object]:
    return {"type": "paragraph", "content": list(content)}


def _card(card_type: str, url: object) -> dict[str, object]:
    return {"type": card_type, "attrs": {"url": url}}


def _ticket(description: ADFNode | None, comments: list[ADFNode] | None = None) -> JiraTicket:
    return JiraTicket(
        key="PROJ-1",
        summary="s",
        status="Open",
        issue_type="Task",
        description=description,
        comments=[
            JiraComment(author="a", created="c", body=body) for body in (comments or [])
        ],
    )


def _page(body: ADFNode | None) -> ConfluencePage:
    return ConfluencePage(id="1", title="t", status="current", body=body)


def test_is_jira_key() -> None:
    assert is_jira_key("PROJ-1")
    assert is_jira_key("AB1-999")
    assert not is_jira_key("proj-1")
    assert not is_jira_key("not-a-key")
    assert not is_jira_key("PROJ-1 extra")


def test_bare_key_in_plain_text_is_extracted() -> None:
    doc = _doc(_paragraph(_text("See PROJ-2 for details.")))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == ["PROJ-2"]


def test_link_mark_to_same_site_jira_issue_is_extracted() -> None:
    doc = _doc(
        _paragraph(_text("ticket", href=f"{SITE_URL}/browse/PROJ-3"))
    )

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == ["PROJ-3"]


def test_link_mark_to_same_site_confluence_page_is_extracted() -> None:
    doc = _doc(
        _paragraph(
            _text("page", href=f"{SITE_URL}/wiki/spaces/ENG/pages/12345/A+Page")
        )
    )

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.confluence_page_ids == ["12345"]


def test_link_mark_to_unrelated_external_site_is_ignored() -> None:
    doc = _doc(_paragraph(_text("other", href="https://example.com/browse/PROJ-4")))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == []
    assert result.confluence_page_ids == []


def test_inline_card_with_jira_url_is_extracted() -> None:
    doc = _doc(_paragraph(_card("inlineCard", f"{SITE_URL}/browse/PROJ-5")))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == ["PROJ-5"]


def test_block_card_with_confluence_url_is_extracted() -> None:
    doc = _doc(_card("blockCard", f"{SITE_URL}/wiki/spaces/ENG/pages/54321/Other"))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.confluence_page_ids == ["54321"]


def test_embed_card_with_jira_url_is_extracted() -> None:
    doc = _doc(_paragraph(_card("embedCard", f"{SITE_URL}/browse/PROJ-6")))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == ["PROJ-6"]


def test_card_with_none_url_is_skipped_without_crashing() -> None:
    doc = _doc(_paragraph(_card("inlineCard", None)))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == []
    assert result.confluence_page_ids == []


def test_duplicate_mentions_across_description_and_comments_are_deduplicated() -> None:
    description = _doc(_paragraph(_text("PROJ-7")))
    comment1 = _doc(_paragraph(_text("PROJ-7")))
    comment2 = _doc(_paragraph(_text("PROJ-7")))

    result = extract_ticket_links(_ticket(description, [comment1, comment2]), SITE_URL)

    assert result.jira_keys == ["PROJ-7"]


def test_empty_description_yields_no_links() -> None:
    ticket = _ticket(description=None)

    result = extract_ticket_links(ticket, SITE_URL)

    assert result.jira_keys == []
    assert result.confluence_page_ids == []
    assert result.issue_links == []


def test_sorted_output_ordering() -> None:
    doc = _doc(_paragraph(_text("PROJ-9 mentions PROJ-2 and PROJ-10")))

    result = extract_ticket_links(_ticket(doc), SITE_URL)

    assert result.jira_keys == ["PROJ-10", "PROJ-2", "PROJ-9"]


def test_issue_links_are_passed_through_from_ticket_not_rederived() -> None:
    ticket = _ticket(description=None)
    ticket.issue_links = [JiraIssueLink(key="PROJ-8", relation="blocks")]

    result = extract_ticket_links(ticket, SITE_URL)

    assert result.issue_links == [JiraIssueLink(key="PROJ-8", relation="blocks")]


def test_extract_page_links_walks_page_body_only() -> None:
    body = _doc(
        _paragraph(_text("PROJ-11")),
        _card("inlineCard", f"{SITE_URL}/wiki/spaces/ENG/pages/999/Page"),
    )

    result = extract_page_links(_page(body), SITE_URL)

    assert result.jira_keys == ["PROJ-11"]
    assert result.confluence_page_ids == ["999"]


def test_extract_page_links_with_no_body_yields_no_links() -> None:
    result = extract_page_links(_page(None), SITE_URL)

    assert result.jira_keys == []
    assert result.confluence_page_ids == []
