"""
Simulation Utilities for Alpha Research Automation
데이터셋-리전 매핑 및 시뮬레이션 설정 관련 유틸리티 함수들
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatasetRegionMapper:
    """
    Brain API를 통해 데이터셋 정보를 조회하고
    데이터셋 ID로부터 Region을 추출하는 클래스
    """
    
    def __init__(self, ace_module):
        """
        Args:
            ace_module: ace 모듈 (get_datasets 함수 포함)
        """
        self.ace = ace_module
        self._cache = None
        self._cache_time = None
        self._cache_duration = timedelta(hours=1)  # 캐시 유효 시간: 1시간
    
    def _is_cache_valid(self) -> bool:
        """
        캐시가 유효한지 확인
        
        Returns:
            bool: 캐시가 유효하면 True, 아니면 False
        """
        if self._cache is None or self._cache_time is None:
            return False
        
        elapsed = datetime.now() - self._cache_time
        return elapsed < self._cache_duration
    
    def _load_datasets(self, session) -> pd.DataFrame:
        """
        Brain API로부터 전체 데이터셋 목록 조회
        
        Args:
            session: Brain API 인증 세션
            
        Returns:
            pd.DataFrame: 데이터셋 정보가 담긴 DataFrame
        """
        try:
            logger.info("Fetching datasets from Brain API...")
            
            # 기본 파라미터로 데이터셋 조회
            datasets_df = self.ace.get_datasets(
                session,
                instrument_type="EQUITY",
                region="USA",  # 기본값, 실제로는 여러 region 반환됨
                delay=1,
                universe="TOP3000"
            )
            
            logger.info(f"Successfully fetched {len(datasets_df)} datasets")
            return datasets_df
            
        except Exception as e:
            logger.error(f"Failed to fetch datasets: {str(e)}")
            raise RuntimeError(f"Brain API dataset fetch failed: {str(e)}")
    
    def get_region(self, session, dataset_id: str) -> str:
        """
        데이터셋 ID로부터 해당하는 Region을 반환
        
        Args:
            session: Brain API 인증 세션
            dataset_id (str): 데이터셋 ID (예: 'analyst10')
            
        Returns:
            str: Region 코드 (예: 'USA', 'GLOBAL', 'ASIA', 'EUROPE')
            
        Raises:
            ValueError: dataset_id가 None이거나 빈 문자열인 경우
            ValueError: 해당 dataset_id를 찾을 수 없는 경우
            TypeError: dataset_id가 문자열이 아닌 경우
        """
        # 입력 검증
        if dataset_id is None:
            raise ValueError("dataset_id cannot be None")
        
        if not isinstance(dataset_id, str):
            raise TypeError(f"dataset_id must be a string, got {type(dataset_id)}")
        
        dataset_id = dataset_id.strip()
        if not dataset_id:
            raise ValueError("dataset_id cannot be empty string")
        
        # 캐시 확인 및 로드
        if not self._is_cache_valid():
            logger.info("Cache invalid or expired. Reloading datasets...")
            self._cache = self._load_datasets(session)
            self._cache_time = datetime.now()
        else:
            logger.info("Using cached dataset information")
        
        # 데이터셋 ID로 필터링
        filtered = self._cache[self._cache['id'] == dataset_id]
        
        if filtered.empty:
            logger.error(f"Dataset '{dataset_id}' not found in Brain API")
            raise ValueError(
                f"Dataset '{dataset_id}' not found. "
                f"Please check the dataset ID or refresh the dataset list."
            )
        
        # Region 추출
        try:
            region = filtered.iloc[0]['region']
            logger.info(f"Dataset '{dataset_id}' mapped to region '{region}'")
            return region
            
        except KeyError:
            logger.error("'region' column not found in dataset information")
            raise KeyError(
                "Dataset information structure has changed. "
                "'region' column not found."
            )
    
    def clear_cache(self):
        """캐시 강제 초기화"""
        self._cache = None
        self._cache_time = None
        logger.info("Dataset cache cleared")
    
    def get_dataset_info(self, session, dataset_id: str) -> dict:
        """
        데이터셋의 전체 정보 반환 (디버깅/확인용)
        
        Args:
            session: Brain API 인증 세션
            dataset_id (str): 데이터셋 ID
            
        Returns:
            dict: 데이터셋 전체 정보
        """
        # 캐시 확인 및 로드
        if not self._is_cache_valid():
            self._cache = self._load_datasets(session)
            self._cache_time = datetime.now()
        
        filtered = self._cache[self._cache['id'] == dataset_id]
        
        if filtered.empty:
            raise ValueError(f"Dataset '{dataset_id}' not found")
        
        return filtered.iloc[0].to_dict()


# 편의 함수 (간단한 사용을 위한 래퍼)
_mapper = None

def dataset_to_region(session, dataset_id: str, ace_module=None) -> str:
    """
    데이터셋 ID로부터 Region을 반환하는 편의 함수
    
    Args:
        session: Brain API 인증 세션
        dataset_id (str): 데이터셋 ID (예: 'analyst10')
        ace_module: ace 모듈 (첫 호출 시 필수)
        
    Returns:
        str: Region 코드 (예: 'USA')
        
    Example:
        >>> import ace
        >>> from simulation_utils import dataset_to_region
        >>> 
        >>> session = ace.create_session(...)
        >>> region = dataset_to_region(session, 'analyst10', ace_module=ace)
        >>> print(region)  # 'USA'
    """
    global _mapper
    
    # 첫 호출 시 mapper 초기화
    if _mapper is None:
        if ace_module is None:
            raise ValueError(
                "ace_module must be provided for the first call to initialize the mapper"
            )
        _mapper = DatasetRegionMapper(ace_module)
    
    return _mapper.get_region(session, dataset_id)


def clear_dataset_cache():
    """캐시 초기화 편의 함수"""
    global _mapper
    if _mapper is not None:
        _mapper.clear_cache()


def get_dataset_info(session, dataset_id: str) -> dict:
    """데이터셋 전체 정보 조회 편의 함수"""
    global _mapper
    if _mapper is None:
        raise RuntimeError("Mapper not initialized. Call dataset_to_region first.")
    return _mapper.get_dataset_info(session, dataset_id)


if __name__ == "__main__":
    # 테스트 코드 (실제 사용 시에는 실행되지 않음)
    print("simulation_utils.py loaded successfully")
    print("Available functions:")
    print("  - dataset_to_region(session, dataset_id, ace_module)")
    print("  - clear_dataset_cache()")
    print("  - get_dataset_info(session, dataset_id)")