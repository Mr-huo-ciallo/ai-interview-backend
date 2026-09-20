ROLE_KEYWORDS = {
    "java": {
        "tech": [
            "java", "spring", "spring boot", "mysql", "redis", "缓存", "索引", "并发",
            "接口", "数据库", "项目", "事务", "优化", "jvm", "线程", "分布式",
        ],
        "match": [
            "java", "spring", "mysql", "redis", "后端", "接口", "数据库", "服务端",
            "缓存", "微服务", "高并发",
        ],
        "suggestions": [
            "建议继续强化 Spring、MySQL、Redis 等高频后端知识点。",
            "回答项目题时尽量按照“背景-方案-难点-结果”结构展开。",
            "可针对高并发、缓存一致性、数据库优化等场景进行专项练习。",
        ],
    },
    "frontend": {
        "tech": [
            "html", "css", "javascript", "typescript", "vue", "react", "组件",
            "浏览器", "性能优化", "路由", "状态管理", "前端", "页面", "交互", "工程化",
        ],
        "match": [
            "vue", "react", "javascript", "typescript", "前端", "组件", "浏览器",
            "性能", "页面", "交互", "工程化",
        ],
        "suggestions": [
            "建议继续强化 Vue/React、浏览器原理和性能优化相关知识点。",
            "回答项目题时突出个人贡献、技术难点和优化效果。",
            "可针对组件通信、状态管理和页面性能优化进行专项练习。",
        ],
    },
    "qa": {
        "tech": [
            "qa", "testing", "test", "quality", "assurance", "bug", "defect",
            "test case", "test plan", "test strategy", "automation", "regression",
            "unit testing", "integration testing", "performance testing", "selenium",
            "质量", "测试", "缺陷", "用例", "回归", "自动化", "验收",
        ],
        "match": [
            "qa", "testing", "quality", "bug", "defect", "test case", "automation",
            "测试", "质量保障", "缺陷定位", "测试策略", "自动化测试",
        ],
        "suggestions": [
            "建议围绕测试流程、缺陷生命周期、测试策略和自动化测试继续补强。",
            "回答场景题时结合需求分析、用例设计、执行结果、缺陷定位和复盘改进展开。",
            "可专项练习回归测试、接口测试、性能测试、自动化测试框架和质量风险控制。",
        ],
    },
    "python": {
        "tech": [
            "python", "django", "flask", "fastapi", "pandas", "numpy", "asyncio",
            "decorator", "generator", "iterator", "list", "dict", "oop", "class",
            "object", "exception", "package", "module", "pytest", "gil", "性能",
            "异步", "装饰器", "生成器", "数据处理",
        ],
        "match": [
            "python", "django", "flask", "fastapi", "pandas", "numpy", "pytest",
            "异步", "数据处理", "后端", "脚本", "自动化",
        ],
        "suggestions": [
            "建议继续强化 Python 语言机制、常用库、异常处理、测试和工程化能力。",
            "回答时尽量补充适用场景、边界条件、性能影响和实际项目用法。",
            "可针对装饰器、生成器、异步编程、包模块管理、FastAPI/Django 等方向专项练习。",
        ],
    },
    "cs_basic": {
        "tech": [
            "computer science", "software engineering", "data structure", "algorithm",
            "database", "operating system", "network", "oop", "abstraction",
            "encapsulation", "inheritance", "polymorphism", "complexity", "compiler",
            "memory", "process", "thread", "计算机", "数据结构", "算法", "数据库",
            "操作系统", "网络", "复杂度", "面向对象",
        ],
        "match": [
            "computer science", "software engineering", "data structure", "algorithm",
            "oop", "database", "operating system", "network", "计算机基础", "软件工程",
            "数据结构", "算法", "面向对象",
        ],
        "suggestions": [
            "建议系统复习数据结构、算法、操作系统、网络、数据库和软件工程基础。",
            "回答概念题时补充定义、使用场景、常见误区和与相近概念的区别。",
            "可针对复杂度分析、面向对象特性、进程线程、数据库索引和网络协议进行专项练习。",
        ],
    },
}

SUPPORTED_ROLES = frozenset(ROLE_KEYWORDS)

ROLE_TECH_FEEDBACK = {
    "java": {
        "strength": "后端相关知识点命中较多，体现出一定的岗位准备度。",
        "weakness": "对后端高频知识点如 Spring、MySQL、Redis 的覆盖还不够充分。",
    },
    "frontend": {
        "strength": "前端相关知识点覆盖较全面，岗位针对性较强。",
        "weakness": "对前端高频知识点如 Vue/React、浏览器原理、性能优化的覆盖仍需加强。",
    },
    "qa": {
        "strength": "测试与质量保障相关知识点命中较多，体现出较好的 QA 岗位准备度。",
        "weakness": "对测试流程、缺陷定位、测试策略和自动化测试的覆盖仍需加强。",
    },
    "python": {
        "strength": "Python 语言机制和工程实践相关知识点覆盖较好，岗位针对性较强。",
        "weakness": "对 Python 语言机制、常用框架和工程化实践的覆盖仍需加强。",
    },
    "cs_basic": {
        "strength": "计算机基础与软件工程概念覆盖较全面，基础能力表现较稳。",
        "weakness": "对数据结构、算法、操作系统、网络和软件工程基础的覆盖仍需加强。",
    },
}

STRUCTURE_WORDS = [
    "首先", "其次", "然后", "最后", "例如", "比如", "在项目中", "实际开发中",
]

LOGIC_WORDS = [
    "首先", "其次", "然后", "最后", "因为", "所以", "具体来说", "在项目中",
    "例如", "因此", "如果", "否则", "对比", "取舍", "验证",
]

ROLE_SCORE_WEIGHTS = {
    "java": {
        "tech": 0.40,
        "expression": 0.15,
        "logic": 0.20,
        "match": 0.25,
    },
    "frontend": {
        "tech": 0.30,
        "expression": 0.25,
        "logic": 0.20,
        "match": 0.25,
    },
    "qa": {
        "tech": 0.32,
        "expression": 0.20,
        "logic": 0.23,
        "match": 0.25,
    },
    "python": {
        "tech": 0.38,
        "expression": 0.17,
        "logic": 0.20,
        "match": 0.25,
    },
    "cs_basic": {
        "tech": 0.35,
        "expression": 0.18,
        "logic": 0.27,
        "match": 0.20,
    },
}
