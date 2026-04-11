ROLE_KEYWORDS = {
    "java": {
        "tech": [
            "java",
            "spring",
            "spring boot",
            "mysql",
            "redis",
            "缓存",
            "索引",
            "并发",
            "接口",
            "数据库",
            "项目",
            "事务",
            "优化"
        ],
        "match": [
            "java",
            "spring",
            "mysql",
            "redis",
            "后端",
            "接口",
            "数据库",
            "服务端",
            "缓存"
        ],
        "suggestions": [
            "建议继续强化 Spring、MySQL、Redis 等高频后端知识点。",
            "回答项目题时尽量按照“背景-方案-难点-结果”结构展开。",
            "可针对高并发、缓存一致性、数据库优化等场景进行专项练习。"
        ]
    },
    "frontend": {
        "tech": [
            "html",
            "css",
            "javascript",
            "vue",
            "react",
            "组件",
            "浏览器",
            "性能优化",
            "路由",
            "状态管理",
            "前端",
            "页面",
            "交互",
            "优化"
        ],
        "match": [
            "vue",
            "react",
            "javascript",
            "前端",
            "组件",
            "浏览器",
            "性能",
            "页面",
            "交互"
        ],
        "suggestions": [
            "建议继续强化 Vue/React、浏览器原理和性能优化相关知识点。",
            "回答项目题时突出个人贡献、技术难点和优化效果。",
            "可针对组件通信、状态管理和页面性能优化进行专项练习。"
        ]
    }
}

STRUCTURE_WORDS = [
    "首先",
    "其次",
    "然后",
    "最后",
    "例如",
    "比如",
    "在项目中",
    "实际开发中"
]

LOGIC_WORDS = [
    "首先",
    "其次",
    "然后",
    "最后",
    "因为",
    "所以",
    "具体来说",
    "在项目中",
    "例如",
    "因此"
]

ROLE_SCORE_WEIGHTS = {
    "java": {
        "tech": 0.40,
        "expression": 0.15,
        "logic": 0.20,
        "match": 0.25
    },
    "frontend": {
        "tech": 0.30,
        "expression": 0.25,
        "logic": 0.20,
        "match": 0.25
    }
}