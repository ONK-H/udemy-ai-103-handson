"""L3-4 実践: 画像を Content Safety に送り、しきい値で受理/拒否を判定する。

Content Safety は 4カテゴリ(Hate/Sexual/Violence/Self-Harm)の重大度(0/2/4/6)を
マルチラベルで返すだけ。受理(Accepted)/拒否(Rejected)はアプリ側がしきい値で決める。
認証はキーレス(DefaultAzureCredential)。

使い方:
  python main.py                      # test.jpg を判定
  python main.py <画像のパス>          # 別の画像を判定
  python main.py test.jpg --threshold 0   # すべてのカテゴリのしきい値を上書きして判定
"""

import argparse
import os

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeImageOptions, ImageData
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.environ["CONTENT_SAFETY_ENDPOINT"]

# カテゴリごとの拒否しきい値(この重大度「以上」なら拒否)。0/2/4/6 の4段階。
# 例: 性的・暴力は厳しめ(2)、ヘイト・自傷は中(4)
THRESHOLDS = {"Sexual": 2, "Violence": 2, "Hate": 4, "SelfHarm": 4}

# キーレス認証
client = ContentSafetyClient(ENDPOINT, DefaultAzureCredential())


def analyze(image_path: str, thresholds: dict) -> str:
    with open(image_path, "rb") as f:
        data = f.read()
    print(f"画像: {image_path}（{len(data) // 1024} KB）")

    request = AnalyzeImageOptions(image=ImageData(content=data))
    response = client.analyze_image(request)

    rejected = False
    print("=== カテゴリ別の重大度 (0=Safe,2=Low,4=Medium,6=High) ===")
    for item in response.categories_analysis:
        cat = item.category
        sev = item.severity
        limit = thresholds.get(str(cat), 4)
        flag = "NG(拒否)" if sev >= limit else "OK"
        if sev >= limit:
            rejected = True
        print(f"  {cat}: severity={sev} / しきい値={limit} -> {flag}")

    # 判定はサービスではなく、このアプリが決めている
    verdict = "Rejected(拒否)" if rejected else "Accepted(受理)"
    print(f"\n判定: {verdict}")
    return verdict


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="?", default="test.jpg")
    parser.add_argument("--threshold", type=int, choices=[0, 2, 4, 6],
                        help="すべてのカテゴリのしきい値をこの値で上書きする")
    args = parser.parse_args()

    thresholds = dict(THRESHOLDS)
    if args.threshold is not None:
        thresholds = {k: args.threshold for k in THRESHOLDS}

    try:
        analyze(args.image, thresholds)
    except HttpResponseError as ex:
        # 入力の制限違反・権限不足・リージョン未対応などはここに来る
        code = (ex.error.code if ex.error else None) or ex.reason
        msg = ex.error.message if ex.error else ex.message
        print(f"Content Safety エラー: {ex.status_code} {code}: {msg}")
    except FileNotFoundError:
        print(f"画像が見つかりません: {args.image}")
