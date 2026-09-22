# L2-12 実践: プロンプト改善 ＋ self-critique で品質を上げる

同じタスクを **①baseline（素のプロンプト）→ ②改善プロンプト（役割・制約・出力形式を明確化）→ ③self-critique（自己批評→改稿）** の3段階で実行し、出力の変化を比較するハンズオンです。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | baseline → improved → critique → revised の4回のモデル呼び出しを行い、すべて表示する |
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

python main.py
```

## 期待される出力（例）
```
===== (1) baseline =====
（素のプロンプトへの応答）

===== (2) 改善プロンプト =====
（役割・対象・出力形式を指定した応答）

===== 批評 =====
（辛口編集者としての弱点指摘・箇条書き）

===== (3) 改善＋self-critique =====
（批評を反映した最終版）
```

## つまずき
- モデル呼び出しが**1回のプロセスで4回**行われるため、他レッスンより実行に時間がかかります（数十秒程度）。
- 出力の質はモデル・実行のたびに変わります。**「self-critiqueが必ず良くなる」とは限らない**点も観察してください（改善プロンプト自体が既に強く効いている場合、self-critiqueの上乗せ効果は小さいことがあります）。
- **定量比較（スコアリング）はこのコードには含まれていません**。定量的に比較したい場合は `L2-5_evaluate_rag`（またはそれに準じる評価器）で baseline と revised を採点してください。

## 後片付け
- 特別な後片付けは不要です（作成した Foundry リソースは他レッスンでも使うため削除しない）。
