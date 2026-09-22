# L2-1 実践: 履歴つき・ストリーミング表示の CLI チャットアプリ

Microsoft Foundry のプロジェクトに接続し、**Responses API** で多ターン対話する最小の CLI チャットです。会話履歴を自前の配列で保持し（方式B）、`stream=True` で逐次表示、システムメッセージは `instructions` で毎ターン効かせます。

> 対応レクチャー：実践 `L2-1-3`
> 認証は**キーレス**（`az login` ＋ `DefaultAzureCredential`）。APIキーは使いません。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | 履歴つき・ストリーミング表示の CLI チャット本体 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ（`azure-ai-projects>=2.0.0` は 1.x と非互換） |

## 前提
- **Foundry プロジェクト**にチャットモデルをデプロイ済み（`MODEL_DEPLOYMENT` は**デプロイ名**。カタログ名ではない）
- `az login` 済み ／ Python 3.10+
- ロール：プロジェクトに **Foundry User**

## 進め方
```bash
python -m venv .venv
. .venv/bin/Activate.ps1        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.sample .env             # Windows: copy .env.sample .env
```

`.env` の `PROJECT_ENDPOINT` は、`az` が使えるなら次のコマンドで取得できます（リソース名・プロジェクト名は自分の環境のものに置き換える）：
```bash
az cognitiveservices account project show \
  --name <project-name> --resource-group <resource-group> \
  --query 'properties.endpoints."AI Foundry API"' -o tsv
```

`.env` を編集して `PROJECT_ENDPOINT` と `MODEL_DEPLOYMENT`（自分の環境の実際のデプロイ名）を書き込んだら：
```bash
python main.py
```

## 使い方
起動すると `あなた>` のプロンプトが出ます。日本語で話しかけると、ストリーミングで逐次応答が表示されます。`exit` または `quit` で終了します。

## 期待される出力（例）
```
CLIチャット（終了: exit / quit）。話しかけてください。

あなた> Microsoft Foundryとは何ですか？
AI> Microsoft Foundry は、生成AIアプリケーションを構築・運用するための統合プラットフォームです。...

あなた> exit
終了します。
```

## ポイント（試験の論点）
- **会話履歴は自前で配列管理**（`history` に `user`/`assistant` を積んでいく）。システムメッセージは履歴に入れず、毎ターン `instructions` で渡す。
- `system` の直後に `type` を付けない `user` メッセージを置くと **400** になる（Responses API の仕様）。本コードは `instructions=` を使うことでこの問題を回避している。
- `stream=True` にすると `response.output_text.delta` イベントが逐次届き、`response.completed` で終了する。TTFT（最初のトークンまでの時間）が体感で短くなる。

## つまずきポイント
| 症状 | 対処 |
|---|---|
| `model not found` | `MODEL_DEPLOYMENT` が**デプロイ名**と一致しているか（カタログ名ではない） |
| `401`/`403` | `az login` 済みか、プロジェクトに **Foundry User** ロールがあるか |
| エラー時に会話が壊れる | 本コードは失敗したユーザー発言を履歴から取り除いてから続行する |

## 後片付け（課金回避）
- 推論を数回するだけ（数円程度）。削除が必要な永続リソースはありません。
