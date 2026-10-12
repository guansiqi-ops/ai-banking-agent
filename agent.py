import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL_NAME", "deepseek-chat")

print(f"API_KEY: {API_KEY[:10] if API_KEY else 'None'}...")
print(f"BASE_URL: {BASE_URL}")
print(f"MODEL: {MODEL}")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

def parse_intent(user_input: str) -> dict:
    print(f"正在解析: {user_input}")
    
    prompt = f"""
你是一个银行智能助手。请将用户的指令解析为JSON格式。

用户说："{user_input}"

支持的场景：
1. 转账 (transfer): 按人名/手机号转账、定时转账
2. AA收款 (aa): 拆分AA收款
3. 账单查询 (query_bill): 月度/年度账单
4. 卡片管理 (card_manage): 申请/冻结/解冻/挂失
5. 风险评估 (risk_assess): 评估风险等级，推荐产品
6. 订阅管理 (subscribe_manage): 取消订阅/续费提醒

输出规则：
- 只输出JSON，不要有任何额外文字
- action字段：transfer/aa/query_bill/card_manage/risk_assess/subscribe_manage/unknown

各场景JSON格式：
1. 转账: {{"action":"transfer","recipient":"姓名","amount":金额,"time":"立即/定时时间"}}
2. AA: {{"action":"aa","total_amount":总金额,"people":["人名1","人名2"]}}
3. 账单: {{"action":"query_bill","type":"monthly/yearly"}}
4. 卡片: {{"action":"card_manage","card_number":"卡号","operation":"apply/freeze/unfreeze/loss"}}
5. 风险评估: {{"action":"risk_assess"}}
6. 订阅: {{"action":"subscribe_manage","merchant":"商户名","amount":金额,"operation":"cancel/renew"}}

示例：
输入："转500给张三"
输出：{{"action":"transfer","recipient":"张三","amount":500}}

输入："明天下午3点转200给李四"
输出：{{"action":"transfer","recipient":"李四","amount":200,"time":"明天下午3点"}}

输入："300块3个人AA"
输出：{{"action":"aa","total_amount":300,"people":["张三","李四","王五"]}}

输入："这个月账单"
输出：{{"action":"query_bill","type":"monthly"}}

输入："冻结卡片6222****1234"
输出：{{"action":"card_manage","card_number":"6222****1234","operation":"freeze"}}

输入："挂失我的信用卡"
输出：{{"action":"card_manage","card_number":"6222****1234","operation":"loss"}}

输入："帮我评估风险"
输出：{{"action":"risk_assess"}}

输入："取消Netflix订阅"
输出：{{"action":"subscribe_manage","merchant":"Netflix","operation":"cancel"}}

现在请解析：{user_input}
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        content = response.choices[0].message.content
        print(f"原始返回: {content}")
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        result = json.loads(content)
        print(f"解析结果: {result}")
        return result
    except Exception as e:
        print(f"错误: {e}")
        return {"action": "unknown", "raw": user_input}