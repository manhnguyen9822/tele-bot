import pandas as pd
import unicodedata
import re
from difflib import SequenceMatcher
import string
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")
FILE = "file.xlsx"

# ===== NORMALIZE =====
def normalize(text):
    text = str(text).lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9 ]', '', text)
    return text

# ===== CLEAN HTML =====
def clean_html(text):
    return re.sub(r'<.*?>', '', str(text))

# ===== TẠO ABBR CHỈ TỪ 5-7 TỪ ĐẦU =====
def build_abbr(text):
    text = normalize(text)

    # 🔥 bỏ dấu phẩy (quan trọng)
    text = text.replace(",", " ")

    words = text.split()

    # chỉ lấy 5-7 từ đầu
    first_words = words[:7]

    abbr = ''.join(w[0] for w in first_words if w)

    return abbr

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
                    options[letters[idx]] = str(val)
                    idx += 1

        question = clean_html(row["Câu hỏi"])

        # ===== ĐÁP ÁN =====
        correct_raw = str(row["Đáp án đúng"]).strip()
        correct_list = []
        parts = re.split(r"[,\s;]+", correct_raw)

        for p in parts:
            if p.isdigit():
                i = int(p) - 1
                if 0 <= i < len(options):
                    correct_list.append(letters[i])
            else:
                correct_list.append(p.upper())

        item = {
            "question": question,
            "question_norm": normalize(question),
            "abbr": build_abbr(question),  # 🔥 chỉ 5-7 từ đầu
            "correct": correct_list,
            "options": options
        }

        data.append(item)

    print(f"✅ Loaded {len(data)} câu hỏi")
    return data

data = load_data()

# ===== SEARCH =====
def search(query):
    q = normalize(query).replace(" ", "")

    best = None
    best_score = 0

    # ===== MATCH ABBR =====
    for item in data:
        abbr = item["abbr"]

        score = SequenceMatcher(None, q, abbr).ratio()

        # 🔥 match đầu câu cực mạnh
        if abbr.startswith(q):
            score += 1.0

        if score > best_score:
            best_score = score
            best = item

    if best_score > 0.6:
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
        await update.message.reply_text("⚠️ Gõ 5-7 chữ cái đầu (vd: ksdht)")
        return

    await update.message.reply_text(format_msg(result))

# ===== RUN =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Thiếu TOKEN")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT, handle))

        print("🚀 Bot chạy tối ưu 5-7 từ đầu...")
        app.run_polling()
