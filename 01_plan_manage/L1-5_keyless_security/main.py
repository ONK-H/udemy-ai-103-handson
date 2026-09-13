"""L1-5 実践 (1): キーレスで Foundry プロジェクトを呼ぶ。

APIキーを一切使わず、`az login` した ID（または Azure 上のマネージドID）の
トークンで Foundry プロジェクトの Responses API を呼び出す。

ポイント:
- 認証は DefaultAzureCredential（キーレス）。コードにキーは無い。
- AIProjectClient -> get_openai_client() は本講座の標準（Responses API）。
- トークンは SDK が裏で自動取得・更新する（スコープ https://ai.azure.com/.default）。

必要ロール: Foundry プロジェクト(またはアカウント)に対する「Foundry User」(旧 Azure AI User)。
- Owner / Contributor では推論できない。データアクションを持つロールが必要。
- 上位スコープ(サブスクリプション/リソースグループ)の割り当ては下位に継承される。
- 割り当て直後は反映に数分かかる(公式ガイダンスは「最初の呼び出しまで5分以上待つ」)。
"""

import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")  # 例: https://<resource>.services.ai.azure.com/api/projects/<project>
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")  # カタログ名ではなく "デプロイ名"
PROMPT = "キーレス認証(Microsoft Entra ID)の利点を1文で説明してください。"


def main() -> None:
    if not PROJECT_ENDPOINT:
        print("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
        return
    try:
        # credential はコンテキストマネージャで閉じる（トークンキャッシュの後始末）
        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project,
        ):
            client = project.get_openai_client()  # openai 互換クライアント。api_key は渡さない
            print(f"✅ キーレスで接続: {PROJECT_ENDPOINT}")

            res = client.responses.create(model=MODEL, input=PROMPT)
            print("\n----- モデル応答 -----")
            print(res.output_text)
    except Exception as ex:  # 教育目的でまとめて捕捉（401=認証/403=ロール不足 を切り分ける）
        print(f"エラー: {type(ex).__name__}: {ex}")
        print("  - 401 (トークンが無い/期限切れ/宛先違い): `az login` とスコープを確認")
        print("  - 403 Forbidden / 401 PermissionDenied: ロール不足。")
        print("    プロジェクト(かアカウント)に Foundry User を割り当て、数分待って再実行")
        print("  - 404 Workspace not found: PROJECT_ENDPOINT のプロジェクトが存在しない")


if __name__ == "__main__":
    main()
