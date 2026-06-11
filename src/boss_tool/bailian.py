from __future__ import annotations

import base64
import json
import re
from typing import Any

import requests

from boss_tool.config import AppConfig
from boss_tool.models import ScanSnapshot


class BailianError(RuntimeError):
    """Raised when a Bailian request fails."""


class BailianClient:
    def __init__(self, config: AppConfig, timeout_seconds: int = 60) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def analyze_snapshot(self, snapshot: ScanSnapshot) -> dict[str, Any]:
        content = _build_text_prompt(snapshot)
        payload = {
            "model": self.config.text_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是招聘沟通助手。请根据结构化聊天信息输出 JSON，"
                        "包含 unread_summary、current_chat_summary、priorities、reply_suggestions。"
                    ),
                },
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
        }
        data = self._post_chat(payload)
        content_text = data["choices"][0]["message"]["content"]
        try:
            return parse_model_json_content(content_text)
        except json.JSONDecodeError:
            return {
                "unread_summary": "",
                "current_chat_summary": _content_to_text(content_text),
                "priorities": [],
                "reply_suggestions": [],
            }

    def analyze_region_image(self, image_bytes: bytes, instruction: str) -> dict[str, Any]:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.config.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }
        data = self._post_chat(payload)
        content_text = data["choices"][0]["message"]["content"]
        return parse_model_json_content(content_text)

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            raise BailianError(
                f"Bailian request failed: {response.status_code} {response.text}"
            )
        return response.json()


def _build_text_prompt(snapshot: ScanSnapshot) -> str:
    conversations = [
        {
            "name": item.name,
            "job_title": item.job_title,
            "last_message": item.last_message,
            "time_label": item.time_label,
            "unread_count": item.unread_count,
        }
        for item in snapshot.conversation_list
    ]
    messages = [
        {
            "speaker": item.speaker,
            "text": item.text,
            "time_label": item.time_label,
        }
        for item in snapshot.current_messages
    ]
    return json.dumps(
        {
            "current_candidate": {
                "name": snapshot.current_candidate.name,
                "summary_lines": snapshot.current_candidate.summary_lines,
            },
            "conversation_list": conversations,
            "current_messages": messages,
        },
        ensure_ascii=False,
        indent=2,
    )


def parse_model_json_content(content: Any) -> dict[str, Any]:
    text = _content_to_text(content).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        extracted = _extract_first_json_object(text)
        if extracted:
            return json.loads(extracted)
        raise


def _content_to_text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    return str(content)


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""
