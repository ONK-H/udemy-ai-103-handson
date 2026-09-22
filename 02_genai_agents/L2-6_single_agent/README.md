# L2-6 実践: 単一エージェントの作成と実行（Code Interpreter付き）

`PromptAgentDefinition`（model/instructions/tools）で組み込みツール **Code Interpreter** 付きのエージェントを定義し、会話に紐づけて多ターンで対話するハンズオンです。計算が絡む質問は Code Interpreter が担います。

> 対応レクチャー：実践 `L2-6-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。エージェントは `finally` で削除され、プロジェクトに残りません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | エージェントの作成・会話（複数ターン）・削除（`finally`） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・チャットモデルを1つデプロイ済み（例 `gpt-5-mini`）

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
エージェント作成: <agent-id> v1
AI> （Code Interpreter が計算した結果を含む回答）
...
エージェントを削除しました
```

## つまずき
- **`model not found`（404）**：`MODEL_DEPLOYMENT` は**カタログ名ではなくデプロイ名**。`.env` にある名前が、実際にデプロイした名前と一致しているか確認。
- **`DeploymentNotFound`**：環境に存在しないデプロイ名を指定すると発生します。`az cognitiveservices account deployment list` で実際のデプロイ名を確認。
- **Code Interpreter のセッション課金**：Code Interpreter はセッション単位で追加課金されます（呼ばなければ課金されません）。

## 後片付け
- エージェントは実行のたびに `finally` で削除されるため、プロジェクトには残りません。特別な後片付けは不要です。
