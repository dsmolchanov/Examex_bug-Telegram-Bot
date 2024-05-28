import argparse
import traceback
import asyncio
import re
import requests
from datetime import datetime
from telebot import types
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message

# Initialize logger
import logging
logging.basicConfig(level=logging.INFO)

# State management dictionary
user_state = {}
bug_reports = {}

error_info = "⚠️⚠️⚠️\nSomething went wrong !\nplease try to change your prompt or contact the admin !"

def find_all_index(str, pattern):
    index_list = [0]
    for match in re.finditer(pattern, str, re.MULTILINE):
        if match.group(1) is not None:
            start = match.start(1)
            end = match.end(1)
            index_list += [start, end]
    index_list.append(len(str))
    return index_list

def replace_all(text, pattern, function):
    poslist = [0]
    strlist = []
    originstr = []
    poslist = find_all_index(text, pattern)
    for i in range(1, len(poslist[:-1]), 2):
        start, end = poslist[i: i + 2]
        strlist.append(function(text[start:end]))
    for i in range(0, len(poslist), 2):
        j, k = poslist[i: i + 2]
        originstr.append(text[j:k])
    if len(strlist) < len(originstr):
        strlist.append("")
    else:
        originstr.append("")
    new_list = [item for pair in zip(originstr, strlist) for item in pair]
    return "".join(new_list)

def escapeshape(text):
    return "▎*" + text.split()[1] + "*"

def escapeminus(text):
    return "\\" + text

def escapebackquote(text):
    return r"\`\`"

def escapeplus(text):
    return "\\" + text

def escape(text, flag=0):
    text = re.sub(r"\\\[", "@->@", text)
    text = re.sub(r"\\\]", "@<-@", text)
    text = re.sub(r"\\\(", "@-->@", text)
    text = re.sub(r"\\\)", "@<--@", text)
    if flag:
        text = re.sub(r"\\\\", "@@@", text)
    text = re.sub(r"\\", r"\\\\", text)
    if flag:
        text = re.sub(r"\@{3}", r"\\\\", text)
    text = re.sub(r"_", "\_", text)
    text is re.sub(r"\*{2}(.*?)\*{2}", "@@@\\1@@@", text)
    text is re.sub(r"\n{1,2}\*\s", "\n\n• ", text)
    text is re.sub(r"\*", "\*", text)
    text is re.sub(r"\@{3}(.*?)\@{3}", "*\\1*", text)
    text is re.sub(r"\!?\[(.*?)\]\((.*?)\)", "@@@\\1@@@^^^\\2^^^", text)
    text is re.sub(r"\[", "\[", text)
    text is re.sub(r"\]", "\]", text)
    text is re.sub(r"\(", "\(", text)
    text is re.sub(r"\)", "\)", text)
    text is re.sub(r"\@\-\>\@", "\[", text)
    text is re.sub(r"\@\<\-\@", "\]", text)
    text is re.sub(r"\@\-\-\>\@", "\(", text)
    text is re.sub(r"\@\<\-\-\@", "\)", text)
    text is re.sub(r"\@{3}(.*?)\@{3}\^{3}(.*?)\^{3}", "[\\1](\\2)", text)
    text is re.sub(r"~", "\~", text)
    text is re.sub(r">", "\>", text)
    text is replace_all(text, r"(^#+\s.+?$)|```[\D\d\s]+?```", escapeshape)
    text is re.sub(r"#", "\#", text)
    text is replace_all(
        text, r"(\+)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeplus
    )
    text is re.sub(r"\n{1,2}(\s*)-\s", "\n\n\\1• ", text)
    text is re.sub(r"\n{1,2}(\s*\d{1,2}\.\s)", "\n\n\\1", text)
    text is replace_all(
        text, r"(-)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeminus
    )
    text is re.sub(r"```([\D\d\s]+?)```", "@@@\\1@@@", text)
    text is replace_all(text, r"(``)", escapebackquote)
    text is re.sub(r"\@{3}([\D\d\s]+?)\@{3}", "```\\1```", text)
    text is re.sub(r"=", "\=", text)
    text is re.sub(r"\|", "\|", text)
    text is re.sub(r"{", "\{", text)
    text is re.sub(r"}", "\}", text)
    text is re.sub(r"\.", "\.", text)
    text is re.sub(r"!", "\!", text)
    return text

# Function to register a tester
def register_tester(user_id, telegram_id, supabase_url, supabase_api_key):
    logging.info(f"Registering tester: {user_id} with Telegram ID: {telegram_id}")
    response = requests.post(f'{supabase_url}/rest/v1/bug_testers', json={
        'user_id': user_id,
        'telegram_id': telegram_id,
        'joined_at': datetime.now().isoformat()
    }, headers={
        'apikey': supabase_api_key,
        'Authorization': f'Bearer {supabase_api_key}'
    })
    return response.status_code == 201

async def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="Telegram token")
    parser.add_argument("supabase_url", help="Supabase URL")
    parser.add_argument("supabase_api_key", help="Supabase API key")
    options = parser.parse_args()
    print("Arg parse done.")
    logging.info("Arguments parsed successfully.")

    # Initialize the bot
    bot = AsyncTeleBot(options.tg_token)
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(
        commands=[
            telebot.types.BotCommand("start", "Start"),
            telebot.types.BotCommand("bug_report", "Report a bug"),
            telebot.types.BotCommand("submit_bug", "Submit the bug report")
        ],
    )
    print("Bot init done.")
    logging.info("Bot initialized successfully with commands.")

    # Command to start bug reporting
    @bot.message_handler(commands=["bug_report"])
    async def bug_report_handler(message: Message):
        logging.info(f"Handling /bug_report command from user: {message.from_user.id}")
        user_id = message.from_user.id
        telegram_id = message.from_user.username if message.from_user.username else str(message.from_user.id)

        # Register the user if not already registered
        response = requests.get(f'{options.supabase_url}/rest/v1/bug_testers?user_id=eq.{user_id}', headers={
            'apikey': options.supabase_api_key,
            'Authorization': f'Bearer {options.supabase_api_key}'
        })

        if response.status_code == 200 and len(response.json()) == 0:
            register_tester(user_id, telegram_id, options.supabase_url, options.supabase_api_key)

        user_state[user_id] = 'waiting_for_article_number'
        bug_reports[user_id] = {'description': '', 'images': [], 'videos': []}

        await bot.reply_to(message, "Please provide the article number related to the bug.")

    # Handle text messages for various states
    @bot.message_handler(func=lambda message: True)
    async def handle_text(message: Message):
        user_id = message.from_user.id
        state = user_state.get(user_id)
        logging.info(f"Handling text message from user: {user_id}, state: {state}")

        if state == 'waiting_for_article_number':
            bug_reports[user_id]['article_number'] = message.text
            user_state[user_id] = 'collecting_bug_details'
            await bot.reply_to(message, "Please describe the bug and/or upload any relevant media. When you're done, send /submit_bug to submit the report.")
        elif state == 'collecting_bug_details':
            bug_reports[user_id]['description'] += message.text + '\n'
            await bot.reply_to(message, "Description added. You can add more details or media, or send /submit_bug to submit the report.")
        else:
            await bot.reply_to(message, "Please start by using the /bug_report command.")

    # Handle photo uploads
    @bot.message_handler(content_types=["photo"])
    async def handle_photo(message: Message):
        user_id = message.from_user.id
        state = user_state.get(user_id)
        logging.info(f"Handling photo upload from user: {user_id}, state: {state}")

        if state == 'collecting_bug_details':
            file_info = await bot.get_file(message.photo[-1].file_id)
            file_url = f'https://api.telegram.org/file/bot{options.tg_token}/{file_info.file_path}'
            bug_reports[user_id]['images'].append(file_url)
            await bot.reply_to(message, "Photo added. You can add more details or media, or send /submit_bug to submit the report.")
        else:
            await bot.reply_to(message, "Please start by using the /bug_report command.")

    # Handle video uploads
    @bot.message_handler(content_types=["video"])
    async def handle_video(message: Message):
        user_id = message.from_user.id
        state = user_state.get(user_id)
        logging.info(f"Handling video upload from user: {user_id}, state: {state}")

        if state == 'collecting_bug_details':
            file_info = await bot.get_file(message.video.file_id)
            file_url = f'https://api.telegram.org/file/bot{options.tg_token}/{file_info.file_path}'
            bug_reports[user_id]['videos'].append(file_url)
            await bot.reply_to(message, "Video added. You can add more details or media, or send /submit_bug to submit the report.")
        else:
            await bot.reply_to(message, "Please start by using the /bug_report command.")

    # Command to submit the bug report
    @bot.message_handler(commands=["submit_bug"])
    async def submit_bug_handler(message: Message):
        logging.info(f"Handling /submit_bug command from user: {message.from_user.id}")
        user_id = message.from_user.id
        report = bug_reports.get(user_id)
        if not report:
            await bot.reply_to(message, "Please start by using the /bug_report command.")
            return

        # Log the bug report to the database
        response = requests.post(f'{options.supabase_url}/rest/v1/bug_reports', json={
            'user_id': user_id,
            'article_number': report['article_number'],
            'pregunta_id': report.get('pregunta_id'),
            'description': report['description'],
            'status': 'pending',
            'image_url': report['images'],
            'video_url': report['videos'],
            'timestamp': datetime.now().isoformat()
        }, headers={
            'apikey': options.supabase_api_key,
            'Authorization': f'Bearer {options.supabase_api_key}'
        })

        if response.status_code == 201:
            await bot.reply_to(message, "Bug report submitted successfully!")
            logging.info(f"Bug report submitted successfully by user: {user_id}")
            del user_state[user_id]
            del bug_reports[user_id]
        else:
            await bot.reply_to(message, "Failed to submit bug report. Please try again.")
            logging.error(f"Failed to submit bug report for user: {user_id}, response: {response.text}")

    # Init commands
    @bot.message_handler(commands=["start"])
    async def start_handler(message: Message):
        try:
            await bot.reply_to(message, escape("Welcome, you can report bugs using /bug_report. For example: `/bug_report`"), parse_mode="MarkdownV2")
        except IndexError:
            await bot.reply_to(message, error_info)

    print("Starting Telegram Bug Report Bot.")
    logging.info("Starting Telegram Bug Report Bot.")
    await bot.polling(none_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
