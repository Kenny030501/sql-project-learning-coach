TASKS = [
    {
        "id": "quality",
        "title": "01 数据质量检查",
        "brief": "统计orders总行数和customer_id为空的订单数。输出 total_orders、missing_customer_orders。空客户订单保留在质量报告中。",
        "answer": "SELECT COUNT(*) AS total_orders, SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS missing_customer_orders FROM orders",
        "hints": [
            "先定义质量检查对象是订单表，不要连接明细。",
            "COUNT(*)计算总量；条件聚合识别缺失客户。",
            "SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END)",
        ],
        "kind": "sql",
        "ordered": False,
    },
    {
        "id": "scale",
        "title": "02 订单规模与GMV",
        "brief": "只统计status='delivered'订单。输出 delivered_orders（去重订单数）、gmv（quantity×unit_price之和）；金额单位为教学币，不是收入。",
        "answer": "SELECT COUNT(DISTINCT o.order_id) AS delivered_orders, SUM(i.quantity*i.unit_price) AS gmv FROM orders o JOIN order_items i USING(order_id) WHERE o.status='delivered'",
        "hints": [
            "连接明细后，一笔订单可能对应多行。",
            "订单数去重，GMV在商品行相加，先筛选已交付。",
            "COUNT(DISTINCT o.order_id)",
        ],
        "kind": "sql",
        "ordered": False,
    },
    {
        "id": "category",
        "title": "03 品类贡献",
        "brief": "计算已交付订单各品类的GMV。输出 category、gmv，按gmv降序、category升序排列。",
        "answer": "SELECT p.category, SUM(i.quantity*i.unit_price) AS gmv FROM orders o JOIN order_items i USING(order_id) JOIN products p USING(product_id) WHERE o.status='delivered' GROUP BY p.category ORDER BY gmv DESC,p.category",
        "hints": [
            "品类来自products，金额来自order_items。",
            "连接三表后按品类分组；过滤订单状态。",
            "SUM(i.quantity*i.unit_price) AS gmv",
        ],
        "kind": "sql",
        "ordered": True,
    },
    {
        "id": "repeat",
        "title": "04 复购客户",
        "brief": "以至少有一笔已交付订单且customer_id非空的客户为分母，统计至少两笔已交付订单的客户数。输出 buyers、repeat_buyers、repeat_rate（0–1，不四舍五入）。",
        "answer": "WITH c AS (SELECT customer_id,COUNT(*) AS n FROM orders WHERE status='delivered' AND customer_id IS NOT NULL GROUP BY customer_id) SELECT COUNT(*) AS buyers,SUM(CASE WHEN n>=2 THEN 1 ELSE 0 END) AS repeat_buyers,AVG(CASE WHEN n>=2 THEN 1.0 ELSE 0.0 END) AS repeat_rate FROM c",
        "hints": [
            "先聚合到客户粒度，订单行不是客户人数。",
            "先按客户计数，再统计n>=2的客户比例。",
            "WITH c AS (SELECT customer_id, COUNT(*) AS n FROM orders WHERE status='delivered' AND customer_id IS NOT NULL GROUP BY customer_id)",
        ],
        "kind": "sql",
        "ordered": False,
    },
    {
        "id": "growth",
        "title": "05 月度增长拆解",
        "brief": "对已交付订单按购买月份计算：month（YYYY-MM）、orders（去重订单）、gmv、aov=gmv/orders。按month升序。用订单数×客单价解释金额变化，不将变化称为因果。",
        "answer": "SELECT STRFTIME(o.ordered_at,'%Y-%m') AS month,COUNT(DISTINCT o.order_id) AS orders,SUM(i.quantity*i.unit_price) AS gmv,SUM(i.quantity*i.unit_price)/COUNT(DISTINCT o.order_id) AS aov FROM orders o JOIN order_items i USING(order_id) WHERE o.status='delivered' GROUP BY 1 ORDER BY 1",
        "hints": [
            "月份归属使用购买时间；同月各指标分母一致。",
            "按月聚合；AOV等于当月GMV/去重订单数。",
            "STRFTIME(o.ordered_at, '%Y-%m') AS month",
        ],
        "kind": "sql",
        "ordered": True,
    },
    {
        "id": "decision",
        "title": "06 形成业务建议",
        "brief": "引用至少两项前述实际查询结果，提出一个行动、一个替代解释和一个后续验证指标。AI提供4维辅助反馈，最终由人工复核。",
        "answer": "参考结构：观察数据→不确定性→行动→验证指标。不存在唯一标准结论。",
        "hints": [
            "先区分事实、解释和行动。",
            "至少引用两项查询结果，并提出一个可能推翻你判断的解释。",
            "建议格式：观察到…；可能因为…；先做…；用…验证。",
        ],
        "kind": "business",
        "ordered": False,
    },
    {
        "id": "transfer1",
        "title": "迁移一：取消订单分析",
        "brief": "独立计算status='cancelled'的去重订单数和商品金额，输出 cancelled_orders、cancelled_value。金额不能解释为已收款或损失。",
        "answer": "SELECT COUNT(DISTINCT o.order_id) AS cancelled_orders,SUM(i.quantity*i.unit_price) AS cancelled_value FROM orders o JOIN order_items i USING(order_id) WHERE o.status='cancelled'",
        "hints": [
            "将已学过的粒度和状态口径迁移到新情境。",
            "保留订单去重与明细金额计算，但改变状态。",
            "COUNT(DISTINCT o.order_id)",
        ],
        "kind": "sql",
        "ordered": False,
    },
    {
        "id": "transfer2",
        "title": "迁移二：地区购买结构",
        "brief": "按客户region统计已交付订单的去重订单数和GMV，排除region为空及没有客户记录的订单。输出 region、orders、gmv；按gmv降序、region升序。",
        "answer": "SELECT c.region,COUNT(DISTINCT o.order_id) AS orders,SUM(i.quantity*i.unit_price) AS gmv FROM orders o JOIN customers c USING(customer_id) JOIN order_items i USING(order_id) WHERE o.status='delivered' AND c.region IS NOT NULL GROUP BY c.region ORDER BY gmv DESC,c.region",
        "hints": [
            "新的维度来自customers，仍要保护订单粒度。",
            "检查客户匹配与region非空条件。",
            "JOIN customers c USING(customer_id)",
        ],
        "kind": "sql",
        "ordered": True,
    },
]
SCHEMA = [
    {
        "table": "customers",
        "grain": "一行一位客户",
        "columns": "customer_id INTEGER, region VARCHAR；region可能为空",
    },
    {
        "table": "orders",
        "grain": "一行一笔订单",
        "columns": "order_id INTEGER, customer_id INTEGER, ordered_at DATE, status VARCHAR；状态delivered/cancelled/processing，部分客户为空",
    },
    {
        "table": "order_items",
        "grain": "一行一个订单商品项",
        "columns": "order_id INTEGER, item_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price DECIMAL(10,2)",
    },
    {
        "table": "products",
        "grain": "一行一种商品",
        "columns": "product_id INTEGER, category VARCHAR",
    },
]
BY_ID = {t["id"]: t for t in TASKS}


def public_tasks():
    return [{k: v for k, v in t.items() if k not in {"answer", "hints"}} for t in TASKS]
