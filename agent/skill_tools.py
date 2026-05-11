"""技能 tool-calling 适配层 —— 将10个主动技能暴露为 OpenAI function calling 工具

每局双方各随机分配一个技能。全部为主动技能，每局限1次。
技能由 skill_officer Agent 裁决是否使用。
"""

from typing import Optional

# 技能类名 → tool 定义映射
_ACTIVE_SKILL_TOOLS = {
    "追加落子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "在任意空位额外放置1颗己方棋子。第5回合后可用，每局限1次。"
                "使用时机：存在'只差1子'即可形成活三/活四/双重威胁的空位时。"
                "需提供目标坐标(x,y)。"
            ),
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
    "复制己子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "选择己方1子，在其相邻4格空位中生成1颗同色子。第3回合后可用，每局限1次。"
                "使用时机：己方有活二棋子，其相邻空位落子可立即形成活三时。"
                "target(x,y)必须是己方棋子相邻4格内的空位。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "目标空位列 (0-14)，须与己方棋子相邻"},
                    "y": {"type": "integer", "description": "目标空位行 (0-14)，须与己方棋子相邻"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "连打两子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "本回合连续落下2子。第10回合后可用，每局限1次。"
                "使用时机：存在两个空位，同时落下可形成活四或四三杀等必胜定式时。"
                "无参数——激活后连续选两个落子位即可。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    "移除敌子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "删除对手任意1颗棋子。第3回合后可用，每局限1次。"
                "使用时机：对手存在活三或冲四，且删除其中某颗棋子能破坏该连线时。"
                "需提供对手棋子的坐标(x,y)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "对手棋子列 (0-14)"},
                    "y": {"type": "integer", "description": "对手棋子行 (0-14)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "转化棋子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "将对手1颗棋子变为己方颜色。第8回合后可用，每局限1次。"
                "使用时机：对手棋子恰好位于己方活二/活三的延伸路径上，转化后可一举形成活三/活四。"
                "需提供对手棋子的坐标(x,y)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "对手棋子列 (0-14)"},
                    "y": {"type": "integer", "description": "对手棋子行 (0-14)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "封禁空位": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "标记1个空位为封锁，对手下1回合不能落此位。第3回合后可用，每局限1次。"
                "使用时机：对手存在活三（算法将标注其两端空位），封禁其中一端可阻止其活三扩展1回合。"
                "需提供空位坐标(x,y)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "空位列 (0-14)"},
                    "y": {"type": "integer", "description": "空位行 (0-14)"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "强制跳过": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "对手跳过下个回合（你连续走两轮）。第8回合后可用，每局限1次。"
                "使用时机：你需要连续两手才能构造必胜，且正常轮替对手会在中间堵住时。"
                "无参数。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    "移位己子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "将己方1子移动到相邻8格内的任意空位。第3回合后可用，每局限1次。"
                "使用时机：己方存在孤立棋子（不在任何连珠线中），移入后可加入已有活二/活三时。"
                "技能会自动识别目标空位相邻的己方棋子并移动之。需提供目标空位坐标(x,y)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "目标空位列 (0-14)，相邻8格内须有己方棋子"},
                    "y": {"type": "integer", "description": "目标空位行 (0-14)，相邻8格内须有己方棋子"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "交换棋子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "交换己方1子与相邻对手1子的位置。第8回合后可用，每局限1次。"
                "使用时机：己方关键棋子旁有对手棋子阻碍，交换后可同时破坏对手+增强己方。"
                "需提供己方棋子坐标(x,y)，技能会自动找相邻对手棋子交换。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "己方棋子列 (0-14)，相邻须有对手棋子"},
                    "y": {"type": "integer", "description": "己方棋子行 (0-14)，相邻须有对手棋子"},
                },
                "required": ["x", "y"],
            },
        },
    },
    "回溯落子": {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "撤销自己上一步落子，重新选择位置。第5回合后可用，每局限1次。"
                "使用时机：上步落子后算法显示对手形成必胜威胁（活四/活三），且该威胁与你上步直接相关时。"
                "无参数——自动撤销上一步己方落子。"
            ),
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

    from ..五子棋.core.models import Position

    name = skill.skill_name

    # 需要坐标参数的技能
    if name in ("追加落子", "封禁空位"):
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return f"[{name}] 需要指定目标坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[{name}] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "移除敌子":
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return f"[移除敌子] 需要指定对手棋子坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[移除敌子] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "转化棋子":
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return f"[转化棋子] 需要指定对手棋子坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[转化棋子] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "复制己子":
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return f"[复制己子] 需要指定空位坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[复制己子] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "移位己子":
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return f"[移位己子] 需要指定目标空位坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[移位己子] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "交换棋子":
        x = arguments.get("x")
        y = arguments.get("y")
        if x is None or y is None:
            return f"[交换棋子] 需要指定己方棋子坐标 (x, y)"
        if not (0 <= x < 15 and 0 <= y < 15):
            return f"[交换棋子] 坐标 ({x},{y}) 超出棋盘范围"
        target = Position(x, y)
        result = skill.activate(player, opponent, board, turn_count, target=target)
        return result.message

    elif name == "连打两子":
        result = skill.activate(player, opponent, board, turn_count)
        return result.message

    elif name == "强制跳过":
        result = skill.activate(player, opponent, board, turn_count)
        return result.message

    elif name == "回溯落子":
        # 自动使用 last_move_pos 作为回溯目标
        result = skill.activate(player, opponent, board, turn_count, target=last_move_pos)
        return result.message

    return f"[技能] 未知招式: {name}"
