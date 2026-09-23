"""L0-3 実践: Hello, Foundry。

Microsoft Foundry プロジェクトにキーレス(DefaultAzureCredential)で接続し、
Responses API でチャットモデルを1回呼んで応答を表示する、最小のサンプル。

前提:
- `az login` 済み（ローカルの資格情報をキーレス認証に使う）
- プロジェクトにモデルをデプロイ済み（.env の MODEL_DEPLOYMENT = デプロイ名）
- 自分のアカウントに「Foundry User」ロール（CLI で作った場合は自動で付かないので README の手順8で付ける）

実行: python main.py
"""

import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")  # 例: https://<resource>.services.ai.azure.com/api/projects/<project>
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4-nano")  # カタログ名ではなく "デプロイ名"
PROMPT = "Microsoft Foundry とは何かを、初心者向けに2文で説明してください。"


def main() -> None:
    if not PROJECT_ENDPOINT:
        print("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
        return
    try:
        # credential / client はコンテキストマネージャで閉じる
        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project,
        ):
            openai = project.get_openai_client()  # OpenAI 互換クライアント。api_key は渡さない（キーレス）
            print(f"✅ キーレスで接続: {PROJECT_ENDPOINT}")

            res = openai.responses.create(model=MODEL, input=PROMPT)
            print("\n----- モデル応答 -----")
            print(res.output_text)
    except Exception as ex:  # 教育目的でまとめて捕捉（401=認証 / 403=ロール不足 / 404=デプロイ名違い を切り分ける）
        print(f"エラー: {type(ex).__name__}: {ex}")
        print("  - 401: トークン未取得/期限切れ。`az login` を確認")
        print("  - 403: ロール不足。Foundry User を割り当てたか確認（README の手順8）")
        print("  - 404: デプロイ名違い。.env の MODEL_DEPLOYMENT が実際のデプロイ名と一致するか確認")


if __name__ == "__main__":
    main()
