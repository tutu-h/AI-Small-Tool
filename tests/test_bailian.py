from boss_tool.bailian import parse_model_json_content


def test_parse_model_json_content_accepts_markdown_json_fence() -> None:
    content = """```json
{"messages": [{"speaker": "候选人", "text": "明天可以面试吗"}]}
```"""

    data = parse_model_json_content(content)

    assert data["messages"][0]["text"] == "明天可以面试吗"


def test_parse_model_json_content_extracts_first_json_object_from_text() -> None:
    content = '识别结果如下：{"candidate": {"name": "灵灵"}} 请参考。'

    data = parse_model_json_content(content)

    assert data["candidate"]["name"] == "灵灵"
