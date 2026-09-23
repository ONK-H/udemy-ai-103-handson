"""L2-7 自作関数を FunctionTool でエージェントに登録して使わせる。

FunctionTool でスキーマを宣言し、エージェント定義に登録する。
function_call → アプリが実行 → function_call_output → 最終回答 のループを、
function_call が出なくなるまで回す。エラーもモデルに返す。認証はキーレス。finally で後片付け。

使い方:
    python main.py                                  # 既定：「商品 X1 の在庫はいくつ？」
    python main.py "商品 X1 と M27 の在庫を比べて。"   # 2つの商品を調べる
    python main.py "商品 Z9 の在庫は？"               # 存在しない商品（エラーをモデルに返す）
"""

import os
import sys
import json
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from openai.types.responses.response_input_param import FunctionCallOutput
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-4.1-mini")
AGENT_NAME = "inventory-agent"
MAX_TURNS = 5  # ツール呼び出しの往復の上限（無限ループ防止）

# --- 自作関数の実体（アプリ側で実行。在庫はモック） ---
_STOCK = {"X1": 3, "X2": 0, "M27": 12}


def get_inventory(product_code: str) -> dict:
    """商品コードの在庫数を返す"""
    if product_code not in _STOCK:
        return {"error": f"unknown product_code: {product_code}"}  # エラーもモデルに返す
    return {"product_code": product_code, "stock": _STOCK[product_code]}


# --- FunctionTool でスキーマを宣言（実体は上の関数。宣言と実体は別物） ---
inv_tool = FunctionTool(
    name="get_inventory",
    description="商品コードの在庫数を取得する。型番が分かるときに使う。",
    parameters={
        "type": "object",
        "properties": {"product_code": {"type": "string", "description": "商品コード（例 X1）"}},
        "required": ["product_code"],
        "additionalProperties": False,
    },
    strict=True,
)


def run_tool(item) -> dict:
    """function_call を1件実行する。引数が壊れていても落とさず、エラーとして返す。"""
    try:
        args = json.loads(item.arguments)
    except json.JSONDecodeError as ex:
        return {"error": f"invalid arguments: {ex}"}
    print(f"[ツール要求] {item.name}({args})")  # モデルは「呼びたい」と依頼するだけ
    if item.name != "get_inventory":
        return {"error": f"unknown tool: {item.name}"}
    result = get_inventory(**args)  # 実行するのはアプリ
    print(f"[実行] {item.name} -> {result}")
    return result


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
    question = sys.argv[1] if len(sys.argv) > 1 else "商品 X1 の在庫はいくつ？"

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    agent = conversation = None
    try:
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT,
                instructions=("在庫を聞かれたら get_inventory ツールで調べてください。"
                              "在庫の数は推測せず、ツールの結果だけを使い、日本語で1〜2行で答えてください。"),
                tools=[inv_tool],
            ),
        )
        print(f"エージェント作成: name={agent.name}, version={agent.version}, model={MODEL_DEPLOYMENT}")
        conversation = openai.conversations.create()
        ref = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}

        print(f"\nUSER> {question}")
        res = openai.responses.create(input=question, conversation=conversation.id, extra_body=ref)

        for turn in range(1, MAX_TURNS + 1):  # function_call が出なくなるまで往復する
            calls = [i for i in res.output if getattr(i, "type", None) == "function_call"]
            print(f"[応答{turn}] function_call {len(calls)} 件")
            if not calls:
                break
            input_list = [FunctionCallOutput(
                type="function_call_output", call_id=c.call_id,
                output=json.dumps(run_tool(c), ensure_ascii=False)) for c in calls]
            res = openai.responses.create(input=input_list, conversation=conversation.id, extra_body=ref)

        print(f"AI> {res.output_text}")
    except Exception as ex:  # 教育目的の素朴なエラーハンドリング
        print(f"[エラー] {ex}")
    finally:
        # 会話と、作成したエージェントの版を削除し、残っていないことを確かめる
        if conversation:
            openai.conversations.delete(conversation_id=conversation.id)
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
            left = [a.name for a in project.agents.list() if a.name == agent.name]
            print(f"会話とエージェントを削除しました（残り: {len(left)} 件）")


if __name__ == "__main__":
    main()
