import pytest

from scoring.config import ROLE_TECH_FEEDBACK, SUPPORTED_ROLES
from scoring.rules import generate_strengths, generate_weaknesses


@pytest.mark.parametrize("role", sorted(SUPPORTED_ROLES))
def test_role_feedback_comes_from_shared_config(role):
    strengths = generate_strengths(role, 80, 75, 75, 75)
    weaknesses = generate_weaknesses(role, 70, 75, 75, 75)

    assert ROLE_TECH_FEEDBACK[role]["strength"] in strengths
    assert ROLE_TECH_FEEDBACK[role]["weakness"] in weaknesses


def test_unknown_role_uses_only_dimension_feedback():
    strengths = generate_strengths("unknown", 80, 75, 75, 75)
    weaknesses = generate_weaknesses("unknown", 70, 75, 75, 75)

    assert strengths == [
        "对目标岗位的核心技术点覆盖较好。",
        "整体表达较清晰，回答比较完整。",
        "回答具有一定层次性和逻辑性。",
        "回答内容与目标岗位要求匹配度较高。",
    ]
    assert weaknesses == ["岗位核心知识点覆盖不足，技术回答深度仍需提升。"]
