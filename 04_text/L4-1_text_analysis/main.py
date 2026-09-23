"""L4-1 実践: レビュー文から「感情＋エンティティ＋要約」を構造化JSONで抽出（生成プロンプト版）。

Responses API の structured outputs（json_schema / strict）で、
スキーマに準拠したJSONを取り出す。キーレス認証（DefaultAzureCredential）。
"""

import os
import sys
import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")

# 出力スキーマ（JSON Schema）。構造化出力の制約：
#   - すべてのフィールドを required にする
#   - object には additionalProperties: false を付ける
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sentiment": {
            "type": "string",
            "enum": ["positive", "negative", "neutral", "mixed"],
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["text", "category"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["sentiment", "entities", "summary"],
}

SYSTEM_PROMPT = (
    "あなたは商品レビューの分析器です。入力レビューについて、"
    "全体の感情、登場する主要エンティティ（製品名・機能・場所・組織など）とそのカテゴリ、"
    "および日本語1〜2文の要約を返してください。出力は指定スキーマのJSONのみ。"
)

# キーレス認証（az login 済みの資格情報）
project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
client = project.get_openai_client()  # OpenAI 互換クライアント（Responses API）


def analyze_review(text: str) -> dict:
    """1件のレビューを構造化JSONに分析して返す。"""
    # システムメッセージは instructions で渡す（system の直後に type なしの user を並べると 400 になるため）
    response = client.responses.create(
        model=MODEL_DEPLOYMENT,
        instructions=SYSTEM_PROMPT,
        input=text,
        text={
            "format": {
                "type": "json_schema",
                "name": "review_analysis",
                "strict": True,
                "schema": REVIEW_SCHEMA,
            }
        },
    )
    # 構造化出力なのでスキーマ準拠のJSON文字列が返る → そのままパース
    return json.loads(response.output_text)


def to_display(result: dict) -> str:
    """画面で読みやすいように、entities の要素だけ1行1件にして整形する（中身は同じJSON）。"""
    lines = [
        "{",
        f'  "sentiment": {json.dumps(result["sentiment"], ensure_ascii=False)},',
        '  "entities": [',
    ]
    ents = [json.dumps(e, ensure_ascii=False) for e in result["entities"]]
    lines += [f"    {e}{',' if i < len(ents) - 1 else ''}" for i, e in enumerate(ents)]
    lines += ["  ],", f'  "summary": {json.dumps(result["summary"], ensure_ascii=False)}', "}"]
    return "
".join(lines)


def main():
    with open("reviews.json", encoding="utf-8") as f:
        reviews = json.load(f)

    # 引数でレビューの番号を選べる（例: python main.py 1 3）。省略すると全件
    picks = [int(a) for a in sys.argv[1:]] or range(1, len(reviews) + 1)
    print(f"モデル（デプロイ名）: {MODEL_DEPLOYMENT}")
    for i in picks:
        review = reviews[i - 1]
        print(f"\n=== レビュー {i} ===")
        print(f"入力: {review}")
        try:
            result = analyze_review(review)
            print("分析結果(JSON):")
            print(to_display(result))
        except Exception as ex:
            print(f"[エラー] {ex}")


if __name__ == "__main__":
    main()
