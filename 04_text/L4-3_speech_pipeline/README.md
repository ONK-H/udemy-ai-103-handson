# L4-3 実践: 音声パイプライン（STT → LLM → TTS）

①**STT**（音声→テキスト）→ ②**LLM**（Responses API で処理）→ ③**TTS**（テキスト→音声）を1本のパイプラインでつなぐハンズオンです。認証はキーレス（Entra ID）。STT は `token_credential`、TTS も `token_credential` で書けます（マイク・スピーカーの無い環境では、WAVファイルの入出力で代替します）。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `main.py` | STT → LLM → TTS の一連の処理 |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Speech リソース作成済み（**カスタムドメイン必須**。キーレス認証の前提）・Foundry プロジェクトにチャットモデルをデプロイ済み
- 入力用の `input.wav`（自分の声・自由な素材で用意。16kHz/16bit/モノラルが既定）

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集: SPEECH_ENDPOINT / SPEECH_REGION / SPEECH_RESOURCE_ID / PROJECT_ENDPOINT / MODEL_DEPLOYMENT を埋める
# INPUT_WAV に input.wav を指定（マイクが無い場合）。無ければ既定のマイクを使う

python main.py
```

### もう一度STTに通して確かめる（任意）
```powershell
# 1回目の出力 output.wav を、もう一度STTにかけて文字起こしを見る
$env:INPUT_WAV = "output.wav"
python main.py | Select-String "STT"
Remove-Item Env:INPUT_WAV
```

### わざと失敗させる（任意）
```powershell
# 存在しない入力ファイル
$env:INPUT_WAV = "no-such.wav"
python main.py
Remove-Item Env:INPUT_WAV

# 実在しないエンドポイント
$env:SPEECH_ENDPOINT = "https://no-such-host.cognitiveservices.azure.com"
python main.py
Remove-Item Env:SPEECH_ENDPOINT
```

## 期待される出力（例）
```
[STT] Azure でキーを使わずに認証する方法を、一文で教えてください。
[LLM] （応答テキスト）
[TTS] output.wav に書き出しました
```

## つまずき
- **`token_credential` を使うとリージョン名のエンドポイントが通らない**：`SpeechConfig(token_credential=...)` はカスタムドメインのエンドポイントが前提。`SPEECH_REGION` はこの書き方では使わない。
- **`.env` の値が反映されない**：`load_dotenv()` は既存の環境変数を上書きしないので、シェルの環境変数が優先される。`Remove-Item Env:<変数名>` で消してから再実行する。
- **入力ファイルが見つからない**：`INPUT_WAV` のパスを確認。空にすると既定のマイクにフォールバックする（Codespacesなどマイクの無い環境ではエラーになる）。
- **デプロイ名エラー**：`MODEL_DEPLOYMENT` はカタログ名ではなく「デプロイ名」。

## 後片付け
呼び出した分だけの課金で、共有のリソースは消しません。
