"""L2-12 プロンプト改善＋self-critique で品質を上げる。

同一タスクを baseline → 改善プロンプト → self-critique（批評→改稿）で実行し、
ビフォーアフターを比較する。認証はキーレス（DefaultAzureCredential + az login）。
定量比較はこのコードには入れていない。L2-5 の評価器で baseline と revised を採点する。
"""

import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-4.1-mini")

TASK = "新しい家計簿アプリの紹介文を書いて。"


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    def ask(instructions: str, user_input: str) -> str:
        r = openai.responses.create(model=MODEL, instructions=instructions, input=user_input)
        return r.output_text

    # ① baseline：素のプロンプト
    baseline = ask("あなたは役立つアシスタントです。", TASK)

    # ② 改善プロンプト：役割・制約・出力形式を明確化
    improved_instructions = (
        "あなたはプロのコピーライターです。"
        "対象は家計簿が続かない20-30代。ベネフィットを具体的に、"
        "見出し＋3つの箇条書き＋一言CTA の形式で、120字程度の日本語で書いてください。"
    )
    improved = ask(improved_instructions, TASK)

    # ③ self-critique：②を自己批評させ、改稿させる
    critique = ask(
        "あなたは辛口の編集者です。次の紹介文の弱点（具体性・訴求・形式）を箇条書きで指摘してください。",
        improved)
    revised = ask(
        improved_instructions + "\n以下の批評を反映して改善してください：\n" + critique,
        TASK)

    print("===== (1) baseline =====\n", baseline)
    print("\n===== (2) 改善プロンプト =====\n", improved)
    print("\n===== 批評 =====\n", critique)
    print("\n===== (3) 改善＋self-critique =====\n", revised)


if __name__ == "__main__":
    main()
