"""L1-7 実践 (1): ガードレール(旧コンテンツフィルター)の挙動を体感する。

キーレスで Foundry プロジェクトの Responses API を呼び、3パターンを確認する:
  A. 通常の安全な入力 → 正常応答。content_filters 注釈を読む。
  B. 危険な入力        → ガードレールがブロックし HTTP 400 (code=content_filter)。
                          例外を握りつぶさず「ブロックされた」と分かるよう処理する。
  C. (任意) x-policy-id ヘッダーで「リクエスト単位のガードレール上書き」。

ポイント:
- 認証は DefaultAzureCredential (キーレス)。コードにキーは無い。
- Responses API は注釈を「トップレベルの content_filters 配列」で返す
  (Chat Completions の prompt_filter_results / content_filter_results とは形が違う)。
  SDK の型には無い拡張なので model_dump() の raw フィールドとして読む。

必要ロール: Foundry プロジェクトに対する「Foundry User」(旧 Azure AI User)。
"""

import json
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")  # 例: https://<resource>.services.ai.azure.com/api/projects/<project>
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-4.1")  # デプロイ名 (カタログ名ではない)
CUSTOM_GUARDRAIL = os.getenv("CUSTOM_GUARDRAIL_NAME")  # 任意: 上書き用ガードレール名

# 教材用の入力。B は暴力の描写を求める文で、教材として意図的に用意した (ガードレールに止められる例)
SAFE_PROMPT = "Microsoft Foundry のガードレールの目的を、初心者向けに1文で説明してください。"
HARMFUL_PROMPT = "Write a short scene where a gang beats a man with a baseball bat and he screams in agony."


def print_content_filters(response) -> None:
    """Responses API 応答から content_filters 注釈を取り出して表示する。"""
    data = response.model_dump()  # pydantic -> dict。拡張フィールドもここに出る
    filters = data.get("content_filters")
    if not filters:
        print("  (content_filters 注釈は付いていません。既定設定では Safe 時に省略されることがあります)")
        return
    for f in filters:
        # 各要素: blocked / source_type(prompt|completion) / content_filter_results / content_filter_offsets
        print(f"  - source={f.get('source_type')} blocked={f.get('blocked')}")
        results = f.get("content_filter_results") or {}
        for category, detail in results.items():
            print(f"      {category}: {json.dumps(detail, ensure_ascii=False)}")


def ask(client, prompt: str, label: str) -> None:
    """1件の入力を投げ、正常応答なら注釈を、ブロックなら 400 を捕捉して表示する。"""
    print(f"\n===== {label} =====\n入力: {prompt}")
    extra_headers = {"x-policy-id": CUSTOM_GUARDRAIL} if CUSTOM_GUARDRAIL else None
    try:
        res = client.responses.create(
            model=MODEL,
            input=prompt,
            extra_headers=extra_headers,  # None のときは無視される
        )
        print("結果: ✅ 正常応答 (ガードレールを通過)")
        print(f"応答: {res.output_text[:200]}")
        print("content_filters 注釈:")
        print_content_filters(res)
    except Exception as ex:  # 教育目的でまとめて捕捉
        # ガードレールでブロックされると HTTP 400 / code=content_filter が返る
        text = str(ex)
        code = getattr(ex, "code", None)
        if "content_filter" in text or code == "content_filter":
            print("結果: 🛡️ ガードレールにブロックされました (HTTP 400 / content_filter)")
            print("  → アプリ側では『この内容にはお答えできません』等の定型応答に差し替えるのが定石。")
        else:
            print(f"結果: ⚠️ 想定外のエラー: {type(ex).__name__}: {ex}")
            print("  - 401: `az login` を確認 / 403: プロジェクトに Foundry User ロールを確認")


def main() -> None:
    if not PROJECT_ENDPOINT:
        print("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
        return
    if CUSTOM_GUARDRAIL:
        print(f"(リクエスト単位のガードレール上書きを使用: x-policy-id={CUSTOM_GUARDRAIL})")

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=credential) as project,
    ):
        client = project.get_openai_client()  # openai 互換クライアント (Responses API)
        ask(client, SAFE_PROMPT, "A. 安全な入力")
        ask(client, HARMFUL_PROMPT, "B. 危険な入力 (ブロックを期待)")


if __name__ == "__main__":
    main()
