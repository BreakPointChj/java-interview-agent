"""覆盖后端与 Agent 技术栈的内置结构化题库。"""

from __future__ import annotations

import random

from interview_agent.knowledge import KnowledgeBase
from interview_agent.models import Difficulty, Question

SUPPORTED_TOPICS = (
    "Java",
    "Python",
    "Spring",
    "LangChain",
    "LangGraph",
    "数据库",
    "缓存",
    "消息队列",
)

# 元组字段依次为：编号、领域、难度、题干、评分参考点、追问。
QUESTION_DATA: list[tuple[str, str, Difficulty, str, list[str], str | None]] = [
    (
        "java-01",
        "Java",
        Difficulty.JUNIOR,
        "Java 中 == 与 equals 有什么区别？",
        ["引用比较", "值比较", "重写 equals", "hashCode 契约"],
        "为什么重写 equals 时通常也要重写 hashCode？",
    ),
    (
        "java-02",
        "Java",
        Difficulty.INTERMEDIATE,
        "解释 JVM 的内存区域以及常见 OOM 场景。",
        ["堆", "虚拟机栈", "方法区或元空间", "直接内存", "对象生命周期"],
        "如何用工具定位一次线上内存泄漏？",
    ),
    (
        "java-03",
        "Java",
        Difficulty.SENIOR,
        "ConcurrentHashMap 在 JDK 8 中如何保证并发安全？",
        ["CAS", "synchronized", "数组加链表或红黑树", "volatile", "扩容协助"],
        "它的 size 为什么难以在并发下精确统计？",
    ),
    (
        "java-04",
        "Java",
        Difficulty.INTERMEDIATE,
        "线程池的核心参数如何配合，如何避免任务堆积？",
        ["corePoolSize", "maximumPoolSize", "workQueue", "拒绝策略", "任务类型"],
        "CPU 密集型与 IO 密集型参数如何估算？",
    ),
    (
        "java-05",
        "Java",
        Difficulty.SENIOR,
        "请说明 Java 内存模型中的 happens-before 规则。",
        ["可见性", "有序性", "volatile", "锁", "线程启动与终止"],
        "双重检查锁为什么需要 volatile？",
    ),
    (
        "python-01",
        "Python",
        Difficulty.JUNIOR,
        "Python 的可变对象与不可变对象有什么差异？",
        ["对象身份", "原地修改", "list", "tuple", "默认参数风险"],
        "为什么不建议使用可变对象作为函数默认参数？",
    ),
    (
        "python-02",
        "Python",
        Difficulty.INTERMEDIATE,
        "解释迭代器、生成器及 yield 的作用。",
        ["惰性计算", "迭代协议", "内存效率", "状态保存"],
        "生成器异常和关闭应如何处理？",
    ),
    (
        "python-03",
        "Python",
        Difficulty.SENIOR,
        "GIL 对 Python 并发有什么影响？",
        ["字节码互斥", "CPU 密集", "IO 密集", "多进程", "C 扩展"],
        "什么情况下 asyncio 比线程更合适？",
    ),
    (
        "python-04",
        "Python",
        Difficulty.INTERMEDIATE,
        "装饰器的实现原理和典型使用场景是什么？",
        ["闭包", "高阶函数", "functools.wraps", "横切逻辑"],
        "带参数装饰器需要几层函数？",
    ),
    (
        "spring-01",
        "Spring",
        Difficulty.JUNIOR,
        "Spring IOC 和依赖注入解决了什么问题？",
        ["控制反转", "解耦", "Bean 容器", "构造器注入"],
        "为什么通常推荐构造器注入？",
    ),
    (
        "spring-02",
        "Spring",
        Difficulty.INTERMEDIATE,
        "Spring Bean 的完整生命周期有哪些关键扩展点？",
        ["实例化", "属性注入", "Aware", "BeanPostProcessor", "初始化与销毁"],
        "循环依赖与生命周期有什么联系？",
    ),
    (
        "spring-03",
        "Spring",
        Difficulty.SENIOR,
        "@Transactional 在哪些情况下会失效？",
        ["代理调用", "自调用", "非 public", "异常类型", "传播行为"],
        "如何解决同类方法自调用导致的事务失效？",
    ),
    (
        "spring-04",
        "Spring",
        Difficulty.INTERMEDIATE,
        "Spring Boot 自动配置的工作机制是什么？",
        ["自动配置类", "条件注解", "starter", "配置属性", "约定优于配置"],
        "如何排查某个自动配置未生效？",
    ),
    (
        "lc-01",
        "LangChain",
        Difficulty.JUNIOR,
        "LangChain 中 Prompt、Model 和 OutputParser 如何组成链？",
        ["Runnable", "LCEL", "管道组合", "结构化输出"],
        "Runnable 接口带来了哪些统一能力？",
    ),
    (
        "lc-02",
        "LangChain",
        Difficulty.INTERMEDIATE,
        "RAG 的基本流程是什么，如何评价检索质量？",
        ["文档切分", "向量化", "召回", "重排", "上下文生成"],
        "召回率高但答案质量差时如何排查？",
    ),
    (
        "lc-03",
        "LangChain",
        Difficulty.SENIOR,
        "如何为生产级 Agent 设计工具调用的安全边界？",
        ["最小权限", "参数校验", "人工审批", "超时重试", "审计"],
        "如何防御提示词注入影响工具调用？",
    ),
    (
        "lg-01",
        "LangGraph",
        Difficulty.JUNIOR,
        "LangGraph 的 State、Node 和 Edge 分别负责什么？",
        ["共享状态", "节点函数", "状态转移", "条件边"],
        "为什么图适合有状态 Agent？",
    ),
    (
        "lg-02",
        "LangGraph",
        Difficulty.INTERMEDIATE,
        "LangGraph Checkpointer 如何支持多轮对话和恢复？",
        ["thread_id", "checkpoint", "状态持久化", "中断恢复"],
        "生产环境应如何选择 checkpointer？",
    ),
    (
        "lg-03",
        "LangGraph",
        Difficulty.SENIOR,
        "如何在 LangGraph 中实现 human-in-the-loop？",
        ["interrupt", "resume", "审批节点", "持久化", "幂等性"],
        "恢复执行时如何防止有副作用的节点重复运行？",
    ),
    (
        "db-01",
        "数据库",
        Difficulty.JUNIOR,
        "数据库索引为什么能加速查询，又有哪些代价？",
        ["B+树", "减少 IO", "写放大", "空间成本", "选择性"],
        "联合索引的最左前缀如何理解？",
    ),
    (
        "db-02",
        "数据库",
        Difficulty.INTERMEDIATE,
        "MySQL InnoDB 的 MVCC 如何工作？",
        ["隐藏字段", "undo log", "ReadView", "快照读", "隔离级别"],
        "当前读为什么还需要加锁？",
    ),
    (
        "db-03",
        "数据库",
        Difficulty.SENIOR,
        "如何设计分库分表方案并处理跨库事务？",
        ["分片键", "路由", "全局 ID", "最终一致性", "扩容"],
        "热点分片如何迁移和治理？",
    ),
    (
        "db-04",
        "数据库",
        Difficulty.INTERMEDIATE,
        "PostgreSQL 与 MySQL 在工程选型上有哪些重要差异？",
        ["MVCC", "SQL 能力", "扩展性", "JSON", "生态与运维"],
        "什么业务更适合 PostgreSQL？",
    ),
    (
        "cache-01",
        "缓存",
        Difficulty.JUNIOR,
        "缓存穿透、击穿和雪崩分别是什么？",
        ["空值或布隆过滤器", "热点 key", "互斥重建", "随机过期", "限流降级"],
        "布隆过滤器为什么可能误判？",
    ),
    (
        "cache-02",
        "缓存",
        Difficulty.INTERMEDIATE,
        "Cache Aside 模式如何保证数据库与 Redis 的一致性？",
        ["旁路缓存", "先更新数据库", "删除缓存", "延迟双删", "最终一致性"],
        "为什么一般选择删除而不是更新缓存？",
    ),
    (
        "cache-03",
        "缓存",
        Difficulty.SENIOR,
        "Redis 分布式锁怎样实现才相对安全？",
        ["SET NX PX", "唯一令牌", "Lua 解锁", "续期", "故障模型"],
        "Redlock 存在哪些争议？",
    ),
    (
        "mq-01",
        "消息队列",
        Difficulty.JUNIOR,
        "消息队列为系统带来哪些收益和复杂度？",
        ["解耦", "异步", "削峰", "可用性", "一致性"],
        "哪些场景不应该引入消息队列？",
    ),
    (
        "mq-02",
        "消息队列",
        Difficulty.INTERMEDIATE,
        "如何处理消息重复、丢失和顺序性？",
        ["幂等", "确认机制", "重试", "死信队列", "分区有序"],
        "消费端幂等表如何设计？",
    ),
    (
        "mq-03",
        "消息队列",
        Difficulty.SENIOR,
        "Kafka 的副本、ISR 和消费者组如何协作？",
        ["分区", "leader follower", "ISR", "offset", "再均衡"],
        "如何减少消费者再均衡造成的抖动？",
    ),
]


class QuestionBank:
    """提供题目检索、领域校验和不重复选题策略。"""

    def __init__(self) -> None:
        self._questions = [
            Question(
                id=x[0],
                topic=x[1],
                difficulty=x[2],
                question=x[3],
                reference_points=x[4],
                follow_up=x[5],
            )
            for x in QUESTION_DATA
        ]
        # 问答知识库同时扩充模拟面试题，保持同一份标准答案和评分要点。
        existing_ids = {question.id for question in self._questions}
        for entry in KnowledgeBase().entries:
            if entry.id not in existing_ids:
                self._questions.append(
                    Question(
                        id=entry.id,
                        topic=entry.topic,
                        difficulty=entry.difficulty,
                        question=entry.question,
                        reference_points=entry.key_points,
                        follow_up=entry.follow_up_questions[0]
                        if entry.follow_up_questions
                        else None,
                    )
                )
        self._by_id = {question.id: question for question in self._questions}

    def get(self, question_id: str) -> Question:
        """按 ID 获取题目。"""

        try:
            return self._by_id[question_id]
        except KeyError as exc:
            raise KeyError(f"题目不存在：{question_id}") from exc

    @staticmethod
    def validate_topics(topics: list[str]) -> None:
        """校验领域列表，防止已知与未知领域混合时静默忽略错误。"""

        selected_topics = topics or list(SUPPORTED_TOPICS)
        unknown = sorted(set(selected_topics) - set(SUPPORTED_TOPICS))
        if unknown:
            raise ValueError(f"不支持的技术领域：{', '.join(unknown)}")

    def select(
        self,
        topics: list[str],
        difficulty: Difficulty,
        excluded_ids: list[str],
        weak_topics: dict[str, int] | None = None,
    ) -> Question:
        """优先同难度和薄弱领域；同级题用完时允许邻级回退。"""

        self.validate_topics(topics)
        selected_topics = topics or list(SUPPORTED_TOPICS)
        candidates = [
            q for q in self._questions if q.topic in selected_topics and q.id not in excluded_ids
        ]
        if not candidates:
            raise LookupError("所选领域的题目已经用完，请减少题目数量或增加领域")
        same_level = [q for q in candidates if q.difficulty == difficulty]
        pool = same_level or candidates
        weakness = weak_topics or {}
        weights = [1 + weakness.get(question.topic, 0) for question in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    def count_available(self, topics: list[str]) -> int:
        """返回指定领域的题目总量。"""

        self.validate_topics(topics)
        selected = topics or list(SUPPORTED_TOPICS)
        return sum(question.topic in selected for question in self._questions)

    def search(self, query: str, topic: str | None = None, limit: int = 3) -> list[Question]:
        """按领域和关键词检索相关题目，为离线复习回答提供知识锚点。"""

        if topic:
            self.validate_topics([topic])
        normalized = query.lower().replace(" ", "")
        candidates = [
            question for question in self._questions if not topic or question.topic == topic
        ]

        def relevance(question: Question) -> int:
            """主题命中权重最高，参考点和题干命中用于细粒度排序。"""

            score = 5 if question.topic.lower() in normalized else 0
            score += sum(
                3
                for point in question.reference_points
                if point.lower().replace(" ", "") in normalized
            )
            score += sum(1 for char in set(normalized) if char in question.question.lower())
            return score

        return sorted(candidates, key=relevance, reverse=True)[:limit]
