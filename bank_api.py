from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid
import json
from datetime import datetime
import os

app = FastAPI(title="模拟银行API")

# ---------- 数据模型 ----------
class TransferRequest(BaseModel):
    recipient: str
    amount: float
    time: Optional[str] = "立即"
    phone: Optional[str] = None

class AARequest(BaseModel):
    total_amount: float
    people: List[str]

class CardRequest(BaseModel):
    card_number: str
    action: str  # freeze/unfreeze/lock/apply/loss

class RiskAssessmentRequest(BaseModel):
    age: int
    income: float
    investment_experience: str  # none/beginner/intermediate/expert

class SubscribeRequest(BaseModel):
    merchant: str
    amount: float
    action: str  # cancel/renew

# ---------- 模拟数据库 ----------
transactions = []
cards = {
    "6222****1234": {"status": "active", "limit": 50000, "type": "信用卡"},
    "6222****5678": {"status": "active", "limit": 30000, "type": "储蓄卡"},
    "6222****9012": {"status": "frozen", "limit": 20000, "type": "信用卡"},
}
subscribes = [
    {"merchant": "Netflix", "amount": 79, "next_bill": "2026-10-15"},
    {"merchant": "Spotify", "amount": 58, "next_bill": "2026-10-20"},
    {"merchant": "iCloud", "amount": 6, "next_bill": "2026-10-05"},
]
audit_logs = []

# ---------- 审计日志 ----------
def log_audit(user: str, action: str, details: dict, level: str = "INFO"):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user": user or "anonymous",
        "action": action,
        "details": details,
        "level": level
    }
    audit_logs.append(log_entry)
    with open("audit.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    return log_entry

# ---------- API接口 ----------
@app.post("/api/transfer")
def transfer(req: TransferRequest):
    """模拟转账"""
    if req.amount > 10000:
        log_audit(None, "转账", {"recipient": req.recipient, "amount": req.amount}, "WARNING")
        return {
            "status": "failed",
            "code": "LIMIT_EXCEEDED",
            "message": f"单笔转账限额10000元，您当前请求{req.amount}元"
        }
    
    if req.amount <= 0:
        return {
            "status": "failed",
            "code": "INVALID_AMOUNT",
            "message": "转账金额必须大于0"
        }
    
    order_id = f"TX{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:4]}"
    trans = {
        "order_id": order_id,
        "recipient": req.recipient,
        "amount": req.amount,
        "time": req.time,
        "phone": req.phone,
        "status": "success",
        "created_at": datetime.now().isoformat()
    }
    transactions.append(trans)
    log_audit(None, "转账成功", {"order_id": order_id, "amount": req.amount, "recipient": req.recipient})
    
    return {
        "status": "success",
        "order_id": order_id,
        "message": f"已向{req.recipient}转账{req.amount}元",
        "time": req.time
    }

@app.post("/api/aa")
def aa_split(req: AARequest):
    """AA收款拆分"""
    try:
        if len(req.people) == 0:
            return {"status": "failed", "message": "请至少指定一个人"}
        
        if req.total_amount <= 0:
            return {"status": "failed", "message": "总金额必须大于0"}
        
        per_person = round(req.total_amount / len(req.people), 2)
        log_audit(None, "AA收款", {"total": req.total_amount, "people": req.people})
        return {
            "status": "success",
            "per_person": per_person,
            "people": req.people,
            "total": req.total_amount,
            "message": f"共{len(req.people)}人，每人应付{per_person}元"
        }
    except Exception as e:
        return {"status": "failed", "message": f"计算失败: {str(e)}"}

@app.post("/api/card/manage")
def card_manage(req: CardRequest):
    """卡片管理：申请/冻结/解冻/挂失"""
    if req.card_number not in cards and req.action != "apply":
        return {"status": "failed", "message": "卡片不存在"}
    
    if req.action == "apply":
        new_card = f"6222****{uuid.uuid4().hex[:4].upper()}"
        cards[new_card] = {"status": "active", "limit": 20000, "type": "储蓄卡"}
        log_audit(None, "卡片申请", {"card": new_card, "status": "active"})
        return {"status": "success", "message": f"新卡{new_card}申请成功", "card": new_card}
    
    card = cards[req.card_number]
    
    if req.action == "freeze":
        card["status"] = "frozen"
        log_audit(None, "卡片冻结", {"card": req.card_number})
        return {"status": "success", "message": f"卡片{req.card_number}已冻结"}
    
    elif req.action == "unfreeze":
        card["status"] = "active"
        log_audit(None, "卡片解冻", {"card": req.card_number})
        return {"status": "success", "message": f"卡片{req.card_number}已解冻"}
    
    elif req.action == "loss":
        card["status"] = "lost"
        log_audit(None, "卡片挂失", {"card": req.card_number}, "WARNING")
        return {"status": "success", "message": f"卡片{req.card_number}已挂失"}
    
    else:
        return {"status": "failed", "message": "不支持的操作"}

@app.post("/api/risk/assess")
def risk_assess(req: RiskAssessmentRequest):
    """风险评估"""
    score = 50
    level = "保守型"
    
    if req.investment_experience in ["intermediate", "expert"]:
        score += 20
    if req.income > 200000:
        score += 10
    if req.age < 30:
        score += 10
    
    if score >= 80:
        level = "进取型"
    elif score >= 60:
        level = "成长型"
    elif score >= 40:
        level = "稳健型"
    else:
        level = "保守型"
    
    products = {
        "保守型": ["货币基金", "定期存款"],
        "稳健型": ["债券基金", "混合基金"],
        "成长型": ["指数基金", "FOF基金"],
        "进取型": ["股票基金", "QDII基金"]
    }
    
    log_audit(None, "风险评估", {"level": level, "score": score})
    return {
        "status": "success",
        "risk_level": level,
        "score": score,
        "recommended_products": products.get(level, ["货币基金"])
    }

@app.get("/api/transactions")
def get_transactions(limit: int = 10):
    return {"transactions": transactions[-limit:]}

@app.get("/api/subscribes")
def get_subscribes():
    return {"subscribes": subscribes}

@app.post("/api/subscribe/manage")
def subscribe_manage(req: SubscribeRequest):
    if req.action == "cancel":
        log_audit(None, "取消订阅", {"merchant": req.merchant})
        return {"status": "success", "message": f"已取消{req.merchant}的订阅"}
    elif req.action == "renew":
        log_audit(None, "续费提醒", {"merchant": req.merchant, "amount": req.amount})
        return {"status": "success", "message": f"{req.merchant}续费提醒，金额{req.amount}元"}
    else:
        return {"status": "failed", "message": "支持操作: cancel/renew"}

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/audit/logs")
def get_audit_logs(limit: int = 20):
    return {"logs": audit_logs[-limit:]}