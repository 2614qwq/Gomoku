"""技能 tool-calling 适配层 —— 将万宁招式暴露为 OpenAI function calling 工具

每局双方各随机分配一个招式。只有主动招式可被 AI 作为 tool 调用，
被动招式由游戏控制器自动触发，不需要 AI 干预。
"""

from typing import Optional

# 招式类名 → tool 定义映射（仅主动招式）
_ACTIVE_SKILL_TOOLS = {
    "万宁阵法": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": "在指定空位额外生成1颗棋子。每3回合可用一次。调用前确认 turn_count 是3的倍数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "目标列 (0-14)"},
                    "y": {"type": "integer", "description": "目标行 (0-14)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "血狱影杀阵": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": "20%概率在上一落子相邻格生成1子。每次落子后可尝试，无需参数。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    "四方阵": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": "在上一落子斜向随机生成1颗棋子。每次落子后可尝试，无需参数。",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
}


def get_skill_tool(player) -> Optional[dict]:
    """获取当前玩家可用的技能 tool schema（仅主动招式）

    Args:
        player: Player 对象，其 .skill 属性为当前分配的招式

    Returns:
        OpenAI tool schema dict，若当前无主动招式则返回 None
    """
    skill = getattr(player, 'skill', None)
    if skill is None:
        return None
    name = skill.skill_name
    return _ACTIVE_SKILL_TOOLS.get(name)


def execute_skill_tool(player, opponent, board, turn_count,
                       arguments: dict, last_move_pos) -> str:
    """执行 AI 调用的技能 tool

    Args:
        player: 当前玩家
        opponent: 对手
        board: 棋盘
        turn_count: 当前回合数
        arguments: LLM 传入的 tool arguments，如 {"x": 7, "y": 8}
        last_move_pos: 上一落子位置 (Position)

    Returns:
        执行结果描述字符串
    """
    skill = getattr(player, 'skill', None)
    if skill is None:
        return "[技能] 当前无可用招式"

    from 五子棋.core.models import Position

    name = skill.skill_name

    if name == "万宁阵法":
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return "[万宁阵法] 需要指定目标坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[万宁阵法] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "血狱影杀阵":
        result = skill.activate(player, opponent, board, turn_count,
                                target=last_move_pos)
        return result.message

    elif name == "四方阵":
        result = skill.activate(player, opponent, board, turn_count,
                                target=last_move_pos)
        return result.message

    return f"[技能] 未知招式: {name}"
