# L2-4 実践: 複数ステップのツール呼び出し（検索→計算→整形）

Responses API の function calling ループを**自分の手で回し**、複数の自作ツール（検索・計算・整形）をモデルが順番に呼ぶ多段推論を観察するハンズオンです。外部サービスは使わず、ツールはすべてモック（アプリ内の固定データ）です。

> 対応レクチャー：実践 `L2-4-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。外部サービス不要。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 自作ツール（在庫検索・計算・整形）の実装と、function calling ループの本体 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み（例 `gpt-5.4` または `gpt-5-mini`）

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（PROJECT_ENDPOINT・MODEL_DEPLOYMENT）してから:

python main.py
```

## 期待される出力（例）
```
[ツール呼び出し] search_inventory(...)
[ツール呼び出し] calc_total(...)
[ツール呼び出し] format_reply(...)

----- 最終回答 -----
（整形された返答テキスト）
```
モデルは1回の呼び出しでは答えを確定できず、複数のツールを順番に呼んでから最終回答を返します。ログに並ぶツール呼び出しの順序が、モデルが組んだ実行計画です。

## つまずき
- **`model not found`（404）**：`MODEL_DEPLOYMENT` は**カタログ名ではなくデプロイ名**。`.env` を確認。
- **`insufficient quota`**：最下位のクォータティアでは `gpt-5-mini` に既定割り当てがあります。`gpt-5.4` 系は割り当てゼロのことがあるので、その場合は `gpt-5-mini` などに読み替えてください（詳細は `FAQ.md`）。
- **ツール呼び出しが1回で終わる／ループが止まらない**：`main.py` のループ上限・終了条件（`tool_calls` が空になったら終了）を確認してください。

## 後片付け
- 外部リソースを作らないハンズオンなので、後片付けは不要です。
