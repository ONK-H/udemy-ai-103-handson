"""L2-9 Microsoft Agent Framework で主＋専門エージェントを協調（Magentic）。

マネージャー（主）エージェントが専門エージェント（調査・執筆）を動的に
調整し、成果を統合する。認証はキーレス（AzureCliCredential + az login）。

⚠️ Agent Framework は活発に進化中。クラス名・引数が変わることがあるため、
   実行前に公式サンプルで最新APIを確認すること:
   https://github.com/microsoft/agent-framework/tree/main/python/samples/03-workflows/orchestrations
   （2026-09 時点で確認：agent-framework-core 1.19 / -foundry 1.13 / -orchestrations 1.2）
"""

import os
import sys
import asyncio
from collections import Counter
from typing import Annotated, Literal
from agent_framework import Agent, AgentResponseUpdate
from agent_framework.foundry import FoundryChatClient
from agent_framework.orchestrations import MagenticBuilder
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

load_dotenv()

DEFAULT_TASK = "社内の経費精算のルールを調べて、新入社員向けの案内を3行で書いて。"

# 社内規程（モック）。調査担当だけがこの関数ツールを持つ
POLICIES = {
    "経費精算": "申請は発生日から30日以内。領収書の画像を添付。1万円以上は上長の承認が必要。",
    "有給休暇": "申請は取得日の3営業日前まで。半日単位で取得できる。",
}


def lookup_policy(topic: Annotated[Literal["経費精算", "有給休暇"], "調べたい規程の名前"]) -> str:
    """社内規程を名前で調べて、本文を返す。"""
    result = POLICIES.get(topic, f"「{topic}」の規程はありません（あるのは {', '.join(POLICIES)}）")
    print(f"\n[ツール] lookup_policy({topic!r}) -> {result}", flush=True)
    return result


async def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK
    print(f"TASK> {task}  （モデル: {os.environ['FOUNDRY_MODEL']}）")

    # 共有クライアント（キーレス）
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["FOUNDRY_MODEL"],
        credential=AzureCliCredential(),
    )

    # 専門エージェント（役割を分ける）。description はマネージャーが担当を選ぶ手がかり
    researcher = Agent(client=client, name="researcher",
                       description="社内規程を lookup_policy ツールで調べる調査担当",
                       instructions="あなたは調査担当。社内規程は必ず lookup_policy で調べ、事実だけを箇条書き3点以内・各1行で返します。",
                       tools=[lookup_policy])
    writer = Agent(client=client, name="writer",
                   description="調査結果を読みやすい日本語に整える執筆担当",
                   instructions="あなたは執筆担当。調査結果を、指定の行数以内の分かりやすい日本語にまとめます。")
    # マネージャー（主）エージェント：計画・委譲・調整
    manager = Agent(client=client, name="manager",
                    description="計画を立て、専門エージェントに委譲して成果を統合する進行役",
                    instructions="あなたは進行役。専門エージェントに委譲し、成果を統合します。")

    # Magentic：マネージャーが専門エージェントを動的に調整
    workflow = MagenticBuilder(
        participants=[researcher, writer],
        manager_agent=manager,
        intermediate_output_from=[researcher, writer],  # 専門エージェントの途中出力も流す
        max_round_count=8,   # 調整ラウンドの上限
        max_stall_count=3,   # 停滞時の再計画上限
    ).build()

    delegated = Counter()  # マネージャーが次の担当に選んだ回数（＝委譲の回数）
    rounds = 0             # 進捗台帳の更新回数（＝調整ラウンド）
    last_speaker = None    # 直前に出力した話者（見出しを出す判定用）
    # ストリーミング実行（旧 API の run_stream() は廃止 → run(..., stream=True)）
    async for event in workflow.run(task, stream=True):
        if event.type == "magentic_orchestrator":
            # マネージャーの節目（計画作成・再計画・進捗台帳の更新）
            kind = event.data.event_type.name
            if kind == "PROGRESS_LEDGER_UPDATED":
                rounds += 1
                ledger = event.data.content
                if ledger.is_request_satisfied.answer is True:
                    print(f"\n[manager] {kind} → 完了と判断（最終成果をまとめる）", flush=True)
                else:
                    nxt = ledger.next_speaker.answer
                    delegated[nxt] += 1
                    print(f"\n[manager] {kind} → 次の担当: {nxt}", flush=True)
            else:
                print(f"\n[manager] {kind}", flush=True)
            last_speaker = None  # マネージャーの節目のあとは、同じ担当でも見出しを出し直す
        elif event.type in ("intermediate", "output") and isinstance(event.data, AgentResponseUpdate):
            # intermediate＝専門エージェントの途中出力 / output＝マネージャーの最終成果
            # message_id は None のことがあるため、話者（担当の名前）が変わったときに見出しを出す
            label = "最終成果" if event.type == "output" else event.executor_id
            if label != last_speaker:
                print(f"\n--- {label} ---", flush=True)
                last_speaker = label
            print(event.data, end="", flush=True)
    print()
    summary = " / ".join(f"{name} {n} 回" for name, n in delegated.items()) or "なし"
    print(f"\n[まとめ] 調整ラウンド {rounds} 回、委譲: {summary}")


if __name__ == "__main__":
    asyncio.run(main())
