"""L2-1 履歴つき・ストリーミング表示の CLI チャットアプリ。

Microsoft Foundry のプロジェクトに接続し、Responses API で多ターン対話する。
- 会話履歴を自前で配列管理（方式B）して文脈を保持
- stream=True で逐次表示（TTFT 改善）
- システムメッセージ（instructions）で役割を固定
認証はキーレス（DefaultAzureCredential + az login）。
"""

import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini")

# システムメッセージ（役割・口調を固定。毎ターン先頭に効かせる）
SYSTEM_PROMPT = "あなたは親切で簡潔な日本語のアシスタントです。専門用語は噛み砕いて説明してください。"


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    # キーレス認証（az login 済みの資格情報を使用）
    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()  # OpenAI 互換クライアント（Responses API）

    # 会話履歴を自前で保持（方式B）。システムメッセージは履歴に入れず instructions で渡す
    # （system ロールのメッセージの直後に type なしの user メッセージを並べると 400 になるため）
    history = []

    print("CLIチャット（終了: exit / quit）。話しかけてください。")
    while True:
        try:
            user_input = input("\nあなた> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            break
        if user_input.lower() in ("exit", "quit"):
            print("終了します。")
            break
        if not user_input:
            continue

        # ユーザー発言を履歴に追加
        history.append({"role": "user", "content": user_input})

        # ストリーミングで応答を生成・逐次表示
        print("AI> ", end="", flush=True)
        answer = ""
        try:
            stream = openai.responses.create(
                model=MODEL_DEPLOYMENT,
                instructions=SYSTEM_PROMPT,  # 役割・口調は毎ターン instructions で効かせる
                input=history,        # これまでの履歴（user / assistant）をまとめて渡す
                stream=True,
            )
            for event in stream:
                if event.type == "response.output_text.delta":
                    print(event.delta, end="", flush=True)  # 届いた断片を即表示
                    answer += event.delta
                elif event.type == "response.completed":
                    break
            print()  # 改行
        except Exception as ex:  # 教育目的の素朴なエラーハンドリング
            print(f"\n[エラー] {ex}")
            history.pop()  # 失敗したユーザー発言は履歴から戻す
            continue

        # アシスタント応答も履歴に追加（次ターンの文脈になる）
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
