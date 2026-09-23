"""L2-12 プロンプト改善＋self-critique で品質を上げる。

同一タスクを baseline → 改善プロンプト → self-critique（批評→改稿）で実行し、
ビフォーアフターを比較する。認証はキーレス（DefaultAzureCredential + az login）。
最後に、段階ごとの字数・出力トークン（うち推論）・秒数を一覧にする（品質とコスト・遅延のトレードオフを見る）。
定量的な品質比較はこのコードには入れていない。L2-5 の評価器で baseline と revised を採点する。

使い方:
    python main.py              # .env の MODEL_DEPLOYMENT（既定 gpt-4.1-mini：推論しないモデル）
    python main.py gpt-5.4 medium   # デプロイ名と推論の強さ（reasoning effort）を引数で差し替える
"""

import os
import sys
import time
import unicodedata

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL = sys.argv[1] if len(sys.argv) > 1 else os.getenv("MODEL_DEPLOYMENT", "gpt-4.1-mini")
# 推論の強さ（none / low / medium / high）。推論モデルにだけ渡す。推論しないモデルに渡すと 400 になる
EFFORT = sys.argv[2] if len(sys.argv) > 2 else None

TASK = "新しい家計簿アプリの紹介文を書いて。"


def pad(text: str, width: int) -> str:
    """全角を2桁と数えて左詰めする（ターミナルで列をそろえるため）。"""
    w = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(0, width - w)


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")

    project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    openai = project.get_openai_client()
    stats = []  # (段階, 字数, 出力トークン, うち推論, 秒)

    def ask(label: str, instructions: str, user_input: str) -> str:
        t0 = time.perf_counter()
        extra = {"reasoning": {"effort": EFFORT}} if EFFORT else {}
        r = openai.responses.create(model=MODEL, instructions=instructions, input=user_input, **extra)
        sec = time.perf_counter() - t0
        u = r.usage
        details = getattr(u, "output_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", 0) or 0
        stats.append((label, len(r.output_text), u.output_tokens, reasoning, sec))
        return r.output_text

    print(f"モデル（デプロイ名）: {MODEL}" + (f" ／ 推論の強さ: {EFFORT}" if EFFORT else ""))

    # ① baseline：素のプロンプト
    baseline = ask("(1) baseline", "あなたは役立つアシスタントです。", TASK)

    # ② 改善プロンプト：役割・制約・出力形式を明確化
    improved_instructions = (
        "あなたはプロのコピーライターです。"
        "対象は家計簿が続かない20-30代。ベネフィットを具体的に、"
        "見出し＋3つの箇条書き＋一言CTA の形式で、120字程度の日本語で書いてください。"
    )
    improved = ask("(2) 改善", improved_instructions, TASK)

    # ③ self-critique：②を自己批評させ、改稿させる
    critique = ask(
        "批評",
        "あなたは辛口の編集者です。次の紹介文の弱点（具体性・訴求・形式）を箇条書きで指摘してください。",
        improved)
    revised = ask(
        "(3) 改稿",
        improved_instructions + "\n以下の批評を反映して改善してください：\n" + critique,
        TASK)

    print("\n===== (1) baseline =====\n", baseline)
    print("\n===== (2) 改善プロンプト =====\n", improved)
    print("\n===== 批評 =====\n", critique)
    print("\n===== (3) 改善＋self-critique =====\n", revised)

    # まとめ：品質を上げた分のコスト（呼び出し回数・トークン・時間）を並べて見る
    print(f"\n===== まとめ（{MODEL}{' / ' + EFFORT if EFFORT else ''}） =====")
    print(pad("段階", 14) + "  字数  出力トークン  うち推論    秒")
    for label, chars, out_tok, rsn, sec in stats:
        print(f"{pad(label, 14)}{chars:>6}{out_tok:>14}{rsn:>10}{sec:>6.1f}")
    total_tok = sum(s[2] for s in stats)
    total_sec = sum(s[4] for s in stats)
    print(f"{pad('合計', 14)}{'':>6}{total_tok:>14}{sum(s[3] for s in stats):>10}{total_sec:>6.1f}"
          f"  （呼び出し {len(stats)} 回）")


if __name__ == "__main__":
    main()
