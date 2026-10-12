from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
import os
import json
from datetime import datetime
from agent import parse_intent

app = FastAPI(title="AI Banking Agent")

app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    text: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    reply: str
    action: str
    data: dict = {}
    need_confirm: bool = False
    risk_level: str = "绿色"

sessions = {}
BANK_API_URL = "http://localhost:8001"

def check_permission(action: str, amount: float = 0) -> tuple:
    if action in ["query_bill", "health", "transactions", "risk_assess"]:
        return ("绿色", False, False)
    if action in ["aa", "card_manage", "subscribe_manage"]:
        return ("黄色", True, False)
    if action == "transfer" and amount <= 1000:
        return ("黄色", True, False)
    if action == "transfer" and amount > 1000:
        return ("红色", True, True)
    return ("黄色", True, False)

def log_audit(action: str, details: dict, level: str = "INFO"):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
        "level": level
    }
    with open("audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    return log_entry

@app.post("/api/chat")
def chat(req: ChatRequest):
    intent = parse_intent(req.text)
    action = intent.get("action", "unknown")
    amount = intent.get("amount", 0)
    
    risk_level, need_confirm, need_auth = check_permission(action, amount)
    
    if action == "transfer":
        return handle_transfer(intent, need_confirm, need_auth)
    elif action == "aa":
        return handle_aa(intent, need_confirm)
    elif action == "query_bill":
        return handle_query_bill(intent)
    elif action == "card_manage":
        return handle_card_manage(intent, need_confirm)
    elif action == "risk_assess":
        return handle_risk_assess(intent)
    elif action == "subscribe_manage":
        return handle_subscribe_manage(intent, need_confirm)
    elif action == "unknown":
        log_audit("未知指令", {"text": req.text}, "WARNING")
        return ChatResponse(
            reply="抱歉，我没理解您的意思。试试：\n💰 转500给张三\n📊 这个月账单\n👥 300块3个人AA\n💳 冻结卡片6222****1234",
            action="unknown",
            data={}
        )
    else:
        return ChatResponse(reply=f"功能'{action}'正在开发中", action=action, data={})

def handle_transfer(intent: dict, need_confirm: bool, need_auth: bool) -> ChatResponse:
    recipient = intent.get("recipient")
    amount = intent.get("amount")
    time = intent.get("time", "立即")
    
    if not recipient or not amount:
        return ChatResponse(
            reply="请告诉我转给谁、转多少？例如：'转500给张三'",
            action="transfer", data={}
        )
    
    auth_msg = ""
    if need_auth:
        auth_msg = " ⚠️ 大额转账需要人脸验证，请打开APP完成"
    elif need_confirm:
        auth_msg = " ℹ️ 请在APP确认此操作"
    
    try:
        resp = requests.post(
            f"{BANK_API_URL}/api/transfer",
            json={"recipient": recipient, "amount": amount, "time": time},
            timeout=5
        )
        result = resp.json()
        
        if result.get("status") == "success":
            log_audit("转账成功", {"order_id": result.get("order_id"), "amount": amount})
            return ChatResponse(
                reply=f"✅ {result['message']}，订单号：{result.get('order_id', '')}{auth_msg}",
                action="transfer", data=result,
                need_confirm=need_confirm,
                risk_level="红色" if need_auth else ("黄色" if need_confirm else "绿色")
            )
        else:
            return ChatResponse(
                reply=f"❌ 转账失败：{result.get('message', '未知错误')}",
                action="transfer", data=result
            )
    except Exception as e:
        log_audit("转账异常", {"error": str(e)}, "ERROR")
        return ChatResponse(reply=f"⚠️ 系统异常：{str(e)}", action="transfer", data={})

def handle_aa(intent: dict, need_confirm: bool) -> ChatResponse:
    total = intent.get("total_amount")
    people = intent.get("people", [])
    
    if not total or not people:
        return ChatResponse(
            reply="请告诉我总金额和参与AA的人，例如：'300块3个人AA'",
            action="aa", data={}
        )
    
    try:
        total = float(total)
        if isinstance(people, int):
            people = [f"人{i+1}" for i in range(people)]
        elif isinstance(people, str):
            people = [people]
        
        resp = requests.post(
            f"{BANK_API_URL}/api/aa",
            json={"total_amount": total, "people": people},
            timeout=5
        )
        result = resp.json()
        
        if result.get("status") == "success":
            log_audit("AA收款", {"total": total, "people": people})
            confirm_msg = " ℹ️ 请在APP确认此操作" if need_confirm else ""
            return ChatResponse(
                reply=f"💰 {result['message']}，每人{result['per_person']}元{confirm_msg}",
                action="aa", data=result,
                need_confirm=need_confirm, risk_level="黄色"
            )
        else:
            return ChatResponse(
                reply=f"❌ AA计算失败：{result.get('message', '未知错误')}",
                action="aa", data=result
            )
    except Exception as e:
        log_audit("AA异常", {"error": str(e)}, "ERROR")
        return ChatResponse(reply=f"⚠️ AA计算异常：{str(e)}", action="aa", data={})

def handle_query_bill(intent: dict) -> ChatResponse:
    bill_type = intent.get("type", "monthly")
    mock_data = {
        "monthly": {
            "total": 3420.50,
            "categories": {"餐饮": 1200, "购物": 800, "交通": 300, "其他": 1120.50},
            "anomalies": ["2026-09-01 消费2680元，超出日常3倍"]
        },
        "yearly": {
            "total": 41200.00,
            "categories": {"餐饮": 15000, "购物": 12000, "房租": 10000, "其他": 4200},
            "anomalies": ["2026-03-15 消费15000元，超出日常5倍"]
        }
    }
    data = mock_data.get(bill_type, mock_data["monthly"])
    log_audit("账单查询", {"type": bill_type})
    
    anomaly_msg = ""
    if data.get("anomalies"):
        anomaly_msg = f"\n⚠️ 异常交易：{data['anomalies'][0]}"
    
    return ChatResponse(
        reply=f"📊 {bill_type}账单：总计{data['total']}元，分类：{data['categories']}{anomaly_msg}",
        action="query_bill", data=data, risk_level="绿色"
    )

def handle_card_manage(intent: dict, need_confirm: bool) -> ChatResponse:
    card_number = intent.get("card_number", "6222****1234")
    operation = intent.get("operation", "freeze")
    
    try:
        resp = requests.post(
            f"{BANK_API_URL}/api/card/manage",
            json={"card_number": card_number, "action": operation},
            timeout=5
        )
        result = resp.json()
        
        if result.get("status") == "success":
            log_audit("卡片管理", {"card": card_number, "operation": operation})
            confirm_msg = " ℹ️ 请在APP确认此操作" if need_confirm else ""
            return ChatResponse(
                reply=f"💳 {result['message']}{confirm_msg}",
                action="card_manage", data=result,
                need_confirm=need_confirm, risk_level="黄色"
            )
        else:
            return ChatResponse(
                reply=f"❌ 操作失败：{result.get('message', '未知错误')}",
                action="card_manage", data=result
            )
    except Exception as e:
        return ChatResponse(reply=f"⚠️ 系统异常：{str(e)}", action="card_manage", data={})

def handle_risk_assess(intent: dict) -> ChatResponse:
    try:
        resp = requests.post(
            f"{BANK_API_URL}/api/risk/assess",
            json={"age": 30, "income": 150000, "investment_experience": "intermediate"},
            timeout=5
        )
        result = resp.json()
        
        if result.get("status") == "success":
            log_audit("风险评估", {"level": result.get("risk_level")})
            return ChatResponse(
                reply=f"📈 风险评估结果：{result['risk_level']}（评分{result['score']}）\n推荐产品：{', '.join(result.get('recommended_products', []))}",
                action="risk_assess", data=result, risk_level="绿色"
            )
        else:
            return ChatResponse(
                reply=f"❌ 风险评估失败：{result.get('message', '未知错误')}",
                action="risk_assess", data=result
            )
    except Exception as e:
        return ChatResponse(reply=f"⚠️ 系统异常：{str(e)}", action="risk_assess", data={})

def handle_subscribe_manage(intent: dict, need_confirm: bool) -> ChatResponse:
    merchant = intent.get("merchant", "Netflix")
    operation = intent.get("operation", "cancel")
    amount = intent.get("amount", 0)
    
    try:
        resp = requests.post(
            f"{BANK_API_URL}/api/subscribe/manage",
            json={"merchant": merchant, "amount": amount, "action": operation},
            timeout=5
        )
        result = resp.json()
        
        if result.get("status") == "success":
            log_audit("订阅管理", {"merchant": merchant, "operation": operation})
            confirm_msg = " ℹ️ 请在APP确认此操作" if need_confirm else ""
            return ChatResponse(
                reply=f"📋 {result['message']}{confirm_msg}",
                action="subscribe_manage", data=result,
                need_confirm=need_confirm, risk_level="黄色"
            )
        else:
            return ChatResponse(
                reply=f"❌ 操作失败：{result.get('message', '未知错误')}",
                action="subscribe_manage", data=result
            )
    except Exception as e:
        return ChatResponse(reply=f"⚠️ 系统异常：{str(e)}", action="subscribe_manage", data={})

@app.get("/")
def index():
    return FileResponse("static/index.html")