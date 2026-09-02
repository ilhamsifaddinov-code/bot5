import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
import database as db

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]
CLINIC_NAME = os.getenv("CLINIC_NAME", "Shıpa Nur Klinika")
CLINIC_PHONE = os.getenv("CLINIC_PHONE", "+998 91 234 56 78")
CLINIC_ADDRESS = os.getenv("CLINIC_ADDRESS", "Nókis qalası, A. Dosnazarov kóshesi, 18-jay")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation Basqıshları
SELECT_DEPT, SELECT_DOCTOR, ENTER_PATIENT, SELECT_DATE, SELECT_TIME, ENTER_PHONE = range(6)

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🩺 Shıpakerler", "📅 Shıpakerge jazılıw"],
        ["📋 Meniń jazılıwlarım", "📍 Klinika maǵlıwmatları"]
    ], resize_keyboard=True)

# /start
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    text = (
        f"Assalawma áleykum, <b>{name}</b>! 🏥✨\n\n"
        f"<b>«{CLINIC_NAME}»</b> klinikasınıń qabıllawǵa jazılıw botına xosh kelipsiz!\n\n"
        f"Bul jerde siz qániyge shıpakerlerimiz benen tanısıp, náwbetsiz qabıllawǵa jazıla alasız."
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode="HTML")

# Shıpakerler dizimi
async def doctors_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db.get_connection()
    docs = conn.execute("""
        SELECT d.name, d.experience, d.price, dep.name as dep_name 
        FROM doctors d 
        JOIN departments dep ON d.department_id = dep.id
    """).fetchall()
    conn.close()

    text = "👩‍⚕️ <b>Klinikamız shıpakerleri:</b>\n\n"
    for doc in docs:
        text += (
            f"🔹 <b>{doc['name']}</b>\n"
            f"   🩺 Qániygeligi: <i>{doc['dep_name']}</i>\n"
            f"   ⭐ Tájiriybesi: {doc['experience']}\n"
            f"   💰 Qabıllaw bahası: <b>{doc['price']:,.0f} so'm</b>\n\n"
        )
    keyboard = [[InlineKeyboardButton("📅 Qabıllawǵa jazılıw", callback_data="start_med_booking")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# Baylanıs
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📍 <b>«{CLINIC_NAME}» Baylanıs maǵlıwmatları:</b>\n\n"
        f"🏢 <b>Mánzil:</b> {CLINIC_ADDRESS}\n"
        f"☎️ <b>Telefon:</b> {CLINIC_PHONE}\n"
        f"⏰ <b>Qabıllaw waqtı:</b> 08:30 - 18:00 (Dúyshembi - Shembi)\n"
        f"🚑 Tez medicinalıq járdem xızmeti bar."
    )
    await update.message.reply_text(text, parse_mode="HTML")

# Meniń jazılıwlarım
async def my_appointments_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    apps = db.get_user_appointments(update.effective_user.id)
    if not apps:
        await update.message.reply_text("Sizde házirshe aktiv jazılıwlar joq. 🩺")
        return

    text = "📋 <b>Siziń aktiv jazılıwlarıńız:</b>\n\n"
    keyboard = []
    for a in apps:
        text += (
            f"🆔 <b>Jazılıw #{a['id']}</b>\n"
            f"👤 Nawqas: <b>{a['patient_name']}</b>\n"
            f"👩‍⚕️ Shıpaker: <b>{a['doctor_name']}</b> ({a['specialty']})\n"
            f"📅 Waqıt: <b>{a['app_date']} saat {a['app_time']}</b>\n"
            f"💰 Bahası: <b>{a['price']:,.0f} so'm</b>\n\n"
        )
        keyboard.append([InlineKeyboardButton(f"❌ #{a['id']} Biykar etiw", callback_data=f"cancel_app_{a['id']}")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def cancel_app_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    app_id = int(query.data.split("_")[2])
    db.cancel_appointment(app_id)
    await query.edit_message_text(f"✅ <b>Jazılıw #{app_id} biykar etildi!</b>", parse_mode="HTML")

# ==================== JAZÍLÍW (CONVERSATION) ====================

async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        msg = update.callback_query.message
    else:
        msg = update.message

    conn = db.get_connection()
    deps = conn.execute("SELECT * FROM departments").fetchall()
    conn.close()

    keyboard = [[InlineKeyboardButton(f"{d['name']}", callback_data=f"dep_{d['id']}")] for d in deps]
    keyboard.append([InlineKeyboardButton("🔙 Biykar etiw", callback_data="cancel_conv")])

    await msg.reply_text("1️⃣ <b>Kerekli medicinalıq bólimdi tańlań:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return SELECT_DEPT

async def dept_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dep_id = int(query.data.split("_")[1])

    conn = db.get_connection()
    dep = conn.execute("SELECT name FROM departments WHERE id = ?", (dep_id,)).fetchone()
    docs = conn.execute("SELECT * FROM doctors WHERE department_id = ?", (dep_id,)).fetchall()
    conn.close()

    context.user_data["specialty"] = dep["name"]

    keyboard = [[InlineKeyboardButton(f"👩‍⚕️ {doc['name']} ({doc['price']:,.0f} s.)", callback_data=f"doc_{doc['id']}")] for doc in docs]
    keyboard.append([InlineKeyboardButton("🔙 Biykar etiw", callback_data="cancel_conv")])

    await query.edit_message_text(f"Bólim: <b>{dep['name']}</b>\n\n2️⃣ <b>Shıpakerdi tańlań:</b>",
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return SELECT_DOCTOR

async def doctor_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    doc_id = int(query.data.split("_")[1])

    conn = db.get_connection()
    doc = conn.execute("SELECT * FROM doctors WHERE id = ?", (doc_id,)).fetchone()
    conn.close()

    context.user_data["doctor_id"] = doc["id"]
    context.user_data["doctor_name"] = doc["name"]
    context.user_data["price"] = doc["price"]

    await query.edit_message_text(
        f"Shıpaker: <b>{doc['name']}</b>\n\n"
        f"3️⃣ <b>Nawqastıń atı-familiyasın kirgiziń:</b>\n"
        f"<i>(Mısalı: Marat Allanazarov)</i>",
        parse_mode="HTML"
    )
    return ENTER_PATIENT

async def patient_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["patient_name"] = update.message.text.strip()

    keyboard = []
    today = datetime.now()
    for i in range(5):
        day = today + timedelta(days=i)
        d_str = day.strftime("%Y-%m-%d")
        disp = day.strftime("%d.%m.%Y")
        if i == 0: disp += " (Búgin)"
        elif i == 1: disp += " (Erteń)"
        keyboard.append([InlineKeyboardButton(f"📅 {disp}", callback_data=f"date_{d_str}")])
    keyboard.append([InlineKeyboardButton("🔙 Biykar etiw", callback_data="cancel_conv")])

    await update.message.reply_text("4️⃣ <b>Qabıllaw kúnin tańlań:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return SELECT_DATE

async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_")[1]
    context.user_data["app_date"] = date_str
    doc_id = context.user_data["doctor_id"]

    slots = db.get_available_doctor_slots(doc_id, date_str)
    if not slots:
        await query.edit_message_text("Keshirersiz, bul kúnge shıpakerdiń barlıq qabıllaw waqıtları bánt! 😔")
        return ConversationHandler.END

    keyboard = []
    row = []
    for slot in slots:
        row.append(InlineKeyboardButton(f"⏰ {slot}", callback_data=f"time_{slot}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Biykar etiw", callback_data="cancel_conv")])

    await query.edit_message_text(f"Sáne: <b>{date_str}</b>\n\n5️⃣ <b>Bos waqıttı tańlań:</b>",
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    return SELECT_TIME

async def time_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["app_time"] = query.data.split("_")[1]

    await query.edit_message_text("6️⃣ <b>Baylanıs ushın telefon nomerińizdi jiberiń:</b>\n<i>(Mısalı: +998912345678)</i>", parse_mode="HTML")
    return ENTER_PHONE

async def phone_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    user = update.effective_user

    app_id = db.create_appointment(
        user_id=user.id,
        user_name=user.full_name,
        phone=phone,
        patient_name=context.user_data["patient_name"],
        doctor_id=context.user_data["doctor_id"],
        doctor_name=context.user_data["doctor_name"],
        specialty=context.user_data["specialty"],
        price=context.user_data["price"],
        date_str=context.user_data["app_date"],
        time_str=context.user_data["app_time"]
    )

    text = (
        f"🎉 <b>Qabıllawǵa jazılıw tastıyıqlandı! (Jazılıw #{app_id})</b>\n\n"
        f"👤 Nawqas: <b>{context.user_data['patient_name']}</b>\n"
        f"👩‍⚕️ Shıpaker: <b>{context.user_data['doctor_name']}</b> ({context.user_data['specialty']})\n"
        f"💰 Konsultatsiya bahası: <b>{context.user_data['price']:,.0f} so'm</b>\n"
        f"📅 Sánesi: <b>{context.user_data['app_date']}</b> saat <b>{context.user_data['app_time']}</b>\n\n"
        f"Klinikaǵa 10 minut aldın keliwińizdi soraymız! ✨"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode="HTML")

    # Adminge xabar
    admin_msg = (
        f"🔔 <b>JAŃA SHÍPAKERGE JAZÍLÍW! (#{app_id})</b>\n\n"
        f"👤 Nawqas: <b>{context.user_data['patient_name']}</b>\n"
        f"📱 Tel: <b>{phone}</b>\n"
        f"👩‍⚕️ Shıpaker: <b>{context.user_data['doctor_name']}</b>\n"
        f"📅 Waqıt: <b>{context.user_data['app_date']} | {context.user_data['app_time']}</b>"
    )
    for adm in ADMIN_IDS:
        try: await context.bot.send_message(chat_id=adm, text=admin_msg, parse_mode="HTML")
        except Exception: pass

    return ConversationHandler.END

async def cancel_conv_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Jazılıw biykar etildi.")
    return ConversationHandler.END

# ==================== ADMIN PANEL ====================
async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Ruxsat joq!")
        return

    keyboard = [
        [InlineKeyboardButton("📋 Aktiv Qabıllawlar", callback_data="adm_apps")],
        [InlineKeyboardButton("📊 Klinika Statistikası", callback_data="adm_stats")]
    ]
    await update.message.reply_text("👑 <b>Klinika Admin Paneli:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS: return

    if query.data == "adm_apps":
        apps = db.get_all_active_appointments()
        if not apps:
            await query.edit_message_text("📭 Házirshe aktiv qabıllawlar joq.")
            return

        text = "📋 <b>Aktiv jazılıwlar dizimi:</b>\n\n"
        for a in apps:
            text += (
                f"🆔 <b>#{a['id']}</b> | 📅 {a['app_date']} {a['app_time']}\n"
                f"👤 Nawqas: <b>{a['patient_name']}</b> ({a['phone']})\n"
                f"👩‍⚕️ Shıpaker: {a['doctor_name']} ({a['specialty']})\n\n"
            )
        await query.edit_message_text(text, parse_mode="HTML")

    elif query.data == "adm_stats":
        st = db.get_clinic_stats()
        text = (
            f"📊 <b>Klinika Statistikası:</b>\n\n"
            f"📌 Jámi jazılıwlar: <b>{st['total']}</b>\n"
            f"✅ Aktiv jazılıwlar: <b>{st['active']}</b>\n"
            f"💰 Kútilip atırǵan túsim: <b>{st['revenue']:,.0f} so'm</b>"
        )
        await query.edit_message_text(text, parse_mode="HTML")

def main():
    if not BOT_TOKEN:
        print("❌ .env faylında BOT_TOKEN joq!")
        return

    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Appointment Conversation
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^📅 Shıpakerge jazılıw$"), start_booking),
            CallbackQueryHandler(start_booking, pattern=r"^start_med_booking$")
        ],
        states={
            SELECT_DEPT: [CallbackQueryHandler(dept_selected, pattern=r"^dep_")],
            SELECT_DOCTOR: [CallbackQueryHandler(doctor_selected, pattern=r"^doc_")],
            ENTER_PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, patient_entered)],
            SELECT_DATE: [CallbackQueryHandler(date_selected, pattern=r"^date_")],
            SELECT_TIME: [CallbackQueryHandler(time_selected, pattern=r"^time_")],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_entered)],
        },
        fallbacks=[CallbackQueryHandler(cancel_conv_cb, pattern=r"^cancel_conv$")]
    )

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("admin", admin_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^🩺 Shıpakerler$"), doctors_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^📍 Klinika maǵlıwmatları$"), contact_handler))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 Meniń jazılıwlarım$"), my_appointments_handler))
    app.add_handler(CallbackQueryHandler(cancel_app_callback, pattern=r"^cancel_app_"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern=r"^adm_"))
    app.add_handler(conv)

    print("🚀 Shıpakerge Jazılıw Botı tabıslı iske tústi!")
    app.run_polling()

if __name__ == "__main__":
    main()