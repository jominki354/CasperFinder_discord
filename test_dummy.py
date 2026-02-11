"""
더미 데이터 테스트 — 각 기획전 채널에 샘플 Embed 1개씩 전송
"""

import asyncio
from datetime import datetime
import discord
from core.config import load_config

config = load_config()

DUMMY_VEHICLES = [
    {
        "label": "특별기획전",
        "color": 0x3B82F6,
        "vehicle": {
            "modelNm": "캐스퍼 일렉트릭",
            "trimNm": "인스퍼레이션",
            "extCrNm": "아틀라스 화이트",
            "intCrNm": "블랙 인조가죽",
            "poName": "인천출고센터",
            "price": 35040000,
            "discountAmt": 1500000,
            "optionList": [
                {"optName": "선루프"},
                {"optName": "현대 스마트센스 I"},
                {"optName": "컴포트"},
            ],
            "vehicleId": "TEST-001",
        },
    },
    {
        "label": "전시차",
        "color": 0x8B5CF6,
        "vehicle": {
            "modelNm": "캐스퍼 일렉트릭",
            "trimNm": "프리미엄",
            "extCrNm": "톰보이 카키",
            "intCrNm": "뉴트로 베이지",
            "poName": "칠곡출고센터",
            "price": 29360000,
            "discountAmt": 0,
            "optionList": [
                {"optName": "하이패스"},
            ],
            "vehicleId": "TEST-002",
        },
    },
    {
        "label": "리퍼브",
        "color": 0x10B981,
        "vehicle": {
            "modelNm": "캐스퍼 일렉트릭",
            "trimNm": "크로스",
            "extCrNm": "어비스 블랙 펄",
            "intCrNm": "다크 그레이 라이트 카키 베이지",
            "poName": "양산출고센터",
            "price": 35150000,
            "discountAmt": 500000,
            "optionList": [
                {"optName": "파킹 어시스트"},
                {"optName": "익스테리어 디자인"},
            ],
            "vehicleId": "TEST-003",
        },
    },
]


def fmt_price(value):
    if isinstance(value, (int, float)) and value > 0:
        return f"{int(value):,}원"
    return "-"


def build_embed(vehicle, label, color):
    model = vehicle.get("modelNm", "-")
    trim = vehicle.get("trimNm", "-")
    ext = vehicle.get("extCrNm", "-")
    intc = vehicle.get("intCrNm", "-")
    center = vehicle.get("poName", "-")
    price = vehicle.get("price", 0)
    discount = vehicle.get("discountAmt", 0)
    opts = vehicle.get("optionList", [])
    opt_text = ", ".join(o.get("optName", "") for o in opts) if opts else "없음"
    vid = vehicle.get("vehicleId", "")
    url = f"https://casper.hyundai.com/vehicles/detail?vehicleId={vid}"

    desc = (
        f"**모델** {model} / {trim}\n"
        f"**외장** {ext}\n"
        f"**내장** {intc}\n"
        f"**출고** {center}\n"
        f"**가격** {fmt_price(price)}\n"
        f"**할인** {fmt_price(discount)}\n"
        f"**옵션** {opt_text}\n\n"
        f"**[구매링크]({url})**"
    )

    return discord.Embed(
        title=f"{label} — 신규 차량",
        description=desc,
        color=color,
        timestamp=datetime.now(),
    )


async def main():
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"[테스트] 로그인: {client.user}")

        integrated_ch = client.get_channel(
            int(config["discord"]["integratedChannelId"])
        )

        for i, dummy in enumerate(DUMMY_VEHICLES):
            target = config["targets"][i]
            embed = build_embed(dummy["vehicle"], dummy["label"], dummy["color"])

            # 통합 채널
            if integrated_ch:
                await integrated_ch.send(content="@everyone", embed=embed)
                print(f"[테스트] #통합 전송 완료 — {dummy['label']}")

            # 개별 채널
            target_ch = client.get_channel(int(target["channelId"]))
            if target_ch:
                await target_ch.send(content="@everyone", embed=embed)
                print(f"[테스트] #{dummy['label']} 전송 완료")

        print("[테스트] 완료. 종료합니다.")
        await client.close()

    await client.start(config["discord"]["token"])


asyncio.run(main())
