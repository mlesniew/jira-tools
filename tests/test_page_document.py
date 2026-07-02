from jira_tools.adf import ADFNode
from jira_tools.atlassian_client import ConfluencePage
from jira_tools.page_document import build_page_document


def _text_doc(text: str) -> ADFNode:
    return ADFNode.model_validate(
        {
            "type": "doc",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
        }
    )


def test_document_with_body() -> None:
    page = ConfluencePage(
        id="12345",
        title="A Page",
        status="current",
        body=_text_doc("The page body."),
    )

    document = build_page_document(page)

    assert "# A Page" in document
    assert "12345" in document
    assert "current" in document
    assert "The page body." in document
    assert "simplified" in document


def test_document_with_no_body() -> None:
    page = ConfluencePage(id="12345", title="A Page", status="current", body=None)

    document = build_page_document(page)

    assert "No content" in document
