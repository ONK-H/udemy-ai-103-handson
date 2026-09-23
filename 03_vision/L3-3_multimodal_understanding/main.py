"""L3-3 実践: 画像をマルチモーダルモデルに渡してキャプション＋視覚QA。

同じ画像入力(Chat Completions の content に テキスト＋画像)の上で、
プロンプトを変えるだけで「簡潔キャプション」「物体の列挙(視覚QA)」「alt-text」を作り分ける。
画像は base64 データURIで渡す。認証はキーレス(DefaultAzureCredential)。

使い方:
    python main.py                      # 3つのタスクをまとめて実行
    python main.py "窓はいくつありますか？"  # 自分の質問で視覚QA（1問）
"""

import os
import sys
import base64
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-5.4")  # vision 対応モデルのデプロイ名
IMAGE_DETAIL = os.getenv("IMAGE_DETAIL", "auto")     # 画像の解像度の扱い: auto / low / high
IMAGE_PATH = "sample.jpg"

# キーレス認証で Foundry プロジェクトに接続し、OpenAI クライアントを取得
project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
client = project.get_openai_client()


def to_data_uri(path: str) -> str:
    """ローカル画像を base64 データURIに変換する。"""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def ask_about_image(image_path: str, prompt: str) -> tuple[str, int]:
    """テキスト＋画像のメッセージを vision 対応モデルに渡し、回答と入力トークン数を返す。"""
    res = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": to_data_uri(image_path), "detail": IMAGE_DETAIL},
                    },
                ],
            }
        ],
    )
    return res.choices[0].message.content, res.usage.prompt_tokens


if __name__ == "__main__":
    print(f"デプロイ: {VISION_MODEL} ／ 画像: {IMAGE_PATH} ／ detail: {IMAGE_DETAIL}")

    if len(sys.argv) > 1:
        # 自分の質問で視覚QA（答えは短く）
        tasks = {"視覚QA": " ".join(sys.argv[1:]) + " 1〜2文で答えてください。"}
    else:
        # 同じ画像に対し、プロンプトを変えるだけで複数の視覚理解タスクを行う
        tasks = {
            "簡潔キャプション": "この画像を一文で簡潔に説明してください。",
            "物体の列挙(視覚QA)": "この画像に写っている主な物体を、5つまで箇条書きで列挙してください。",
            "alt-text": "視覚障害者のスクリーンリーダー向けに、この画像のalt-textを1文で作成してください。",
        }

    try:
        for label, prompt in tasks.items():
            answer, prompt_tokens = ask_about_image(IMAGE_PATH, prompt)
            print(f"\n===== {label} =====（入力 {prompt_tokens} トークン）")
            print(answer)
    except Exception as ex:
        print(f"エラー: {ex}")
