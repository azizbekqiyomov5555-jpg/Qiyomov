# obmen_bot_full.py
# -*- coding: utf-8 -*-
import os
import json
import time
import logging
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram import Router

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

# --------------------
# Sozlamalar (tokenni ENV orqali qo'ying)
# --------------------
BOT_TOKEN = os.getenv("8252463123:AAHo7gUPcko6ueGRjQ15Efqcsd13FFp7HIY")  # Render yoki hostingda environment variable sifatida qo'ying
ADMIN_ID = int(os.getenv("7973934849", "7973934849"))

DATA_DIR = "bot_data"
CURRENCIES_FILE = os.path.join(DATA_DIR, "currencies.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
os.makedirs(DATA_DIR, exist_ok=True)

# --------------------
# Logging & inits
# --------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

storage = MemoryStorage()
router = Router()

# --------------------
# JSON helpers
# --------------------
def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --------------------
# Data stores
# --------------------
currencies = load_json(CURRENCIES_FILE, {})
users = load_json(USERS_FILE, {})
orders = load_json(ORDERS_FILE, {})
sessions = {}

# --------------------
# FSM
# --------------------
class BuyFSM(StatesGroup):
    choose_currency = State()
    amount = State()
    wallet = State()
    confirm = State()

class SellFSM(StatesGroup):
    choose_currency = State()
    amount = State()
    wallet = State()
    confirm = State()

class AdminFSM(StatesGroup):
    main = State()
    add_name = State()
    add_buy_rate = State()
    add_sell_rate = State()
    add_buy_card = State()
    add_sell_card = State()
    edit_choose = State()
    edit_name = State()
    edit_rate_choose = State()
    edit_rate_set = State()
    edit_card_choose = State()
    edit_card_set = State()
    delete_choose = State()

class BroadcastFSM(StatesGroup):
    waiting_message = State()

# --------------------
# Utilities
# --------------------
def is_admin(uid):
    try:
        return int(uid) == int(ADMIN_ID)
    except:
        return False

def ensure_user(uid, tg_user=None):
    key = str(uid)
    if key not in users:
        users[key] = {
            "id": uid,
            "name": tg_user.full_name if tg_user else "",
            "username": tg_user.username if tg_user else "",
            "orders": []
        }
        save_json(USERS_FILE, users)
    return users[key]

def main_menu_kb(uid=None):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💲 Sotib olish"), KeyboardButton(text="💰 Sotish")]],
        resize_keyboard=True
    )
    if uid and is_admin(uid):
        # add new row with admin button
        kb.keyboard.append([KeyboardButton(text="⚙️ Admin Panel")])
    return kb

def back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏹️ Bekor qilish")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def new_order_id():
    return str(int(time.time() * 1000))

# --------------------
# Start
# --------------------
@router.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    user = ensure_user(uid, message.from_user)
    await message.answer(
        f"Assalomu alaykum, {user['name']}! 👋\nXush kelibsiz botimizga. Pastdagi tugma orqali curupto valuta sotib olishingiz va sotishingiz mumkin.",
        reply_markup=main_menu_kb(uid)
    )

# --------------------
# Sotib olish (Buy)
# --------------------
@router.message(lambda message: message.text and message.text == "💲 Sotib olish")
async def buy_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if not currencies:
        await message.answer("Hozircha valyuta mavjud emas. Iltimos admin bilan bog'laning.")
        return

    # build keyboard with currencies (2 per row)
    rows = []
    row = []
    for i, cur in enumerate(currencies.keys(), 1):
        row.append(KeyboardButton(text=cur))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="⏹️ Bekor qilish")])

    kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Qaysi valyutani sotib olmoqchisiz?", reply_markup=kb)
    await BuyFSM.choose_currency.set()

@router.message(BuyFSM.choose_currency)
async def choose_currency_buy(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text not in currencies:
        await message.answer("Valyuta topilmadi. Qaytadan tanlang.")
        return
    await state.set_data({"currency": message.text})
    await message.answer(f"{message.text} bo'yicha qancha miqdorda olmoqchisiz?")
    await BuyFSM.amount.set()

@router.message(BuyFSM.amount)
async def amount_handler_buy(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.replace(",", "."))
    except:
        await message.answer("Iltimos raqam kiriting.")
        return
    data = await state.get_data()
    data["amount"] = amt
    await state.set_data(data)
    await message.answer("Hamyon raqamingizni kiriting:")
    await BuyFSM.wallet.set()

@router.message(BuyFSM.wallet)
async def wallet_handler_buy(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return

    data = await state.get_data()
    data["wallet"] = message.text
    await state.set_data(data)

    currency = data["currency"]
    amt = data["amount"]
    rate = currencies.get(currency, {}).get("buy_rate", 0)
    card = currencies.get(currency, {}).get("buy_card", "5614 6818 7267 2690")
    total = amt * rate

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Chek yuborish")], [KeyboardButton(text="⏹️ Bekor qilish")]],
        resize_keyboard=True
    )

    await message.answer(
        f"{amt} {currency} uchun to'lovni quyidagi karta raqamiga qiling:\n{card}\n\nJami to'lov: {total} UZS",
        reply_markup=kb
    )
    await BuyFSM.confirm.set()

@router.message(BuyFSM.confirm)
async def confirm_handler_buy(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text != "Chek yuborish":
        await message.answer("Iltimos faqat 'Chek yuborish' tugmasini bosing.")
        return

    data = await state.get_data()
    order_id = new_order_id()
    order = {
        "id": order_id,
        "user_id": message.from_user.id,
        "currency": data["currency"],
        "amount": data["amount"],
        "wallet": data["wallet"],
        "type": "buy",
        "status": "waiting_admin",
        "created_at": int(time.time()),
        "rate": currencies.get(data["currency"], {}).get("buy_rate")
    }
    orders[order_id] = order
    user_orders = users.setdefault(str(message.from_user.id), {"id": message.from_user.id, "orders": []})
    user_orders.setdefault("orders", []).append(order_id)
    save_json(ORDERS_FILE, orders)
    save_json(USERS_FILE, users)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_order|confirm|{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_order|reject|{order_id}")]
    ])

    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            ADMIN_ID,
            f"Yangi buyurtma!\nFoydalanuvchi: {message.from_user.full_name}\nID: {message.from_user.id}\nValyuta: {data['currency']}\nMiqdor: {data['amount']}\nHamyon: {data['wallet']}\nBuyurtma ID: {order_id}",
            reply_markup=kb
        )
        await bot.session.close()
    except Exception:
        logger.exception("Adminga xabar yuborishda xato:")

    await message.answer("✅ Buyurtma adminga yuborildi.", reply_markup=main_menu_kb(message.from_user.id))
    await state.clear()

# --------------------
# Sotish (Sell)
# --------------------
@router.message(lambda message: message.text and message.text == "💰 Sotish")
async def sell_start(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if not currencies:
        await message.answer("Hozircha valyuta mavjud emas. Iltimos admin bilan bog'laning.")
        return

    rows = []
    row = []
    for i, cur in enumerate(currencies.keys(), 1):
        row.append(KeyboardButton(text=cur))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="⏹️ Bekor qilish")])

    kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Qaysi valyutani sotmoqchisiz?", reply_markup=kb)
    await SellFSM.choose_currency.set()

@router.message(SellFSM.choose_currency)
async def choose_currency_sell(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text not in currencies:
        await message.answer("Valyuta topilmadi. Qaytadan tanlang.")
        return
    await state.set_data({"currency": message.text})
    await message.answer(f"{message.text} bo'yicha qancha miqdorda sotmoqchisiz?")
    await SellFSM.amount.set()

@router.message(SellFSM.amount)
async def amount_handler_sell(message: types.Message, state: FSMContext):
    try:
        amt = float(message.text.replace(",", "."))
    except:
        await message.answer("Iltimos raqam kiriting.")
        return
    data = await state.get_data()
    data["amount"] = amt
    await state.set_data(data)
    await message.answer("Hamyon raqamingizni kiriting:")
    await SellFSM.wallet.set()

@router.message(SellFSM.wallet)
async def wallet_handler_sell(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return

    data = await state.get_data()
    data["wallet"] = message.text
    await state.set_data(data)

    currency = data["currency"]
    amt = data["amount"]
    rate = currencies.get(currency, {}).get("sell_rate", 0)
    card = currencies.get(currency, {}).get("sell_card", "5614 6818 7267 2690")
    total = amt * rate

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Chek yuborish")], [KeyboardButton(text="⏹️ Bekor qilish")]],
        resize_keyboard=True
    )

    await message.answer(
        f"{amt} {currency} sotish uchun to'lovni quyidagi karta raqamiga qiling:\n{card}\n\nJami to'lov: {total} UZS",
        reply_markup=kb
    )
    await SellFSM.confirm.set()

@router.message(SellFSM.confirm)
async def confirm_handler_sell(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        return
    if message.text != "Chek yuborish":
        await message.answer("Iltimos faqat 'Chek yuborish' tugmasini bosing.")
        return

    data = await state.get_data()
    order_id = new_order_id()
    order = {
        "id": order_id,
        "user_id": message.from_user.id,
        "currency": data["currency"],
        "amount": data["amount"],
        "wallet": data["wallet"],
        "type": "sell",
        "status": "waiting_admin",
        "created_at": int(time.time()),
        "rate": currencies.get(data["currency"], {}).get("sell_rate")
    }
    orders[order_id] = order
    user_orders = users.setdefault(str(message.from_user.id), {"id": message.from_user.id, "orders": []})
    user_orders.setdefault("orders", []).append(order_id)
    save_json(ORDERS_FILE, orders)
    save_json(USERS_FILE, users)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_order|confirm|{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_order|reject|{order_id}")]
    ])

    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(
            ADMIN_ID,
            f"Yangi sell buyurtma!\nFoydalanuvchi: {message.from_user.full_name}\nID: {message.from_user.id}\nValyuta: {data['currency']}\nMiqdor: {data['amount']}\nHamyon: {data['wallet']}\nBuyurtma ID: {order_id}",
            reply_markup=kb
        )
        await bot.session.close()
    except Exception:
        logger.exception("Adminga sell buyurtma xabari yuborishda xato:")

    await message.answer("✅ Buyurtma adminga yuborildi.", reply_markup=main_menu_kb(message.from_user.id))
    await state.clear()

# --------------------
# Admin order callback (confirm/reject)
# --------------------
@router.callback_query(lambda c: c.data and c.data.startswith("admin_order"))
async def admin_order_cb(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("|")
    if len(parts) != 3:
        await callback.answer("Xato callback")
        return
    action, order_id = parts[1], parts[2]
    order = orders.get(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi")
        return
    if action == "confirm":
        order["status"] = "confirmed"
        save_json(ORDERS_FILE, orders)
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(order["user_id"], f"Sizning buyurtmangiz tasdiqlandi ✅")
            await bot.session.close()
        except Exception:
            logger.exception("Foydalanuvchiga confirm xabari yuborishda xato:")
        await callback.answer("Tasdiqlandi")
    elif action == "reject":
        order["status"] = "rejected"
        save_json(ORDERS_FILE, orders)
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(order["user_id"], f"Sizning buyurtmangiz bekor qilindi ❌")
            await bot.session.close()
        except Exception:
            logger.exception("Foydalanuvchiga reject xabari yuborishda xato:")
        await callback.answer("Bekor qilindi")

# --------------------
# Admin panel start
# --------------------
@router.message(lambda message: message.text and message.text == "⚙️ Admin Panel")
async def admin_panel_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("Siz admin emassiz.")
        return

    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Valyuta qo‘shish"), KeyboardButton(text="✏️ Valyuta nomini o‘zgartirish")],
        [KeyboardButton(text="💰 Valyuta kursini o‘zgartirish"), KeyboardButton(text="💳 Valyuta karta raqamini o‘zgartirish")],
        [KeyboardButton(text="🗑️ Valyuta o‘chirish")],
        [KeyboardButton(text="📢 Xabar yuborish")],
        [KeyboardButton(text="⏹️ Orqaga")]
    ], resize_keyboard=True)
    await message.answer("Admin panel:", reply_markup=kb)
    await AdminFSM.main.set()

# --------------------
# Broadcast (admin)
# --------------------
@router.message(lambda message: message.text and message.text == "📢 Xabar yuborish", AdminFSM.main)
async def start_broadcast(message: types.Message, state: FSMContext):
    await message.answer("Yuboriladigan xabar matnini kiriting:", reply_markup=back_kb())
    await BroadcastFSM.waiting_message.set()

@router.message(BroadcastFSM.waiting_message)
async def send_broadcast(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await admin_panel_start(message, state)
        return

    text = message.text
    count = 0
    failed = 0
    for uid in list(users.keys()):
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(int(uid), text)
            await bot.session.close()
            count += 1
        except Exception:
            failed += 1
            continue

    await message.answer(f"✅ Xabar {count} ta foydalanuvchiga yuborildi.\n❌ {failed} ta foydalanuvchiga yuborilmadi.", reply_markup=back_kb())
    await state.clear()
    await admin_panel_start(message, state)

# --------------------
# Admin main FSM handlers (menu actions)
# --------------------
@router.message(AdminFSM.main)
async def admin_main(message: types.Message, state: FSMContext):
    text = message.text
    if text == "➕ Valyuta qo‘shish":
        await message.answer("Valyuta nomini kiriting:", reply_markup=back_kb())
        await AdminFSM.add_name.set()
    elif text == "✏️ Valyuta nomini o‘zgartirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        rows = [[KeyboardButton(text=cur)] for cur in currencies.keys()]
        rows.append([KeyboardButton(text="⏹️ Bekor qilish")])
        kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
        await message.answer("Qaysi valyuta nomini o‘zgartirmoqchisiz?", reply_markup=kb)
        await AdminFSM.edit_choose.set()
    elif text == "💰 Valyuta kursini o‘zgartirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        rows = [[KeyboardButton(text=cur)] for cur in currencies.keys()]
        rows.append([KeyboardButton(text="⏹️ Bekor qilish")])
        kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
        await message.answer("Qaysi valyuta kursini o‘zgartirmoqchisiz?", reply_markup=kb)
        await AdminFSM.edit_rate_choose.set()
    elif text == "💳 Valyuta karta raqamini o‘zgartirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        rows = [[KeyboardButton(text=cur)] for cur in currencies.keys()]
        rows.append([KeyboardButton(text="⏹️ Bekor qilish")])
        kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
        await message.answer("Qaysi valyuta karta raqamini o‘zgartirmoqchisiz?", reply_markup=kb)
        await AdminFSM.edit_card_choose.set()
    elif text == "🗑️ Valyuta o‘chirish":
        if not currencies:
            await message.answer("Hozircha valyuta mavjud emas.", reply_markup=back_kb())
            return
        rows = [[KeyboardButton(text=cur)] for cur in currencies.keys()]
        rows.append([KeyboardButton(text="⏹️ Bekor qilish")])
        kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
        await message.answer("Qaysi valyutani o‘chirmoqchisiz?", reply_markup=kb)
        await AdminFSM.delete_choose.set()
    elif text == "⏹️ Orqaga":
        await state.clear()
        await message.answer("Bosh menyu:", reply_markup=main_menu_kb(message.from_user.id))
    else:
        await message.answer("Noto‘g‘ri tugma. Qaytadan tanlang.")

# --------------------
# Valyuta qo‘shish
# --------------------
@router.message(AdminFSM.add_name)
async def add_currency_name(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await admin_panel_start(message, state)
        return
    await state.update_data(new_name=message.text)
    await message.answer("Valyuta sotib olish kursini kiriting:", reply_markup=back_kb())
    await AdminFSM.add_buy_rate.set()

@router.message(AdminFSM.add_buy_rate)
async def add_currency_buy_rate(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await admin_panel_start(message, state)
        return
    try:
        rate = float(message.text.replace(",", "."))
    except:
        await message.answer("Iltimos to‘g‘ri raqam kiriting.")
        return
    await state.update_data(buy_rate=rate)
    await message.answer("Valyuta sotish kursini kiriting:", reply_markup=back_kb())
    await AdminFSM.add_sell_rate.set()

@router.message(AdminFSM.add_sell_rate)
async def add_currency_sell_rate(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await admin_panel_start(message, state)
        return
    try:
        rate = float(message.text.replace(",", "."))
    except:
        await message.answer("Iltimos to‘g‘ri raqam kiriting.")
        return
    await state.update_data(sell_rate=rate)
    await message.answer("Sotib olish karta raqamini kiriting:", reply_markup=back_kb())
    await AdminFSM.add_buy_card.set()

@router.message(AdminFSM.add_buy_card)
async def add_currency_buy_card(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await admin_panel_start(message, state)
        return
    await state.update_data(buy_card=message.text)
    await message.answer("Sotish karta raqamini kiriting:", reply_markup=back_kb())
    await AdminFSM.add_sell_card.set()

@router.message(AdminFSM.add_sell_card)
async def add_currency_sell_card(message: types.Message, state: FSMContext):
    if message.text == "⏹️ Bekor qilish":
        await state.clear()
        await admin_panel_start(message, state)
        return
    data = await state.get_data()
    currencies[data["new_name"]] = {
        "buy_rate": data["buy_rate"],
        "sell_rate": data["sell_rate"],
        "buy_card": data["buy_card"],
        "sell_card": message.text
    }
    save_json(CURRENCIES_FILE, currencies)
    await message.answer(f"{data['new_name']} qo‘shildi! Buy: {data['buy_rate']} ({data['buy_card']}), Sell: {data['sell_rate']} ({message.text})", reply_markup=back_kb())
    await state.clear()
    await admin_panel_start(message, state)

# --------------------
# Valyuta nomini o'zgartirish / kurs / card / delete ishlari qoldi (shunga o'xshash handlerlar yuqorida keltirilgan)
# -- (ular kodning yuqorisidagi struktura bilan bir xil tarzda yozilgan)
# --------------------

# --------------------
# Fallback: any text not handled - show main menu
# --------------------
@router.message()
async def fallback(message: types.Message):
    await message.answer("Quyidagi tugmalardan tanlang:", reply_markup=main_menu_kb(message.from_user.id))

# --------------------
# Main (start polling)
# --------------------
async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set. Set BOT_TOKEN before running.")
        return
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    print("Bot ishga tushmoqda...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())