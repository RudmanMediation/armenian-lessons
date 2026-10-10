"""Turns the lesson scripts in ../lessons into data the apps use.

Writes:
  recorder/lines.js  - every Armenian phrase that needs recording, once each,
                       with who should record it (M = man, W = woman).
  lessons.json       - each lesson as a sequence of steps, for the player app.

Run it again whenever a lesson script changes.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "lessons"

SEP = " — "  # " — "


def key_of(translit):
    """Same phrase, same recording. Keeps the question mark (it changes the intonation)."""
    k = translit.strip().lower()
    k = re.sub(r"[.,!։]+", "", k)
    k = re.sub(r"\s+", " ", k).strip()
    return k


def line_id(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def parse_lesson(path):
    num = int(re.search(r"(\d+)", path.stem).group(1))
    steps = []
    part = ""
    in_dialog = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            part = line[3:].strip()
            in_dialog = "opening conversation" in part.lower()
            continue
        if line.startswith("### "):
            break  # speaker notes
        if "conversation plays again" in line:
            steps.append({"type": "replay_dialog"})
            continue
        m = re.match(r"^(N|M|W):\s*(.+)$", line)
        if not m:
            continue
        who, text = m.group(1), m.group(2)
        if who == "N":
            pause = "(pause)" in text
            text = text.replace("(pause)", "").strip()
            steps.append({"type": "narrator", "text": text, "pause": pause})
            continue
        if "(pause)" in text and "…" in text:
            # a breakdown line: "sin (pause) … asin (pause) … miasin (pause)"
            pieces = [p.replace("(pause)", "").strip() for p in text.split("…")]
            pieces = [p for p in pieces if p]
            for p in pieces:
                steps.append({"type": "say", "who": who, "translit": p, "piece": True,
                              "word": pieces[-1], "pause": True, "dialog": False, "part": part})
            continue
        pause = "(pause)" in text
        text = text.replace("(pause)", "").strip()
        bits = text.split(SEP)
        translit = bits[0].strip()
        armenian = bits[1].strip() if len(bits) > 1 else ""
        meaning = bits[2].strip().strip("*") if len(bits) > 2 else ""
        steps.append({"type": "say", "who": who, "translit": translit, "armenian": armenian,
                      "meaning": meaning, "piece": False, "pause": pause,
                      "dialog": in_dialog, "part": part})
    return num, steps


def main():
    lessons = {}
    for path in sorted(LESSONS.glob("lesson-*.md")):
        num, steps = parse_lesson(path)
        lessons[num] = steps

    # One recording per phrase. Dialog speakers win; otherwise first speaker heard.
    phrases = {}
    for num in sorted(lessons):
        for s in lessons[num]:
            if s["type"] != "say":
                continue
            k = key_of(s["translit"])
            s["id"] = line_id(k)
            p = phrases.get(k)
            if p is None:
                p = phrases[k] = {"id": s["id"], "who": s["who"], "translit": s["translit"],
                                  "armenian": "", "meaning": "", "lesson": num,
                                  "piece": s["piece"], "word": s.get("word", ""),
                                  "dialog": False, "order": len(phrases)}
            if s.get("dialog") and not p["dialog"]:
                p["who"] = s["who"]
                p["dialog"] = True
            if s.get("armenian") and not p["armenian"]:
                p["armenian"] = s["armenian"]
            if s.get("meaning") and not p["meaning"]:
                p["meaning"] = s["meaning"]
            if not s["piece"]:
                p["piece"] = False

    # Fill missing meanings from the narrator's teaching lines is too fuzzy; leave blank.
    items = sorted(phrases.values(), key=lambda p: p["order"])
    for p in items:
        p.pop("order")

    out = ROOT / "recorder" / "lines.js"
    out.parent.mkdir(exist_ok=True)
    out.write_text("// Built by tools/build.py from the lesson scripts. Do not edit by hand.\n"
                   "window.LINES = " + json.dumps(items, ensure_ascii=False, indent=1) + ";\n",
                   encoding="utf-8")
    (ROOT / "lessons.json").write_text(json.dumps(lessons, ensure_ascii=False, indent=1),
                                       encoding="utf-8")

    for who in "MW":
        mine = [p for p in items if p["who"] == who]
        print(f"{who}: {len(mine)} recordings "
              + ", ".join(f"L{n}: {sum(1 for p in mine if p['lesson'] == n)}" for n in sorted(lessons)))


if __name__ == "__main__":
    main()
