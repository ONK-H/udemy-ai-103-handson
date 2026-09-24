"""L3-2 実践: テキストから短い動画を非同期生成して取得する（動画生成モデル sora-2）。

動画生成は非同期のジョブ。流れは次の3段:
  1) ジョブ作成   client.videos.create()    -> すぐに ID と status=queued が返る
  2) 状態の確認   client.videos.retrieve()  -> queued -> in_progress -> completed / failed
  3) 取得         client.videos.download_content() -> output.mp4

使い方:
  python main.py                 生成して output.mp4 に保存する
  python main.py --seconds 5     対応していない長さを渡して、400 の中身を見る
  python main.py list            サービスに保存されている動画の一覧
  python main.py delete all      保存されている動画をすべて削除する

認証はキーレス（az login 済みの DefaultAzureCredential）。動画生成はプレビュー。
"""

import argparse
import os
import sys
import time
import warnings

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv()

BASE_URL = os.environ["FOUNDRY_OPENAI_BASE_URL"]      # https://<リソース名>.openai.azure.com/openai/v1/
DEPLOYMENT = os.environ.get("VIDEO_MODEL", "sora-2")   # デプロイ名
PROMPT = ("A paper boat drifting slowly on a calm pond at sunrise, "
          "soft watercolor illustration style, gentle camera pan")

# キーレス認証: az login した ID のトークンを、呼び出しのたびに取り直す
token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")
client = OpenAI(base_url=BASE_URL, api_key=token_provider)

# openai SDK は動画 API を呼ぶたびに提供終了の予告（DeprecationWarning）を出す。
# 画面が流れないよう、1回だけ表示して以降は出さない。
warnings.simplefilter("once", DeprecationWarning)
warnings.showwarning = lambda msg, *a, **k: print(f"[SDK の警告] {msg}")


def generate(size: str, seconds: str) -> None:
    print(f"デプロイ: {DEPLOYMENT} / サイズ: {size} / 長さ: {seconds} 秒")
    # 1) ジョブ作成。ここではまだ動画はできていない（ID と状態だけが返る）
    video = client.videos.create(model=DEPLOYMENT, prompt=PROMPT, size=size, seconds=seconds)
    print(f"ジョブを作成: {video.id}  状態: {video.status}")

    # 2) 状態をポーリング（5秒おき）。状態か進み具合が変わったときだけ表示する
    start, last = time.time(), None
    while video.status not in ("completed", "failed"):
        time.sleep(5)
        video = client.videos.retrieve(video.id)
        now = (video.status, video.progress)
        if now != last:
            print(f"  {int(time.time() - start):>3} 秒  状態: {video.status}  進み: {video.progress}%")
            last = now

    # 3) 完成したらダウンロード。失敗なら理由を1行で出す
    if video.status == "completed":
        content = client.videos.download_content(video.id, variant="video")
        content.write_to_file("output.mp4")
        print(f"保存しました: output.mp4（{os.path.getsize('output.mp4'):,} バイト）"
              f"  かかった時間: {int(time.time() - start)} 秒")
    else:
        print(f"失敗しました: {video.error}")


def list_videos() -> None:
    items = list(client.videos.list())
    print(f"保存されている動画: {len(items)} 件")
    for v in items:
        print(f"  {v.id}  {v.status}  {v.size}  {v.seconds} 秒")


def delete_all() -> None:
    for v in list(client.videos.list()):
        client.videos.delete(v.id)
        print(f"削除しました: {v.id}")
    print(f"残り: {len(list(client.videos.list()))} 件")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("mode", nargs="?", default="generate", choices=["generate", "list", "delete"])
    p.add_argument("target", nargs="?", default="all")
    p.add_argument("--size", default=os.environ.get("VIDEO_SIZE", "1280x720"))
    p.add_argument("--seconds", default=os.environ.get("VIDEO_SECONDS", "4"))
    a = p.parse_args()
    try:
        if a.mode == "list":
            list_videos()
        elif a.mode == "delete":
            delete_all()
        else:
            generate(a.size, a.seconds)
    except OpenAIError as ex:
        # 長いスタックトレースで画面が流れないよう、要点だけ1行で出す
        print(f"エラー: {str(ex).splitlines()[0][:220]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
