from __future__ import annotations

import json
from pathlib import Path

import requests

from .config import Settings
from .models import StockAnalysisResult


def send_ranked_results(settings: Settings, results: list[StockAnalysisResult]) -> None:
    if settings.feishu_send_mode == "app":
        send_text_message(settings, _render_text_message(results))
        return
    if settings.feishu_send_mode == "webhook":
        _send_via_webhook(settings.feishu_webhook_url, _render_text_message(results))
        return
    raise ValueError(f"Unsupported FEISHU_SEND_MODE: {settings.feishu_send_mode}")


def send_text_message(settings: Settings, text: str) -> None:
    if settings.feishu_send_mode == "app":
        _send_via_app(settings, text)
        return
    if settings.feishu_send_mode == "webhook":
        _send_via_webhook(settings.feishu_webhook_url, text)
        return
    raise ValueError(f"Unsupported FEISHU_SEND_MODE: {settings.feishu_send_mode}")


def send_file_message(settings: Settings, file_path: Path) -> None:
    if settings.feishu_send_mode != "app":
        raise ValueError("File sending is currently supported only for FEISHU_SEND_MODE=app")
    token = _get_tenant_access_token(settings.feishu_app_id, settings.feishu_app_secret)
    receive_id_type, receive_id = _resolve_receive_target(settings, token)
    file_key = _upload_file(token, file_path)
    response = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": receive_id_type},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "receive_id": receive_id,
            "msg_type": "file",
            "content": json.dumps({"file_key": file_key}, ensure_ascii=False),
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, "0", None):
        raise ValueError(f"Feishu file send failed: {payload}")


def _upload_file(token: str, file_path: Path) -> str:
    with file_path.open("rb") as file_handle:
        response = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            data={"file_type": "pdf", "file_name": file_path.name},
            files={"file": (file_path.name, file_handle, "application/pdf")},
            timeout=60,
        )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, "0", None):
        raise ValueError(f"Feishu file upload failed: {payload}")
    file_key = str(payload.get("data", {}).get("file_key", "")).strip()
    if not file_key:
        raise ValueError(f"Feishu file_key missing in upload response: {payload}")
    return file_key


def _send_via_webhook(webhook_url: str, text: str) -> None:
    if not webhook_url:
        raise ValueError("Missing FEISHU_WEBHOOK_URL")
    response = requests.post(
        webhook_url,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=20,
    )
    response.raise_for_status()


def _send_via_app(settings: Settings, text: str) -> None:
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        raise ValueError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET")
    if not settings.feishu_receive_id:
        raise ValueError("Missing FEISHU_RECEIVE_ID")

    token = _get_tenant_access_token(settings.feishu_app_id, settings.feishu_app_secret)
    receive_id_type, receive_id = _resolve_receive_target(settings, token)

    response = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": receive_id_type},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, "0", None):
        raise ValueError(f"Feishu app send failed: {payload}")


def _resolve_receive_target(settings: Settings, token: str) -> tuple[str, str]:
    if settings.feishu_receive_id_type != "mobile":
        return settings.feishu_receive_id_type, settings.feishu_receive_id

    response = requests.post(
        "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={"mobiles": [settings.feishu_receive_id]},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, "0"):
        raise ValueError(f"Failed to resolve mobile to user id: {payload}")

    user_list = payload.get("data", {}).get("user_list", [])
    if not user_list:
        raise ValueError(f"No Feishu user found for mobile: {settings.feishu_receive_id}")

    open_id = str(user_list[0].get("user_id", "")).strip()
    if not open_id:
        raise ValueError(f"Resolved mobile but missing user id: {payload}")
    return "open_id", open_id


def _get_tenant_access_token(app_id: str, app_secret: str) -> str:
    response = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in (0, "0"):
        raise ValueError(f"Failed to get Feishu tenant access token: {payload}")
    token = payload.get("tenant_access_token")
    if not token:
        raise ValueError("Feishu tenant_access_token is missing in response")
    return token


def _render_text_message(results: list[StockAnalysisResult]) -> str:
    lines = ["今日自选股优先级分析"]
    for index, result in enumerate(results, start=1):
        rating = str(result.extra.get("rating", "")).strip()
        conclusion = str(result.extra.get("one_line_conclusion", result.reasoning)).strip()
        lines.append(
            (
                f"{index}. {result.symbol} {result.name} | "
                f"优先级 {result.priority_score:.1f} | "
                f"评分 {result.llm_score:.1f} | "
                f"{rating or result.recommendation}\n"
                f"{conclusion}\n"
                f"{result.recommendation}\n"
                f"技术分 {result.technical_score:.1f} / 综合评分 {result.llm_score:.1f}\n"
                f"{result.reasoning}"
            )
        )
    return "\n\n".join(lines)


def render_markdown_report(results: list[StockAnalysisResult]) -> str:
    lines = ["# 今日自选股分析", ""]
    for index, result in enumerate(results, start=1):
        strengths = result.extra.get("strengths", [])
        risks = result.extra.get("risks", [])
        follow_up_metrics = result.extra.get("follow_up_metrics", [])
        breakdown = result.extra.get("breakdown", {})
        lines.extend(
            [
                f"## {index}. {result.symbol} {result.name}",
                f"- 综合评分：{result.llm_score:.2f}",
                f"- 排序优先级：{result.priority_score:.2f}",
                f"- 技术分：{result.technical_score:.2f}",
                f"- 评级：{result.extra.get('rating', '')}",
                f"- 建议：{result.recommendation}",
                f"- 一句话结论：{result.extra.get('one_line_conclusion', result.reasoning)}",
                f"- 技术总结：{result.extra.get('technical_summary', '')}",
                f"- 分析结论：{result.reasoning}",
                "",
            ]
        )
        if breakdown:
            lines.extend(
                [
                    "### 分项打分",
                    f"- 行业景气度：{_score_of(breakdown, 'industry_prosperity')}/20",
                    f"- 公司竞争力：{_score_of(breakdown, 'company_competitiveness')}/25",
                    f"- 财务质量：{_score_of(breakdown, 'financial_quality')}/20",
                    f"- 估值水平：{_score_of(breakdown, 'valuation_level')}/20",
                    f"- 周期与资金位置：{_score_of(breakdown, 'cycle_and_flow')}/15",
                    f"- 红旗扣分：-{_score_of(breakdown, 'red_flag_penalty')}",
                    "",
                ]
            )
        if strengths:
            lines.extend(["### 核心优点", *[f"- {item}" for item in strengths], ""])
        if risks:
            lines.extend(["### 核心风险", *[f"- {item}" for item in risks], ""])
        if follow_up_metrics:
            lines.extend(["### 后续跟踪指标", *[f"- {item}" for item in follow_up_metrics], ""])
    return "\n".join(lines)


def _score_of(breakdown: object, key: str) -> str:
    if isinstance(breakdown, dict):
        section = breakdown.get(key, {})
        if isinstance(section, dict):
            return str(section.get("score", ""))
    return ""
