import pandas as pd
import unicodedata
import re
from difflib import SequenceMatcher
import string
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ===== TOKEN (ENV) =====
TOKEN = os.getenv("TOKEN")

# ===== FILE EXCEL =====
FILE = "file.xlsx"

# ===== CHUẨN HÓA TEXT =====
def normalize(text):
    text = str(text).lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9 ]', '', text)
    return text

# ===== XÓA HTML =====
def clean_html(text):
    return re.sub(r'<.*?>', '', str(text))

# ===== LOAD DATA =====
def load_data():
    if not os.path.exists(FILE):
        print("❌ Không tìm thấy file.xlsx")
        return []

    df = pd.read_excel(FILE)
    data = []
    letters = list(string.ascii_uppercase)

    for _, row in df.iterrows():
        options = {}
        idx = 0

        for col in df.columns:
            if "Đáp án" in col and col != "Đáp án đúng":
                val = row[col]
                if pd.notna(val):
                    letter = letters[idx]
                    options[letter] = str(val)
                    idx += 1

        question = clean_html(row["Câu hỏi"])

        correct_raw = str(row["Đáp án đúng"]).strip()
        correct_list = []
        parts = re.split(r"[,\s;]+", correct_raw)

        for p in parts:
            if p.isdigit():
                index = int(p) - 1
                if 0 <= index < len(options):
                    correct_list.append(letters[index])
            else:
                correct_list.append(p.upper())

        item = {
            "keyword": normalize(row.get("keyword", "")),
            "question": question,
            "question_norm": normalize(question),
            "correct": correct_list,
            "options": options
        }

        data.append(item)

    print(f"✅ Loaded {len(data)} câu hỏi")
    return data

data = load_data()

# ===== SIMILARITY =====
def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

# ===== SEARCH =====
def search(query):
    query_norm = normalize(query)
    words = query_norm.split()

    if len(words) <= 2:
        return None

    best = None
    best_score = 0

    for item in data:
        score = 0

        if item["keyword"] and query_norm == item["keyword"]:
            return item

        score += similarity(query_norm, item["question_norm"]) * 2

        match_count = sum(1 for w in words if w in item["question_norm"])
        if words:
            score += (match_count / len(words)) * 1.5

        if any(w in item["question_norm"] for w in words[:2]):
            score += 0.3

        if len(words) <= 3:
            score *= 0.7

        if score > best_score:
            best_score = score
            best = item

    if best_score > 0.65:
        return best

    return None

# ===== FORMAT =====
def format_msg(item):
    msg = f"📌 {item['question']}\n\n"

    correct_set = set(item["correct"])

    for k, v in item["options"].items():
        if k in correct_set:
            msg += f"👉 ✅ {k}. {v}  (ĐÁP ÁN)\n"
        else:
            msg += f"{k}. {v}\n"

    return msg

# ===== HANDLE =====
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    result = search(text)

    if result is None:
        if len(text.split()) <= 2:
            await update.message.reply_text("⚠️ Nhập rõ hơn (ít nhất 3-4 từ)")
        else:
            await update.message.reply_text("❌ Không tìm thấy câu phù hợp")
        return

    msg = format_msg(result)

    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000])
    else:
        await update.message.reply_text(msg)

# ===== RUN =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Thiếu TOKEN (set trong Railway Variables)")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT, handle))

        print("🚀 Bot đang chạy 24/24...")
        app.run_polling()
