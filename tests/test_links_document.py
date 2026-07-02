from jira_tools.atlassian_client import JiraIssueLink
from jira_tools.link_extraction import PageLinks, TicketLinks
from jira_tools.links_document import build_links_document


def test_ticket_links_with_all_categories_populated() -> None:
    result = TicketLinks(
        jira_keys=["PROJ-1", "PROJ-2"],
        issue_links=[JiraIssueLink(key="PROJ-3", relation="blocks")],
        confluence_page_ids=["12345"],
    )

    document = build_links_document("PROJ-1", result)

    assert "# Links found in PROJ-1" in document
    assert "## Jira keys" in document
    assert "- PROJ-1" in document
    assert "- PROJ-2" in document
    assert "## Issue links" in document
    assert "- PROJ-3 (blocks)" in document
    assert "## Confluence pages" in document
    assert "- 12345" in document


def test_page_links_has_no_issue_links_section() -> None:
    result = PageLinks(jira_keys=["PROJ-1"], confluence_page_ids=["12345"])

    document = build_links_document("12345", result)

    assert "## Issue links" not in document
    assert "## Jira keys" in document
    assert "## Confluence pages" in document


def test_all_empty_results_render_none_found_states() -> None:
    result = TicketLinks(jira_keys=[], issue_links=[], confluence_page_ids=[])

    document = build_links_document("PROJ-1", result)

    assert "*No Jira keys found.*" in document
    assert "*No issue links found.*" in document
    assert "*No Confluence pages found.*" in document
