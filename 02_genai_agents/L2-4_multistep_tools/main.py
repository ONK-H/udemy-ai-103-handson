"""L2-4 ツールをつなぐ多段フロー（検索→計算→整形）。

Responses API の function calling ループを手で回し、複数の自作ツールを
モデルが順番に呼ぶ多段推論を観察する。実行するのはアプリ（モデルではない）。
認証はキーレス（DefaultAzureCredential + az login）。外部サービス不要（モック）。
"""

import os
import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini")

# --- 自作ツールの実装（モック）。実行するのはアプリ（モデルではない） ---
_INVENTORY = {
    "ノートPC": [{"name": "X1", "price": 180000, "qty": 3}, {"name": "X2", "price": 220000, "qty": 2}],
    "モニター": [{"name": "M27", "price": 35000, "qty": 5}],
}


def search_products(category: str):
    """カテゴリの在庫一覧を返す"""
    return _INVENTORY.get(category, [])


def calc_total(items: list):
    """price*qty の合計を返す"""
    return sum(i["price"] * i["qty"] for i in items)


TOOL_IMPL = {"search_products": search_products, "calc_total": calc_total}

# --- ツール定義（JSONスキーマ。Responses API の function ツール形式） ---
tools = [
    {
        "type": "function",
        "name": "search_products",
        "description": "指定カテゴリの在庫一覧（name/price/qty）を取得する",
        "parameters": {
            "type": "object",
            "properties": {"category": {"type": "string", "description": "商品カテゴリ名"}},
            "required": ["category"],
        },
    },
    {
        "type": "function",
        "name": "calc_total",
        "description": "在庫一覧の price*qty の合計金額を計算する",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                            "qty": {"type": "number"},
                        },
                    },
                }
            },
            "required": ["items"],
        },
    },
]


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    messages = [{"role": "user", "content": "ノートPCの在庫の合計金額を計算して、結果を日本語でまとめて。"}]

    for _step in range(6):  # 無限ループ防止の上限
        res = openai.responses.create(model=MODEL_DEPLOYMENT, input=messages, tools=tools)
        calls = [o for o in res.output if getattr(o, "type", None) == "function_call"]
        if not calls:
            print("\n=== 最終回答 ===")
            print(res.output_text)
            break
        # モデルの出力（function_call と、推論モデルなら reasoning 項目）をそのまま入力に積む
        messages += res.output
        for call in calls:
            name = call.name
            args = json.loads(call.arguments)
            print(f"[ツール呼び出し] {name}({args})")
            try:
                result = TOOL_IMPL[name](**args)
            except Exception as ex:  # 信頼性：エラーをモデルに返す
                result = {"error": str(ex)}
            messages.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(result, ensure_ascii=False),
            })
    else:
        print("[警告] ツール呼び出しの上限に達しました。")


if __name__ == "__main__":
    main()
