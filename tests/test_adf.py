from jira_tools.adf import ADFNode, to_markdown


def _doc(*content: dict[str, object]) -> ADFNode:
    return ADFNode.model_validate({"type": "doc", "content": list(content)})


def test_heading_converts_to_markdown_heading() -> None:
    node = _doc(
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Ticket summary"}],
        }
    )

    assert "## Ticket summary" in to_markdown(node)


def test_text_marks_convert_to_bold_and_italic() -> None:
    node = _doc(
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "bold", "marks": [{"type": "strong"}]},
                {"type": "text", "text": " and "},
                {"type": "text", "text": "italic", "marks": [{"type": "em"}]},
            ],
        }
    )

    markdown = to_markdown(node)

    assert "**bold**" in markdown
    assert "*italic*" in markdown


def test_link_mark_converts_to_markdown_link() -> None:
    node = _doc(
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "example",
                    "marks": [{"type": "link", "attrs": {"href": "https://example.com"}}],
                }
            ],
        }
    )

    markdown = to_markdown(node)

    assert "[example]" in markdown
    assert "https://example.com" in markdown


def test_bullet_list_with_inline_code_converts() -> None:
    node = _doc(
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "First item"}]}
                    ],
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Second item with "},
                                {
                                    "type": "text",
                                    "text": "inline code",
                                    "marks": [{"type": "code"}],
                                },
                            ],
                        }
                    ],
                },
            ],
        }
    )

    markdown = to_markdown(node)

    assert "- First item" in markdown
    assert "`inline code`" in markdown


def test_code_block_converts_to_fenced_block() -> None:
    node = _doc(
        {
            "type": "codeBlock",
            "attrs": {"language": "python"},
            "content": [{"type": "text", "text": 'def hello():\n    print("hi")'}],
        }
    )

    markdown = to_markdown(node)

    assert "```python" in markdown
    assert 'print("hi")' in markdown


def test_panel_degrades_gracefully_without_raising() -> None:
    node = _doc(
        {
            "type": "panel",
            "attrs": {"panelType": "warning"},
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "This is a warning panel."}],
                }
            ],
        }
    )

    markdown = to_markdown(node)

    assert "This is a warning panel." in markdown
