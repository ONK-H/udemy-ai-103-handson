# L3-4 実践: 画像のコンテンツモデレーション（Azure AI Content Safety）

画像を Content Safety に送って4カテゴリ（Hate/Sexual/Violence/Self-Harm）の重大度を取得し、アプリ側で決めたしきい値で受理（Accepted）/拒否（Rejected）を判定するハンズオンです。

> 対応レクチャー：実践 `L3-4-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 画像を `analyze_image` に送り、カテゴリ別重大度としきい値判定を表示 |
| `test.jpg` | 動作確認用のテスト画像（自作イラスト） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- **Azure AI Content Safety リソース**を作成済み（特定リージョンのみ対応）
- キーレス認証には **Cognitive Services User** 相当のロールが必要

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（CONTENT_SAFETY_ENDPOINT を設定）

python main.py
```

実行すると、`test.jpg` の4カテゴリ（Hate/Sexual/Violence/SelfHarm）それぞれの重大度（0/2/4/6）と、しきい値と比べた判定（OK / NG）、最終的な受理/拒否の判定が表示されます。

## 注意点（試験の論点）
- Content Safety は**重大度（0/2/4/6の4段階）を返すだけ**です。受理/拒否の最終判断はAPIではなく**アプリ側がしきい値で決めます**（`THRESHOLDS` 辞書）。
- 画像単体のAPIが返す重大度は0/2/4/6のみです（マルチモーダルAPIとは異なり0〜7ではありません）。
- カテゴリごとに異なるしきい値を設定できます（例：性的・暴力は厳しめの2、ヘイト・自傷は中程度の4）。

## 期待される出力（例）
```
=== カテゴリ別の重大度 (0=Safe,2=Low,4=Medium,6=High) ===
  Hate: severity=0 / しきい値=4 -> OK
  SelfHarm: severity=0 / しきい値=4 -> OK
  Sexual: severity=0 / しきい値=2 -> OK
  Violence: severity=0 / しきい値=2 -> OK

判定: Accepted(受理)
```
（`test.jpg` の内容によって結果は変わります）

## つまずき
- **`Content Safety エラー: ... 403 ...`**：ロール不足です。自分のアカウントに Cognitive Services User（またはそれに相当するロール）が割り当てられているか確認してください。
- **`Content Safety エラー: ... region ...`**：Content Safety は特定リージョンのみ対応です。対応リージョンのリソースを使っているか確認してください。
- **画像サイズ超過エラー**：Content Safety には画像サイズの上限があります。`test.jpg` を差し替える場合は上限を確認してください。

## 後片付け
- Content Safety は呼んだ回数分だけ課金されます（数回の検証なら数円程度、F0無料枠のリソースなら無料）。リソース自体は置いてあるだけでは課金されないので、他のレッスンで使わないなら削除は任意です。
