import asyncio
from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiomysql
import datetime
import re
from aiogram.types.bot_command import BotCommand
from aiogram.types.bot_command_scope import *
from config import *

class InfoNotFound(Exception):
    pass

bot = Bot(BOT_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot)

admins = [266428137]

DEBUG_MODE = False

def print_error(block, exception, additional_info=None):
    print(f'Ошибка в блоке {block}\nТип ошибки: {type(exception)}\nОшибка: {exception}\n{additional_info if additional_info else ""}')

async def make_database_request(s):
    result = None
    try:
        async with pool.acquire() as database:
            async with database.cursor() as cursor:
                await cursor.execute(s)
                a = await cursor.fetchall()
                await database.commit()
                result = a
    except Exception as e:
        print_error(f'async def make_database_request(s)', e, f'Текст запроса: {s}')
    finally:
        return result

async def get_disciplines_list():
    try:
        result = await make_database_request(f'SELECT `disciplines`.`id`, `disciplines`.`name` FROM `disciplines`')

        keyboard = InlineKeyboardMarkup(row_width=1)

        if not result:
            return

        for r in result:
            index, name = r
            keyboard.row(InlineKeyboardButton(text=name, callback_data=f'teachers_discipline_{index}'))

        keyboard.row(InlineKeyboardButton(text='Перейти к таблице 🌐', 
                     url='https://docs.google.com/spreadsheets/d/1tUbErivA1WzwKxcMyxEdbdWCZQKwjNnTH0F4rLSvLPc/edit#gid=102204205'))

        keyboard.row(InlineKeyboardButton(text='Закрыть ❌', callback_data='delete'))
        return {'text': '<i>Выберите желаемую дисциплину\n\nТакже эту информацию можно посмотреть в таблице</i>', 'reply_markup': keyboard}
    except Exception as e:
        print_error('async def get_disciplines_list()')

async def get_weeks_list():
    try:
        result = await make_database_request(f'SELECT DISTINCT(`week`) FROM `classes`')

        if not result:
            raise InfoNotFound('Недели не найдены')
        
        weeks = [item for sublist in result for item in sublist]
        week_names = ['Первая', 'Вторая', 'Третья', 'Четвёртая', 'Пятая', 'Шестая', 'Седьмая', 'Восьмая', 'Девятая', 'Десятая']

        keyboard = InlineKeyboardMarkup(row_width=1)

        for week in weeks:
            keyboard.row(InlineKeyboardButton(text=week_names[week-1], callback_data=f'schedule_{week}'))

        keyboard.row(InlineKeyboardButton(text='Официальный сайт с расписанием', url='http://rozklad.kpi.ua/Schedules/ViewSchedule.aspx?g=c8c38838-0dc5-4570-b531-0e0f11a89686'))

        keyboard.row(InlineKeyboardButton(text='Закрыть ❌', callback_data='delete'))

        return {'text': '<i>Для просмотра расписания выберите неделю</i>', 'reply_markup': keyboard}
    except Exception as e:
        print_error('async def get_weeks_list()', e)

async def get_days_list(week):
    try:
        result = await make_database_request(f'SELECT DISTINCT(`day`) FROM `classes` WHERE `week` = {week}')

        if not result:
            raise InfoNotFound(f'Дни не найдены (week == {week})')

        days = [item for sublist in result for item in sublist]
        days_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

        keyboard = InlineKeyboardMarkup(row_width=1)

        for day in days:
            keyboard.row(InlineKeyboardButton(text=days_names[day - 1], callback_data=f'schedule_{week}_{day}'))

        keyboard.row(InlineKeyboardButton(text='👉 Назад', callback_data='show_weeks_list'))

        return {'text': f'<i>Для просмотра расписания выберите день</i>', 'reply_markup': keyboard}
    except Exception as e:
        print_error('async def get_days_list(week)', e)

async def get_classes_list(week, day):
    try:
        result = await make_database_request(f'''SELECT
                                                    `classes`.`num`,
                                                    `timetable`.`time`,
                                                    `disciplines`.`name`, 
                                                    `types`.`name`, 
                                                    `teachers`.`lastName`, 
                                                    `teachers`.`firstName`, 
                                                    `teachers`.`patronymic`, 
                                                    `classes`.`link`
                                                 FROM 
                                                    `classes`,
                                                    `timetable`,
                                                    `disciplines`, 
                                                    `types`, 
                                                    `teachers`
                                                 WHERE
                                                    `classes`.`week` = {week} AND
                                                    `classes`.`day` = {day} AND
                                                    `classes`.`num` = `timetable`.`id` AND
                                                    `classes`.`discipline` = `disciplines`.`id` AND
                                                    `classes`.`type` = `types`.`id` AND
                                                    `classes`.`teacher` = `teachers`.`id` AND 
                                                    `classes`.`isActive`''')

        keyboard = InlineKeyboardMarkup(row_width=1)

        keyboard.row(InlineKeyboardButton(text='👉 Назад', callback_data=f'schedule_{week}'))

        if not result:
            return {'text': '<i>В выбранный день пары отсутствуют</i>', 'reply_markup': keyboard}

        days_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        classes_nums_names = ['Первая', 'Вторая', 'Третья', 'Четвёртая', 'Пятая', 'Шестая', 'Седьмая', 'Восьмая', 'Девятая', 'Десятая']

        text = f'Выбранный день: <b>{days_names[day-1]} ({week} неделя)</b>\n\n'

        for r in result:
            num, class_time, discipline, class_type, teacher_last_name, teacher_first_name, teacher_patronymic, link = r
            if num == 7:
                continue
            start_time = datetime.datetime(year=2021, month=1, day=1, hour=0, minute=0, second=0)
            class_time_start = start_time + class_time
            class_time_end = start_time + class_time + datetime.timedelta(minutes=95)
            if link:
                link = f'<a href="{link}">ссылка</a>'
            else:
                link = 'отсутствует'
            text = f'''{text}<b>{classes_nums_names[num-1]} пара</b>
  ({class_time_start.strftime("%H:%M")} - {class_time_end.strftime("%H:%M")})
  Название: <i>{discipline}</i>
  Тип: <i>{class_type}</i>
  Преподаватель: <i>{teacher_last_name} {teacher_first_name} {teacher_patronymic}</i>
  Ссылка для подключения к паре: <i>{link}</i>\n\n'''

        return {'text': text, 'reply_markup': keyboard}

    except Exception as e:
        print_error('async def get_classes_list(week, day)', e)

@dp.message_handler(commands=['start'])
async def start(message: Message):
    pass
    # await message.reply(str(message.chat.id))

@dp.message_handler(lambda message: message.from_user.id in admins, commands=['test'])
async def test(message: Message):
    search_id = 2
    result = await make_database_request(f'''SELECT `teachers`.`id`, `teachers`.`lastName`, `teachers`.`firstName`, `teachers`.`patronymic`, 
                                         `teachers`.`email`, `teachers`.`telegram`, `teachers`.`phoneNumber`, `teachers`.`disciplines`
                                         FROM `teachers`
                                         WHERE JSON_CONTAINS(`teachers`.`disciplines`, \'{{"id": {search_id}}}\')''')
    for r in result:
        teacher_id, last_name, first_name, patronymic, email, telegram, phone_number, disciplines = r
        disciplines = eval(f'list({disciplines})')
        for d in disciplines:
            if d['id'] == search_id:
                result = await make_database_request(f'SELECT `name` FROM `teachers_types` WHERE `id` = {d["type"]}')
                teacher_type = result[0][0]
        
    # l = eval(f'list({result[0][0]})')
    # print(type(l[0]))
    # print(type(d), d, sep='\n')

@dp.message_handler(lambda message: message.from_user.id in admins, commands=['oldschedule'])
async def show_schedule(message: Message):
    try:
        keyboard = InlineKeyboardMarkup(row_width=1)
        goto_button = InlineKeyboardButton(text='Перейти к таблице 🌐', 
            url='https://docs.google.com/spreadsheets/d/1tUbErivA1WzwKxcMyxEdbdWCZQKwjNnTH0F4rLSvLPc/edit#gid=0')
        keyboard.add(goto_button)
        await bot.send_message(message.chat.id, f'<i>Для просмотра расписания жми на кнопку <b>{goto_button.text}</b></i>', reply_markup=keyboard)
    except Exception as e:
        print_error('commands=[\'schedule\']', e)

@dp.message_handler(commands=['schedule'])
async def testschedule(message: Message):
    try:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass

        wl = await get_weeks_list()
        
        if not wl:
            return

        await bot.send_message(message.chat.id, wl['text'], reply_markup=wl['reply_markup'])

    except Exception as e:
        print_error('commands=[\'schedule\']', e)

@dp.message_handler(commands=['teachers'])
async def testschedule(message: Message):
    try:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass

        dl = await get_disciplines_list()
        await bot.send_message(message.chat.id, dl['text'], reply_markup=dl['reply_markup'])
    except Exception as e:
        print_error('commands[\'teachers\']')

@dp.message_handler(commands=['books'])
async def show_schedule(message: Message):
    try:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass

        await bot.send_message(message.chat.id, '<i>Функция находится в разработке..</i>')
    except Exception as e:
        print_error('commands=[\'books\']', e)

@dp.message_handler(commands=['subscribe'])
async def subscribe(message: Message):
    try:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass

        if message.chat.type != 'private':
            await message.reply('<i>Функция доступна только в личных сообщениях с ботом</i>')
            return

        result = await make_database_request(f'SELECT * FROM `subscriptions` WHERE `chatId` = {message.from_user.id} AND `isActive` = TRUE')

        if result:
            await message.reply('<i>Вы уже подписаны на напоминания</i>')

        else:
            result = await make_database_request(f'SELECT * FROM `subscriptions` WHERE `chatId` = {message.from_user.id}')

            if result:
                await make_database_request(f'UPDATE `subscriptions` SET `isActive` = TRUE WHERE `chatId` = {message.from_user.id}')

            else:
                await make_database_request(f'INSERT INTO `subscriptions` (`chatId`) VALUES ({message.from_user.id})')
                
            await message.reply('<i>Вы успешно подписались на напоминания</i>')
    except Exception as e:
        print_error('commands=[\'subscribe\']', e)

@dp.message_handler(commands=['unsubscribe'])
async def subscribe(message: Message):
    try:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass

        result = await make_database_request(f'SELECT * FROM `subscriptions` WHERE `chatId` = {message.from_user.id} AND `isActive` = TRUE')

        if result:
            await make_database_request(f'UPDATE `subscriptions` SET `isActive` = FALSE WHERE `chatId` = {message.from_user.id}')
            await message.reply('<i>Вы успешно отписались от напоминаний</i>')
        else:
            await message.reply('<i>Вы ещё не подписаны на напоминания</i>')
    except Exception as e:
        print_error('commands=[\'unsubscribe\']', e)

@dp.message_handler(lambda message: message.from_user.id in admins, commands=['eval'])
async def my_eval(message: Message):
    try:
        text = message.get_args()
        text = text.replace('->', 4*' ')
        res = re.search(r'(?P<awaitable>await )?(?P<command>.+)', text, re.DOTALL | re.MULTILINE)
        aw = res.group('awaitable')
        command = res.group('command')
        if aw:
            eval(command)
        else:
            eval(command)
    except Exception as e:
        await message.reply(f'An Error Occurred!\n{e}')

@dp.callback_query_handler(lambda call: True)
async def callback_handler(call: CallbackQuery):
    try:
        if call.data == 'delete':
            await bot.delete_message(call.message.chat.id, call.message.message_id)
        
        elif call.data[:20] == 'teachers_discipline_':
            res = re.search(r'teachers_discipline_(?P<num>\d+)', call.data)
            num = int(res.group('num'))
            result = await make_database_request(f'SELECT `disciplines`.`name` FROM `disciplines` WHERE `disciplines`.`id` = {num}')
            discipline_name = result[0][0]
            result = await make_database_request(f'''SELECT `teachers`.`lastName`, `teachers`.`firstName`, `teachers`.`patronymic`, 
                                         `teachers`.`email`, `teachers`.`telegram`, `teachers`.`phoneNumber`, `teachers`.`disciplines`
                                         FROM `teachers`
                                         WHERE JSON_CONTAINS(`teachers`.`disciplines`, \'{{"id": {num}}}\')''')
            mes_text = f'Выбранная дисциплина: <b>{discipline_name}</b>\n\n'
            for r in result:
                last_name, first_name, patronymic, email, telegram, phone_number, disciplines = r
                disciplines = eval(f'list({disciplines})')
                for d in disciplines:
                    if d['id'] == num:
                        result = await make_database_request(f'SELECT `name` FROM `teachers_types` WHERE `id` = {d["type"]}')
                        teacher_type = result[0][0]
                mes_text += f'<b>{last_name} {first_name} {patronymic if patronymic else ""}</b> ({teacher_type})'
                if email:
                    email = email.replace('\n', '')
                    mes_text += f'\n  Email: <b>{email}</b>'
                if telegram:
                    mes_text += f'\n  Telegram: <b>@{telegram}</b>'
                if phone_number:
                    mes_text += f'\n  Номер телефона: <b>{phone_number}</b>'
                mes_text += '\n\n'
            keybord = InlineKeyboardMarkup(row_width=1)
            return_button = InlineKeyboardButton(text='👉 Назад', callback_data='show_disciplines_list')
            keybord.add(return_button)

            await bot.edit_message_text(mes_text, call.message.chat.id, call.message.message_id, reply_markup=keybord)
            
        elif call.data == 'show_disciplines_list':
            dl = await get_disciplines_list()
            await bot.edit_message_text(dl['text'], call.message.chat.id, call.message.message_id, reply_markup=dl['reply_markup'])

        elif re.match(r'schedule_\d+$', call.data):
            res = re.match(r'schedule_(?P<week>\d+)$', call.data)

            week = int(res.group('week'))

            dl = await get_days_list(week)

            await bot.edit_message_text(dl['text'], call.message.chat.id, call.message.message_id, reply_markup=dl['reply_markup'])

        elif call.data == 'show_weeks_list':
            wl = await get_weeks_list()
            
            await bot.edit_message_text(wl['text'], call.message.chat.id, call.message.message_id, reply_markup=wl['reply_markup'])

        elif re.match(r'schedule_\d+_\d+$', call.data):
            res = re.match(r'schedule_(?P<week>\d+)_(?P<day>\d+)', call.data)

            week = int(res.group('week'))
            day = int(res.group('day'))

            cl = await get_classes_list(week, day)

            await bot.edit_message_text(cl['text'], call.message.chat.id, call.message.message_id, reply_markup=cl['reply_markup'], disable_web_page_preview=True)

    except Exception as e:
        print_error('@dp.callback_query_handler(lambda call: True)', e, f'call.data == {call.data}')

FIRST_DAY = datetime.datetime(year=2021, month=8, day=30)
NOTIFICATION_TIME = 5

async def main():
    global pool
    pool = await aiomysql.create_pool(host=DATABASE_HOST, user=DATABASE_USER, password=DATABASE_PASSWORD, db=DATABASE_DB)
    while True:
        try:
            result = await make_database_request('SELECT * FROM `timetable`')
            now = datetime.datetime.now()
            week = (now - FIRST_DAY).days // 7 % 2 + 1
            day = now.weekday() + 1
            now_td = datetime.timedelta(seconds=((now.hour * 60 + now.minute + NOTIFICATION_TIME) * 60))
            for num, couple_time in result:
                if now_td == couple_time:
                    this_class = await make_database_request(f'SELECT `id` FROM `classes` WHERE `week` = {week} AND `day` = {day} AND `num` = {num} AND `discipline` IS NOT NULL')
                    if not this_class:
                        return
                    this_class = this_class[0][0]
                    result = await make_database_request(f'''SELECT 
                                                                 `disciplines`.`name`, 
                                                                 `types`.`name`, 
                                                                 `teachers`.`lastName`, 
                                                                 `teachers`.`firstName`, 
                                                                 `teachers`.`patronymic`, 
                                                                 `classes`.`link`
                                                             FROM 
                                                                 `classes`, 
                                                                 `disciplines`, 
                                                                 `types`, 
                                                                 `teachers`
                                                             WHERE
                                                                 `classes`.`id` = {this_class} AND
                                                                 `classes`.`discipline` = `disciplines`.`id` AND
                                                                 `classes`.`type` = `types`.`id` AND
                                                                 `classes`.`teacher` = `teachers`.`id` AND 
                                                                 `classes`.`isActive`''')

                    discipline, class_type, teacher_last_name, teacher_first_name, teacher_patronymic, link = result[0]
                    keyboard = None
                    if link:
                        keyboard = InlineKeyboardMarkup(row_width=1)
                        goto_button = InlineKeyboardButton(text='Подключиться к паре 🌐', url=link)
                        keyboard.add(goto_button)
                    result = await make_database_request(f'SELECT `chatId` from `subscriptions` WHERE `isActive`')
                    chats = [item for sublist in result for item in sublist]
                    if DEBUG_MODE:
                        chats = [266428137]
                    for chat in chats:
                        try:
                            await bot.send_message(chat, f'''Напоминание!\n
Через <b>5</b> минут начнётся {class_type} по предмету <b>{discipline}</b>\n
Преподаватель: <b>{teacher_last_name} {teacher_first_name} {teacher_patronymic if teacher_patronymic else ""}</b>\n
{"Ссылка на подключение к паре отсутствует" if not link else f"Для перехода к паре жмите на кнопку <b>{goto_button.text}</b>"}''', reply_markup=keyboard)
                        except Exception as e:
                            print(e)
        except Exception as e:
            print_error('async def main()', e)
        finally:
            await asyncio.sleep(60.5 - datetime.datetime.now().second)

async def on_startup(x):
    ADMIN_COMMANDS = [BotCommand('oldschedule', 'Старое расписание'),
                      BotCommand('eval', 'Выполнить любое действие'),
                      BotCommand('mr', 'Сделать запрос к базе данных')]
    DEFAULT_COMMANDS = [BotCommand('schedule', 'Просмотреть расписание'), 
                        BotCommand('teachers', 'Список преподавателей'),
                        BotCommand('books', 'Просмотреть учебники'),
                        BotCommand('unsubscribe', 'Отписаться от уведомлений')]
    CHAT_COMMANDS = [BotCommand('subscribe', 'Подписаться на уведомления')]
    await bot.set_my_commands(DEFAULT_COMMANDS, BotCommandScopeDefault())
    await bot.set_my_commands(DEFAULT_COMMANDS + CHAT_COMMANDS, BotCommandScopeAllPrivateChats())
    for admin in admins:
        await bot.set_my_commands(DEFAULT_COMMANDS + CHAT_COMMANDS + ADMIN_COMMANDS, BotCommandScopeChat(admin))
    asyncio.create_task(main())

if __name__ == '__main__':
    print('FICT Helper Bot')
    executor.start_polling(dp, on_startup=on_startup)