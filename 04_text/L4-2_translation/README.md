# L4-2 実践: 多言語翻訳とトーン制御の比較

Azure Translator のテキスト翻訳 API（GA `2026-06-06`）で、①**NMT**（従来型の多言語翻訳）と ②**LLM**（トーン制御つき翻訳）を実行し、訳文を比較するハンズオンです。認証は**キーレス**（Entra ID）が第一選択で、キーはフォールバックです。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | ① NMT で多言語翻訳 → ② LLM でトーン制御（formal / informal）翻訳、の順に実行 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Translator リソース作成済み・Foundry プロジェクトにチャットモデルをデプロイ済み（例 `gpt-5.4`）
- プロジェクトに対する **Foundry User** ロール（LLM 翻訳の呼び出しに必要）

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集: TRANSLATOR_ENDPOINT と LLM_DEPLOYMENT の2つに値を入れる
# （TRANSLATOR_KEY / TRANSLATOR_REGION はキー認証のときだけ使うので空でよい）

python main.py
```

### わざと失敗させて挙動を見る（任意）
```powershell
# LLM_DEPLOYMENT に存在しないデプロイ名を入れると、LLM翻訳だけ400になる（本文に理由が出る）
$env:LLM_DEPLOYMENT = "no-such-deployment"
python main.py
Remove-Item Env:LLM_DEPLOYMENT   # 環境変数を消して .env の値に戻す
```

## 期待される出力（例）
```
=== ① NMT 多言語翻訳 ===
原文: ご来店ありがとうございます。本日のおすすめをご案内します。
  [en] Thank you for visiting. Here are today's recommendations.
  [es] Gracias por visitarnos. Aquí tienes las recomendaciones de hoy.
  [de] Vielen Dank für Ihren Besuch. Hier sind die heutigen Empfehlungen.

=== ② LLM トーン制御（英語：formal vs informal） ===
  [formal]   Thank you for visiting our store. We will guide you through today's recommendations.
  [informal] Thank you for coming in. Let me tell you today's recommendations.
```

## つまずき
- **401 / 403**：トークンの宛先、ロール、`.env` に残ったキーを確認する。403 は無料枠を使い切ったときにも出る。
- **LLM 翻訳だけ 400**：`LLM_DEPLOYMENT` が**デプロイ名**（カタログ名ではない）かを疑う。存在しない名前を入れると `404` ではなく `400` が返り、本文に理由が書かれている。
- **tone が効かない**：`targets` の要素に `deploymentName` を指定しているか確認する。NMT の要素に `tone` を付けてもエラーにならず、黙って無視される。
- **設定を変えたのに戻らない**：シェルの環境変数が `.env` より優先されている可能性がある（`load_dotenv()` は既存の環境変数を上書きしない）。
- **レスポンスの形が違う**：`api-version` が新しい版かを確認する。
- **リクエストが大きすぎて 400**：上限は NMT が要素1000個・各5万文字、LLM が要素50個・各5000文字。分割して送る。
- **429**：時間あたりの制限。間隔をあけて送り直す。

## 後片付け
呼び出した分だけの課金で、共有のリソースは消しません。
