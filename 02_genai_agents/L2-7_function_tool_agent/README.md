# L2-7 実践: 自作関数をエージェントに登録する（Function Tool）

自作関数を `FunctionTool` でスキーマ宣言してエージェント定義に登録し、`function_call → アプリが実行 → function_call_output → 最終回答` のループを自分の手で回すハンズオンです。関数を実行するのは**アプリ側**で、モデルではありません。

> 対応レクチャー：実践 `L2-7-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。エージェントは `finally` で削除されます。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 自作関数の実装、`FunctionTool` 定義、承認・実行ループ |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・**関数ツール（Functions）対応のモデル**を1つデプロイ済み（例 `gpt-4.1-mini`）。
  ⚠️ 公式のツール対応表では `gpt-5-mini`・`gpt-5.4` は Functions が **No** です。`.env.sample` の既定は `gpt-4.1-mini` を使ってください。

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（PROJECT_ENDPOINT・MODEL_DEPLOYMENT=gpt-4.1-mini）してから:

python main.py
```

## 期待される出力（例）
```
エージェント作成: <agent-id> v1
[function_call] get_weather(city="Tokyo")
AI> （自作関数の戻り値を踏まえた最終回答）
エージェントを削除しました
```

## つまずき
- **関数が呼ばれない／`function_call` が来ない**：`MODEL_DEPLOYMENT` が Functions 非対応のモデル（`gpt-5-mini` 等）になっていないか確認。
- **`model not found`（404）**：`.env` の `MODEL_DEPLOYMENT` が実際のデプロイ名と一致しているか確認。
- **1往復しか処理されない**：この `main.py` は1往復のやり取りのみ処理する設計です。2回目以降の `function_call` には対応していません。

## 後片付け
- エージェントは実行のたびに `finally` で削除されるため、プロジェクトには残りません。特別な後片付けは不要です。
