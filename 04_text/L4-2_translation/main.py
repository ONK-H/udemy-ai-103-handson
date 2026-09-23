"""L4-2 実践: 多言語翻訳とトーン制御の比較。

Azure Translator テキスト翻訳API（GA 2026-06-06）で
 ① NMT で多言語翻訳（deploymentName 省略＝general）
 ② LLM でトーン制御（formal vs informal）
を実行する。キーレス認証（Entra ID）を第一選択、キーはフォールバック。
  python main.py            ① と ② を実行
  python main.py nmt-tone   NMT（deploymentName なし）に tone を付けても訳文が変わらないことを確かめる
"""

import os
import sys
import requests
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("TRANSLATOR_ENDPOINT", "").rstrip("/")
KEY = os.getenv("TRANSLATOR_KEY")
REGION = os.getenv("TRANSLATOR_REGION")
LLM_DEPLOYMENT = os.getenv("LLM_DEPLOYMENT")

API_VERSION = "2026-06-06"
URL = f"{ENDPOINT}/translator/text/translate?api-version={API_VERSION}"

# キーレス（Entra ID）を第一選択。KEY があればキー認証にフォールバック。
_credential = DefaultAzureCredential()


def auth_headers() -> dict:
    if KEY:
        h = {"Ocp-Apim-Subscription-Key": KEY}
        if REGION:
            h["Ocp-Apim-Subscription-Region"] = REGION
        return h
    # キーレス：Cognitive Services スコープのトークンを取得
    token = _credential.get_token("https://cognitiveservices.azure.com/.default")
    return {"Authorization": f"Bearer {token.token}"}


def translate(text: str, targets: list) -> dict:
    """targets: [{"language":"es","deploymentName":...,"tone":...}, ...]"""
    headers = {"Content-Type": "application/json", **auth_headers()}
    body = {"inputs": [{"text": text, "language": "ja", "targets": targets}]}
    resp = requests.post(URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def nmt_tone_check(text: str):
    """NMT の要素に tone を付けても、エラーにならず黙って無視されることを確かめる。"""
    print("=== NMT に tone を付けた場合 ===")
    for tone in ("formal", "informal"):
        result = translate(text, [{"language": "en", "tone": tone}])
        print(f"  [{tone}] {result['value'][0]['translations'][0]['text']}")


def main():
    text = "ご来店ありがとうございます。本日のおすすめをご案内します。"
    if sys.argv[1:] == ["nmt-tone"]:
        nmt_tone_check(text)
        return

    # ① NMT で多言語翻訳（deploymentName 省略＝general＝NMT）
    print("=== ① NMT 多言語翻訳 ===")
    print(f"原文: {text}")
    result = translate(text, [{"language": "en"}, {"language": "es"}, {"language": "de"}])
    for tr in result["value"][0]["translations"]:
        print(f"  [{tr['language']}] {tr['text']}")

    # ② LLM でトーン制御（formal vs informal）。LLM はデプロイ名が必要
    if not LLM_DEPLOYMENT:
        print("\n[skip] LLM_DEPLOYMENT 未設定のため、トーン比較はスキップします。")
        return
    print(f"\n=== ② LLM トーン制御（英語：formal vs informal／デプロイ: {LLM_DEPLOYMENT}）===")
    result = translate(text, [
        {"language": "en", "deploymentName": LLM_DEPLOYMENT, "tone": "formal"},
        {"language": "en", "deploymentName": LLM_DEPLOYMENT, "tone": "informal"},
    ])
    translations = result["value"][0]["translations"]
    print(f"  [formal]   {translations[0]['text']}")
    print(f"  [informal] {translations[1]['text']}")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as ex:
        print(f"[HTTPエラー] {ex.response.status_code}: {ex.response.text}")
    except Exception as ex:
        print(f"[エラー] {ex}")
