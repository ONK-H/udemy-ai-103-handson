# L4-4 実践: Voice Live エージェント

Foundry エージェントに **Voice Live**（声・VAD・ノイズ抑制の設定）を持たせて作成し、Voice Live API 経由で接続する2ステップのハンズオンです。エージェント経由の接続は**キー認証不可＝Entra ID（キーレス）必須**です。マイク・スピーカーの無い環境（Codespaces等）では、接続・セッション確立までを確認します。

## ファイル構成
| ファイル | 役割 |
|---|---|
| `create_agent_with_voicelive.py` | Voice Live 設定つきの Foundry エージェントを作成（metadata の512字制限に合わせて分割格納） |
| `voice_live_agent.py` | 作成したエージェントに Voice Live で接続する（接続・セッション設定まで。マイク入出力は公式サンプル参照） |
| `.env.sample` | 環境変数の雛形 |
| `requirements.txt` | Python 依存パッケージ（`azure-ai-voicelive` の非同期接続に `aiohttp` が必須） |

## 前提
- Azure サブスクリプション ／ `az login` 済み ／ Python 3.11+
- Foundry プロジェクトにチャットモデルをデプロイ済み
- プロジェクトに対する **Foundry User** ロール

## 進め方
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Successfully installed の行に azure-ai-voicelive / aiohttp / azure-ai-projects が並べば成功

copy .env.sample .env             # macOS/Linux: cp .env.sample .env
# .env を編集: PROJECT_ENDPOINT / VOICELIVE_ENDPOINT / PROJECT_NAME / AGENT_NAME / MODEL_DEPLOYMENT_NAME の5つを埋める
# 2つのエンドポイントはドメインが違う別ものなので取り違えないこと

# 1) Voice Live 設定つきエージェントを作成
python create_agent_with_voicelive.py

# 2) 作成したエージェントに接続する
python voice_live_agent.py
```

### わざと失敗させる（任意）
```powershell
# 存在しないエージェント名で接続
$env:AGENT_NAME = "no-such-agent"
python voice_live_agent.py
Remove-Item Env:AGENT_NAME   # 元の .env の値に戻す
```

## 期待される出力（例）
`create_agent_with_voicelive.py`：
```
エージェントを作成しました: voice-live-demo-agent
```

`voice_live_agent.py`（正常時）：
```
接続しました。セッションを設定しています…
session.updated を受信しました
```

## つまずき
- **接続に失敗する / 401**：エージェント経由はキー認証不可。`az login` 済みでキーレス（`DefaultAzureCredential`）になっているか確認する。
- **`event: error` が届く**：エージェント名が間違っている可能性が高い。`READY` は接続成功の印ではなく、`session.updated` を目印にする。
- **`.env` を直しても反映されない**：シェルの環境変数が優先される（`load_dotenv()` は既存の環境変数を上書きしない）。`Remove-Item Env:<変数名>` で消す。
- **同じ内容で `create_agent_with_voicelive.py` を2回実行しても新しいバージョンにならない**：定義が同じなら `create_version` は新バージョンを積まない仕様。何か1つでも変えると新バージョンになる。
- **`ImportError`（aiohttp関連）**：`azure-ai-voicelive` の非同期接続（`aio.connect`）には `aiohttp` が必要。`requirements.txt` どおりに入っているか確認する。

## 後片付け
作成したエージェントは、他のレッスンで使わないなら Foundry ポータルの「エージェント」から削除してください。呼び出した分のみ課金され、エージェントを残しておくだけでは課金されません。
