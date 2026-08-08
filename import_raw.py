import csv
import os
import re


output_file = "words.csv"

with open(output_file, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["source", "word", "meaning"])

    # raw_data フォルダ内の .txt を全部読む
    for filename in os.listdir("raw_data"):
        if filename.endswith(".txt"):
            source = filename.replace(".txt", "")  # pre1 / target1900 など

            with open(f"raw_data/{filename}", encoding="utf-8") as infile:
                for line in infile:
                    # 行の前後の改行を取り、Lv.数字 を削除、余計なスペースを整える
                    line = line.rstrip("\n\r")
                    line = re.sub(r"Lv\.\d+", "", line)
                    line = re.sub(r"\s+", " ", line).strip()
                    if not line:
                        continue

                    # 単語と意味を分割（タブ・スペース全部OK）
                    parts = re.split(r"\s+", line, maxsplit=1)

                    if len(parts) < 2:
                        continue

                    word = parts[0]
                    meaning = parts[1]

                    # 英単語以外（Lv4、日本語タイトル）は除外
                    if not re.match(r"^[A-Za-z]+$", word):
                        continue

                    writer.writerow([source, word, meaning])
