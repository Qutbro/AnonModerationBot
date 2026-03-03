import json
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os

# Константы
BOT_TOKEN = ""
CHANNEL_ID = -123#id канала
ADMIN_IDS = []  # Здесь список ID всех админов
SEND_BD_FILE = 'send.bd'
BLOCK_FILE = 'block.bd'
MUTE_FILE = 'mut.bd'

pending_messages = {}
SUPER_ADMINS = []  # сюда список ID старших админов


BOT_LINK_USERNAME = ''  # <-- Сюда вставь ссылку на своего бота
import re


def escape_markdown(text: str) -> str:
    """Экранирует специальные символы для корректной отправки текста в формате Markdown V2."""
    escape_chars = r'_*[`'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


def load_send_bd():
    if not os.path.exists(SEND_BD_FILE):
        return {}
    with open(SEND_BD_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_sendbd():
    try:
        with open('send.bd', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_sendbd(data):
    with open('send.bd', 'w') as f:
        json.dump(data, f, indent=4)


# Загрузка данных
def load_blocklist():
    try:
        with open(BLOCK_FILE, 'r') as f:
            return json.load(f)
    except:
        return []


def load_mutelist():
    try:
        with open(MUTE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_blocklist(blocklist):
    with open(BLOCK_FILE, 'w') as f:
        json.dump(blocklist, f)


def save_mutelist(mutelist):
    with open(MUTE_FILE, 'w') as f:
        json.dump(mutelist, f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Загружаем всех пользователей из id.bd
    if os.path.exists('id.bd'):
        with open('id.bd', 'r') as f:
            user_ids = f.read().splitlines()
    else:
        user_ids = []

    # Проверяем, есть ли уже этот пользователь
    if str(user_id) not in user_ids:
        user_ids.append(str(user_id))
        with open('id.bd', 'w') as f:
            f.write('\n'.join(user_ids))

    await update.message.reply_text(
        'Привет! Отправь мне сообщение, фото, видео, кружек и я отправлю его на модерацию 🚀')


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Возникли проблемы напиши нам мы постаремся их решить: ')


async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Проверка блокировки
    blocklist = load_blocklist()
    if user_id in blocklist:
        return

    # Проверка мута
    mutelist = load_mutelist()
    if str(user_id) in mutelist:
        mute_end = mutelist[str(user_id)]
        if time.time() < mute_end:
            await update.message.reply_text('Вы временно замучены. Пожалуйста, подождите немного.')
            return
        else:
            mutelist.pop(str(user_id))
            save_mutelist(mutelist)

    # Генерируем уникальный ID сообщения
    message_id = update.message.message_id
    pending_messages[str(message_id)] = {
        'user_id': user_id,
        'admin_messages': {},
        'content_type': None,
        'content_data': None,
        'caption': update.message.caption if update.message.caption else ''
    }
    # Сразу после заполнения pending_messages[str(message_id)]:

    # Сохраняем что именно прислал пользователь
    if update.message.text:
        pending_messages[str(message_id)]['content_type'] = 'text'
        pending_messages[str(message_id)]['content_data'] = update.message.text

    elif update.message.photo:
        pending_messages[str(message_id)]['content_type'] = 'photo'
        pending_messages[str(message_id)]['content_data'] = update.message.photo[-1].file_id

    elif update.message.document:
        pending_messages[str(message_id)]['content_type'] = 'document'
        pending_messages[str(message_id)]['content_data'] = update.message.document.file_id

    elif update.message.video:
        pending_messages[str(message_id)]['content_type'] = 'video'
        pending_messages[str(message_id)]['content_data'] = update.message.video.file_id

    elif update.message.voice:
        pending_messages[str(message_id)]['content_type'] = 'voice'
        pending_messages[str(message_id)]['content_data'] = update.message.voice.file_id

    elif update.message.video_note:
        pending_messages[str(message_id)]['content_type'] = 'video_note'
        pending_messages[str(message_id)]['content_data'] = update.message.video_note.file_id

    else:
        await update.message.reply_text('Тип сообщения не поддерживается.')
        return
    content_type = pending_messages[str(message_id)]['content_type']
    content_data = pending_messages[str(message_id)]['content_data']

    # Сохраняем в send.bd
    sendbd = load_sendbd()
    sendbd[str(message_id)] = {
        'user_id': user_id,
        'content_type': content_type,
        'content_data': content_data,
        'caption': pending_messages[str(message_id)]['caption'],
        'timestamp': int(time.time())
    }
    save_sendbd(sendbd)
    # Отправляем сообщение всем администраторам
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton('✅ Одобрить', callback_data=f'approve_{message_id}'),
            InlineKeyboardButton('❌ Отклонить', callback_data=f'reject_{message_id}')
        ],
        [
            InlineKeyboardButton('🔇 Замутить 15 мин', callback_data=f'mute_{message_id}'),
            InlineKeyboardButton('⚠️ Предупреждение', callback_data=f'warn_{message_id}'),
            InlineKeyboardButton('🚫 Заблокировать', callback_data=f'block_{message_id}')
        ]
    ])

    for admin_id in ADMIN_IDS:
        if pending_messages[str(message_id)]['content_type'] == 'text':
            sent = await context.bot.send_message(
                chat_id=admin_id,
                text=f"Новое сообщение на проверку:\n\n{pending_messages[str(message_id)]['content_data']}",
                reply_markup=keyboard
            )

        elif pending_messages[str(message_id)]['content_type'] == 'photo':
            sent = await context.bot.send_photo(
                chat_id=admin_id,
                photo=pending_messages[str(message_id)]['content_data'],
                caption=pending_messages[str(message_id)]['caption'] or "Новое фото на проверку",
                reply_markup=keyboard
            )

        elif pending_messages[str(message_id)]['content_type'] == 'document':
            sent = await context.bot.send_document(
                chat_id=admin_id,
                document=pending_messages[str(message_id)]['content_data'],
                caption=pending_messages[str(message_id)]['caption'] or "Новый документ на проверку",
                reply_markup=keyboard
            )

        elif pending_messages[str(message_id)]['content_type'] == 'video':
            sent = await context.bot.send_video(
                chat_id=admin_id,
                video=pending_messages[str(message_id)]['content_data'],
                caption=pending_messages[str(message_id)]['caption'] or "Новое видео на проверку",
                reply_markup=keyboard
            )

        elif pending_messages[str(message_id)]['content_type'] == 'voice':
            sent = await context.bot.send_voice(
                chat_id=admin_id,
                voice=pending_messages[str(message_id)]['content_data'],
                caption="Новое голосовое на проверку",
                reply_markup=keyboard
            )

        elif pending_messages[str(message_id)]['content_type'] == 'video_note':
            sent = await context.bot.send_video_note(
                chat_id=admin_id,
                video_note=pending_messages[str(message_id)]['content_data']
                # Кружки не поддерживают подпись и кнопки — просто отправляем с кнопками
            )
            await context.bot.send_message(
                chat_id=admin_id,
                text="Новый кружок на проверку",
                reply_markup=keyboard
            )

        pending_messages[str(message_id)]['admin_messages'][str(admin_id)] = sent.message_id

    await update.message.reply_text('Сообщение отправлено администраторам на проверку!')





async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in SUPER_ADMINS:
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('📄 Выгрузить базу send.bd', callback_data='export_send_bd')]
    ])

    await update.message.reply_text('Админ-панель:', reply_markup=keyboard)


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    action, message_id = callback_data.split('_', 1)

    if message_id not in pending_messages:
        await query.edit_message_text('Сообщение уже обработано.')
        return

    message_info = pending_messages.pop(message_id)
    user_id = message_info['user_id']
    admin_messages = message_info['admin_messages']
    content_type = message_info['content_type']
    content_data = message_info['content_data']
    caption = message_info.get('caption', '')

    result_text = ""

    if action == 'approve':
        link_text = f"\n\n✉️ [Отправить своё сообщение анонимно]({BOT_LINK_USERNAME})"

        try:
            if content_type == 'text':
                data_text = escape_markdown(content_data)
                post_text = f"{data_text}{link_text}"
                await context.bot.send_message(chat_id=CHANNEL_ID, text=post_text, parse_mode='Markdown')

            elif content_type == 'photo':
                data_caption = escape_markdown(caption)
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=content_data,
                    caption=f"{data_caption}{link_text}" if caption else f"✉️ [Отправить своё сообщение анонимно]({BOT_LINK_USERNAME})",
                    parse_mode='Markdown'
                )

            elif content_type == 'video':
                data_caption = escape_markdown(caption)
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=content_data,
                    caption=f"{data_caption}{link_text}" if caption else f"✉️ [Отправить своё сообщение анонимно]({BOT_LINK_USERNAME})",
                    parse_mode='Markdown'
                )

            elif content_type == 'document':
                data_caption = escape_markdown(caption)
                await context.bot.send_document(
                    chat_id=CHANNEL_ID,
                    document=content_data,
                    caption=f"{data_caption}{link_text}" if caption else f"✉️ [Отправить своё сообщение анонимно]({BOT_LINK_USERNAME})",
                    parse_mode='Markdown'
                )

            elif content_type == 'voice':
                await context.bot.send_voice(
                    chat_id=CHANNEL_ID,
                    voice=content_data,
                    caption=f"✉️ [Отправить своё сообщение анонимно]({BOT_LINK_USERNAME})",
                    parse_mode='Markdown'
                )

            elif content_type == 'video_note':
                # кружки — отдельно, без подписи
                await context.bot.send_video_note(
                    chat_id=CHANNEL_ID,
                    video_note=content_data
                )

        except Exception as e:
            print(f"Ошибка отправки в канал: {e}")

        result_text = '✅ Сообщение одобрено и отправлено в канал.'

    elif action == 'reject':
        result_text = '❌ Сообщение отклонено.'
    elif action == 'mute':
        mutelist = load_mutelist()
        mutelist[str(user_id)] = time.time() + 15 * 60
        save_mutelist(mutelist)
        result_text = '🔇 Пользователь замучен на 15 минут.'
    elif action == 'warn':
        try:
            await context.bot.send_message(chat_id=user_id, text='⚠️ Вам выписано предупреждение за нарушение правил!')
        except:
            pass
        result_text = '⚠️ Пользователь получил предупреждение.'
    elif action == 'block':
        blocklist = load_blocklist()
        if user_id not in blocklist:
            blocklist.append(user_id)
            save_blocklist(blocklist)
        result_text = '🚫 Пользователь заблокирован.'

    # убираем кнопки у всех
    for admin_id, admin_message_id in admin_messages.items():
        try:
            await context.bot.edit_message_reply_markup(chat_id=int(admin_id), message_id=admin_message_id,
                                                        reply_markup=None)
            if content_type == 'text':
                await context.bot.edit_message_text(
                    chat_id=int(admin_id),
                    message_id=admin_message_id,
                    text=f"{content_data}\n\n{result_text}"
                )
            else:
                await context.bot.edit_message_caption(
                    chat_id=int(admin_id),
                    message_id=admin_message_id,
                    caption=f"{caption}\n\n{result_text}" if caption else result_text
                )
        except:
            pass


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('help', help))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, forward_to_admin))
    app.add_handler(CallbackQueryHandler(handle_approval))
    app.add_handler(CommandHandler('admin', admin_panel))

    print('Бот запущен...')
    app.run_polling()


if __name__ == '__main__':
    main()
