from langchain_core.documents import Document
from models import rerank_model

# 使用示例
documents = [
    Document(page_content="咖啡豆的产地主要分布在赤道附近，被称为‘咖啡带’。"),
    Document(page_content="法压壶的步骤：1. 研磨咖啡豆。2. 加入热水。3. 压下压杆。4. 倒入杯中。"),
    Document(page_content="意式浓缩咖啡需要一台高压机器，在9个大气压下快速萃取。"),
    Document(page_content="挑选咖啡豆时，要注意其烘焙日期，新鲜的豆子风味更佳。"),
    Document(page_content="手冲咖啡的技巧：控制水流速度、均匀注水和合适的水温（90-96°C）是关键。"),
]

results = rerank_model.invoke("牛是一种动物如何冲泡一杯好喝的咖啡？", k=4, documents=documents)
print(results)