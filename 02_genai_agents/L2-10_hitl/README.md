# L2-10 実践: 高リスク操作の前に人間承認を挟む（deterministic HITL）

エージェントに**低リスク（読み取り）**と**高リスク（削除）**のツールを与え、高リスク関数は**アプリ側のコードが必ず**承認を要求します（モデルに承認判断を任せない＝ deterministic HITL）。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | `get_record`（低リスク・自動実行）／`delete_record`（高リスク・承認必須）を持つエージェント |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集：PROJECT_ENDPOINT・MODEL_DEPLOYMENT

# 1) 既定（引数なし）：高リスクの削除を依頼 → 承認プロンプトが出る
python main.py

# 2) 引数で低リスクの読み取りを依頼 → 承認なしで自動実行される
python main.py "レコード 1001 を見せて。"
```

## 期待される出力（例）
引数なし（削除）：
```
USER> レコード 1002 を削除して。
[承認] delete_record({'record_id': '1002'}) を実行しますか？ (y/N): y
AI> レコード 1002 を削除しました。
```
引数あり（読み取り）：
```
USER> レコード 1001 を見せて。
[自動実行] get_record({'record_id': '1001'}) -> {'record_id': '1001', 'name': '山田'}
AI> レコード 1001 は山田さんです。
```

## つまずき
- **承認プロンプトが出ない**：モデルが `delete_record` ではなく `get_record` を選んでいないか確認（指示文を「削除して」など明確にする）。
- **`PROJECT_ENDPOINT が未設定です`**：`.env` の作成・値の入力を確認。
- **往復が5回で止まる**：`MAX_TURNS = 5`（無限ループ防止）。それ以上の往復が必要なタスクでは値を増やす。
- このサンプルのデータベースはインメモリ（`_DB` 辞書）です。**再実行するたびに 1001/1002 のレコードに初期化**されます（削除しても次回起動時は復活）。

## 後片付け
- エージェント・会話は `finally` で毎回削除されます。データベースはインメモリなので後片付け不要です。
