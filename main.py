import json
import requests
import tldextract
from bs4 import BeautifulSoup
from urllib.parse import urlsplit
from urllib.parse import urlparse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

TELEGRAM_BOT_TOKEN = "BOT_TOKEN"
CHATGPT_TOKEN = "CHAT_GPT_API_KEY"

def load_allowed_users(filename):
    with open(filename, 'r') as file:
        allowed_users = [int(line.strip()) for line in file.readlines()]
    return allowed_users

def load_credits(filename):
    with open(filename, 'r') as file:
        credits = [line.strip() for line in file.readlines()]
    return credits

ALLOWED_USERS = load_allowed_users('user.txt')
CREDITS = load_credits('credits.txt')

def scraper(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.message.chat_id not in ALLOWED_USERS:
        return

    context.user_data["state"] = "scraper_api_key"
    query.edit_message_text(text="Please enter your API key:")

def search_yellowpages(business_type, city, pages):
    base_url = "https://www.yellowpages.com"
    results = []

    for page in range(1, pages + 1):
        search_url = f"{base_url}/search?search_terms={business_type}&geo_location_terms={city}&page={page}"
        response = requests.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        for item in soup.find_all("div", class_="result"):
            try:
                name = item.find("a", class_="business-name").text
                address = item.find("div", class_="street-address").text.strip()
                phone = item.find("div", class_="phone").text.strip()
                website_tag = item.find("a", class_="track-visit-website")
                website = website_tag['href'] if website_tag else "No website available"
                results.append(f"======================\nName: {name}\nAddress: {address}\nPhone: {phone}\nURL: {website}\n")
            except AttributeError:
                continue

    return results

def split_results(results, max_length=4096):
    chunks = []
    current_chunk = ""

    for result in results:
        if len(current_chunk) + len(result) > max_length:
            chunks.append(current_chunk)
            current_chunk = ""

        current_chunk += result

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def biz(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter the type of business you're looking for:")
    context.user_data["state"] = "awaiting_business_type"

def start(update: Update, context: CallbackContext):
    if update.message.chat_id not in ALLOWED_USERS:
        join_button = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Join",
                        url="https://t.me/+QO3d44qHuL4xMGJl",
                    ),
                ],
            ]
        )
        update.message.reply_text("Please join our channel to access this bot.", reply_markup=join_button)
        context.bot.send_message(chat_id=update.message.chat_id, text="Buy this https://t.me/c/1526652665/1768 to get access to this Bot")
    else:
        keyboard = [
            [
                InlineKeyboardButton("Chat With Me", callback_data="Chat With Me"),
                InlineKeyboardButton("Search Biz", callback_data="search_biz"),
                InlineKeyboardButton("Scraper", callback_data="scraper"),
            ],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Hi I am Levi Ackerman.\n\nPlease choose an option:", reply_markup=reply_markup)

def gpt4_response(prompt):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHATGPT_TOKEN}",
    }

    data = {
        "model": "text-davinci-003",
        "prompt": prompt,
        "max_tokens": 4000,
        "temperature": 1.0,
    }

    response = requests.post(
        "https://api.openai.com/v1/completions",
        headers=headers,
        data=json.dumps(data),
        verify=False,
    )

    response_json = response.json()
    return response_json["choices"][0]["text"]

def validate_hunter_api_key(api_key):
    url = f"https://api.hunter.io/v2/account?api_key={api_key}"
    try:
        response = requests.get(url)
        data = response.json()
        if "data" in data:
            return True
    except Exception as e:
        pass
    return False

import requests

def get_emails_from_domain(api_key, domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

    data = response.json()

    if "errors" in data:
        if data["errors"][0]["id"] == "restricted_account":
            return "restricted_account"

    emails = []
    for email_obj in data.get("data", {}).get("emails", []):
        emails.append(email_obj["value"])

    return emails

def extract_domain_from_url(url):
    parsed_url = urlparse(url)
    extracted = tldextract.extract(parsed_url.netloc)
    domain = '.'.join([extracted.domain, extracted.suffix])
    return domain
    
def handle_message(update: Update, context: CallbackContext):
    if update.message.chat_id not in ALLOWED_USERS:
        return
    
    text = update.message.text
    state = context.user_data.get("state")

    if state == "awaiting_business_type":
        context.user_data["business_type"] = text
        update.message.reply_text("Please enter the city:")
        context.user_data["state"] = "awaiting_city"

    elif state == "awaiting_city":
        context.user_data["city"] = text
        update.message.reply_text("Please enter the number of pages to search:")
        context.user_data["state"] = "awaiting_pages"

    elif state == "awaiting_pages":
        pages = int(text)
        city = context.user_data["city"]
        business_type = context.user_data["business_type"]
        results = search_yellowpages(business_type, city, pages)

        if results:
            result_chunks = split_results(results)
            for chunk in result_chunks:
                update.message.reply_text(chunk)
        else:
            update.message.reply_text("No businesses found.")
        context.user_data["state"] = None

    elif state == "scraper_api_key":
        if validate_hunter_api_key(text):
            context.user_data["hunter_api_key"] = text
            context.user_data["state"] = "scraper_domain"
            update.message.reply_text("Please enter the domain you want to scrape emails from:")
        else:
            update.message.reply_text("Invalid API key. Please enter a valid API key:")

    elif state == "scraper_domain":
        domain_or_url = text
        domain = extract_domain_from_url(domain_or_url)
        if not domain:
            domain = domain_or_url

        context.user_data["domain"] = domain
        context.user_data["state"] = None

        hunter_api_key = context.user_data["hunter_api_key"]
        emails = get_emails_from_domain(hunter_api_key, domain)

        if emails == "restricted_account":
            update.message.reply_text("Your API key is restricted.")
        elif emails:
            update.message.reply_text("Emails found:\n" + '\n'.join(emails))
            for email in emails:
                update.message.reply_text(email)
        else:
            update.message.reply_text("No emails found for the given domain.")
    else:
        input_text = update.message.text
        output_text = gpt4_response(input_text)

        for word in CREDITS:
            output_text = output_text.replace(word, "Hackers Assemble")

        output_text += "\n\n@hackers_assemble"
        update.message.reply_text(output_text)


def menu_actions(update: Update, context: CallbackContext):
    if update.callback_query.message.chat_id not in ALLOWED_USERS:
        return

    query = update.callback_query
    query.answer()

    chat_id = query.message.chat_id

    if query.data == "Chat With Me":
        context.bot.send_message(chat_id=chat_id, text="Hi I am Levi. I am your assistent, send me a task.\n\n@hackers_assemble")
        context.user_data["selected_option"] = "Chat With Me"
    elif query.data == "scraper":
        context.bot.send_message(chat_id=chat_id, text="Please enter your API key:")
        context.user_data["state"] = "scraper_api_key"
        context.user_data["selected_option"] = "scraper"
    elif query.data == "search_biz":
        context.bot.send_message(chat_id=chat_id, text="Please enter the type of business you're looking for:")
        context.user_data["state"] = "awaiting_business_type"
        context.user_data["selected_option"] = "search_biz"


def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("biz", biz))
    dp.add_handler(CallbackQueryHandler(menu_actions))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(scraper, pattern="^scraper$"))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
