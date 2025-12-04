"""ChromaDB-based experience storage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from ..paths import get_knowledge_dir

if TYPE_CHECKING:
    import chromadb
    from chromadb.api.types import Collection

logger = logging.getLogger(__name__)


class ExperienceStore:
    """向量数据库存储经验"""
    
    _client: Optional[chromadb.Client]
    _raw_collection: Optional[Collection]
    _refined_collection: Optional[Collection]
    
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        # 使用统一的 .auto-deployer/knowledge 目录
        if persist_dir:
            self.persist_dir = Path(persist_dir)
        else:
            self.persist_dir = get_knowledge_dir()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.embedding_model = embedding_model
        self._client = None
        self._embedding_fn = None
        self._raw_collection = None
        self._refined_collection = None
    
    def _ensure_initialized(self):
        """懒加载初始化 - 延迟导入重型依赖"""
        if self._client is not None:
            return
        
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for knowledge storage. "
                "Install with: pip install chromadb"
            )
        
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embedding. "
                "Install with: pip install sentence-transformers"
            )
        
        # 设置离线模式 - 优先使用本地缓存，避免每次检查更新
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        
        # 初始化 embedding 模型（使用本地缓存）
        logger.info(f"Loading embedding model: {self.embedding_model}")
        try:
            model = SentenceTransformer(self.embedding_model, local_files_only=True)
        except Exception:
            # 如果本地没有缓存，才尝试下载
            logger.info("Local cache not found, downloading model...")
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            model = SentenceTransformer(self.embedding_model)
        
        # ChromaDB embedding function 包装 - 使用新 API
        from chromadb import EmbeddingFunction, Documents, Embeddings
        
        class CustomEmbeddingFunction(EmbeddingFunction):
            def __init__(self, st_model):
                self._model = st_model
            
            def __call__(self, input: Documents) -> Embeddings:
                embeddings = self._model.encode(list(input), convert_to_numpy=True)
                return embeddings.tolist()
        
        self._embedding_fn = CustomEmbeddingFunction(model)
        
        # 初始化 ChromaDB - 使用新 API（持久化客户端）
        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        
        # 创建两个 collection
        self._raw_collection = self._client.get_or_create_collection(
            name="raw_experiences",
            embedding_function=self._embedding_fn,
            metadata={"description": "Raw experiences extracted from logs"}
        )
        
        self._refined_collection = self._client.get_or_create_collection(
            name="refined_experiences", 
            embedding_function=self._embedding_fn,
            metadata={"description": "LLM-refined experiences"}
        )
        
        logger.info("Knowledge store initialized")
    
    # ========== Raw Experiences ==========
    
    def add_raw_experience(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """添加原始经验"""
        self._ensure_initialized()
        
        try:
            # 确保 metadata 值都是字符串（ChromaDB 要求）
            clean_metadata = {
                k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                for k, v in metadata.items()
            }
            
            self._raw_collection.add(
                ids=[id],
                documents=[content],
                metadatas=[clean_metadata]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add raw experience {id}: {e}")
            return False
    
    def get_raw_experience(self, id: str) -> Optional[Dict[str, Any]]:
        """获取原始经验"""
        self._ensure_initialized()
        
        result = self._raw_collection.get(ids=[id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "content": result["documents"][0],
                "metadata": result["metadatas"][0]
            }
        return None
    
    def get_all_raw_experiences(self) -> List[Dict[str, Any]]:
        """获取所有原始经验"""
        self._ensure_initialized()
        
        result = self._raw_collection.get()
        experiences = []
        for i, id in enumerate(result["ids"]):
            experiences.append({
                "id": id,
                "content": result["documents"][i],
                "metadata": result["metadatas"][i]
            })
        return experiences
    
    def get_unprocessed_raw_experiences(self) -> List[Dict[str, Any]]:
        """获取未处理的原始经验"""
        self._ensure_initialized()
        
        result = self._raw_collection.get(
            where={"processed": "False"}
        )
        experiences = []
        for i, id in enumerate(result["ids"]):
            experiences.append({
                "id": id,
                "content": result["documents"][i],
                "metadata": result["metadatas"][i]
            })
        return experiences
    
    def mark_raw_as_processed(self, id: str) -> bool:
        """标记原始经验为已处理"""
        self._ensure_initialized()
        
        try:
            exp = self.get_raw_experience(id)
            if exp:
                exp["metadata"]["processed"] = "True"
                self._raw_collection.update(
                    ids=[id],
                    metadatas=[exp["metadata"]]
                )
            return True
        except Exception as e:
            logger.error(f"Failed to mark {id} as processed: {e}")
            return False
    
    def raw_exists(self, id: str) -> bool:
        """检查原始经验是否存在"""
        self._ensure_initialized()
        result = self._raw_collection.get(ids=[id])
        return len(result["ids"]) > 0
    
    def raw_count(self) -> int:
        """原始经验数量"""
        self._ensure_initialized()
        return self._raw_collection.count()
    
    def search_raw(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """搜索原始经验（语义搜索）"""
        self._ensure_initialized()
        
        results = self._raw_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where
        )
        
        experiences = []
        if results["ids"] and results["ids"][0]:
            for i, id in enumerate(results["ids"][0]):
                experiences.append({
                    "id": id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None
                })
        
        return experiences
    
    # ========== Refined Experiences ==========
    
    def add_refined_experience(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """添加精炼经验"""
        self._ensure_initialized()
        
        try:
            clean_metadata = {
                k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                for k, v in metadata.items()
            }
            
            self._refined_collection.add(
                ids=[id],
                documents=[content],
                metadatas=[clean_metadata]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add refined experience {id}: {e}")
            return False
    
    def get_refined_experience(self, id: str) -> Optional[Dict[str, Any]]:
        """获取精炼经验"""
        self._ensure_initialized()
        
        result = self._refined_collection.get(ids=[id])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "content": result["documents"][0],
                "metadata": result["metadatas"][0]
            }
        return None
    
    def get_all_refined_experiences(self) -> List[Dict[str, Any]]:
        """获取所有精炼经验"""
        self._ensure_initialized()
        
        result = self._refined_collection.get()
        experiences = []
        for i, id in enumerate(result["ids"]):
            experiences.append({
                "id": id,
                "content": result["documents"][i],
                "metadata": result["metadatas"][i]
            })
        return experiences
    
    def search_refined(
        self,
        query: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """搜索精炼经验"""
        self._ensure_initialized()
        
        results = self._refined_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where
        )
        
        experiences = []
        if results["ids"] and results["ids"][0]:
            for i, id in enumerate(results["ids"][0]):
                experiences.append({
                    "id": id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None
                })
        
        return experiences
    
    def refined_exists(self, id: str) -> bool:
        """检查精炼经验是否存在"""
        self._ensure_initialized()
        result = self._refined_collection.get(ids=[id])
        return len(result["ids"]) > 0
    
    def refined_count(self) -> int:
        """精炼经验数量"""
        self._ensure_initialized()
        return self._refined_collection.count()
    
    # ========== Stats ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._ensure_initialized()
        
        raw = self.get_all_raw_experiences()
        refined = self.get_all_refined_experiences()
        
        # 统计各类型经验
        universal_count = sum(1 for e in refined if e["metadata"].get("scope") == "universal")
        project_specific_count = sum(1 for e in refined if e["metadata"].get("scope") == "project_specific")
        
        # 统计各项目类型
        project_types = {}
        for e in refined:
            pt = e["metadata"].get("project_type", "unknown")
            project_types[pt] = project_types.get(pt, 0) + 1
        
        return {
            "raw_count": len(raw),
            "refined_count": len(refined),
            "unprocessed_count": sum(1 for e in raw if e["metadata"].get("processed") == "False"),
            "universal_count": universal_count,
            "project_specific_count": project_specific_count,
            "project_types": project_types,
            "persist_dir": str(self.persist_dir)
        }
    
    def persist(self):
        """持久化数据 - PersistentClient 会自动持久化，此方法保留以兼容旧代码"""
        # 新版 ChromaDB PersistentClient 自动持久化
        logger.debug("Knowledge store auto-persisted by PersistentClient")
