import pandas as pd
import unicodedata
import re
from difflib import SequenceMatcher
import string
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ===== TOKEN =====
TOKEN = os.getenv("TOKEN")

# ===== FILE =====
FILE = "file.xlsx"

# ===== STOP WORDS =====
STOP_WORDS = {
    "la","va","cua","co","trong","cho","mot","cac","nhung",
    "duoc","the","nao","sau","day","voi","tu","den","khi",
    "neu","thi","do","nay","kia","gi","nhu"
}

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

# ===== BUILD MULTI ABBR =====
def build_abbrs(text):
    words = normalize(text).split()

    # full
    abbr_full = ''.join(w[0] for w in words if w)

    # bỏ stop words
    filtered = [w for w in words if w not in STOP_WORDS]
    abbr_filtered = ''.join(w[0] for w in filtered if w)

    # từ quan trọng (>=4 ký tự)
    keywords = [w for w in filtered if len(w) >= 4]
    if not keywords:
        keywords = filtered
    abbr_keywords = ''.join(w[0] for w in keywords if w)

    return {abbr_full, abbr_filtered, abbr_keywords}

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

        # ===== MULTI ANSWER =====
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
            "abbrs": build_abbrs(question),
            "correct": correct_list,
            "options": options
        }

        data.append(item)

    print(f"✅ Loaded {len(data)} câu hỏi")
    return data

data = load_data()

# ===== SEARCH =====
def search(query):
    raw = normalize(query)
    q = raw.replace(" ", "")
    words = raw.split()

    # 🔥 chỉ lấy phần đầu để match viết tắt (fix ksdht)
    q_short = q[:6]

    best = None
    best_score = 0

    # ===== 1. MATCH ABBR (CỰC QUAN TRỌNG) =====
    for item in data:
        for abbr in item["abbrs"]:
            score = SequenceMatcher(None, q_short, abbr).ratio()

            # match đầu câu (quan trọng nhất)
            if abbr.startswith(q_short):
                score += 0.7

            # match prefix chính xác
            if abbr[:len(q_short)] == q_short:
                score += 0.7

            # match chứa
            if q_short in abbr:
                score += 0.3

            if score > best_score:
                best_score = score
                best = item

    if best_score > 0.65:
        return best

    # ===== 2. CHẶN NGẮN =====
    if len(words) <= 2:
        return None

    # ===== 3. MATCH CÂU =====
    best = None
    best_score = 0

    for item in data:
        question = item["question_norm"]

        score = SequenceMatcher(None, raw, question).ratio() * 2

        match_count = sum(1 for w in words if w in question)
        score += (match_count / len(words)) * 2

        if score > best_score:
            best_score = score
            best = item

    if best_score > 0.7:
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
        await update.message.reply_text("⚠️ Nhập rõ hơn hoặc viết tắt (vd: cttt)")
        return

    await update.message.reply_text(format_msg(result))

# ===== RUN =====
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Thiếu TOKEN")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(MessageHandler(filters.TEXT, handle))

        print("🚀 Bot đang chạy...")
        app.run_polling()
