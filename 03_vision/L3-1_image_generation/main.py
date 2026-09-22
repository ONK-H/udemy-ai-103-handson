"""L3-1 実践: 画像を生成して、マスクで一部を編集する(inpainting)。

流れ:
  1) テキストから画像を生成 (client.images.generate)  -> generated.png
  2) 中央を透明にしたマスクを自動生成 (Pillow)         -> mask.png
  3) inpainting で透明部分だけを書き換える (client.images.edit) -> edited.png

GPT-image 系は応答を base64 (b64_json) で返すのでデコードして保存する。
認証はキーレス (az login 済みの DefaultAzureCredential)。

接続先は Foundry リソースの /openai/v1/ エンドポイント。プロジェクトのエンドポイント
(.../api/projects/<name>) 経由の project.get_openai_client() では、画像の生成・編集が
404 になる（2026-09-22 実測）ため、L1-5 の直接呼び出しと同じ形で OpenAI クライアントを作る。
"""

import os
import base64
from io import BytesIO

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image, ImageDraw

load_dotenv()

BASE_URL = os.getenv("FOUNDRY_OPENAI_BASE_URL")  # https://<resource>.openai.azure.com/openai/v1/
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")  # デプロイ名
SIZE = "1024x1024"

# キーレス認証: api_key の代わりに Entra ID のトークンプロバイダーを渡す
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://ai.azure.com/.default"
)
client = OpenAI(base_url=BASE_URL, api_key=token_provider)


def save_b64_png(b64_data: str, path: str):
    """base64 の画像データをデコードして PNG 保存する。"""
    img = Image.open(BytesIO(base64.b64decode(b64_data)))
    img.save(path)
    print(f"保存しました: {path}")


def generate_image(prompt: str, path: str):
    """テキストから画像を生成して保存(GPT-image 系は base64 を返す)。"""
    result = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        n=1,
        size=SIZE,
        quality="medium",      # 検証は medium で十分(low/medium/high)
        output_format="png",
    )
    save_b64_png(result.data[0].b64_json, path)


def make_center_mask(src_path: str, mask_path: str):
    """元画像と同じ寸法で、中央の矩形だけを透明(編集対象)にしたマスクPNGを作る。
    ルール: 透明(アルファ=0)の部分が「編集してよい領域」。それ以外は元画像が保持される。
    """
    base = Image.open(src_path).convert("RGBA")
    w, h = base.size
    # まず全面を不透明(白)で塗り、編集したい中央領域だけアルファ=0 にする
    mask = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(mask)
    # 中央 50% の矩形を透明にする
    left, top, right, bottom = w // 4, h // 4, w * 3 // 4, h * 3 // 4
    draw.rectangle([left, top, right, bottom], fill=(0, 0, 0, 0))
    mask.save(mask_path)
    print(f"保存しました: {mask_path}(中央が編集対象)")


def edit_image(src_path: str, mask_path: str, prompt: str, out_path: str):
    """inpainting: 画像 + マスク + プロンプトで、透明部分だけを書き換える。"""
    with open(src_path, "rb") as image_file, open(mask_path, "rb") as mask_file:
        result = client.images.edit(
            model=IMAGE_MODEL,
            image=image_file,
            mask=mask_file,
            prompt=prompt,
            n=1,
            size=SIZE,
            quality="medium",
        )
    save_b64_png(result.data[0].b64_json, out_path)


if __name__ == "__main__":
    try:
        # (1) 生成: テキスト -> 画像
        generate_image(
            "A cozy wooden desk by a window, soft morning light, minimal style",
            "generated.png",
        )
        # (2) マスク: 中央を透明にする(編集対象)
        make_center_mask("generated.png", "mask.png")
        # (3) 編集(inpainting): 中央にだけ観葉植物の鉢を追加
        #     プロンプトは「マスクの部分に何を描くか」を明示する。短く「Place a plant」だけだと、
        #     中央が黒く塗りつぶされて返ることがあった（2026-09-22 実測）。
        edit_image(
            "generated.png",
            "mask.png",
            "Fill the masked area with a small potted green plant standing on the desk, "
            "matching the lighting and style of the rest of the image",
            "edited.png",
        )
        print("\n完了: generated.png / mask.png / edited.png を見比べてください。")
    except Exception as ex:
        # コンテンツフィルタ(contentFilter)・認証・クォータ(429)等はここに来る
        print(f"エラー: {ex}")
