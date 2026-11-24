"""Track exactly DMIT LAX.AS3.Pro.TINY (PID 253) and send ServerChan alerts.

The stock source is a third-party snapshot; alerts are signals to verify on DMIT.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PRODUCT = "LAX.AS3.Pro.TINY"
PID = 253
PRICE = "$10.90"
STOCK_URL = "https://vpsrestock.com/dmit/"
CHECKOUT_URL = f"https://www.dmit.io/cart.php?a=add&pid={PID}"
STATE_PATH = Path(__file__).with_name("stock_state.json")
UTC = timezone.utc


class StockCheckError(RuntimeError):
    pass


def now_utc() -> datetime:
    return datetime.now(UTC)


def parse_stock(html: str) -> str:
    """Return 'in', 'out', or 'unknown'; fail closed on malformed/stale pages.

    Website headings can be assembled from multiple HTML spans. Reading every
    span as a separate line cannot reliably match the package name.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    product_pattern = re.compile(
        r"DMIT\s*[·•]\s*LAX\s*\.\s*AS3\s*\.\s*Pro\s*\.\s*TINY\b", re.I
    )
    matches = list(product_pattern.finditer(text))
    if len(matches) != 1:
        print(f"库存解析：目标套餐匹配数量 {len(matches)}，安全返回 unknown")
        return "unknown"

    match = matches[0]
    # Stock badge must be immediately before the exact product heading.
    prefix = text[max(0, match.start() - 90):match.start()]
    badge = re.search(
        r"(?:^|\s)(现货|有货|在售|缺货|无货|售罄|in stock|out of stock)\s*$",
        prefix, re.I,
    )
    if not badge:
        print("库存解析：未找到紧邻目标套餐的库存标签")
        return "unknown"
    label = badge.group(1).casefold()
    status = "in" if label in {"现货", "有货", "在售", "in stock"} else "out"

    # Stop at the next card, avoiding price/confirmation from another plan.
    suffix = text[match.end():]
    next_product = re.search(r"DMIT\s*[·•]\s*", suffix, re.I)
    detail = suffix[:next_product.start()] if next_product else suffix
    if not re.search(r"\$\s*10\.90\b", detail) or not re.search(
        r"\bPremium\b", detail, re.I
    ):
        print("库存解析：目标套餐价格或线路信息不符")
        return "unknown"

    freshness = re.search(
        r"(?:✓|✔)\s*(\d+)\s*分钟\s*前\s*确认", detail
    )
    if freshness:
        if int(freshness.group(1)) > 60:
            print("库存解析：确认时间超过 60 分钟")
            return "unknown"
    elif not re.search(r"(?:✓|✔)\s*(?:刚刚|刚才)\s*确认", detail):
        print("库存解析：找不到新鲜的确认时间")
        return "unknown"
    return status


def get_stock() -> str:
    try:
        r = requests.get(
            STOCK_URL, timeout=(8, 20),
            headers={"User-Agent": "Mozilla/5.0 (compatible; DMIT-TINY-stock-notifier/1.0)"},
        )
        r.raise_for_status()
        return parse_stock(r.text)
    except requests.RequestException as exc:
        # No credentials in this request; log only exception class/status, not URL/body.
        status = getattr(getattr(exc, "response", None), "status_code", None)
        print(f"库存请求失败：{type(exc).__name__}" + (f" HTTP {status}" if status else ""))
        raise StockCheckError("库存页面请求失败") from None


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def write_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def sender_url(sendkey: str) -> str:
    if sendkey.startswith("SCT"):
        return f"https://sctapi.ftqq.com/{sendkey}.send"
    match = re.fullmatch(r"sctp(\d+)t.+", sendkey)
    if match:
        return f"https://{match.group(1)}.push.ft07.com/send/{sendkey}.send"
    raise ValueError("SendKey 格式不受支持：需要 SCT 或 sctp 开头的密钥")


def send_wechat(title: str, body: str) -> None:
    key = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
    if not key:
        raise RuntimeError("缺少 GitHub Actions Secret: SERVERCHAN_SENDKEY")
    url = sender_url(key)
    try:
        resp = requests.post(url, data={"title": title, "desp": body}, timeout=(8, 20))
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise RuntimeError("微信通知服务拒绝推送")
    except (requests.RequestException, ValueError, RuntimeError):
        # Do not print HTTP exceptions: request URLs contain the SendKey.
        raise RuntimeError("微信通知失败；请检查 SendKey、推送渠道或当日额度") from None


def maybe_weekly_heartbeat(state: dict, now: datetime) -> None:
    """Occasional state commit helps avoid long-inactive public repository workflows."""
    last = state.get("heartbeat_at")
    try:
        last_dt = datetime.fromisoformat(last) if last else None
    except ValueError:
        last_dt = None
    if last_dt is None or now - last_dt >= timedelta(days=7):
        state["heartbeat_at"] = now.isoformat(timespec="seconds")


def run_once() -> str:
    if not os.environ.get("SERVERCHAN_SENDKEY", "").strip():
        raise RuntimeError("请先设置 GitHub Secret: SERVERCHAN_SENDKEY")

    now = now_utc()
    state = read_state()
    try:
        current = get_stock()
    except StockCheckError:
        current = "unknown"

    if current == "unknown":
        state["failures"] = int(state.get("failures", 0)) + 1
        # Warn only after six consecutive failures, then at most once per 24 hours.
        previous_alarm = state.get("last_failure_alert_at")
        try:
            previous_alarm_dt = datetime.fromisoformat(previous_alarm) if previous_alarm else None
        except ValueError:
            previous_alarm_dt = None
        if state["failures"] >= 6 and (
            previous_alarm_dt is None or now - previous_alarm_dt >= timedelta(hours=24)
        ):
            send_wechat(
                "DMIT 库存监控异常",
                f"连续 {state['failures']} 次无法确定 {PRODUCT} 库存。"
                f"\n\n监控来源：{STOCK_URL}\n请检查网页结构及 GitHub Actions 日志。",
            )
            state["last_failure_alert_at"] = now.isoformat(timespec="seconds")
        print(f"库存未知，连续异常次数：{state['failures']}。不发送补货通知。")
    else:
        last_good = state.get("status")
        if current == "in" and last_good != "in":
            send_wechat(
                f"DMIT 疑似补货！{PRODUCT}",
                f"**套餐**：{PRODUCT}\n\n**价格**：{PRICE}/月\n\n"
                f"**官方下单地址**：{CHECKOUT_URL}\n\n"
                f"第三方库存页：{STOCK_URL}\n\n"
                "这是第三方库存信号，不代表 DMIT 官方已确认可购买，请及时进入官网核实。",
            )
            print("已发送疑似补货微信通知")
        state["status"] = current
        state["failures"] = 0
        print(f"{PRODUCT}: {current}, 上次确认状态: {last_good}")
    maybe_weekly_heartbeat(state, now)
    write_state(state)
    return current


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="只发送微信测试消息，不检测库存")
    args = parser.parse_args()
    if args.test:
        send_wechat("DMIT 补货监控测试", f"微信通知接通。监控目标：{PRODUCT}\n商品：{CHECKOUT_URL}")
        print("测试消息已发送，请检查微信")
    else:
        run_once()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
