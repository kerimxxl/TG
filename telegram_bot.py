import logging
from datetime import datetime
from db import User, Task, Event, File, db_session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, ConversationHandler,
    MessageHandler, Filters, CallbackContext
)

def get_or_create_user(telegram_user):
    user = User.query.filter(User.telegram_id == telegram_user.id).first()
    if not user:
        user = User(telegram_id=telegram_user.id, name=telegram_user.username)
        db_session.add(user)
        db_session.commit()
    return user

def start(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    user = User.query.filter_by(telegram_id=user_id).first()

    if user:
        update.message.reply_text(f"Добро пожаловать снова, {user.username}!")
    else:
        new_user = User(telegram_id=user_id, name=update.message.from_user.first_name)
        db_session.add(new_user)
        db_session.commit()
        update.message.reply_text(f"Добро пожаловать, {new_user.username}! Ваш аккаунт был зарегистрирован.")
    show_buttons(update, context)

def message_needs_modification(new_text, reply_markup, message):
    return new_text != message.text or reply_markup != message.reply_markup

def show_buttons(update: Update, context: CallbackContext):
    keyboard = [
        [
            InlineKeyboardButton("Список задач", callback_data="list_tasks"),
            InlineKeyboardButton("Добавить задачу", callback_data="add_task")
        ],
        [
            InlineKeyboardButton("Список мероприятий", callback_data="list_events"),
            InlineKeyboardButton("Добавить мероприятие", callback_data="add_event")
        ],
        [
            InlineKeyboardButton("Список файлов", callback_data="list_files"),
            InlineKeyboardButton("Загрузить файл", callback_data="upload_file")
        ],
        [
            InlineKeyboardButton("Отправить сообщение всем", callback_data="send_message_to_all_prompt")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    new_text = "Выберите действие:"

    if update.callback_query:
        query = update.callback_query
        message = query.message

        if message_needs_modification(new_text, reply_markup, message):
            query.edit_message_text(new_text, reply_markup=reply_markup)
        else:
            query.answer()
    else:
        update.message.reply_text(new_text, reply_markup=reply_markup)

def handle_callback(update, context, state=None):
    query = update.callback_query
    query.answer()

    if query.data == "list_tasks":
        list_tasks(update, context)
    elif query.data == "add_task":
        add_task(update, context)
    elif query.data == "list_events":
        list_events(update, context)
    elif query.data == "add_event":
        add_event(update, context)
    elif query.data == "list_files":
        list_files(update, context)
    elif query.data == "upload_file":
        upload_file(update, context)
    elif query.data == "send_message_to_all_prompt":
        query.message.reply_text("Введите сообщение, которое вы хотите отправить всем пользователям:")
        return 1
    else:
        query.message.reply_text("Неизвестный запрос.")


def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Список доступных команд:\n"
        "/start - начать работу с ботом\n"
        "/help - список доступных команд\n"
        "/send_message_to_all - отправить сообщение всем пользователям\n"
        "/list_tasks - показать список задач\n"
        "/add_task - добавить задачу\n"
        "/delete_task - удалить задачу\n"
        "/list_events - показать список событий\n"
        "/add_event - добавить событие\n"
        "/delete_event - удалить событие\n"
        "/list_files - показать список файлов\n"
        "/upload_file - загрузить файл\n"
        "/delete_file - удалить файл\n"
    )


def add_task(update: Update, context: CallbackContext):
    message = update.message
    if not message:
        return

    message_text = message.text
    if not message_text.startswith("/add_task "):
        return

    args = message_text[len("/add_task "):].split(",")
    if len(args) != 3:
        message.reply_text("Неверный формат сообщения. Используйте следующий формат:\n/add_task Заголовок, Описание, ГГГГ.ММ.ДД")
        return

    title, description, deadline = args
    chat_id = message.chat_id

    try:
        task = Task(chat_id=chat_id, title=title, description=description, deadline=datetime.strptime(deadline, "%Y.%m.%d"))
        db_session.add(task)
        db_session.commit()
        message.reply_text("Задача успешно добавлена!")
    except ValueError:
        message.reply_text("Неверный формат даты. Используйте следующий формат: ГГГГ-ММ-ДД")


def delete_task(update: Update, context: CallbackContext):
    message = update.message
    if not message:
        return

    message_text = message.text
    if not message_text.startswith("/delete_task "):
        return

    task_id = message_text[len("/delete_task "):]
    try:
        task_id = int(task_id)
    except ValueError:
        message.reply_text("Неверный формат ID задачи. ID задачи должен быть числом.")
        return

    task = Task.query.get(task_id)
    if task:
        db_session.delete(task)
        db_session.commit()
        message.reply_text("Задача успешно удалена!")
    else:
        message.reply_text("Задача с указанным ID не найдена.")


def list_tasks(update, context):
    query = update.callback_query
    user_id = query.message.chat_id
    user = db_session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        tasks = db_session.query(Task).filter_by(user_id=user.id).order_by(Task.deadline).all()
        if tasks:
            response = "Your tasks:\n\n"
            for task in tasks:
                response += f"{task.id}: {task.description} - {task.deadline}\n"
            query.message.reply_text(response)
        else:
            query.message.reply_text("You have no tasks.")
    else:
        query.message.reply_text("Please use /start to register.")


def list_events(update, context):
    chat_id = update.callback_query.message.chat_id
    events = db_session.query(Event).filter(Event.user_id == chat_id).order_by(Event.date).all()

    if not events:
        update.callback_query.message.reply_text("У вас нет запланированных мероприятий.")
        return

    events_list = []
    for event in events:
        event_date = event.date.strftime("%d.%m.%Y")
        events_list.append(f"{event.title} - {event_date}")

    events_text = "\n".join(events_list)
    update.callback_query.message.reply_text(f"Ваши мероприятия:\n\n{events_text}")


def add_event(update: Update, context: CallbackContext, description=None):
    chat_id = update.message.chat_id
    text = update.message.text
    command, *args = text.split()
    if len(args) < 2:
        update.message.reply_text(
            "Пожалуйста, укажите название и дату мероприятия. Например: /add_event Название мероприятия; 2023-04-20")
        return
    date_str = args[-1]
    title = " ".join(args[:-1])
    if date_str:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        update.message.reply_text("Не удалось распознать дату. Пожалуйста, укажите дату в формате YYYY-MM-DD.")
        return

    event = Event(title=title, description=description, date=date_obj, user_id=chat_id)
    db_session.add(event)
    db_session.commit()

    update.message.reply_text(f"Мероприятие добавлено:\nНазвание: {title}\nДата: {date_str}")


def delete_event(update: Update, context: CallbackContext):
    message = update.message
    if not message:
        return

    message_text = message.text
    if not message_text.startswith("/delete_event "):
        return

    event_id = message_text[len("/delete_event "):]
    try:
        event_id = int(event_id)
    except ValueError:
        message.reply_text("Неверный формат ID мероприятия. ID мероприятия должен быть числом.")
        return

    event = Event.query.get(event_id)
    if event:
        db_session.delete(event)
        db_session.commit()
        message.reply_text("Мероприятие успешно удалено!")
    else:
        message.reply_text("Мероприятие с указанным ID не найдено.")


def handle_message(update: Update, context: CallbackContext):
    update.message.reply_text("Неизвестная команда. Введите /help для получения списка команд.")

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Действие отменено.")
    return ConversationHandler.END


def get_all_users():
    users = User.query.all()
    return users

def send_message_to_all(update, context):
    if context.user_data.get('state') == SENDING_MESSAGE:
        message = update.message.text
    if update is None or update.message is None:
        return
    if not context.args:
        update.message.reply_text("Пожалуйста, предоставьте сообщение для отправки.")
        return
    context.user_data.pop('state', None)

    message = " ".join(context.args)
    all_users = get_all_users()
    for user in all_users:
        try:
            context.bot.send_message(chat_id=user.telegram_id, text=message)
        except Exception as e:
            print(f"Error sending message to {user.telegram_id}: {e}")
    return ConversationHandler.END


def handle_file(update, context):
    user_id = update.message.chat_id
    user = db_session.query(User).filter_by(telegram_id=user_id).first()

    if user:
        if update.message.document:
            file = context.bot.get_file(update.message.document.file_id)
            file_name = update.message.document.file_name
        elif update.message.photo:
            file = context.bot.get_file(update.message.photo[-1].file_id)
            file_name = "photo"
        elif update.message.video:
            file = context.bot.get_file(update.message.video.file_id)
            file_name = "video"
        else:
            update.message.reply_text("Document not found in message. Please send a file.")
            return
        new_file = File(file_id=file.file_id, file_name=file_name, user_id=user.id)
        db_session.add(new_file)
        db_session.commit()

        update.message.reply_text(f"File '{file_name}' successfully uploaded.")
    else:
        update.message.reply_text("Please use /start first.")


def list_files(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    files = File.query.all()
    if not files:
        query.message.reply_text("Список файлов пуст.")
        return

    file_text = "Ваши файлы:\n\n"
    for file in files:
        file_text += f"{file.file_name} - file_id: {file.file_id}\n"

    query.message.reply_text(file_text)


def upload_file(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    user = db_session.query(User).filter_by(telegram_id=user_id).first()

    if not user:
        update.message.reply_text("Please use /start first.")
        return

    if update.message.document:
        file = update.message.document
        file_id = file.file_id
        file_name = file.file_name
        new_file = File(file_name=file_name, file_id=file_id, user_id=user.id)
        db_session.add(new_file)
        db_session.commit()
        update.message.reply_text(f"Файл {file_name} успешно загружен.")
    else:
        update.message.reply_text("Пожалуйста, отправьте документ вместе с командой /upload_file.")


def delete_file(update: Update, context: CallbackContext):
    message = update.message
    if not message:
        return

    message_text = message.text
    if not message_text.startswith("/delete_file "):
        return

    file_id = message_text[len("/delete_file "):]
    try:
        file_id = int(file_id)
    except ValueError:
        message.reply_text("Неверный формат ID файла. ID файла должен быть числом.")
        return

    file = File.query.get(file_id)
    if file:
        db_session.delete(file)
        db_session.commit()
        message.reply_text("Файл успешно удален!")
    else:
        message.reply_text("Файл с указанным ID не найден.")

# Main
BOT_TOKEN = "5884394290:AAG5KRca93pUSO6A81wqbi9_dEpkB1iF0VA"

SENDING_MESSAGE = range(1)

send_message_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(lambda update, context: handle_callback(update, context, SENDING_MESSAGE), pattern='^send_message_to_all_prompt$')],
    states={
        SENDING_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, send_message_to_all, pass_user_data=True)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

def handle_callback(update, context, state, bot_functions=None):
    query = update.callback_query
    query.answer()

    if state == SENDING_MESSAGE:
        if query.data == "list_tasks":
            list_tasks(update, context)

    if query.data == "list_tasks":
        bot_functions.list_tasks(update, context)
    elif query.data == "add_task":
        bot_functions.add_task(update, context)
    elif query.data == "list_events":
        bot_functions.list_events(update, context)
    elif query.data == "add_event":
        bot_functions.add_event(update, context)
    elif query.data == "delete_event":
        bot_functions.delete_event(update, context)
    elif query.data == "list_files":
        bot_functions.list_files(update, context)
    elif query.data == "upload_file":
        bot_functions.upload_file(update, context)
    elif query.data == "delete_file":
        bot_functions.delete_file(update, context)
    elif query.data == "send_message_to_all_prompt":
        query.message.reply_text("Введите сообщение, которое вы хотите отправить всем пользователям:")
        return 1
    else:
        query.message.reply_text("Неизвестный запрос.")


def menu(update, context):
    keyboard = [
        [
            InlineKeyboardButton("Список задач", callback_data='list_tasks'),
            InlineKeyboardButton("Добавить задачу", callback_data='add_task')
        ],
        [
            InlineKeyboardButton("Список событий", callback_data='list_events'),
            InlineKeyboardButton("Добавить событие", callback_data='add_event')
        ],
        [
            InlineKeyboardButton("Список файлов", callback_data='list_files'),
            InlineKeyboardButton("Загрузить файл", url=f'tg://user?id={update.message.chat_id}&cmd=upload_file')
        ],
        [
            InlineKeyboardButton("Отправить сообщение всем", callback_data="send_message_to_all_prompt")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )

    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("list_tasks", list_tasks))
    dp.add_handler(CommandHandler("add_task", add_task))
    dp.add_handler(CommandHandler("delete_task", delete_task))
    dp.add_handler(CommandHandler("list_events", list_events))
    dp.add_handler(CommandHandler("add_event", add_event))
    dp.add_handler(CommandHandler("delete_event", delete_event))
    dp.add_handler(CommandHandler("list_files", list_files))
    dp.add_handler(CommandHandler("upload_file", upload_file))
    dp.add_handler(CommandHandler("delete_file", delete_file))
    dp.add_handler(CommandHandler("send_message_to_all", send_message_to_all))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()