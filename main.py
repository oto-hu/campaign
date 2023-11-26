import requests
from bs4 import BeautifulSoup
from summarizer import Summarizer
import base64
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# 監視するサイトのリストのURLを入力
# 複数入力可能
sites = [""]

# キャンペーンを示す可能性のあるキーワードのリスト
keywords = ["セール", "キャンペーン", "割引", "期間限定"]

def get_campaign_links(soup, keyword):
    # キーワードを含むテキストを持つaタグをすべて取得
    links = soup.find_all('a', string=lambda text: (text and keyword in text))
    return [link['href'] for link in links if link.has_attr('href')]

def check_campaign(site):
    found_campaigns = set()  # 重複を避けるためのセット
    campaign_summaries = []  # 見つかったキャンペーンのリンクとその要約のリスト

    try:
        response = requests.get(site)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        for keyword in keywords:
            campaign_links = get_campaign_links(soup, keyword)
            for link in campaign_links:
                # 絶対URLへの変換（必要に応じて）
                if not link.startswith('http'):
                    link = site.rstrip('/') + '/' + link.lstrip('/')
                # 重複を避けるためにセットに追加
                if link not in found_campaigns:  # この行を追加
                    found_campaigns.add(link)  # この行を変更
                    # ここで要約を取得し、キャンペーン情報リストに追加
                    summary = summarize_with_nlp(link)
                    if summary:
                        campaign_summaries.append((link, summary))

    except requests.RequestException:
        print(f"{site} のチェック中にエラーが発生しました。")
        
    return campaign_summaries  # キャンペーンのリンクとその要約のリストを返す

model = Summarizer()
def summarize_with_nlp(url):
    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()

        # 前処理: 余分な空白や改行を取り除く
        text = ' '.join(text.split())

        # BERTモデルを使った要約
        summary = model(text, min_length=60, max_length=150)  # min_lengthとmax_lengthは調整可能

        return summary
    except requests.RequestException:
        print(f"{url} の要約中にエラーが発生しました。")
        return None

# OAuth2の設定
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service

def send_email(subject, body):
    service = get_service()
    
    # MIMEヘッダをUTF-8でエンコード
    headers = f"To:自身のアドレスを入力\nSubject: =?utf-8?B?{base64.b64encode(subject.encode('utf-8')).decode()}?=\n\n"
    raw_message = base64.urlsafe_b64encode((headers + body).encode('utf-8')).decode('utf-8')
    message = {
        'raw': raw_message
    }

    service.users().messages().send(userId='me', body=message).execute()

if __name__ == "__main__":
    all_campaign_summaries = []
    for site in sites:
        summaries = check_campaign(site)
        all_campaign_summaries.extend(summaries)
    
    if all_campaign_summaries:
        message_body = "\n\n".join([f"キャンペーンが見つかりました！\nリンク: {link}\n要約: {summary}" for link, summary in all_campaign_summaries])
        send_email("キャンペーンの通知", message_body)
