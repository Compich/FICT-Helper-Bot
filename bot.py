import asyncio
from os import sep
from aiogram import Bot, Dispatcher, executor
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiomysql
import datetime
import re

bot = Bot('1957627434:AAFf7jGsqxFRVd724YHvae8CeQewxDCsQqY', parse_mode='HTML')
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
        keyboard = InlineKeyboardMarkup(row_width=1)
        result = await make_database_request(f'SELECT `disciplines`.`id`, `disciplines`.`name` FROM `disciplines`')
        for r in result:
            index, name = r
            keyboard.row(InlineKeyboardButton(text=name, callback_data=f'teachers_discipline_{index}'))
        table_button = InlineKeyboardButton(text='Перейти к таблице 🌐', 
            url='https://docs.google.com/spreadsheets/d/1tUbErivA1WzwKxcMyxEdbdWCZQKwjNnTH0F4rLSvLPc/edit#gid=102204205')
        keyboard.row(table_button)
        return {'text': '<i>Выберите желаемую дисциплину\n\nТакже эту информацию можно посмотреть в таблице</i>', 'reply_markup': keyboard}
    except Exception as e:
        print_error('async def get_disciplines_list()')

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

@dp.message_handler(commands=['schedule'])
async def show_schedule(message: Message):
    try:
        keyboard = InlineKeyboardMarkup(row_width=1)
        goto_button = InlineKeyboardButton(text='Перейти к таблице 🌐', 
            url='https://docs.google.com/spreadsheets/d/1tUbErivA1WzwKxcMyxEdbdWCZQKwjNnTH0F4rLSvLPc/edit#gid=0')
        keyboard.add(goto_button)
        await bot.send_message(message.chat.id, f'<i>Для просмотра расписания жми на кнопку <b>{goto_button.text}</b></i>', reply_markup=keyboard)
    except Exception as e:
        print_error('commands=[\'schedule\']', e)

@dp.message_handler(lambda message: message.from_user.id in admins, commands=['testschedule'])
async def testschedule(message: Message):
    pass

@dp.message_handler(commands=['teachers'])
async def testschedule(message: Message):
    try:
        dl = await get_disciplines_list()
        await bot.send_message(message.chat.id, dl['text'], reply_markup=dl['reply_markup'])
    except Exception as e:
        print_error('commands[\'teachers\']')

@dp.message_handler(commands=['books'])
async def show_schedule(message: Message):
    try:
        await bot.send_message(message.chat.id, '<i>Функция находится в разработке..</i>')
    except Exception as e:
        print_error('commands=[\'books\']', e)

@dp.message_handler(commands=['subscribe'])
async def subscribe(message: Message):
    try:
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
        result = await make_database_request(f'SELECT * FROM `subscriptions` WHERE `chatId` = {message.from_user.id} AND `isActive` = TRUE')
        if result:
            await make_database_request(f'UPDATE `subscriptions` SET `isActive` = FALSE WHERE `chatId` = {message.from_user.id}')
            await message.reply('<i>Вы успешно отписались от напоминаний</i>')
        else:
            await message.reply('<i>Вы ещё не подписаны на напоминания</i>')
    except Exception as e:
        print_error('commands=[\'unsubscribe\']', e)

@dp.callback_query_handler(lambda call: True)
async def callback_handler(call: CallbackQuery):
    try:
        if call.data[:20] == 'teachers_discipline_':
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

    except Exception as e:
        print_error('@dp.callback_query_handler(lambda call: True)', e, f'call.data == {call.data}')

FIRST_DAY = datetime.datetime(year=2021, month=8, day=30)
NOTIFICATION_TIME = 5

async def main():
    global pool
    pool = await aiomysql.create_pool(host='localhost', user='Compich', password=r'zWKHqx1N3%Gt', db='fict_helper')
    while True:
        try:
            result = await make_database_request('SELECT * FROM `timetable`')
            now = datetime.datetime.now()
            #now = datetime.datetime(year=2021, month=9, day=5)
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
    asyncio.create_task(main())

if __name__ == '__main__':
    print('FICT Schedule Bot')
    executor.start_polling(dp, on_startup=on_startup)