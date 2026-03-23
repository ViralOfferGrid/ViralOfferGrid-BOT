import json
import os
import requests
import re
import base64
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GPLINKS_API = os.environ.get("GPLINKS_API", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "ViralOfferGrid/ViralOfferGrid-BOT")


def shorten_url(url):
    if not GPLINKS_API:
        return url
    try:
        api_url = f"https://api.gplinks.com/api?api={GPLINKS_API}&url={url}&format=text"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
    except Exception:
        pass
    return url


def extract_urls(text):
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)


def get_posts():
    if not GITHUB_TOKEN:
        return [], None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/posts.json"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content), data["sha"]
        elif response.status_code == 404:
            return [], "new"
    except Exception:
        pass
    return [], None


def save_posts(posts, sha):
    if not GITHUB_TOKEN:
        return False
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/posts.json"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    content = base64.b64encode(
        json.dumps(posts, ensure_ascii=False, indent=2).encode()
    ).decode()
    payload = {
        "message": f"New post - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": content,
    }
    if sha and sha != "new":
        payload["sha"] = sha
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        return response.status_code in (200, 201)
    except Exception:
        return False


def send_message(chat_id, text, parse_mode=None):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass


def process_message(message):
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text") or message.get("caption", "")
    if not text or not chat_id:
        return

    urls = extract_urls(text)
    processed_text = text
    short_urls = []

    for url in urls:
        short = shorten_url(url)
        processed_text = processed_text.replace(url, short)
        short_urls.append({"original": url, "short": short})

    post = {
        "id": int(datetime.now().timestamp()),
        "text": processed_text,
        "original_text": text,
        "short_urls": short_urls,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": int(datetime.now().timestamp()),
        "chat_id": str(chat_id),
    }

    posts, sha = get_posts()

    if sha is None:
        send_message(chat_id, "❌ GitHub টোকেন বা repo সেট করুন!")
        return

    posts.insert(0, post)
    posts = posts[:100]

    if save_posts(posts, sha):
        short_list = "\n".join([u["short"] for u in short_urls[:3]]) or "(কোনো URL নেই)"
        reply = f"✅ পোস্ট সফল!\n\n🔗 Short URLs:\n{short_list}"
        send_message(chat_id, reply)
    else:
        send_message(chat_id, "❌ পোস্ট সেভ করতে সমস্যা হয়েছে!")


def set_webhook(host):
    webhook_url = f"https://{host}/.netlify/functions/bot"
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}"
    try:
        response = requests.get(telegram_url, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def handler(event, context):
    method = event.get("httpMethod", "GET")

    if method == "GET":
        params = event.get("queryStringParameters") or {}
        if params.get("set"):
            host = (event.get("headers") or {}).get("host", "")
            result = set_webhook(host)
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Webhook set!", "result": result}),
            }
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "BD ToolX Bot চলছে!"}),
        }

    if method == "POST":
        try:
            body = json.loads(event.get("body") or "{}")
            message = body.get("message") or body.get("channel_post")
            if message:
                process_message(message)
            return {"statusCode": 200, "body": "OK"}
        except Exception as e:
            return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    return {"statusCode": 405, "body": "Method Not Allowed"}
