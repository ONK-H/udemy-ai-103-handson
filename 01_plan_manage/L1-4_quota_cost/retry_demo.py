"""L1-4 実践(2/3): レート制限(429)に強いリトライを実装する。

2 通りを示す:
  方式A) SDK 組み込みリトライ  : openai SDK は 429/一時エラーを指数バックオフで自動再試行(既定2回)。
                                 client.with_options(max_retries=N) で増やすだけ(最も簡単・推奨)。
  方式B) 手動の指数バックオフ  : retry-after を尊重しつつ、自前で backoff + jitter + 最大回数。
                                 中身を理解したいとき / 細かく制御したいとき。

認証はキーレス(DefaultAzureCredential)。本講座の標準どおり
AIProjectClient -> get_openai_client() で Responses API クライアントを取得する。

※ 429 を確実に再現するにはクォータ超過が必要。通常は成功するが、
   「429 を受けたら自動で再試行する形になっている」ことを確認するのが狙い。
"""
import os
import random
import time

import openai
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
MODEL = os.getenv("MODEL_DEPLOYMENT", "gpt-5.4")  # デプロイ名 (カタログ名ではない)
PROMPT = "クォータとレート制限の違いを1文で説明してください。"

project = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential())
client = project.get_openai_client()  # openai 互換クライアント (Responses API)


def call_with_sdk_retry(max_retries: int = 8):
    """方式A: SDK 組み込みリトライ。with_options で max_retries を上書きするだけ。"""
    # SDK が retry-after を尊重し、指数バックオフ + ジッターで自動再試行する
    res = client.with_options(max_retries=max_retries).responses.create(model=MODEL, input=PROMPT)
    return res.output_text


def call_with_manual_backoff(
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    max_retries: int = 6,
):
    """方式B: 手動の指数バックオフ。429(RateLimitError) のときだけ待って再試行する。"""
    num_retries = 0
    delay = initial_delay
    while True:
        try:
            # 自前で待つので SDK 側のリトライは 0 にする（二重に効くと待ち時間が掛け算になる）
            res = client.with_options(max_retries=0).responses.create(model=MODEL, input=PROMPT)
            return res.output_text
        except openai.RateLimitError as ex:
            num_retries += 1
            if num_retries > max_retries:
                raise Exception(f"最大リトライ回数({max_retries})を超えました") from ex
            # retry-after-ms ヘッダがあれば最優先で使う
            retry_after = None
            resp = getattr(ex, "response", None)
            if resp is not None:
                ms = resp.headers.get("retry-after-ms")
                retry_after = (int(ms) / 1000.0) if ms else None
            wait = retry_after if retry_after is not None else delay * (1 + jitter * random.random())
            print(f"  429 を受信。{wait:.2f}s 待って再試行 ({num_retries}/{max_retries})")
            time.sleep(wait)
            delay *= exponential_base  # 失敗のたびに遅延を倍に


def main():
    try:
        print("===== 方式A: SDK 組み込みリトライ (max_retries=8) =====")
        print(call_with_sdk_retry())

        print("\n===== 方式B: 手動の指数バックオフ =====")
        print(call_with_manual_backoff())
    except Exception as ex:
        print(f"エラー: {ex}")


if __name__ == "__main__":
    main()
