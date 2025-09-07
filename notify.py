import argparse
import io
import os
import sys
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Iterable, List, Optional

import requests
from icalendar import Calendar, Event


JST = ZoneInfo("Asia/Tokyo")
LINE_NOTIFY_ENDPOINT = "https://notify-api.line.me/api/notify"
LINE_MESSAGING_PUSH_ENDPOINT = "https://api.line.me/v2/bot/message/push"
LINE_LIMIT = 1000  # LINE Notify message length limit


@dataclass
class NormalizedEvent:
    title: str
    start: datetime  # aware, JST
    end: datetime    # aware, JST, exclusive end
    is_all_day: bool
    location: Optional[str]


def _weekday_ja(dt: date) -> str:
    wk = "月火水木金土日"[(dt.weekday() + 0) % 7]
    return f"{wk}"


def _ensure_aware_jst(v) -> datetime:
    """Convert ical value (date or datetime, tz-aware or naive) to aware JST datetime.
    - date -> 00:00 JST at that date
    - naive datetime -> treat as JST
    - tz-aware -> convert to JST
    """
    if isinstance(v, date) and not isinstance(v, datetime):
        return datetime(v.year, v.month, v.day, tzinfo=JST)
    if isinstance(v, datetime):
        if v.tzinfo is None:
            return v.replace(tzinfo=JST)
        return v.astimezone(JST)
    raise TypeError(f"Unsupported datetime value: {type(v)}")


def parse_ics(ics_bytes: bytes) -> List[NormalizedEvent]:
    cal = Calendar.from_ical(ics_bytes)
    events: List[NormalizedEvent] = []
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        try:
            dtstart_raw = comp.get("DTSTART").dt
        except Exception:
            # Skip malformed event
            continue

        dtend_prop = comp.get("DTEND")
        dtend_raw = dtend_prop.dt if dtend_prop else None

        is_all_day = isinstance(dtstart_raw, date) and not isinstance(dtstart_raw, datetime)

        # DTSTART normalize
        start = _ensure_aware_jst(dtstart_raw)

        # DTEND normalize
        if dtend_raw is None:
            # if missing, use DTSTART as DTEND (zero-duration)
            end = start
        else:
            if is_all_day and isinstance(dtend_raw, date) and not isinstance(dtend_raw, datetime):
                # All-day DTEND in ICS is exclusive; convert to next day 00:00 JST
                end = _ensure_aware_jst(dtend_raw)
            else:
                end = _ensure_aware_jst(dtend_raw)

        title = str(comp.get("SUMMARY") or "(無題)")
        loc = comp.get("LOCATION")
        location = str(loc) if loc else None

        events.append(NormalizedEvent(title=title.strip(), start=start, end=end, is_all_day=is_all_day, location=(location.strip() if location else None)))
    return events


def clip_to_day(ev: NormalizedEvent, day_start: datetime, day_end_exclusive: datetime) -> Optional[NormalizedEvent]:
    # Intersection check using exclusive end
    if ev.end <= day_start or ev.start >= day_end_exclusive:
        return None
    s = max(ev.start, day_start)
    e = min(ev.end, day_end_exclusive)
    return NormalizedEvent(title=ev.title, start=s, end=e, is_all_day=ev.is_all_day, location=ev.location)


def format_message(target_day: date, events: List[NormalizedEvent]) -> str:
    header = f"📅 本日の予定 {target_day.strftime('%Y/%m/%d')}({_weekday_ja(target_day)})"
    day_start = datetime(target_day.year, target_day.month, target_day.day, tzinfo=JST)
    next_day_start = day_start + timedelta(days=1)

    if not events:
        body = "🟢 予定はありません"
        msg = f"{header}\n{body}"
        return msg[:LINE_LIMIT]

    # Sort: all-day first, then by start time
    events_sorted = sorted(events, key=lambda x: (not x.is_all_day, x.start, x.end))

    lines: List[str] = [header]
    for ev in events_sorted:
        if ev.is_all_day:
            line = f"• 終日 {ev.title}"
        else:
            start_s = ev.start.strftime("%H:%M")
            end_dt = ev.end
            # If event is clipped at day end (exclusive), show 23:59 for readability
            if end_dt == next_day_start:
                end_s = "23:59"
            else:
                end_s = end_dt.strftime("%H:%M")
            line = f"• {start_s}–{end_s} {ev.title}"
        if ev.location:
            line += f" ＠{ev.location}"
        # Sanitize newlines and control chars in a simple way
        line = line.replace("\r", " ").replace("\n", " ")
        lines.append(line)

    # Enforce LINE limit: include as many lines as fit, then append summary
    out_lines: List[str] = []
    used = 0
    overflow_count = 0
    for i, line in enumerate(lines):
        add_len = len(line) + (0 if i == 0 else 1)  # +1 for newline except first
        if used + add_len <= LINE_LIMIT:
            out_lines.append(line)
            used += add_len
        else:
            # Remaining lines are overflow (excluding header if first overflow)
            overflow_count = max(0, len(lines) - i)
            break

    if overflow_count > 0:
        tail = f"…ほか{overflow_count}件"
        # Ensure tail fits
        if used + 1 + len(tail) > LINE_LIMIT and out_lines:
            # Trim last line to make room
            last = out_lines[-1]
            room = LINE_LIMIT - used - 1 - len(tail)
            if room > 0:
                out_lines[-1] = last[:room]
            else:
                # Remove last line entirely if no room
                out_lines.pop()
        out_lines.append(tail)

    return "\n".join(out_lines)[:LINE_LIMIT]


def send_line_notify(token: str, message: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": message}
    resp = requests.post(LINE_NOTIFY_ENDPOINT, headers=headers, data=data, timeout=10)
    if resp.status_code >= 400:
        # Avoid printing token or message content
        raise SystemExit(f"LINE Notify error: HTTP {resp.status_code}")


def send_line_messaging(channel_access_token: str, to_user_id: str, message: str) -> None:
    headers = {"Authorization": f"Bearer {channel_access_token}"}
    payload = {
        "to": to_user_id,
        "messages": [
            {"type": "text", "text": message}
        ],
    }
    resp = requests.post(LINE_MESSAGING_PUSH_ENDPOINT, headers=headers, json=payload, timeout=10)
    if resp.status_code >= 400:
        raise SystemExit(f"LINE Messaging API error: HTTP {resp.status_code}")


def read_ics(path: Optional[str]) -> bytes:
    if path:
        with open(path, "rb") as f:
            return f.read()
    # stdin
    return sys.stdin.buffer.read()


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Morning TimeTree notifier")
    parser.add_argument("--ics", help="ICSファイルのパス。未指定時は標準入力から読み込み")
    parser.add_argument("--date", help="対象日 (YYYY-MM-DD, JST)")
    parser.add_argument("--dry-run", action="store_true", help="送信せず標準出力へ表示")
    parser.add_argument("--line-mode", choices=["notify", "messaging"], default="notify", help="送信モードを選択")
    parser.add_argument("--line-channel-access-token", help="Messaging API のチャネルアクセストークン")
    parser.add_argument("--line-user-id", help="Messaging API 送信先ユーザーID")
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Target day in JST
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("--date は YYYY-MM-DD 形式で指定してください")
    else:
        target_date = datetime.now(JST).date()

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=JST)
    next_day_start = day_start + timedelta(days=1)

    ics_bytes = read_ics(args.ics)
    if not ics_bytes:
        raise SystemExit("ICS が空です。エクスポート手順を確認してください。")

    events_all = parse_ics(ics_bytes)
    # Clip by day (exclusive end)
    events_today: List[NormalizedEvent] = []
    for ev in events_all:
        clipped = clip_to_day(ev, day_start, next_day_start)
        if clipped is not None:
            events_today.append(clipped)

    message = format_message(target_date, events_today)

    if args.dry_run:
        print(message)
        return 0

    # Dispatch by line-mode
    if args.line_mode == "notify":
        token = os.getenv("LINE_TOKEN")
        if not token:
            raise SystemExit("LINE Notify を使うには環境変数 LINE_TOKEN が必要です。")
        send_line_notify(token, message)
    else:
        # messaging
        cat = args.line_channel_access_token or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        uid = args.line_user_id or os.getenv("LINE_USER_ID")
        if not cat or not uid:
            raise SystemExit("Messaging API を使うには LINE_CHANNEL_ACCESS_TOKEN と LINE_USER_ID が必要です。")
        send_line_messaging(cat, uid, message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
