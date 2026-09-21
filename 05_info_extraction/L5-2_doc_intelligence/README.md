# L5-2 Document Intelligence：PDF/画像 → RAG 向け markdown

`prebuilt-layout` モデルで PDF や画像を解析し、構造を保った markdown に変換するハンズオン。
あわせて、抽出された表の数と単語の信頼度スコアを確認する。

## 前提リソース
- Azure AI Document Intelligence（または Foundry Tools を含む Microsoft Foundry リソース）
- **カスタムサブドメイン付きエンドポイント**（キーレス認証の条件）

## RBAC（キーレス）
- 自分の ID に `Cognitive Services User`

## 手順
```bash
python -m venv .venv && source .venv/bin/activate   # Windows は .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env   # 値を埋める（エンドポイント・INPUT_FILE）
az login

# sample/ に解析したい PDF/画像（表・見出しを含むもの）を置く（sample/ は同梱していない）
# 例：公式サンプルの請求書（L5-3 と同じ文書）
mkdir -p sample && curl -L -o sample/invoice.pdf https://raw.githubusercontent.com/Azure-Samples/azure-ai-content-understanding-assets/main/document/invoice.pdf
# Windows PowerShell: mkdir sample; Invoke-WebRequest <上のURL> -OutFile sample/invoice.pdf
python analyze_to_markdown.py
# → output.md に markdown、コンソールに表の数・信頼度サマリ
```

## 後片付け
検証専用に作った Document Intelligence / Foundry リソースは削除（リソースグループごとが確実）。

> ⚠️ 無料枠(F0)は月500ページまで無料（F0 は PDF の先頭2ページのみ解析・ファイル4MBまで）。SDK のクラス名・API バージョンは変化が速いので、
> `pip show azure-ai-documentintelligence` と公式ドキュメントで最新を確認すること。
