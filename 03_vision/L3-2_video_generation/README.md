# L3-2 実践: テキストから短い動画を非同期生成する（Sora 2）

テキストから短い動画を1本、非同期ジョブとして生成し、完成をポーリングで待ってダウンロードするハンズオンです。

> 対応レクチャー：実践 `L3-2-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ⚠️ 重要：このレッスンは近く実行できなくなる可能性があります
実行すると `DeprecationWarning: The Sora API is scheduled to permanently shut down on September 24, 2026.` という警告が出ました（2026-09-22実測）。Azureの公式な退役スケジュールは `sora-2`（2025-12-08版）が2026-10-15ですが、それより早く止まる可能性があります。**廃止後はこのレッスンを実行できません**。実行できない場合は、動画（実践レクチャー）で流れを確認してください。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | ジョブ作成（`videos.create`）→ ポーリング（`videos.retrieve`）→ ダウンロード（`videos.download_content`）の3段 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- **`sora-2` をデプロイ済みの Foundry リソース**。Global Standard でデプロイできるのは `eastus2` / `swedencentral` のみ（2026-09-22時点、`japaneast` 不可）
- ⚠️ 最下位のクォータティア（Free Tier / Tier 0）には動画生成モデルが含まれていません。[クォータ増加申請](https://aka.ms/oai/stuquotarequest)が必要な場合があります。

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集（AZURE_OPENAI_ENDPOINT・AZURE_OPENAI_DEPLOYMENT_NAME を設定）

python main.py
```

実行すると、ジョブID→ステータス（`queued`→`in_progress`→`completed`）が5秒おきに表示され、完成すると `output.mp4` が保存されます（生成は1〜5分程度）。

## 注意点（試験の論点）
- コードは openai SDK の `client.videos.create()` / `retrieve()` / `download_content()` を使います（v1 API）。REST の `.../video/generations/jobs` 形式は404になりました（2026-09-22実測）。
- サイズは `720x1280` / `1280x720` / `1024x1792` / `1792x1024` のいずれかのみです。`480x480` 等は400エラーになります（2026-09-22実測）。
- 動画生成はプレビューです。対応リージョンが限られる点、クォータが最下位ティアに含まれない点は画像生成（L3-1）と同様です。

## 期待される出力（例）
```
Job created: video_xxxxxxxx
Job status: queued
Job status: in_progress
Job status: in_progress
Job status: completed
✅ Generated video saved as "output.mp4"
```

## つまずき
- **`DeprecationWarning: ... shut down on September 24, 2026.`**：Sora APIの提供終了警告です。動作した場合はそのまま進められますが、廃止後はこのレッスンを実行できません。
- **400エラー（サイズ指定）**：`size` パラメータが対応値（`720x1280`等）になっているか確認してください。
- **クォータ不足で `sora-2` をデプロイできない**：最下位ティアには動画生成モデルの既定割り当てがありません。[クォータ増加申請](https://aka.ms/oai/stuquotarequest)を出すか、承認まで動画で流れを確認してください。
- **ジョブが`failed`になる**：`video.error` にエラー内容が入っています。プロンプトの内容やリージョンのクォータを確認してください。

## 後片付け
- 動画生成は呼んだ回数・秒数分だけ課金されます。デプロイ自体は置いてあるだけでは課金されないので、他のレッスンで使わないなら削除は任意です。
