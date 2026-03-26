import argparse
import csv
import os
import re
import sqlite3
from collections import defaultdict
from contextlib import ExitStack
from datetime import datetime

from pywxdump.db.dbMSG import decompress_CompressContent, get_BytesExtra
from pywxdump.db.utils.common_utils import xml2dict


TYPE_NAMES = {
    (1, 0): "text",
    (3, 0): "image",
    (34, 0): "voice",
    (43, 0): "video",
    (47, 0): "emoji",
    (48, 0): "location",
    (49, 0): "file",
    (49, 3): "music_share",
    (49, 5): "link_share",
    (49, 6): "file",
    (49, 19): "merged_forward",
    (49, 33): "mini_program",
    (49, 51): "video_channel",
    (49, 53): "group_note",
    (49, 57): "reply",
    (49, 63): "live_or_replay",
    (49, 87): "group_announcement",
    (49, 88): "live_or_replay",
    (49, 92): "unknown_49_92",
    (49, 2000): "transfer",
    (49, 2003): "red_packet_cover",
    (50, 0): "call",
    (10000, 0): "system",
    (10000, 4): "pat",
    (10000, 5): "revoke",
    (10000, 57): "revoke",
    (10000, 8000): "system",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Export merged WeChat messages to per-contact CSV files.")
    parser.add_argument("--msg-db", required=True, help="Path to merged MSG database")
    parser.add_argument("--contact-db", required=True, help="Path to decrypted MicroMsg database")
    parser.add_argument("--out-dir", required=True, help="Directory for CSV exports")
    return parser.parse_args()


def safe_name(value):
    value = (value or "").strip()
    if not value:
        value = "unknown"
    value = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1F]', "_", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = value.rstrip(". ")
    return value[:120] or "unknown"


def unix_to_local_str(ts):
    if not ts:
        return ""
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")


def build_contact_map(contact_db):
    conn = sqlite3.connect(contact_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT UserName, NickName, Remark, Alias
        FROM Contact
        """
    )
    contact_map = {}
    for row in cur.fetchall():
        username = row["UserName"]
        display = row["Remark"] or row["NickName"] or row["Alias"] or username
        contact_map[username] = {
            "username": username,
            "nickname": row["NickName"] or "",
            "remark": row["Remark"] or "",
            "alias": row["Alias"] or "",
            "display_name": display or username,
        }
    conn.close()
    return contact_map


def extract_sender_username(row):
    if row["IsSender"] == 1:
        return "self"
    if not row["StrTalker"].endswith("@chatroom"):
        return row["StrTalker"]
    bytes_extra = row["BytesExtra"]
    if not bytes_extra:
        return ""
    try:
        parsed = get_BytesExtra(bytes_extra)
    except Exception:
        parsed = None
    if isinstance(parsed, dict):
        try:
            candidate = parsed["3"][0]["2"]
            if isinstance(candidate, str):
                return candidate
        except Exception:
            pass
    return ""


def summarize_message(row):
    msg_type = (row["Type"], row["SubType"])
    type_name = TYPE_NAMES.get(msg_type, f"{row['Type']}_{row['SubType']}")
    content = row["StrContent"] or ""
    extra_path = ""

    if msg_type == (1, 0):
        return type_name, content, extra_path

    if msg_type == (3, 0):
        extra_path = extract_filestorage_path(row["BytesExtra"])
        return type_name, "[image]", extra_path

    if msg_type == (34, 0):
        parsed = xml2dict(content) or {}
        voice = parsed.get("voicemsg", {}) if isinstance(parsed, dict) else {}
        secs = voice.get("voicelength", "")
        if str(secs).isdigit():
            secs = f"{int(secs) / 1000:.2f}s"
        else:
            secs = ""
        trans = ""
        if isinstance(parsed, dict):
            trans = parsed.get("voicetrans", {}).get("transtext", "")
        text = "[voice]"
        if secs:
            text += f" {secs}"
        if trans:
            text += f" {trans}"
        return type_name, text, extra_path

    if msg_type == (43, 0):
        extra_path = extract_filestorage_path(row["BytesExtra"], prefer="mp4")
        return type_name, "[video]", extra_path

    if msg_type == (47, 0):
        return type_name, "[emoji]", extra_path

    if msg_type == (48, 0):
        parsed = xml2dict(content) or {}
        location = parsed.get("location", {}) if isinstance(parsed, dict) else {}
        label = location.get("label", "")
        poiname = location.get("poiname", "")
        text = " ".join(part for part in [label, poiname] if part).strip() or "[location]"
        return type_name, text, extra_path

    if msg_type in {(49, 5), (49, 19), (49, 57), (49, 2000)}:
        decoded = decode_compress_content(row["CompressContent"])
        return type_name, decoded, extra_path

    if msg_type in {(49, 0), (49, 6), (49, 33), (49, 51), (49, 53), (49, 63), (49, 87), (49, 88), (49, 92), (49, 2003)}:
        extra_path = extract_filestorage_path(row["BytesExtra"])
        decoded = decode_compress_content(row["CompressContent"])
        if not decoded:
            decoded = content or f"[{type_name}]"
        return type_name, decoded, extra_path

    if msg_type == (50, 0):
        return type_name, f"[call] {row['DisplayContent'] or ''}".strip(), extra_path

    if row["Type"] == 10000:
        return type_name, content or row["DisplayContent"] or f"[{type_name}]", extra_path

    return type_name, content or row["DisplayContent"] or f"[{type_name}]", extra_path


def decode_compress_content(blob):
    if not blob:
        return ""
    try:
        xml_text = decompress_CompressContent(blob)
    except Exception:
        return ""
    if not xml_text:
        return ""
    parsed = xml2dict(xml_text)
    if not isinstance(parsed, dict):
        return xml_text[:500]
    appmsg = parsed.get("appmsg", {})
    if not isinstance(appmsg, dict):
        return xml_text[:500]

    title = appmsg.get("title", "")
    desc = appmsg.get("des", "")
    url = appmsg.get("url", "")
    refer = appmsg.get("refermsg", {}) if isinstance(appmsg.get("refermsg", {}), dict) else {}
    parts = []
    if title:
        parts.append(title)
    if desc:
        parts.append(desc)
    if refer:
        ref_name = refer.get("displayname", "")
        ref_content = refer.get("content", "")
        if ref_name or ref_content:
            parts.append(f"ref:{ref_name} {ref_content}".strip())
    if url:
        parts.append(url)
    return " | ".join(part.strip() for part in parts if part and str(part).strip())[:2000] or xml_text[:500]


def extract_filestorage_path(bytes_extra, prefer=""):
    if not bytes_extra:
        return ""
    try:
        parsed = get_BytesExtra(bytes_extra)
    except Exception:
        return ""
    text = str(parsed)
    matches = re.findall(r"(FileStorage.*?)'", text)
    if not matches:
        return ""
    if prefer:
        preferred = [item for item in matches if prefer.lower() in item.lower()]
        if preferred:
            return preferred[0]
    image_first = [item for item in matches if "Image" in item]
    return (image_first or matches)[0]


def export_csv(msg_db, contact_db, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    chats_dir = os.path.join(out_dir, "chats")
    os.makedirs(chats_dir, exist_ok=True)

    contact_map = build_contact_map(contact_db)
    msg_conn = sqlite3.connect(msg_db)
    msg_conn.row_factory = sqlite3.Row
    cur = msg_conn.cursor()
    cur.execute(
        """
        SELECT
            localId, MsgSvrID, Type, SubType, IsSender, CreateTime,
            StrTalker, StrContent, DisplayContent, CompressContent, BytesExtra
        FROM MSG
        ORDER BY StrTalker ASC, CreateTime ASC, localId ASC
        """
    )

    chat_files = {}
    chat_writers = {}
    chat_stats = defaultdict(lambda: {"count": 0, "first_time": "", "last_time": "", "csv_file": ""})
    with ExitStack() as stack:
        for row in cur:
            talker = row["StrTalker"]
            chat_meta = contact_map.get(talker, {})
            chat_name = chat_meta.get("display_name", talker)
            is_chatroom = int(talker.endswith("@chatroom"))

            if talker not in chat_writers:
                label = safe_name(chat_name)
                filename = f"{len(chat_writers)+1:04d}_{label}.csv"
                csv_path = os.path.join(chats_dir, filename)
                fh = stack.enter_context(open(csv_path, "w", newline="", encoding="utf-8-sig"))
                writer = csv.writer(fh)
                writer.writerow(
                    [
                        "chat_id",
                        "chat_name",
                        "is_chatroom",
                        "timestamp",
                        "msg_id",
                        "msg_type",
                        "is_sender",
                        "sender_username",
                        "sender_name",
                        "content",
                        "attachment_hint",
                    ]
                )
                chat_files[talker] = csv_path
                chat_writers[talker] = writer
                chat_stats[talker]["csv_file"] = filename

            sender_username = extract_sender_username(row)
            sender_name = sender_username
            if sender_username == "self":
                sender_name = "self"
            elif sender_username in contact_map:
                sender_name = contact_map[sender_username]["display_name"]

            msg_type, content, attachment_hint = summarize_message(row)
            timestamp = unix_to_local_str(row["CreateTime"])

            chat_writers[talker].writerow(
                [
                    talker,
                    chat_name,
                    is_chatroom,
                    timestamp,
                    row["MsgSvrID"],
                    msg_type,
                    row["IsSender"],
                    sender_username,
                    sender_name,
                    content,
                    attachment_hint,
                ]
            )

            stats = chat_stats[talker]
            stats["count"] += 1
            stats["first_time"] = stats["first_time"] or timestamp
            stats["last_time"] = timestamp

    index_path = os.path.join(out_dir, "index.csv")
    with open(index_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "chat_id",
                "chat_name",
                "remark",
                "nickname",
                "alias",
                "is_chatroom",
                "message_count",
                "first_time",
                "last_time",
                "csv_file",
            ]
        )
        for talker, stats in sorted(chat_stats.items(), key=lambda item: (-item[1]["count"], item[0])):
            meta = contact_map.get(talker, {})
            writer.writerow(
                [
                    talker,
                    meta.get("display_name", talker),
                    meta.get("remark", ""),
                    meta.get("nickname", ""),
                    meta.get("alias", ""),
                    int(talker.endswith("@chatroom")),
                    stats["count"],
                    stats["first_time"],
                    stats["last_time"],
                    stats["csv_file"],
                ]
            )

    msg_conn.close()
    return index_path, chats_dir, len(chat_stats)


def main():
    args = parse_args()
    index_path, chats_dir, chat_count = export_csv(args.msg_db, args.contact_db, args.out_dir)
    print(f"index: {index_path}")
    print(f"chats_dir: {chats_dir}")
    print(f"chat_count: {chat_count}")


if __name__ == "__main__":
    main()
