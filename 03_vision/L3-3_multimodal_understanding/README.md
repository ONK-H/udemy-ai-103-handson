# L3-3 実践: 画像キャプションと視覚的QA（マルチモーダル理解）

同じ画像を vision 対応モデルに渡し、プロンプトを変えるだけで「簡潔キャプション」「物体の列挙（視覚QA）」「alt-text」の3つを作り分けるハンズオンです。

> 対応レクチャー：実践 `L3-3-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 画像をbase64データURIに変換し、3種類のプロンプトで `chat.completions.create` を呼ぶ |
| `sample.jpg` | 動作確認用のサンプル画像（自作イラスト） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクト作成済み・**画像理解に対応するチャットモデル**（`gpt-4o` 系／`gpt-4.1` 系／`gpt-5` 系／`o` 系など）をデプロイ済み
- 最下位ティア（Free Tier / Tier 0）には `gpt-4o` はありませんが、`gpt-4.1-mini` と `o4-mini` は画像理解に対応しているのでそのまま代用できます

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（PROJECT_ENDPOINT・VISION_MODEL を設定。デプロイできなければ VISION_MODEL=gpt-4.1-mini に）

python main.py
```

実行すると、`sample.jpg` に対して「簡潔キャプション」「物体の列挙(視覚QA)」「alt-text」の3つの回答が順に表示されます。

## 注意点（試験の論点）
- 画像は**base64データURI**（`data:image/jpeg;base64,...`）として `content` に含めて渡します。ファイルアップロードAPIは使いません。
- 同じ画像・同じAPI呼び出し方でも、**プロンプトを変えるだけ**で複数のタスク（キャプション／視覚QA／alt-text）を作り分けられます。
- `mimetypes` などの拡張子判定ではなく、コード側で単純に `.png`かどうかだけを見てMIMEタイプを決めています（他の拡張子は全て `image/jpeg` 扱い）。

## 期待される出力（例）
```
===== 簡潔キャプション =====
木製のデスクの上にノートパソコンと観葉植物が置かれている、明るい窓辺の様子です。

===== 物体の列挙(視覚QA) =====
- ノートパソコン
- 観葉植物
- デスク
- 窓

===== alt-text =====
窓際の木製デスクにノートパソコンと観葉植物が置かれている写真
```
（実際の回答内容はモデル・実行ごとに変わります）

## つまずき
- **`エラー: ... insufficient quota ...`**：`VISION_MODEL` を `gpt-4.1-mini` に変更してください（最下位ティアでも既定割り当てがあります）。
- **画像が読み込めない**：`sample.jpg` が `main.py` と同じフォルダにあるか確認してください。
- **モデルが画像を無視した回答をする**：デプロイしたモデルが画像理解に対応しているか確認してください（テキストのみのモデルでは画像入力が無視されるか、エラーになります）。

## 後片付け
- 呼んだトークン分だけ課金されます（数円程度）。デプロイ自体は置いてあるだけでは課金されないので、他のレッスンで使わないなら削除は任意です。
