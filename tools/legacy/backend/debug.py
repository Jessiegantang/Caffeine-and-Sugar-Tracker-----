import sys, json
from agent import app_graph
state = {
    "drink_records": [],
    "historical_records": [],
    "sleep_records": [],
    "caffeine_total": 0.0,
    "sugar_total": 0.0,
    "risk_level": "未知",
    "advice": ""
}
print(app_graph.invoke(state))
