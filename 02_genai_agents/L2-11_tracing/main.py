"""L2-11 エージェントにトレースを仕込み、失敗ケースを観測して原因を分析する。

client-side 計装（OpenTelemetry → プロジェクトに接続した Application Insights）で、
エージェントの呼び出しと自前のツール関数を span にする。
わざと存在しない商品コードを聞いてツールに error を返させ、
「例外にならない静かな失敗」を、トレース（KQL）から見つける。認証はキーレス。finally で後片付け。

使い方:
    python main.py                        # 既定：「商品 ZZ9 の在庫は？」（存在しない商品 → ツールが error を返す）
    python main.py "商品 X1 の在庫は？"     # 成功する例と見比べる
"""

import os
import sys
import json

from dotenv import load_dotenv

load_dotenv()

# GenAI トレース計測（プレビュー）の設定は、計測を有効にする instrument() より前に行う
os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
# プロンプトと応答の本文も記録する（個人情報を含みうるので開発時だけ）
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
# このアプリの名前。Application Insights の cloud_RoleName になり、サービス側の span と見分けられる
os.environ.setdefault("OTEL_SERVICE_NAME", "inventory-app")

from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.ai.projects import AIProjectClient  # noqa: E402
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool  # noqa: E402
from azure.ai.projects.telemetry import AIProjectInstrumentor, trace_function  # noqa: E402
from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: E402
from openai.types.responses.response_input_param import FunctionCallOutput  # noqa: E402
from opentelemetry import trace  # noqa: E402

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-4.1-mini")
AGENT_NAME = "traced-agent"
MAX_TURNS = 5  # ツール呼び出しの往復の上限（無限ループ防止）

_STOCK = {"X1": 3, "M27": 12}  # 在庫はモック


@trace_function("get_inventory")  # 自前のツール関数も span にする。() を省略すると動かない
def get_inventory(product_code: str) -> dict:
    if product_code not in _STOCK:
        err = f"unknown product_code: {product_code}"
        # 引数・戻り値の code.* 属性は Application Insights に出ないので、検索したい値は別の名前で足す
        trace.get_current_span().set_attribute("app.tool_error", err)
        return {"error": err}  # 例外にせず、error を値として返す（静かな失敗）
    return {"product_code": product_code, "stock": _STOCK[product_code]}


tool = FunctionTool(
    name="get_inventory",
    description="商品コードの在庫数を取得する",
    parameters={"type": "object", "properties": {"product_code": {"type": "string"}},
                "required": ["product_code"], "additionalProperties": False},
    strict=True,
)


def run_tool(item) -> dict:
    """function_call を1件実行する。引数が壊れていても落とさず、エラーとして返す。"""
    try:
        args = json.loads(item.arguments)
    except json.JSONDecodeError as ex:
        return {"error": f"invalid arguments: {ex}"}
    result = get_inventory(**args) if item.name == "get_inventory" else {"error": f"unknown tool: {item.name}"}
    print(f"[実行] {item.name}({args}) -> {result}")
    return result


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
    question = sys.argv[1] if len(sys.argv) > 1 else "商品 ZZ9 の在庫は？"

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    # client-side 計装：プロジェクトに接続した Application Insights へ送る（既定のサンプラーは間引くので全件記録）
    conn = project.telemetry.get_application_insights_connection_string()
    configure_azure_monitor(connection_string=conn, sampling_ratio=1.0)
    AIProjectInstrumentor().instrument()  # エージェントの作成や応答の呼び出しを自動で span にする
    tracer = trace.get_tracer(__name__)

    openai = project.get_openai_client()  # 計装の「後」に取得する
    agent = conversation = None
    trace_id = None
    try:
        with tracer.start_as_current_span("l2-11-inventory-scenario") as root:  # 1回の実行を1本の trace にまとめる
            trace_id = format(root.get_span_context().trace_id, "032x")  # Application Insights の operation_Id
            agent = project.agents.create_version(
                agent_name=AGENT_NAME,
                definition=PromptAgentDefinition(
                    model=MODEL_DEPLOYMENT,
                    instructions=("在庫を聞かれたら get_inventory ツールで調べてください。"
                                  "在庫の数は推測せず、ツールの結果だけを使い、日本語で1〜2行で答えてください。"),
                    tools=[tool]))
            conversation = openai.conversations.create()
            # name と id の両方を渡すと、ポータルのトレースでエージェントと紐づく
            ref = {"agent_reference": {"name": agent.name, "id": agent.id, "type": "agent_reference"}}

            print(f"USER> {question}")
            res = openai.responses.create(input=question, conversation=conversation.id, extra_body=ref)
            for turn in range(1, MAX_TURNS + 1):  # function_call が出なくなるまで往復する
                calls = [i for i in res.output if getattr(i, "type", None) == "function_call"]
                print(f"[応答{turn}] function_call {len(calls)} 件")
                if not calls:
                    break
                outputs = [FunctionCallOutput(type="function_call_output", call_id=c.call_id,
                                              output=json.dumps(run_tool(c), ensure_ascii=False))
                           for c in calls]
                res = openai.responses.create(input=outputs, conversation=conversation.id, extra_body=ref)
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
        trace.get_tracer_provider().force_flush()  # 終了前に span を送り切る
    if trace_id:
        print(f"operation_Id: {trace_id}（Application Insights への反映には数分かかります）")


if __name__ == "__main__":
    main()
