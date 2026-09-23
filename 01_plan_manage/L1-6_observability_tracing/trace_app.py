"""L1-6 実践: アプリに OpenTelemetry トレースを仕込み、Application Insights で可視化する。

本講座の標準どおりキーレス(DefaultAzureCredential)で AIProjectClient を作り、
  1) GenAI トレース計測を有効化 (AIProjectInstrumentor)
  2) プロジェクトに接続済みの Application Insights へ span をエクスポート (configure_azure_monitor)
  3) 自作関数を @trace_function で独自 span 化
してから、Responses API で2回推論する。実行後、Azure Monitor Application Insights で
「呼び出し・トークン・レイテンシ」を確認する（Foundry ポータルのトレース画面はエージェント向けで、
自作アプリのトレースはそこには並ばない）。

注意:
  - GenAI トレースは実験的プレビュー。AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true を
    instrument() の前に設定する必要がある(本ファイルでは import より前に明示設定)。
  - メッセージ本文の記録(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT)は
    個人情報を含みうるため開発時のみ。本番では既定(false)のままにする。
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- GenAI トレース計測の実験フラグは instrument() の前(=import の前)に設定する ---
# .env で上書きしたい場合は setdefault なので .env 側の値が優先される。
os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
# メッセージ本文も span に記録する(開発時のみ。PII を含みうる)
os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")

# 上記フラグ設定後に計測関連を import する
from azure.ai.projects import AIProjectClient  # noqa: E402
from azure.ai.projects.telemetry import AIProjectInstrumentor, trace_function  # noqa: E402
from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: E402
from opentelemetry import trace  # noqa: E402

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")  # デプロイ名 (カタログ名ではない)

# キーレスでプロジェクトへ接続
project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())

# --- 2) プロジェクトに接続済みの Application Insights へ span をエクスポート ---
connection_string = project.telemetry.get_application_insights_connection_string()
# 既定のサンプラーは 1 秒あたり約 5 件に間引き、間引かれた span では計測が落ちることがある。
# デモでは全件記録する (sampling_ratio=1.0)。本番ではコストに応じて下げる。
configure_azure_monitor(connection_string=connection_string, sampling_ratio=1.0)

# --- 1) GenAI 計測を有効化 (Responses/Conversations API 呼び出しが自動トレースされる) ---
AIProjectInstrumentor().instrument()

client = project.get_openai_client()  # openai 互換クライアント (Responses API)
tracer = trace.get_tracer(__name__)


# --- 3) 自作関数を独自 span にする (パラメータ・戻り値が span 属性に記録される) ---
@trace_function("classify-question")
def classify_question(text: str) -> str:
    """超簡易の質問分類。本来はDB照会やAPI呼び出しなどのツールの代わり。"""
    category = "support" if ("エラー" in text or "動かない" in text) else "general"
    # 引数・戻り値の code.* 属性は Application Insights の customDimensions に載らない。
    # KQL で検索したい値は、code. 以外の名前で現在の span に足す。
    trace.get_current_span().set_attribute("app.question_category", category)
    return category


def ask(question: str) -> str:
    """分類 → システムメッセージ切替 → Responses API で生成。一連が trace に乗る。"""
    category = classify_question(question)
    system = (
        "あなたは丁寧なAzureサポート担当です。" if category == "support"
        else "あなたは簡潔なアシスタントです。"
    ) + "答えは2行以内にしてください。"
    # システムメッセージは instructions で渡す。system ロールのメッセージの直後に
    # type なしの user メッセージを並べると、Responses API が 400 を返すことがある。
    res = client.responses.create(
        model=MODEL,
        instructions=system,
        input=question,
    )
    u = res.usage
    print(f"[分類] {category}  [トークン] 入力 {u.input_tokens} / 出力 {u.output_tokens}")
    return res.output_text


def main():
    if not PROJECT_ENDPOINT:
        print("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
        return

    questions = [
        "Microsoft Foundry の可観測性とは何ですか？1文で答えてください。",
        "デプロイしたモデルが動かないエラーの切り分け手順を3つ、それぞれ20文字以内で挙げてください。",
    ]
    try:
        # 親 span でまとめると、Application Insights で1つのトランザクションとして追える
        with tracer.start_as_current_span("l1-6-trace-demo") as root:
            for q in questions:
                print(f"\nQ: {q}")
                answer = ask(q)
                print(f"A: {answer}")
            # Application Insights では、このトレース ID が operation_Id になる
            trace_id = format(root.get_span_context().trace_id, "032x")
        print(f"\n--- トレース送信完了。operation_Id: {trace_id} ---")
        print("Application Insights への反映には数分かかります。")
    except Exception as ex:
        print(f"エラー: {ex}")


if __name__ == "__main__":
    main()
