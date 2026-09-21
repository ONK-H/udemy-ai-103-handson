"""L2-11 エージェントにトレースを仕込み、失敗ケースを観測して原因分析。

server-side トレース（App Insights 接続）＋ client-side 計装（OpenTelemetry）。
わざと存在しない型番を照会してツールが error を返す失敗を起こし、
Foundry ポータルの Traces で span を辿って原因を分析する。
認証はキーレス。finally で後片付け。
"""

import os
import json

# client-side 計装の設定は「計装より前」に行う（import より先に環境変数を立てる）
os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] = "true"            # GenAI トレース（プレビュー）を有効化
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"  # プロンプト内容も記録（個人情報に注意）

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from azure.ai.projects.telemetry import trace_function
from openai.types.responses.response_input_param import FunctionCallOutput
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-4.1-mini")

_STOCK = {"X1": 3}


@trace_function("get_inventory")  # 自前のツール関数も span にする（引数と戻り値が記録される）。() を省略すると動かない
def get_inventory(product_code: str) -> dict:
    if product_code not in _STOCK:
        err = f"unknown product_code: {product_code}"
        trace.get_current_span().set_attribute("app.tool_error", err)  # code.* は出ないので別名で足す
        return {"error": err}  # 失敗を再現
    return {"product_code": product_code, "stock": _STOCK[product_code]}


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    # client-side 計装：接続済み App Insights へテレメトリを送る
    conn = project.telemetry.get_application_insights_connection_string()
    configure_azure_monitor(connection_string=conn, sampling_ratio=1.0)  # 全件記録する（既定は間引く）
    tracer = trace.get_tracer(__name__)

    openai = project.get_openai_client()  # 計装の「後」に取得する（trace context が伝播する）

    tool = FunctionTool(
        name="get_inventory", description="在庫数を取得",
        parameters={"type": "object", "properties": {"product_code": {"type": "string"}},
                    "required": ["product_code"], "additionalProperties": False}, strict=True)

    agent = None
    try:
        with tracer.start_as_current_span("l2-11-inventory-scenario"):  # 1回の実行を1つの trace にまとめる
            agent = project.agents.create_version(
                agent_name="traced-agent",
                definition=PromptAgentDefinition(
                    model=MODEL_DEPLOYMENT,
                    instructions="在庫照会には get_inventory を使ってください。", tools=[tool]))
            conversation = openai.conversations.create()
            # name と id の両方を渡すと、ポータルでエージェントとトレースが紐づく
            ref = {"agent_reference": {"name": agent.name, "id": agent.id, "type": "agent_reference"}}

            # わざと存在しない型番（ZZ9）を照会 → ツールが error を返す失敗ケース
            res = openai.responses.create(input="ZZ9 の在庫は？", conversation=conversation.id, extra_body=ref)
            input_list = []
            for item in res.output:
                if getattr(item, "type", None) == "function_call":
                    result = get_inventory(**json.loads(item.arguments))
                    print(f"[tool] {item.name} -> {result}")
                    input_list.append(FunctionCallOutput(
                        type="function_call_output", call_id=item.call_id,
                        output=json.dumps(result, ensure_ascii=False)))
            if input_list:
                final = openai.responses.create(input=input_list, conversation=conversation.id, extra_body=ref)
                print(f"AI> {final.output_text}")
            else:
                print(f"AI> {res.output_text}")
            print(f"conversation id: {conversation.id}")
        print("Foundry ポータルの Agents → traced-agent → Traces で trace を確認（取り込みに2〜5分）")
        input("確認できたら Enter を押してください（エージェントを削除して終了）> ")
    finally:
        # エージェントを消すとポータルの Traces から辿れなくなるので、確認のあとに削除する（conversation は残す）
        if agent:
            project.agents.delete_version(agent_name=agent.name, agent_version=agent.version)


if __name__ == "__main__":
    main()
