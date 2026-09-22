"""L3-2 実践: テキストから短い動画を非同期生成して取得する(Sora 2)。

動画生成は非同期。ライフサイクルは:
  1) ジョブ作成 (client.videos.create)
  2) 状態ポーリング (client.videos.retrieve)  queued -> in_progress -> completed
  3) 動画ダウンロード (client.videos.download_content) -> output.mp4

認証はキーレス (az login 済みの DefaultAzureCredential)。動画生成はプレビュー。
"""

import os
import time
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

load_dotenv()

endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
deployment_name = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]

# --- キーレス認証(az login 済みの資格情報からトークンを取得) ---
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://ai.azure.com/.default"
)
client = OpenAI(base_url=f"{endpoint}/openai/v1/", api_key=token_provider)

try:
    # 1) ジョブ作成(テキスト -> 動画)。検証用に短い秒数で
    video = client.videos.create(
        model=deployment_name,
        prompt="A cat playing piano in a cozy jazz bar, warm lighting",
        size="720x1280",
        seconds="4",
    )
    print(f"Job created: {video.id}")
    print(f"Job status: {video.status}")

    # 2) 状態をポーリング(completed/failed/cancelled になるまで)
    while video.status not in ("completed", "failed", "cancelled"):
        time.sleep(5)  # 数秒おきに確認(生成は1〜5分程度)
        video = client.videos.retrieve(video.id)
        print(f"Job status: {video.status}")

    # 3) 完成した動画をダウンロード
    if video.status == "completed":
        content = client.videos.download_content(video.id, variant="video")
        content.write_to_file("output.mp4")
        print('✅ Generated video saved as "output.mp4"')
    else:
        raise Exception(f"Job didn't succeed. Status: {video.status}. Error: {video.error}")
except Exception as ex:
    print(f"エラー: {ex}")
