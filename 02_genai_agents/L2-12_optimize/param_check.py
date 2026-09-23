"""L2-12 推論モデルと推論しないモデルで、使えるパラメーターが違うことを確かめる。

同じ短い質問を、temperature や reasoning（推論の強さ）を付けて送り、通るか 400 になるかを表示する。
Learn（Azure OpenAI reasoning models）は、推論モデルでは temperature・top_p などを使えないとしている。
"""

import os

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from dotenv import load_dotenv

load_dotenv()
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")

# (デプロイ名, 付けるパラメーター)
CASES = [
    ("gpt-4.1-mini", {"temperature": 0.2}),
    ("gpt-4.1-mini", {"reasoning": {"effort": "medium"}}),
    ("gpt-5.4", {"reasoning": {"effort": "medium"}}),
    ("gpt-5.4", {"reasoning": {"effort": "medium"}, "temperature": 0.2}),
]


def main() -> None:
    if not PROJECT_ENDPOINT:
        raise SystemExit("PROJECT_ENDPOINT が未設定です。.env を確認してください。")
    openai = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential()).get_openai_client()

    for model, params in CASES:
        try:
            r = openai.responses.create(model=model, input="1+1は？数字だけ", **params)
            rsn = r.usage.output_tokens_details.reasoning_tokens
            print(f"OK   {model:<13}{params}  → 答え {r.output_text}（うち推論トークン {rsn}）")
        except Exception as e:  # 400 の本文から message だけを出す
            msg = getattr(e, "body", None) or {}
            msg = msg.get("message", str(e)) if isinstance(msg, dict) else str(e)
            print(f"400  {model:<13}{params}  → {msg}")


if __name__ == "__main__":
    main()
