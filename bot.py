import os
import asyncio
import sqlite3

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "YOUR_USERNAME")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(TOKEN)
dp = Dispatcher()

# ---------- DATABASE ----------

db = sqlite3.connect("shop.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    product TEXT,
    amount INTEGER,
    status TEXT,
    payment_id TEXT
)
""")

db.commit()


# ---------- MENU ----------

def menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Telegram Premium",
                    callback_data="premium"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Stars",
                    callback_data="stars"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📦 Мои заказы",
                    callback_data="orders"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Поддержка",
                    callback_data="support"
                )
            ]
        ]
    )


# ---------- START ----------

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "⭐ STARSOV SHOP\n\n"
        "Добро пожаловать!\n\n"
        "Выберите раздел:",
        reply_markup=menu()
    )


# ---------- STARS ----------

@dp.callback_query(F.data == "stars")
async def stars(callback: CallbackQuery):

    await callback.message.edit_text(
        "⭐ TELEGRAM STARS\n\n"
        "Stars являются виртуальной валютой Telegram.\n\n"
        "Бот не может купить Stars у Telegram и "
        "перевести их другому пользователю через Bot API.\n\n"
        "Купить Stars можно непосредственно в Telegram.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# ---------- PREMIUM ----------

@dp.callback_query(F.data == "premium")
async def premium(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Premium 3 месяца",
                    callback_data="premium_3"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Premium 6 месяцев",
                    callback_data="premium_6"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Premium 12 месяцев",
                    callback_data="premium_12"
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="back"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "💎 TELEGRAM PREMIUM\n\n"
        "Выберите срок подписки:",
        reply_markup=keyboard
    )

    await callback.answer()


# Цены указаны в Stars только как пример.
# Перед реальными продажами проверь актуальные условия Telegram.

PRICES = {
    3: 1000,
    6: 1800,
    12: 3200,
}


@dp.callback_query(F.data.startswith("premium_"))
async def premium_invoice(callback: CallbackQuery):

    months = int(callback.data.split("_")[1])
    price = PRICES[months]

    prices = [
        LabeledPrice(
            label=f"Telegram Premium — {months} мес.",
            amount=price
        )
    ]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Telegram Premium — {months} месяцев",
        description=(
            f"Заказ Telegram Premium на {months} месяцев."
        ),
        payload=f"premium:{months}:{callback.from_user.id}",
        currency="XTR",
        prices=prices
    )

    await callback.answer()


# ---------- PAYMENT ----------

@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):

    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: Message):

    payment = message.successful_payment
    payload = payment.invoice_payload

    if not payload.startswith("premium:"):
        return

    parts = payload.split(":")
    months = int(parts[1])

    cur.execute(
        """
        INSERT INTO orders
        (user_id, username, product, amount, status, payment_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            message.from_user.id,
            message.from_user.username or "",
            f"Premium {months} месяцев",
            payment.total_amount,
            "PAID_WAITING_FULFILLMENT",
            payment.telegram_payment_charge_id
        )
    )

    db.commit()

    order_id = cur.lastrowid

    await message.answer(
        "✅ Оплата получена!\n\n"
        f"📦 Заказ №{order_id}\n"
        f"💎 Premium: {months} месяцев\n\n"
        "Заказ передан администратору для выполнения."
    )

    if ADMIN_ID:

        username = message.from_user.username or "нет username"

        await bot.send_message(
            ADMIN_ID,
            "💎 НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ\n\n"
            f"Заказ: #{order_id}\n"
            f"User ID: {message.from_user.id}\n"
            f"Username: @{username}\n"
            f"Premium: {months} месяцев\n"
            f"Оплачено: {payment.total_amount} ⭐\n\n"
            "Статус: PAID_WAITING_FULFILLMENT"
        )


# ---------- ORDERS ----------

@dp.callback_query(F.data == "orders")
async def orders(callback: CallbackQuery):

    cur.execute(
        """
        SELECT id, product, amount, status
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (callback.from_user.id,)
    )

    rows = cur.fetchall()

    if not rows:
        await callback.message.edit_text(
            "📦 У вас пока нет заказов.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="◀️ Назад",
                            callback_data="back"
                        )
                    ]
                ]
            )
        )
        await callback.answer()
        return

    text = "📦 МОИ ЗАКАЗЫ\n\n"

    for order_id, product, amount, status in rows:
        text += (
            f"№{order_id}\n"
            f"💎 {product}\n"
            f"⭐ {amount}\n"
            f"Статус: {status}\n\n"
        )

    await callback.message.edit_text(text)
    await callback.answer()


# ---------- SUPPORT ----------

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):

    await callback.message.edit_text(
        "💬 ПОДДЕРЖКА\n\n"
        f"Администратор: @{ADMIN_USERNAME}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="◀️ Назад",
                        callback_data="back"
                    )
                ]
            ]
        )
    )

    await callback.answer()


@dp.message(Command("paysupport"))
async def paysupport(message: Message):

    await message.answer(
        f"💬 Поддержка по оплате:\n"
        f"@{ADMIN_USERNAME}"
    )


# ---------- BACK ----------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    await callback.message.edit_text(
        "⭐ STARSOV SHOP\n\n"
        "Выберите раздел:",
        reply_markup=menu()
    )

    await callback.answer()


# ---------- RENDER HEALTH SERVER ----------

async def health(request):
    return web.Response(text="Bot is running!")


async def start_web_server():

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "10000"))

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port
    )

    await site.start()

    print(f"Web server started on port {port}")


# ---------- MAIN ----------

async def main():

    await start_web_server()

    print("Telegram bot started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
