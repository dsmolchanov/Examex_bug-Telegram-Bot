import argparse
import traceback
import asyncio
import google.generativeai as genai
import re
import requests
from datetime import datetime
from telebot import types
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message

# Initialize logger
import logging
logging.basicConfig(level=logging.INFO)

gemini_player_dict = {}
gemini_pro_player_dict = {}
default_model_dict = {}

error_info = "⚠️⚠️⚠️\nSomething went wrong !\nplease try to change your prompt or contact the admin !"
before_generate_info = "🤖Generating🤖"
download_pic_notify = "🤖Loading picture🤖"

n = 30  # Number of historical records to keep

generation_config = {
    "temperature": 1,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

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
    text = re.sub(r"\*{2}(.*?)\*{2}", "@@@\\1@@@", text)
    text = re.sub(r"\n{1,2}\*\s", "\n\n• ", text)
    text = re.sub(r"\*", "\*", text)
    text = re.sub(r"\@{3}(.*?)\@{3}", "*\\1*", text)
    text = re.sub(r"\!?\[(.*?)\]\((.*?)\)", "@@@\\1@@@^^^\\2^^^", text)
    text = re.sub(r"\[", "\[", text)
    text = re.sub(r"\]", "\]", text)
    text = re.sub(r"\(", "\(", text)
    text = re.sub(r"\)", "\)", text)
    text = re.sub(r"\@\-\>\@", "\[", text)
    text = re.sub(r"\@\<\-\@", "\]", text)
    text = re.sub(r"\@\-\-\>\@", "\(", text)
    text = re.sub(r"\@\<\-\-\@", "\)", text)
    text = re.sub(r"\@{3}(.*?)\@{3}\^{3}(.*?)\^{3}", "[\\1](\\2)", text)
    text = re.sub(r"~", "\~", text)
    text = re.sub(r">", "\>", text)
    text = replace_all(text, r"(^#+\s.+?$)|```[\D\d\s]+?```", escapeshape)
    text = re.sub(r"#", "\#", text)
    text = replace_all(
        text, r"(\+)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeplus
    )
    text = re.sub(r"\n{1,2}(\s*)-\s", "\n\n\\1• ", text)
    text = re.sub(r"\n{1,2}(\s*\d{1,2}\.\s)", "\n\n\\1", text)
    text = replace_all(
        text, r"(-)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeminus
    )
    text = re.sub(r"```([\D\d\s]+?)```", "@@@\\1@@@", text)
    text = replace_all(text, r"(``)", escapebackquote)
    text = re.sub(r"\@{3}([\D\d\s]+?)\@{3}", "```\\1```", text)
    text = re.sub(r"=", "\=", text)
    text = re.sub(r"\|", "\|", text)
    text = re.sub(r"{", "\{", text)
    text = re.sub(r"}", "\}", text)
    text = re.sub(r"\.", "\.", text)
    text = re.sub(r"!", "\!", text)
    return text

# Prevent "create_convo" function from blocking the event loop.
async def make_new_gemini_convo():
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        convo = model.start_chat()
        return convo

    convo = await loop.run_in_executor(None, create_convo)
    return convo

async def make_new_gemini_pro_convo():
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
        )
        convo = model.start_chat()
        return convo

    convo = await loop.run_in_executor(None, create_convo)
    return convo

# Prevent "send_message" function from blocking the event loop.
async def send_message(player, message):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, player.send_message, message)

# Prevent "model.generate_content" function from blocking the event loop.
async def async_generate_content(model, contents):
    loop = asyncio.get_running_loop()

    def generate():
        return model.generate_content(contents=contents)

    response = await loop.run_in_executor(None, generate)
    return response

async def gemini(bot, message, m):
    player = None
    if str(message.from_user.id) not in gemini_player_dict:
        player = await make_new_gemini_convo()
        gemini_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        await send_message(player, m)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)
    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

async def gemini_pro(bot, message, m):
    player = None
    if str(message.from_user.id) not in gemini_pro_player_dict:
        player = await make_new_gemini_pro_convo()
        gemini_pro_player_dict[str(message.from_user.id)] = player
    else:
        player = gemini_pro_player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        await send_message(player, m)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)
    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

# State management dictionary
user_state = {}
bug_reports = {}

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
    parser.add_argument("google_gemini_key", help="Google Gemini API key")
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
            telebot.types.BotCommand("gemini", "Using gemini-1.5-flash"),
            telebot.types.BotCommand("gemini_pro", "Using gemini-1.5-pro"),
            telebot.types.BotCommand("clear", "Clear all history"),
            telebot.types.BotCommand("switch", "Switch default model"),
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
            await bot.reply_to(message, escape("Welcome, you can ask me questions now. \nFor example: `Who is john lennon?`"), parse_mode="MarkdownV2")
        except IndexError:
            await bot.reply_to(message, error_info)

    @bot.message_handler(commands=["gemini"])
    async def gemini_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
        except IndexError:
            await bot.reply_to(message, escape("Please add what you want to say after /gemini. \nFor example: `/gemini Who is john lennon?`"), parse_mode="MarkdownV2")
            return
        await gemini(bot, message, m)

    @bot.message_handler(commands=["gemini_pro"])
    async def gemini_pro_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
        except IndexError:
            await bot.reply_to(message, escape("Please add what you want to say after /gemini_pro. \nFor example: `/gemini_pro Who is john lennon?`"), parse_mode="MarkdownV2")
            return
        await gemini_pro(bot, message, m)

    @bot.message_handler(commands=["clear"])
    async def clear_handler(message: Message):
        if str(message.from_user.id) in gemini_player_dict:
            del gemini_player_dict[str(message.from_user.id)]
        if str(message.from_user.id) in gemini_pro_player_dict:
            del gemini_pro_player_dict[str(message.from_user.id)]
        await bot.reply_to(message, "Your history has been cleared")

    @bot.message_handler(commands=["switch"])
    async def switch_handler(message: Message):
        if message.chat.type != "private":
            await bot.reply_to(message, "This command is only for private chat!")
            return
        if str(message.from_user.id) not in default_model_dict:
            default_model_dict[str(message.from_user.id)] = False
            await bot.reply_to(message, "Now you are using gemini-1.5-pro")
            return
        if default_model_dict[str(message.from_user.id)]:
            default_model_dict[str(message.from_user.id)] = False
            await bot.reply_to(message, "Now you are using gemini-1.5-pro")
        else:
            default_model_dict[str(message.from_user.id)] = True
            await bot.reply_to(message, "Now you are using gemini-1.5-flash")

    @bot.message_handler(func=lambda message: message.chat.type == "private" and not message.text.startswith(("/", ".")), content_types=['text'])
    async def gemini_private_handler(message: Message):
        m = message.text.strip()
        if str(message.from_user.id) not in default_model_dict:
            default_model_dict[str(message.from_user.id)] = True
            await gemini(bot, message, m)
        else:
            if default_model_dict[str(message.from_user.id)]:
                await gemini(bot, message, m)
            else:
                await gemini_pro(bot, message, m)

    @bot.message_handler(content_types=["photo"])
    async def gemini_photo_handler(message: Message) -> None:
        if message.chat.type != "private":
            s = message.caption
            if not s or not (s.startswith("/gemini")):
                return
            try:
                prompt = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
                file_path = await bot.get_file(message.photo[-1].file_id)
                sent_message = await bot.reply_to(message, download_pic_notify)
                downloaded_file = await bot.download_file(file_path.file_path)
            except Exception:
                traceback.print_exc()
                await bot.reply_to(message, error_info)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
            }
            try:
                await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                response = await async_generate_content(model, contents)
                await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception:
                traceback.print_exc()
                await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else:
            s = message.caption if message.caption else ""
            try:
                prompt = s.strip()
                file_path = await bot.get_file(message.photo[-1].file_id)
                sent_message = await bot.reply_to(message, download_pic_notify)
                downloaded_file = await bot.download_file(file_path.file_path)
            except Exception:
                traceback.print_exc()
                await bot.reply_to(message, error_info)
            model = genai.GenerativeModel("gemini-pro-vision")
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
            }
            try:
                await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                response = await async_generate_content(model, contents)
                await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception:
                traceback.print_exc()
                await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    print("Starting Gemini_Telegram_Bot.")
    logging.info("Starting Gemini_Telegram_Bot.")
    await bot.polling(none_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
