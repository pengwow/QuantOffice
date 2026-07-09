extends Node2D
## OfficeManager — 像素办公室场景主管理器
##
## 负责协调 6 个工位、角色动画、屏幕内容显示。
## 通过 ReactBridge 与 React 前端双向通信。

const AGENT_POSITIONS := {
	"chief": Vector2(640, 360),
	"data": Vector2(240, 360),
	"strategy": Vector2(360, 520),
	"risk": Vector2(920, 520),
	"execution": Vector2(1040, 360),
	"report": Vector2(640, 600),
}

const AGENT_COLORS := {
	"chief": Color(0.0, 0.72, 0.58),      # 绿
	"data": Color(0.45, 0.72, 1.0),        # 蓝
	"strategy": Color(0.88, 0.42, 0.36),   # 橙
	"risk": Color(1.0, 0.46, 0.46),        # 红
	"execution": Color(0.64, 0.61, 0.99),  # 紫
	"report": Color(0.99, 0.81, 0.43),     # 黄
}

var _agent_status: Dictionary = {}

func _ready() -> void:
	_draw_workstations()
	_setup_bridge()

func _draw_workstations() -> void:
	var ws := $Workstations
	for name in AGENT_POSITIONS:
		var node = ws.get_node(name)
		node.position = AGENT_POSITIONS[name]

func _setup_bridge() -> void:
	pass

## 更新 Agent 状态 — 来自 React 端推送
func update_agent_status(agent_id: String, status: String, metrics: Dictionary) -> void:
	_agent_status[agent_id] = {"status": status, "metrics": metrics}
	# 在真实实现中触发动画切换

## 处理来自 React 的事件
func handle_react_event(event_type: String, payload: Dictionary) -> void:
	match event_type:
		"agent_status":
			update_agent_status(payload.get("id", ""), payload.get("status", "idle"), payload.get("metrics", {}))
		_:
			pass
