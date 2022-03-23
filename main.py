import logging

from aiogram import Bot
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher
from aiogram.utils.exceptions import MessageNotModified
from contextlib import suppress
from aiogram.dispatcher.webhook import SendMessage
from aiogram.utils.executor import start_webhook

from mytoken import TOKEN as API_TOKEN
from Vacancy import vacancy_per_user, Vacancy, types, MENU_ACTIONS

# from testing.sqllighter3 import SQLighter

WEBHOOK_HOST = 'https://3b53-51-250-25-255.ngrok.io'
WEBHOOK_PATH = '/'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = 'localhost'
WEBAPP_PORT = 4443

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


def chat_message_id(message: types.Message) -> tuple:
    """

    :param message:
    :return: chat_id and message_id
    """
    match type(message):
        case types.Message:
            return message.chat.id, message.message_id
        case types.CallbackQuery:
            return message.message.chat.id, message.message.message_id


# очищает историю сообщений, по default - 2 последних
async def delete_prev_messages(current_message_id, chat_id, count_to_delete=2):
    if not (chat_id and current_message_id):
        return
    counter = current_message_id
    while True:
        if counter == current_message_id - count_to_delete:
            break
        try:
            await bot.delete_message(chat_id=chat_id, message_id=counter)
        except:
            print('No message to dlt')
            continue
        finally:
            counter -= 1


# очищает клавиатуру сообщений, по default - 2 последних включительно текущее
async def clear_markup(current_message_id, chat_id, count_to_delete=5):
    """# очищает markup, по default - 2— последних"""
    if not (chat_id and current_message_id):
        return
    counter = current_message_id
    while True:
        if counter == current_message_id - count_to_delete:
            break
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=counter, reply_markup=None)
        except:
            print('No message to clear')
            continue
        finally:
            counter -= 1


# Команда для полной перезагрузки и начала с меню
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    with suppress(MessageNotModified):
        """
        При старте бота
            Приветственное сообщение
            Создание новой вакансии
        :param message:
        :return: None
        """
        chat_id, mg_id = chat_message_id(message)
        await bot.send_message(chat_id, text=f"Hello, {message.from_user.full_name}",
                               reply_markup=types.ReplyKeyboardRemove())

        await new_vacancy(message)


@dp.message_handler(commands=['new'])
async def new_vacancy(message: types.Message):
    """
    Создание новой вакансии
        Создает новое голавное сообщение и присваивает его к объекту вакансии
        Возврат в главное меню
    :param message:
    :return:
    """
    with suppress(MessageNotModified):
        chat_id, mg_id = chat_message_id(message)
        # на всякий случай очищает клавиатуры последних 2 сообщений
        await clear_markup(mg_id, chat_id)

        # Работаем с этим сообщением
        main_mg = await bot.send_message(chat_id, ' MENU')
        cur_vacancy = Vacancy(main_mg.message_id, chat_id)

        vacancy_per_user[chat_id] = cur_vacancy

        mp = cur_vacancy.get_mp

        await bot.edit_message_reply_markup(chat_id, cur_vacancy.mg_id, reply_markup=mp)
        return cur_vacancy


# Работа с данными без клавиатуры - описание, и др., где требуется ввод с клавиатуры
@dp.message_handler(content_types=['text'])
async def text_handler(message: types.Message):
    with suppress(MessageNotModified):
        chat_id, cb_mg_id = chat_message_id(message)
        cur_vacancy = vacancy_per_user.get(chat_id, None)

        if cur_vacancy:

            action = cur_vacancy.menu.menu_action()

            if action == 'text':
                if message.text.lower() == 'clear' or message.text == '/clear':
                    cur_vacancy.info[cur_vacancy.menu.cb_tag] = None
                    await menu_return(message)
                cur_vacancy.info[cur_vacancy.menu.cb_tag] = message.text
                await cur_vacancy.update_vacancy_text(message.chat.id, bot)
                await menu_return(message)
                print(cur_vacancy.info)
            # удаляет сообщение пользователя, когда не надо вводить ничего!
            await delete_prev_messages(message.message_id, message.chat.id, 1)


# Меню заполнения вакансии
@dp.callback_query_handler(lambda call: call.data == 'back_menu')
async def menu_return(cb):
    with suppress(MessageNotModified):
        try:
            chat_id, cb_mg_id = chat_message_id(cb)
            cur_vacancy = vacancy_per_user.get(chat_id, None)
            if not cur_vacancy:
                cur_vacancy = await new_vacancy(cb.message)

            # Работаем только с актуальным сообщением
            if cb_mg_id == cur_vacancy.mg_id or type(cb) is types.Message:
                try:
                    cur_vacancy.menu = cur_vacancy.menu.back_menu()
                except Exception as err:
                    print(err)
                mp = cur_vacancy.get_mp
                try:
                    await bot.edit_message_reply_markup(chat_id, cur_vacancy.mg_id, reply_markup=mp)
                except Exception as err:
                    print(err)
            else:  # одно из предыдущий Сообщений
                await bot.answer_callback_query(show_alert=False, callback_query_id=cb.id, text="Error!")

            if type(cb) is types.CallbackQuery:
                await bot.answer_callback_query(show_alert=False, callback_query_id=cb.id, text="Success!")
        except Exception as err:
            if type(cb) is types.CallbackQuery:
                await bot.answer_callback_query(show_alert=False, callback_query_id=cb.id, text="Error!")


@dp.callback_query_handler(lambda call: call.data in ('Junior', 'Middle', "Senior"))
async def jun_mid_sen(cb):
    with suppress(MessageNotModified):
        # для удобной работы с данными сообщения
        chat_id, cb_mg_id = chat_message_id(cb)

        cur_vacancy = vacancy_per_user.get(chat_id, None)
        if not cur_vacancy:
            await new_vacancy(cb.message)
            return

        if cb_mg_id == cur_vacancy.mg_id:
            cur_vacancy.info['jun_mid_sen'] = cb.data
            try:
                await cur_vacancy.update_vacancy_text(chat_id, bot)
                await menu_return(cb.message)
            except Exception as err:
                print(err)


@dp.callback_query_handler(lambda call: call.data in ('art', 'code'))
async def art_code_cb(cb):
    with suppress(MessageNotModified):
        # для удобной работы с данными сообщения
        chat_id, cb_mg_id = chat_message_id(cb)

        cur_vacancy = vacancy_per_user.get(chat_id, None)
        if not cur_vacancy:
            await new_vacancy(cb.message)
            return

        if cb_mg_id == cur_vacancy.mg_id:
            cur_vacancy.info['art_code'] = cb.data
            try:
                await cur_vacancy.update_vacancy_text(chat_id, bot)
                await menu_return(cb.message)
            except Exception as err:
                print(err)


@dp.callback_query_handler(
    lambda call: call.data in ('Remote', 'PC', "Console", "VR", "Mobile"))
async def platform_cb(cb):
    with suppress(MessageNotModified):
        # для удобной работы с данными сообщения
        chat_id, cb_mg_id = chat_message_id(cb)

        cur_vacancy = vacancy_per_user.get(chat_id, None)
        if not cur_vacancy:
            await new_vacancy(cb.message)
            return

        if cb_mg_id == cur_vacancy.mg_id:
            if not cur_vacancy.info.get(cb.data, None):
                cur_vacancy.info[cb.data] = cb.data
            else:
                cur_vacancy.info[cb.data] = None
            try:
                await cur_vacancy.update_vacancy_text(chat_id, bot)
                await bot.edit_message_reply_markup(chat_id, message_id=cur_vacancy.mg_id,
                                                    reply_markup=cur_vacancy.get_mp)
            except Exception as err:
                print(err)


@dp.callback_query_handler(
    lambda call: call.data in ('Full-Time', "Part-Time", "Contract"))
async def platform_cb(cb):
    with suppress(MessageNotModified):
        # для удобной работы с данными сообщения
        chat_id, cb_mg_id = chat_message_id(cb)

        cur_vacancy = vacancy_per_user.get(chat_id, None)
        if not cur_vacancy:
            await new_vacancy(cb.message)
            return

        if cb_mg_id == cur_vacancy.mg_id:
            if not cur_vacancy.info.get(cb.data, None):
                cur_vacancy.info['schedule'] = cb.data
            else:
                cur_vacancy.info['schedule'] = None
            try:
                await cur_vacancy.update_vacancy_text(chat_id, bot)
                await bot.edit_message_reply_markup(chat_id, message_id=cur_vacancy.mg_id,
                                                    reply_markup=cur_vacancy.get_mp)
            except Exception as err:
                print(err)


# Меню заполнения вакансии
# проверка cb на тег меню
@dp.callback_query_handler(lambda call: True)
async def callback4_all(cb):
    with suppress(MessageNotModified):
        # для удобной работы с данными сообщения
        chat_id, cb_mg_id = chat_message_id(cb)

        cur_vacancy = vacancy_per_user.get(chat_id, None)
        if not cur_vacancy:
            await new_vacancy(cb.message)

        # Работаем только с актуальным сообщением
        if cb_mg_id == cur_vacancy.mg_id:
            if cb.data in cur_vacancy.menu.children.keys():
                cur_vacancy.menu = cur_vacancy.menu.children[cb.data]
                mp = cur_vacancy.get_mp
                try:
                    await bot.edit_message_reply_markup(chat_id, cb_mg_id, reply_markup=mp)
                except Exception as err:
                    print(err)
        else:  # одно из предыдущий Сообщений
            await bot.answer_callback_query(show_alert=False, callback_query_id=cb.id, text="Error!", cache_time=2)
        await bot.answer_callback_query(show_alert=False, callback_query_id=cb.id, text="Success!")


async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)
    # insert code here to run it after start


async def on_shutdown(dp):
    logging.warning('Shutting down..')

    # insert code here to run it before shutdown

    # Remove webhook (not acceptable in some cases)
    await bot.delete_webhook()

    # Close DB connection (if used)
    await dp.storage.close()
    await dp.storage.wait_closed()

    logging.warning('Bye!')


if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
