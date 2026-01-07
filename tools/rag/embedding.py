from models import embed_model

def test_embedding_model():
    """测试Embedding模型是否能正常调用"""
    print("开始测试Embedding模型...")

    # 1. 测试单句嵌入
    try:
        test_text = "这是一个测试句子，用于验证Embedding模型是否正常工作"
        print(f"\n测试文本：{test_text}")

        # 生成嵌入向量
        embedding = embed_model.embed_query(test_text)

        # 验证结果
        if embedding and isinstance(embedding, list):
            print(f"✅ 单句嵌入成功！")
            print(f"   向量维度：{len(embedding)}")
            print(f"   向量前5个值：{embedding[:5]}")
            print(f"   向量后5个值：{embedding[-5:]}")
        else:
            print("❌ 单句嵌入失败：返回结果为空或格式不正确")
            return False

    except Exception as e:
        print(f"❌ 单句嵌入出错：{str(e)}")
        print(f"   错误类型：{type(e).__name__}")
        return False

    # 2. 测试批量嵌入
    try:
        test_texts = [
            "第一个测试句子",
            "第二个测试句子",
            "第三个测试句子"
        ]
        print(f"\n测试批量嵌入，共{len(test_texts)}个句子...")

        # 生成批量嵌入向量
        embeddings = embed_model.embed_documents(test_texts)

        # 验证结果
        if embeddings and isinstance(embeddings, list) and len(embeddings) == len(test_texts):
            print(f"✅ 批量嵌入成功！")
            for i, emb in enumerate(embeddings):
                print(f"   句子{i + 1} - 向量维度：{len(emb)}")

            # 计算向量相似度（可选）
            from scipy import spatial
            similarity = 1 - spatial.distance.cosine(embeddings[0], embeddings[1])
            print(f"   句子1和句子2的余弦相似度：{similarity:.4f}")
        else:
            print("❌ 批量嵌入失败：返回结果数量不匹配或格式不正确")
            return False

    except ImportError:
        print("⚠️ 跳过相似度计算：未安装scipy库（可执行 pip install scipy 安装）")
    except Exception as e:
        print(f"❌ 批量嵌入出错：{str(e)}")
        print(f"   错误类型：{type(e).__name__}")
        return False

# 执行测试
success = test_embedding_model()