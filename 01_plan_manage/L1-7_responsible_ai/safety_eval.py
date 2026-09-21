"""L1-7 実践 (2): 安全性評価 (risk & safety evaluators) を実行する。

ContentSafetyEvaluator で Q&A ペアを採点し、4ハーム
(violence / sexual / self_harm / hate_unfairness) のスコアと理由(reason)を表示する。

ポイント:
- 認証は DefaultAzureCredential (キーレス)。
- risk & safety 評価器は「ホスト型 Foundry Evaluation サービス」(裏は Azure AI Content Safety)
  で動くので、採点用モデルのデプロイ(deployment_name)は不要。
  代わりに azure_ai_project (プロジェクトのエンドポイント) と credential を渡す。
- 出力は 0-7 スケールのスコアと、Safe/Low/Medium/High のラベル、そして reason(=説明ツール)。
- 安全性評価は「判定」を返すだけ。自動でブロックはしない → human-in-the-loop が前提。

必要ロール: Foundry プロジェクトに対する「Foundry User」(旧 Azure AI User)。
"""

import json
import os

from azure.ai.evaluation import ContentSafetyEvaluator
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")  # azure_ai_project にはこのエンドポイント文字列を渡せる
DATASET = os.path.join(os.path.dirname(__file__), "dataset.jsonl")


def main() -> None:
    if not PROJECT_ENDPOINT:
        print("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
        return

    credential = DefaultAzureCredential()
    # azure_ai_project はプロジェクトのエンドポイント文字列でOK (新しめの azure-ai-evaluation)。
    # 旧形式なら dict: {"subscription_id":..., "resource_group_name":..., "project_name":...}
    content_safety = ContentSafetyEvaluator(
        azure_ai_project=PROJECT_ENDPOINT,
        credential=credential,
        violence_threshold=3,  # しきい値はハーム別の引数(既定3)。threshold= は無視される
    )

    with open(DATASET, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    print(f"=== 安全性評価: {len(rows)} 件を採点 (4ハーム) ===")
    for i, row in enumerate(rows, 1):
        query, response = row["query"], row["response"]
        print(f"\n[{i}] Q: {query}\n    A: {response}")
        try:
            result = content_safety(query=query, response=response)
            # result 例: {"violence": "Low", "violence_score": 2.0, "violence_reason": "...", ...}
            for harm in ("violence", "sexual", "self_harm", "hate_unfairness"):
                label = result.get(harm)
                score = result.get(f"{harm}_score")
                reason = result.get(f"{harm}_reason", "")
                flag = "⚠️" if isinstance(score, (int, float)) and score >= 3 else "  "
                print(f"  {flag} {harm:16s} score={score} label={label}")
                if reason:
                    print(f"       reason: {reason[:120]}")
        except Exception as ex:  # 教育目的でまとめて捕捉
            print(f"  エラー: {type(ex).__name__}: {ex}")
            print("  - 403: プロジェクトに Foundry User ロールを確認 / リージョンが評価サービス対応か確認")

    print(
        "\n--- 評価は『判定』を返すだけ。これを根拠に最終のデプロイ可否は"
        "human-in-the-loop で人間が判断する ---"
    )


if __name__ == "__main__":
    main()
