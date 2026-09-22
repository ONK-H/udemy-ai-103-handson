# L3-1 実践: 画像の生成とインペイント（inpainting）

テキストから画像を1枚生成し、中央だけを透明にしたマスクを自動生成して、その部分だけを別の内容に書き換える（inpainting）ハンズオンです。

> 対応レクチャー：実践 `L3-1-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 画像生成（`images.generate`）→ マスク自動生成（Pillow）→ 編集（`images.edit`）の3段 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- **画像生成モデル（`gpt-image-2` など）をデプロイ済みの Foundry リソース**（`japaneast` など APAC 不可。`eastus2` / `westus3` / `polandcentral` / `swedencentral` / `uaenorth` のいずれか）
- ⚠️ 最下位のクォータティア（Free Tier / Tier 0）には画像生成モデルが1つも含まれていません。差し替えでの回避はできないため、[クォータ増加申請](https://aka.ms/oai/stuquotarequest)が必要な場合があります。

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（FOUNDRY_OPENAI_BASE_URL に画像生成用リソースの /openai/v1/ エンドポイントを設定）

python main.py
```

実行すると、`generated.png`（生成画像）→ `mask.png`（中央が透明なマスク）→ `edited.png`（中央だけ書き換えた画像）の順に3枚が作られます。3枚を見比べてください。

## 注意点（試験の論点）
- ⚠️ **プロジェクトのエンドポイント（`.../api/projects/<name>`）経由では画像の生成・編集が404になります**（2026-09-22実測）。このレッスンだけは、L1-5の直接呼び出しと同じ形で**リソースの `/openai/v1/` エンドポイント**を直接使います。
- マスクは「透明（アルファ=0）の部分が編集してよい領域」というルールです。不透明な部分は元画像がそのまま保持されます。
- 編集プロンプトは**「マスクの部分に何を描くか」を明示的に書く**ことが重要です。短すぎるプロンプト（例：`"Place a plant"`）だけだと、中央が黒く塗りつぶされて返ることがありました（2026-09-22実測）。

## 期待される出力（例）
```
保存しました: generated.png
保存しました: mask.png（中央が編集対象）
保存しました: edited.png

完了: generated.png / mask.png / edited.png を見比べてください。
```

## つまずき
- **`エラー: ... 404 ...`**：`FOUNDRY_OPENAI_BASE_URL` がプロジェクトのエンドポイントになっていないか確認してください。リソースの `/openai/v1/` 形式が必要です。
- **`エラー: ... content_filter ...`**：プロンプトの内容がコンテンツフィルタに引っかかっています。プロンプトを穏当な内容に変えてください。
- **編集結果の中央が黒く塗りつぶされる**：編集プロンプトが短すぎる可能性があります。「マスクの部分に何を描くか」を具体的に書いてください。
- **クォータ不足で生成モデルをデプロイできない**：最下位ティアには画像生成モデルの既定割り当てがありません。[クォータ増加申請](https://aka.ms/oai/stuquotarequest)を出すか、承認まで動画で流れを確認してください。

## 後片付け
- 画像生成は呼んだ回数分だけ課金されます（数円程度）。デプロイ自体は置いてあるだけでは課金されないので、他のレッスンで使わないなら削除は任意です。
