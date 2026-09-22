# L2-5 実践: RAG の回答を評価器でスコア化する

`azure-ai-evaluation` の `evaluate()` で、Groundedness（根拠性）・Relevance（関連性）・Coherence（一貫性）の3つの評価器を `data.jsonl` に対してまとめて実行し、RAG の回答品質をスコアで可視化するハンズオンです。評価はローカル実行（ポータルには残りません）。

> 対応レクチャー：実践 `L2-5-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。judge（採点役）モデルの呼び出しにはキーが必要な場合があります（`.env` 参照）。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 評価器（Groundedness/Relevance/Coherence）を組み立て、`data.jsonl` に対して `evaluate()` を実行 |
| `data.jsonl` | 評価対象のQ&Aデータ（質問・コンテキスト・回答の組。3件） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry リソースに **judge 用の非推論モデル**（`gpt-4.1` 系）をデプロイ済み。
  ⚠️ **judge は非推論モデルにすること**。`gpt-5` 系などの推論モデルは `is_reasoning_model=True` が必要で、この `main.py` は未対応です。

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（AZURE_OPENAI_ENDPOINT・JUDGE_DEPLOYMENT）してから:

python main.py
```

## 期待される出力（例。スコアは実行ごとに変わります）
```
groundedness: 3.67 / relevance: 5.0 / coherence: 4.0
（3件中1件は groundedness が低く fail 判定）
```
スコアの絶対値は judge モデルや実行タイミングで変動します。傾向（どの回答が他より低いか）を見る使い方をしてください。

## つまずき
- **`insufficient quota` で `gpt-4.1` がデプロイできない**：最下位のクォータティア（Free Tier / Tier 0）にあるのは `gpt-4.1-mini` で、`gpt-4.1` は別物です。`.env.sample` の該当行のコメントアウトを外して `JUDGE_DEPLOYMENT=gpt-4.1-mini` に切り替えてください（採点役を変えるとスコアの絶対値は変わりますが、傾向の比較には使えます）。詳細は `FAQ.md`。
- **`is_reasoning_model` 関連のエラー**：`JUDGE_DEPLOYMENT` に推論モデル（`gpt-5` 系等）を指定していないか確認してください。
- **評価結果がポータルに出てこない**：この `main.py` はローカル評価（`azure_ai_project` 未指定）です。クラウド評価としてポータルに残したい場合は `evaluate()` に `azure_ai_project` を渡す必要があります（本レッスンの範囲外）。

## 後片付け
- ローカル評価のみで外部リソースを作らないため、後片付けは不要です。
