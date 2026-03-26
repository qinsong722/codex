import argparse
import csv
import json
import math
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare a GPT-ready persona analysis package from WeChat exports.")
    parser.add_argument("--msg-db", required=True, help="Path to merged MSG database")
    parser.add_argument("--contact-db", required=True, help="Path to decrypted MicroMsg database")
    parser.add_argument("--out-dir", required=True, help="Directory for generated analysis artifacts")
    return parser.parse_args()


def load_contacts(contact_db):
    conn = sqlite3.connect(contact_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT UserName, NickName, Remark, Alias FROM Contact")
    contacts = {}
    for row in cur.fetchall():
        display_name = row["Remark"] or row["NickName"] or row["Alias"] or row["UserName"]
        contacts[row["UserName"]] = {
            "username": row["UserName"],
            "display_name": display_name,
            "remark": row["Remark"] or "",
            "nickname": row["NickName"] or "",
            "alias": row["Alias"] or "",
        }
    conn.close()
    return contacts


def dt_str(ts):
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")


def percentile(sorted_values, p):
    if not sorted_values:
        return 0
    idx = min(len(sorted_values) - 1, max(0, math.floor((len(sorted_values) - 1) * p)))
    return sorted_values[idx]


def build_stats(msg_db, contacts):
    conn = sqlite3.connect(msg_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    stats = {}

    cur.execute("SELECT COUNT(*) FROM MSG WHERE IsSender=1")
    stats["self_total_messages"] = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM MSG
        WHERE IsSender=1 AND Type=1 AND SubType=0 AND length(trim(coalesce(StrContent,'')))>0
        """
    )
    stats["self_text_messages"] = cur.fetchone()[0]

    cur.execute(
        """
        SELECT MIN(CreateTime), MAX(CreateTime)
        FROM MSG
        WHERE IsSender=1
        """
    )
    min_ts, max_ts = cur.fetchone()
    stats["self_date_range"] = {
        "start": dt_str(min_ts) if min_ts else "",
        "end": dt_str(max_ts) if max_ts else "",
    }

    cur.execute(
        """
        SELECT strftime('%H', CreateTime, 'unixepoch', 'localtime') AS hour, COUNT(*) AS c
        FROM MSG
        WHERE IsSender=1
        GROUP BY hour
        ORDER BY c DESC
        LIMIT 12
        """
    )
    stats["top_active_hours"] = [{"hour": row["hour"], "count": row["c"]} for row in cur.fetchall()]

    cur.execute(
        """
        SELECT strftime('%w', CreateTime, 'unixepoch', 'localtime') AS weekday, COUNT(*) AS c
        FROM MSG
        WHERE IsSender=1
        GROUP BY weekday
        ORDER BY c DESC
        """
    )
    weekday_names = {
        "0": "Sunday",
        "1": "Monday",
        "2": "Tuesday",
        "3": "Wednesday",
        "4": "Thursday",
        "5": "Friday",
        "6": "Saturday",
    }
    stats["weekday_activity"] = [
        {"weekday": weekday_names.get(row["weekday"], row["weekday"]), "count": row["c"]}
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT StrTalker, COUNT(*) AS c
        FROM MSG
        WHERE IsSender=1 AND Type=1 AND SubType=0
        GROUP BY StrTalker
        ORDER BY c DESC
        LIMIT 30
        """
    )
    top_chats = []
    for row in cur.fetchall():
        talker = row["StrTalker"]
        meta = contacts.get(talker, {})
        top_chats.append(
            {
                "chat_id": talker,
                "chat_name": meta.get("display_name", talker),
                "is_chatroom": talker.endswith("@chatroom"),
                "self_text_count": row["c"],
            }
        )
    stats["top_self_text_chats"] = top_chats

    cur.execute(
        """
        SELECT CreateTime, StrContent
        FROM MSG
        WHERE IsSender=1 AND Type=1 AND SubType=0 AND length(trim(coalesce(StrContent,'')))>0
        ORDER BY CreateTime ASC
        """
    )
    lengths = []
    punct_counter = Counter()
    token_counter = Counter()
    for row in cur.fetchall():
        text = row["StrContent"].strip()
        lengths.append(len(text))
        for ch in text:
            if ch in "!?！？。,.，；;：:":
                punct_counter[ch] += 1
        for token in simple_tokens(text):
            token_counter[token] += 1

    lengths.sort()
    stats["text_length"] = {
        "avg": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "p50": percentile(lengths, 0.5),
        "p90": percentile(lengths, 0.9),
        "max": max(lengths) if lengths else 0,
    }
    stats["top_punctuation"] = [{"symbol": k, "count": v} for k, v in punct_counter.most_common(12)]
    stats["top_tokens"] = [{"token": k, "count": v} for k, v in token_counter.most_common(50)]

    conn.close()
    return stats


def simple_tokens(text):
    chunks = []
    buf = []
    for ch in text.lower():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            buf.append(ch)
        else:
            if len(buf) >= 2:
                chunks.append("".join(buf))
            buf = []
    if len(buf) >= 2:
        chunks.append("".join(buf))
    return chunks


def sample_messages(msg_db, contacts, out_dir):
    conn = sqlite3.connect(msg_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT StrTalker, COUNT(*) AS c
        FROM MSG
        WHERE IsSender=1 AND Type=1 AND SubType=0 AND length(trim(coalesce(StrContent,'')))>0
        GROUP BY StrTalker
        ORDER BY c DESC
        LIMIT 40
        """
    )
    top_talkers = [row["StrTalker"] for row in cur.fetchall()]

    selected_rows = []
    for talker in top_talkers:
        cur.execute(
            """
            SELECT StrTalker, CreateTime, StrContent
            FROM MSG
            WHERE IsSender=1 AND Type=1 AND SubType=0
              AND length(trim(coalesce(StrContent,'')))>0
              AND StrTalker=?
            ORDER BY CreateTime ASC
            """,
            (talker,),
        )
        rows = cur.fetchall()
        if not rows:
            continue
        picks = pick_evenly(rows, 12)
        meta = contacts.get(talker, {})
        for row in picks:
            selected_rows.append(
                {
                    "chat_id": talker,
                    "chat_name": meta.get("display_name", talker),
                    "is_chatroom": int(talker.endswith("@chatroom")),
                    "timestamp": dt_str(row["CreateTime"]),
                    "content": row["StrContent"].strip(),
                }
            )

    selected_rows.sort(key=lambda item: (item["chat_name"], item["timestamp"]))

    samples_path = os.path.join(out_dir, "persona_samples.csv")
    with open(samples_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["chat_id", "chat_name", "is_chatroom", "timestamp", "content"],
        )
        writer.writeheader()
        writer.writerows(selected_rows)

    conn.close()
    return samples_path, selected_rows


def pick_evenly(rows, n):
    if len(rows) <= n:
        return rows
    indices = sorted({round(i * (len(rows) - 1) / (n - 1)) for i in range(n)})
    return [rows[i] for i in indices]


def write_prompt(stats, samples, out_dir):
    prompt_path = os.path.join(out_dir, "persona_prompt.md")
    sample_lines = []
    for row in samples[:180]:
        sample_lines.append(f"- [{row['timestamp']}] ({row['chat_name']}) {row['content']}")

    prompt = f"""You are an expert behavioral analyst and communication profiler.

Goal:
Build a detailed persona profile of the message author ("me") from the supplied WeChat messaging data.

Requirements:
1. Infer from evidence only. Separate strong evidence from weak inference.
2. Focus on these dimensions:
   - Core personality tendencies
   - Communication style
   - Emotional expression
   - Relationship patterns
   - Work style and decision habits
   - Social role across 1:1 chats vs group chats
   - Personal habits visible from timing, wording, and topic choices
   - Possible strengths, blind spots, and stress patterns
3. Quote or paraphrase concrete message evidence.
4. Where evidence is mixed, describe the contradiction instead of forcing a conclusion.
5. End with:
   - A one-paragraph executive summary
   - A structured profile table
   - 10 high-confidence traits
   - 10 lower-confidence hypotheses
   - Suggestions for how this person likely prefers others to communicate with them

High-level stats:
{json.dumps(stats, ensure_ascii=False, indent=2)}

Representative self-authored text samples:
{os.linesep.join(sample_lines)}
"""

    with open(prompt_path, "w", encoding="utf-8") as fh:
        fh.write(prompt)
    return prompt_path


def write_brief(stats, samples_path, prompt_path, out_dir):
    brief_path = os.path.join(out_dir, "persona_brief.md")
    lines = [
        "# Persona Analysis Package",
        "",
        "This folder is prepared for a downstream GPT persona analysis run.",
        "",
        "## Files",
        f"- `persona_stats.json`: aggregate behavior and language stats",
        f"- `persona_samples.csv`: representative self-authored message samples",
        f"- `persona_prompt.md`: ready-to-paste analysis prompt",
        "",
        "## Snapshot",
        f"- Self total messages: {stats['self_total_messages']}",
        f"- Self text messages: {stats['self_text_messages']}",
        f"- Date range: {stats['self_date_range']['start']} -> {stats['self_date_range']['end']}",
        f"- Top active hours: {', '.join([item['hour'] for item in stats['top_active_hours'][:6]])}",
        "",
        "Use `persona_prompt.md` as the main input and attach `persona_samples.csv` if the model supports file upload.",
    ]
    with open(brief_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return brief_path


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    contacts = load_contacts(args.contact_db)
    stats = build_stats(args.msg_db, contacts)

    stats_path = os.path.join(args.out_dir, "persona_stats.json")
    with open(stats_path, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    samples_path, samples = sample_messages(args.msg_db, contacts, args.out_dir)
    prompt_path = write_prompt(stats, samples, args.out_dir)
    brief_path = write_brief(stats, samples_path, prompt_path, args.out_dir)

    print(f"stats: {stats_path}")
    print(f"samples: {samples_path}")
    print(f"prompt: {prompt_path}")
    print(f"brief: {brief_path}")


if __name__ == "__main__":
    main()
