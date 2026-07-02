from jira_tools.adf import ADFNode
from jira_tools.atlassian_client import JiraComment, JiraTicket
from jira_tools.ticket_document import build_ticket_document


def _text_doc(text: str) -> ADFNode:
    return ADFNode.model_validate(
        {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
        }
    )


def test_document_with_description_and_comments() -> None:
    ticket = JiraTicket(
        key="PROJ-1",
        summary="Something is broken",
        status="In Progress",
        issue_type="Bug",
        description=_text_doc("The description body."),
        comments=[
            JiraComment(
                author="Jane Doe",
                created="2026-01-01T00:00:00.000+0000",
                body=_text_doc("First comment."),
            ),
            JiraComment(
                author="John Roe",
                created="2026-01-02T00:00:00.000+0000",
                body=_text_doc("Second comment."),
            ),
        ],
    )

    document = build_ticket_document(ticket)

    assert "# Something is broken" in document
    assert "PROJ-1" in document
    assert "In Progress" in document
    assert "Bug" in document
    assert "## Description" in document
    assert "The description body." in document
    assert "## Comments" in document
    assert "### Comment by Jane Doe (2026-01-01T00:00:00.000+0000)" in document
    assert "First comment." in document
    assert "### Comment by John Roe (2026-01-02T00:00:00.000+0000)" in document
    assert "Second comment." in document
    # comments render in order
    assert document.index("First comment.") < document.index("Second comment.")


def test_document_with_no_description() -> None:
    ticket = JiraTicket(
        key="PROJ-2",
        summary="No description ticket",
        status="Open",
        issue_type="Task",
        description=None,
        comments=[],
    )

    document = build_ticket_document(ticket)

    assert "## Description" in document
    assert "No description" in document


def test_document_with_no_comments() -> None:
    ticket = JiraTicket(
        key="PROJ-3",
        summary="No comments ticket",
        status="Open",
        issue_type="Task",
        description=_text_doc("Has a description."),
        comments=[],
    )

    document = build_ticket_document(ticket)

    assert "## Comments" in document
    assert "No comments" in document
