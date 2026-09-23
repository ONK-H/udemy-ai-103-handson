"""L5-2 実践: PDF/画像を Layout モデルで解析し、RAG 向け markdown を生成する。

あわせて表と信頼度スコアを確認する。認証はキーレス（az login + DefaultAzureCredential）。
"""

import os
import sys
from azure.identity import DefaultAzureCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentContentFormat, AnalyzeResult
from dotenv import load_dotenv

load_dotenv()
ENDPOINT = os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"]
INPUT_FILE = os.getenv("INPUT_FILE", "sample/invoice.pdf")
OUTPUT_MD = os.getenv("OUTPUT_MD", "output.md")


def main() -> None:
    client = DocumentIntelligenceClient(
        endpoint=ENDPOINT, credential=DefaultAzureCredential())

    # ローカルファイルを Layout で解析し、markdown 形式で出力
    with open(INPUT_FILE, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            body=f,
            output_content_format=DocumentContentFormat.MARKDOWN,
        )
    result: AnalyzeResult = poller.result()

    # 1) markdown を保存（RAG のセマンティックチャンクに使える形）
    with open(OUTPUT_MD, "w", encoding="utf-8") as out:
        out.write(result.content)
    print(f"markdown を保存しました: {OUTPUT_MD}（{len(result.content)} 文字・{len(result.pages)} ページ）")

    # 2) 構造の確認：抽出された表の数と形
    if result.tables:
        print(f"\n表を {len(result.tables)} 個検出:")
        for i, table in enumerate(result.tables):
            print(f"  表#{i}: {table.row_count} 行 x {table.column_count} 列")

    # 3) 信頼度の確認：1ページ目の単語の信頼度（低信頼の検出に使う）
    if result.pages and result.pages[0].words:
        low = [w for w in result.pages[0].words if w.confidence is not None and w.confidence < 0.8]
        print(f"\n1ページ目の単語: {len(result.pages[0].words)} 個 / "
              f"信頼度0.8未満: {len(low)} 個")
        for w in low[:5]:
            print(f"  低信頼: '{w.content}' (confidence={w.confidence:.2f})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 教育目的のエラーハンドリング
        print(f"エラー: {type(e).__name__}: {e}")
        print("エンドポイントがカスタムサブドメイン付きか、データ操作のロール（Foundry User など）が "
              "付いているか、INPUT_FILE のパスを確認してください。")
        sys.exit(1)  # 失敗を終了コードで呼び出し元に伝える（握りつぶさない）
