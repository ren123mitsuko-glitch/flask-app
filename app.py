from flask import Flask, render_template, request, redirect, session
from flask import Flask, session
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

import csv
import random
import json
import json

def remove_duplicates(words):
    seen = set()
    unique = []
    for w in words:
        if w["word"] not in seen:
            unique.append(w)
            seen.add(w["word"])
    return unique


def load_idioms():
    with open("raw_data/idioms.json", "r", encoding="utf-8") as f:
        return json.load(f)

from datetime import datetime, timedelta
import time


SCORE_FILE = "score_history.csv"

def load_words(range_filter=None):
    words = []
    with open("words.csv", encoding="utf-8") as f:
        first = True
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if first:
                first = False
                continue  # ヘッダー飛ばす
            
            parts = line.split(",", 2)
            if len(parts) < 2:
                continue
            
            word_range = parts[0] if len(parts) > 2 else ""
            word = parts[1] if len(parts) > 2 else parts[0]
            meaning = parts[2] if len(parts) > 2 else parts[1]
            
            if range_filter and word_range != range_filter:
                continue
            
            words.append({
                "word": word,
                "meaning": meaning,
                "range": word_range
            })
    
    return words
def load_koten():
    with open("raw_data/koten.json", encoding="utf-8") as f:
        words = json.load(f)
    words = remove_duplicates(words)   # ★ 重複を自動で除去
    return words



def make_choices(correct_word, all_words=None, num_choices=4):
    if all_words is None:
        all_words = load_words()

    candidates = [w for w in all_words if w["word"] != correct_word["word"]]
    num_dummies = min(num_choices - 1, len(candidates))
    choices = [correct_word]
    if num_dummies > 0:
        choices.extend(random.sample(candidates, num_dummies))
    random.shuffle(choices)
    return choices


import csv

def load_wrong():
    wrong = []
    with open("wrong_history.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # ヘッダーを飛ばす
        for row in reader:
            # 壊れた行は無視
            if len(row) != 4:
                continue

            word = row[0]
            meaning = row[1]
            last_time = float(row[2])
            interval = int(float(row[3].strip()))


            wrong.append({
                "word": word,
                "meaning": meaning,
                "last_time": last_time,
                "interval": interval
            })
    return wrong


def get_review_words():

    wrong = load_wrong()
    now = time.time()
    candidates = []

    for w in wrong:
        interval = w["interval"]
        last_time = w["last_time"]

        # --- 未来の last_time を自動補正 ---
        # last_time が now より未来なら、now - 1 に置き換えた値を使う
        effective_last_time = min(last_time, now - 1)
        # -------------------------------------

        # 忘却曲線：次の復習タイミング
        if interval == 1:
            due = effective_last_time + 86400          # 1日後
        elif interval == 2:
            due = effective_last_time + 3 * 86400      # 3日後
        else:
            due = effective_last_time + 7 * 86400      # 7日後

        # まだ復習タイミングじゃない → スキップ
        if now < due:
            continue

        # 優先度スコア
        priority = 0

        # ① 間違えた回数（interval）
        priority += interval * 2

        # ② 直近の誤答（24時間以内なら +1）
        if now - effective_last_time < 86400:
            priority += 1

        # ③ 忘却曲線：期限を過ぎてるほど優先度UP
            overdue = now - due
            priority += overdue / 86400  # ← 1日ごとに +1 に変更


        w["priority"] = priority
        candidates.append(w)

    # 優先度の高い順に並べる
    candidates.sort(key=lambda x: x["priority"], reverse=True)

    return candidates


# --- SRS helpers (simple JSON-backed) ---
def today():
    return datetime.now().strftime("%Y-%m-%d")


def today_plus(days):
    try:
        days = int(days)
    except Exception:
        days = 0
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def load_srs_data():
    try:
        with open("srs_data.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_srs_data(srs):
    with open("srs_data.json", "w", encoding="utf-8") as f:
        json.dump(srs, f, ensure_ascii=False, indent=2)


def update_wrong(word, meaning, correct):
    wrong = load_wrong()
    now = time.time()  # ← これに変更（絶対に未来にならない）

    updated = False

    for w in wrong:
        if w["word"] == word:
            w["interval"] = w["interval"] * 2 if correct else 1
            w["last_time"] = now
            updated = True
            break

    if not updated:
        wrong.append({
            "word": word,
            "meaning": meaning,
            "last_time": now,
            "interval": 1
        })

    with open("wrong_history.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "meaning", "last_time", "interval"])
        for w in wrong:
            writer.writerow([
                w["word"],
                w["meaning"],
                w["last_time"],
                w["interval"]
            ])




def save_wrong(word, meaning):
    update_wrong(word, meaning, False)


import csv
from datetime import datetime
import ast

def save_score(correct, total, mode, wrong_list):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if wrong_list is None:
        wrong_list = []

    wrong_json = json.dumps(wrong_list, ensure_ascii=False)
    total_time = session.get("quiz_time", 0)  # ★ 合計タイムを取得

    write_header = not os.path.exists(SCORE_FILE) or os.path.getsize(SCORE_FILE) == 0

    with open(SCORE_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["date", "correct", "total", "mode", "wrong_list", "time"])  # ★ time を追加

        writer.writerow([date, correct, total, mode, wrong_json, total_time])  # ★ time を追加



def load_scores():
    scores = []
    with open("score_history.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if row[0] == "date":
                continue
            wrong_words = json.loads(row[4]) if len(row) > 4 and row[4] else []
            scores.append({
                "date": row[0],
                "correct": row[1],
                "total": row[2],
                "mode": row[3],
                "wrong_words": wrong_words
            })
    return scores


@app.route("/")
def index():
    return render_template("index.html")

from flask import session
import random

from flask import session, redirect
import random


@app.route("/quiz")
def quiz():
    count = int(request.args.get("count", 5))

    # 初回アクセス → 問題セットを作る
    if "quiz_words" not in session:
        mode = request.args.get("range", "all")
        session["mode"] = mode

        # モード別のデータ読み込み
        if mode == "pre1":
            words = load_words("pre1")
        elif mode == "target1900":
            words = load_words("target1900")
        
        else:
            words = load_words()

        sampled = random.sample(words, count)
        session["quiz_words"] = [w["word"] for w in sampled]
        session["quiz_index"] = 0
        session["quiz_total"] = count

    # 辞書に戻す
    mode = session.get("mode", "all")

    if mode == "pre1":
        all_words = load_words("pre1")
    elif mode == "target1900":
        all_words = load_words("target1900")
   
    else:
        all_words = load_words()

    quiz_word_keys = session["quiz_words"]
    word_map = {w["word"]: w for w in all_words}
    quiz_words = [word_map[k] for k in quiz_word_keys]

    idx = session["quiz_index"]

    if idx >= len(quiz_words):
        return redirect("/result")

    q = quiz_words[idx]

    choices = make_choices(q, all_words)
    sec = session.get("quiz_time", 0)

    return render_template(
        "quiz.html",
        q=q,
        choices=choices,
        sec=sec,
        mode=mode,
        current=idx + 1,
        total=session["quiz_total"]
    )



@app.route("/idioms")
def idioms_page():
    idioms = load_idioms()
    return render_template("idioms.html", idioms=idioms)


@app.route("/idioms_quiz")
def idioms_quiz():
    idioms = load_idioms()
    q = random.choice(idioms)

    # 選択肢生成（高速版）
    pool = [i for i in idioms if i["meaning"] != q["meaning"]]
    random.shuffle(pool)
    choices = [
        {"meaning": q["meaning"]},
        {"meaning": pool[0]["meaning"]},
        {"meaning": pool[1]["meaning"]},
        {"meaning": pool[2]["meaning"]}
    ]
    random.shuffle(choices)

    return render_template("idioms_quiz.html", q=q, choices=choices)

@app.route("/idioms_answer", methods=["POST"])
def idioms_answer():
    correct = request.form.get("correct")
    answer = request.form.get("answer")

    if correct == answer:
        result = "正解！"
    else:
        result = "不正解！！"

    return render_template("idioms_result.html", result=result)


@app.route("/clear_session")
def clear_session():
    session.clear()
    return "Session cleared!"


@app.route("/answer", methods=["POST"])
def answer():

    time_spent = int(request.form.get("time", 0))
    session["quiz_time"] = time_spent


    word = request.form["word"]
    meaning = request.form["meaning"]
    user_answer = request.form["answer"]
    correct = request.form["correct"]
    mode = request.form.get("mode", "normal")


    # --- スコア用セッション初期化 ---
    if "correct_count" not in session:
        session["correct_count"] = 0
    if "wrong_count" not in session:
        session["wrong_count"] = 0
    if "wrong_list" not in session:
        session["wrong_list"] = []

    if "quiz_index" not in session or "quiz_words" not in session:
        return redirect("/quiz")

    # --- 正誤判定 ---
    is_correct = (user_answer == correct)

    if is_correct:
        session["correct_count"] += 1
    else:
        session["wrong_count"] += 1
        wrong_list = session.get("wrong_list", [])
        wrong_list.append({"word": word, "meaning": meaning})
        session["wrong_list"] = wrong_list

    update_wrong(word, meaning, is_correct)

    # --- SRS処理 ---
    srs = load_srs_data()
    if word not in srs:
        srs[word] = {"interval": 1, "next": today()}

    if is_correct:
        srs[word]["interval"] *= 2
    else:
        srs[word]["interval"] = 1

    srs[word]["next"] = today_plus(srs[word]["interval"])
    save_srs_data(srs)

    # ★★★ 復習モードなら次の復習へ ★★★
    if mode == "review":
        review_words = session.get("review_words", [])
        if review_words:
            review_words.pop(0)  # ← 今日の復習リストから削除
            session["review_words"] = review_words
        return redirect("/review")

    # --- 通常クイズモード ---
    session["quiz_index"] += 1

    if session["quiz_index"] >= session["quiz_total"]:
        save_score(
            session["correct_count"],
            session["quiz_total"],
            session.get("mode", "normal"),
            session["wrong_list"]
        )
        return redirect("/result")

    return redirect("/quiz")


    session["koten_words_all"] = koten_words[:]   # ← 全問題をコピーして保存
    session["koten_wrong"] = []
    session["koten_start_time"] = time.time()


@app.route("/koten_quiz")
def koten_quiz():
    session["mode"] = "koten"

    session["koten_start_time"] = time.time()


    koten = load_koten()



    # 初回アクセスなら10問セットを作る
    if "koten_words" not in session:
        sampled = random.sample(koten, 10)
        session["koten_words"] = sampled
        session["koten_index"] = 0

    idx = session["koten_index"]
    words = session["koten_words"]

    # 全部終わったら結果へ
    if idx >= len(words):
        return redirect("/koten_result")

    q = words[idx]

    # 選択肢生成
    correct = q["meaning"][0]
    pool = [w["meaning"][0] for w in koten if w["word"] != q["word"]]
    random.shuffle(pool)
    wrong = pool[:3]
    choices = [correct] + wrong
    random.shuffle(choices)

    return render_template("koten_quiz.html", q=q, choices=choices, current=idx+1, total=len(words))



@app.route("/koten_answer", methods=["POST"])
def koten_answer():
    correct = request.form.get("correct")
    chosen = request.form.get("chosen")

    # 初期化
    if "koten_wrong" not in session:
        session["koten_wrong"] = []

    # 間違えたら記録
    if correct != chosen:
        idx = session["koten_index"]
        q = session["koten_words"][idx]
        session["koten_wrong"].append(q)

    # 次の問題へ
    session["koten_index"] += 1

    # 10問終わったら結果へ
    if session["koten_index"] >= len(session["koten_words"]):
        return redirect("/koten_finish")

    return redirect("/koten_quiz")


@app.route("/koten_result")
def koten_result():
    idx = session.get("koten_index", 0)
    total = len(session.get("koten_words", []))
    

    # 全部終わったら終了画面
    if idx >= total:
        # セッション消す
        session.pop("koten_words", None)
        session.pop("koten_index", None)
        return "古典10問終了！"

    # まだ続くなら次へ
    return redirect("/koten_quiz")

import json
import csv
import time
from datetime import datetime

@app.route("/koten_finish")
def koten_finish():
    wrong = session.get("koten_wrong", [])


    # セッション消す
    session.pop("koten_words", None)
    session.pop("koten_index", None)

    # ★ 成績保存（古典）
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    correct = len(session.get("koten_words_all", [])) - len(wrong)
    total = len(session.get("koten_words_all", []))

    with open("score_history.csv", "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if "koten_start_time" in session:
            total_time = int(time.time() - session["koten_start_time"])
        else:
            total_time = 0

        wrong_json = json.dumps(wrong, ensure_ascii=False)
        writer.writerow([
            timestamp,
            correct,
            total,
            "koten",
            wrong_json,
            total_time
        ])

        wrong_list = session.get("koten_wrong", [])
        total = len(session.get("koten_words_all", []))
        correct = total - len(wrong_list)


    return render_template("koten_finish.html", wrong=wrong)


@app.route("/result")
def result():
    
    correct = session.get("correct_count", 0)
    wrong = session.get("wrong_count", 0)
    total = correct + wrong
    wrong_list = session.get("wrong_list", [])
    total_time = session.get("quiz_time", 0)  # ← ここで取得 OK

    accuracy = round((correct / total) * 100, 1) if total > 0 else 0

    # セッションリセット（タイムは消さない）
    for key in ["quiz_words", "quiz_index", "quiz_total", "correct_count", "wrong_count", "wrong_list"]:
        session.pop(key, None)

    return render_template(
        "result.html",
        correct=correct,
        wrong=wrong,
        total=total,
        accuracy=accuracy,
        wrong_list=wrong_list,
        total_time=total_time   # ← ★これが無いと Jinja が undefined になる
    )

@app.route("/review")
def review():
    # 今日の復習リストを初回だけ作る
    if "review_words" not in session:
        words = get_review_words()  # ← 蓮のSRSロジックそのまま使う
        if not words:
            return "今は復習すべき単語がありません！"
        session["review_words"] = words

    # 今日の復習リスト
    words = session["review_words"]

    # 全部終わったら終了
    if not words:
        session.pop("review_words", None)
        return "今日の復習は終わり！"

    # 最優先の1語を出す（蓮のロジックそのまま）
    q = words[0]

    # 選択肢は words.csv から（蓮のロジックそのまま）
    all_words = load_words()
    choices = random.sample(all_words, 3)
    choices.append(q)
    random.shuffle(choices)

    return render_template("quiz.html",
                           q=q,
                           choices=choices,
                           mode="review",
                           priority=q["priority"],
                           remaining=len(words),        # ← 追加
                           total=len(session["review_words"])  # ← 追加
)



@app.route("/admin_login")
def admin_login():
    return render_template("admin_login.html")


@app.route("/admin_auth", methods=["POST"])
def admin_auth():
    pw = request.form["pw"]

    ADMIN_PASSWORD = "鬱"  # ← 好きに変えてOK

    if pw == ADMIN_PASSWORD:
        session["is_admin"] = True
        return redirect("/admin")
    else:
        return "<h3>パスワードが違います</h3><a href='/admin_login'>戻る</a>"



@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect("/admin_login")
    return render_template("admin_dashboard.html")

import csv
import ast

@app.route("/score")
def score():
    scores = []

    with open("score_history.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:

            # 列数チェック（最低6列）
            if len(row) < 6:
                continue

            date = row[0]
            correct = int(row[1])
            total = int(row[2])
            mode = row[3]

            # wrong_list は JSON 文字列
            wrong_json = row[4]
            try:
                wrong_list = json.loads(wrong_json)
            except:
                wrong_list = []  # 壊れてる場合は空にする

            # total_time（秒）
            try:
                total_time = int(row[5])
            except:
                total_time = 0

            # 秒 → 分:秒
            m = total_time // 60
            s = total_time % 60
            time_str = f"{m:02d}:{s:02d}"

            scores.append({
                "date": date,
                "correct": correct,
                "total": total,
                "mode": mode,
                "wrong_list": wrong_list,
                "time": time_str
            })

    scores.reverse()
    return render_template("score.html", scores=scores)


@app.route("/stats")
def stats():
    total = 0
    correct = 0
    quiz_total = quiz_correct = 0
    review_total = review_correct = 0

    with open("score_history.csv", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            date, c, t, mode = line.split(",")
            c = int(c)
            t = int(t)

            total += t
            correct += c

            if mode == "quiz":
                quiz_total += t
                quiz_correct += c
            else:
                review_total += t
                review_correct += c

    return render_template("stats.html",
                           total=total, correct=correct,
                           quiz_total=quiz_total, quiz_correct=quiz_correct,
                           review_total=review_total, review_correct=review_correct)

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    return render_template("admin.html")



@app.route("/admin/wrong_list")
def wrong_list():
    wrong = load_wrong()
    return render_template("wrong_list.html", wrong=wrong)

@app.route("/admin/score_list")
def score_list():
    scores = []
    with open("score_history.csv", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            date, correct, total, mode = line.split(",")
            scores.append({
                "date": date,
                "correct": correct,
                "total": total,
                "mode": mode
            })

    scores.reverse()
    return render_template("admin_scores.html", scores=scores)

   

@app.route("/admin/words")
def admin_words():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    words = load_words()
    return render_template("admin_words.html", words=words)

@app.route("/admin/add", methods=["GET", "POST"])
def admin_add():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    if request.method == "POST":
        rng = request.form["range"]
        word = request.form["word"]
        meaning = request.form["meaning"]

        with open("words.csv", "a", encoding="utf-8") as f:
            f.write(f"{rng},{word},{meaning}\n")

        return redirect("/admin/words")

    return render_template("admin_add.html")

@app.route("/admin/delete", methods=["GET", "POST"])
def admin_delete():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    words = load_words()

    if request.method == "POST":
        target = request.form["word"]

        new_words = [w for w in words if w["word"] != target]

        with open("words.csv", "w", encoding="utf-8") as f:
            f.write("range,word,meaning\n")
            for w in new_words:
                f.write(f"{w['range']},{w['word']},{w['meaning']}\n")

        return redirect("/admin/words")

    return render_template("admin_delete.html", words=words)

from datetime import datetime

@app.route("/admin/scores")
def admin_scores():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    scores = []
    with open("score_history.csv", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split(",")
            if len(parts) != 4:
                # 壊れた行でも落とさず残す
                date = parts[0]
                correct = parts[1] if len(parts) > 1 else "?"
                total = parts[2] if len(parts) > 2 else "?"
                mode = parts[3] if len(parts) > 3 else ""
            else:
                date, correct, total, mode = parts

            scores.append({
                "date": date,
                "correct": correct,
                "total": total,
                "mode": mode
            })

    # ★ 日付で完全ソート（新しい順）
    def parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.min  # 壊れた日付は一番下へ

    scores.sort(key=lambda x: parse_date(x["date"]), reverse=True)

    return render_template("admin_scores.html", scores=scores)

    

@app.route("/admin/srs")
def admin_srs():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    srs = load_srs_data()
    return render_template("admin_srs.html", srs=srs)

@app.route("/admin/settings")
def admin_settings():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    return render_template("admin_settings.html")

@app.route("/add_myword", methods=["POST"])
def add_myword():
    word = request.form["word"]
    meaning = request.form["meaning"]

    # 重複チェック
    exists = False
    with open("my_words.csv", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith(word + ","):
                exists = True
                break

    if not exists:
        with open("my_words.csv", "a", encoding="utf-8") as f:
            f.write(f"{word},{meaning}\n")

    return redirect("/mywords")

@app.route("/mywords")
def mywords():
    words = []
    with open("my_words.csv", encoding="utf-8") as f:
        first = True
        for line in f:
            if first:
                first = False
                continue
            line = line.strip()
            if not line:
                continue
            word, meaning = line.split(",", 1)
            words.append({"word": word, "meaning": meaning})

    return render_template("mywords.html", words=words)


@app.route("/admin/mywords")
def admin_mywords():
    if not session.get("is_admin"):
        return redirect("/admin_login")

    words = []
    if os.path.exists("my_words.csv"):
        with open("my_words.csv", encoding="utf-8") as f:
            first = True
            for line in f:
                if first:
                    first = False
                    continue
                line = line.strip()
                if not line:
                    continue
                word, meaning = line.split(",", 1)
                words.append({"word": word, "meaning": meaning})

    return render_template("admin_mywords.html", words=words)

@app.route("/delete_myword", methods=["POST"])
def delete_myword():
    word = request.form["word"]

    lines = []
    with open("my_words.csv", encoding="utf-8") as f:
        for line in f:
            if not line.startswith(word + ","):
                lines.append(line)

    with open("my_words.csv", "w", encoding="utf-8") as f:
        f.writelines(lines)

    return "OK"


@app.route("/scores")
def scores():
    data = load_scores()
    return render_template("scores.html", scores=data)




@app.route("/admin/range_stats")
def range_stats():
    words = load_words()
    stats = {}

    for w in words:
        rng = w["range"]
        if rng not in stats:
            stats[rng] = 0
        stats[rng] += 1

    return render_template("range_stats.html", stats=stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)



