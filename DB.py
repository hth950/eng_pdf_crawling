from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Tuple, Any

import logging

logger = logging.getLogger("eduspace")


class DatabaseError(Exception):
    """사용자 정의 예외 클래스: 데이터베이스 작업 중 발생한 예외를 처리합니다."""

    pass


class DatabaseManager:
    def __init__(self, db_url: str):
        """
        데이터베이스 매니저 초기화. SQLAlchemy 세션 설정.

        Args:
            db_url (str): 데이터베이스 연결 URL (예: `sqlite+aiosqlite:///example.db`).
        """
        self.engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=20,  # 기본 풀 크기
            max_overflow=30,  # 초과 연결 허용 수
            pool_timeout=60,  # 연결 대기 타임아웃
            pool_recycle=1800,
            pool_pre_ping=True,
        )  # 연결 재사용 시간(초))
        self.async_session = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def connect(self):
        """테이블 생성 및 연결 확인."""
        try:
            async with self.engine.begin() as conn:
                # await conn.run_sync(Base.metadata.create_all)  # 모든 테이블 생성
                logger.info("데이터베이스에 성공적으로 연결되었습니다.")
        except SQLAlchemyError as e:
            logger.error(f"데이터베이스 연결 실패: {str(e)}")
            raise DatabaseError("데이터베이스 연결 중 오류가 발생했습니다.")

    async def disconnect(self):
        """데이터베이스 연결 해제."""
        try:
            await self.engine.dispose()
            logger.info("데이터베이스 연결이 성공적으로 해제되었습니다.")
        except SQLAlchemyError as e:
            logger.error(f"데이터베이스 연결 해제 실패: {str(e)}")
            raise DatabaseError("데이터베이스 연결 해제 중 오류가 발생했습니다.")

    async def add_entry(self, entry):
        """
        데이터를 데이터베이스에 추가.

        Args:
            entry: 추가할 ORM 객체.
        """
        async with self.async_session() as session:
            try:
                session.add(entry)
                await session.commit()
                logger.info(f"데이터가 성공적으로 추가되었습니다: {entry}")
            except SQLAlchemyError as e:
                logger.error(f"데이터 추가 중 오류 발생: {str(e)}")
                await session.rollback()
                raise DatabaseError("데이터 추가 중 오류가 발생했습니다.")

    async def execute(self, sql: str):
        async with self.async_session() as session:
            try:
                result = await session.execute(sql)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e

    async def get_all(self, model, filters: Optional[dict] = None) -> List[Any]:
        """
        특정 조건에 맞는 모든 데이터를 조회합니다.

        Args:
            model: 조회할 SQLAlchemy 모델.
            filters (Optional[dict]): 조회 조건. 딕셔너리 형태여야 합니다.

        Returns:
            List[Any]: 조회된 데이터 리스트.
        """
        async with self.async_session() as session:
            try:
                query = select(model)
                if filters and isinstance(filters, dict):  # filters가 딕셔너리인지 확인
                    query = query.filter_by(**filters)
                result = await session.execute(query)
                data = result.scalars().all()
                logger.info(
                    f"{model.__tablename__}에서 {len(data)}개의 데이터를 조회했습니다."
                )
                return data
            except SQLAlchemyError as e:
                logger.error(
                    f"{model.__tablename__}에서 데이터 조회 중 오류 발생: {str(e)}"
                )
                raise DatabaseError("데이터 조회 중 오류가 발생했습니다.")

    async def get_by_id(self, model, entry_id: int) -> Optional[Any]:
        """
        ID를 기준으로 데이터를 조회합니다.

        Args:
            model: 조회할 SQLAlchemy 모델.
            entry_id (int): 조회할 데이터의 ID.

        Returns:
            Optional[Any]: 조회된 데이터.
        """
        async with self.async_session() as session:
            try:
                query = select(model).where(model.id == entry_id)
                result = await session.execute(query)
                data = result.scalars().first()
                if data:
                    logger.info(
                        f"{model.__tablename__}에서 ID={entry_id} 데이터 조회 성공."
                    )
                else:
                    logger.warning(
                        f"{model.__tablename__}에서 ID={entry_id} 데이터가 없습니다."
                    )
                return data
            except SQLAlchemyError as e:
                logger.error(
                    f"{model.__tablename__}에서 ID={entry_id} 데이터 조회 중 오류 발생: {str(e)}"
                )
                raise DatabaseError("데이터 조회 중 오류가 발생했습니다.")

    async def update_entry(self, model, entry_id: int, updates: dict):
        """
        데이터를 업데이트합니다.

        Args:
            model: 업데이트할 SQLAlchemy 모델.
            entry_id (int): 업데이트할 데이터의 ID.
            updates (dict): 업데이트할 필드와 값.
        """
        async with self.async_session() as session:
            try:
                stmt = update(model).where(model.id == entry_id).values(**updates)
                await session.execute(stmt)
                await session.commit()
                logger.info(
                    f"{model.__tablename__}에서 ID={entry_id} 데이터 업데이트 성공."
                )
            except SQLAlchemyError as e:
                logger.error(
                    f"{model.__tablename__}에서 ID={entry_id} 데이터 업데이트 중 오류 발생: {str(e)}"
                )
                await session.rollback()
                raise DatabaseError("데이터 업데이트 중 오류가 발생했습니다.")

    async def delete_entry(self, model, entry_id: int):
        """
        데이터를 삭제합니다.

        Args:
            model: 삭제할 SQLAlchemy 모델.
            entry_id (int): 삭제할 데이터의 ID.
        """
        async with self.async_session() as session:
            try:
                stmt = delete(model).where(model.id == entry_id)
                await session.execute(stmt)
                await session.commit()
                logger.info(
                    f"{model.__tablename__}에서 ID={entry_id} 데이터 삭제 성공."
                )
            except SQLAlchemyError as e:
                logger.error(
                    f"{model.__tablename__}에서 ID={entry_id} 데이터 삭제 중 오류 발생: {str(e)}"
                )
                await session.rollback()
                raise DatabaseError("데이터 삭제 중 오류가 발생했습니다.")

    async def fetch_all(
        self,
        model,
        filters: dict = None,
        options: list = None,
        additional_filters: list = None,
        joins: list = None,  # 추가된 인자: 조인 대상 관계 리스트
    ) -> list:
        """
        ORM 모델에서 조건에 맞는 모든 데이터를 조회합니다.

        Args:
            model (Base): 조회할 SQLAlchemy 모델 클래스.
            filters (dict): 조회 조건 (예: {"id": 1}).
            options (list): 추가 로드 옵션 (예: [joinedload(Model.relation)]).
            additional_filters (list): 추가 필터 조건 (예: [Model.field == value]).
            joins (list): 조인 대상 관계 리스트 (예: [Model.relation]).

        Returns:
            list: 조건에 맞는 ORM 객체 리스트.
        """
        async with self.async_session() as session:
            try:
                query = select(model)

                # 조인 처리
                if joins:
                    for join_relation in joins:
                        query = query.join(join_relation)

                # 필터 처리
                if filters:
                    query = query.filter_by(**filters)
                if additional_filters:
                    for filter_condition in additional_filters:
                        query = query.filter(filter_condition)

                # 옵션 처리
                if options:
                    for option in options:
                        query = query.options(option)

                result = await session.execute(query)
                data = result.unique().scalars().all()
                return data
            except Exception as e:
                logger.error(
                    f"{model.__tablename__} 테이블에서 데이터를 조회하는 중 오류가 발생했습니다: {e}"
                )
                raise

    # async def fetch_all(
    #     self,
    #     model,
    #     filters: dict = None,
    #     options: list = None,
    #     additional_filters: list = None,
    # ) -> list:
    #     """
    #     ORM 모델에서 조건에 맞는 모든 데이터를 조회합니다.

    #     Args:
    #         model (Base): 조회할 SQLAlchemy 모델 클래스.
    #         filters (dict): 조회 조건 (예: {"id": 1}).
    #         options (list): 추가 로드 옵션 (예: [joinedload(Model.relation)]).

    #     Returns:
    #         list: 조건에 맞는 ORM 객체 리스트.
    #     """
    #     async with self.async_session() as session:
    #         try:
    #             query = select(model)
    #             if filters:
    #                 query = query.filter_by(**filters)
    #             if additional_filters:
    #                 query = query.filter(*additional_filters)
    #             if options:
    #                 for option in options:
    #                     query = query.options(option)
    #             result = await session.execute(query)
    #             data = result.scalars().all()
    #             return data
    #         except Exception as e:
    #             logger.error(
    #                 f"{model.__tablename__} 테이블에서 데이터를 조회하는 중 오류가 발생했습니다: {e}"
    #             )
    #             raise

    async def fetch_one(
        self,
        model,
        filters: dict = None,
        options: list = None,
        additional_filters: list = None,
    ):
        """
        ORM 모델에서 하나의 데이터를 조회합니다.

        Args:
            model (Base): 조회할 SQLAlchemy 모델 클래스.
            filters (dict): 기본 조회 조건 (예: {"id": 1}).
            options (list): 추가 로드 옵션 (예: [joinedload(Model.relation)]).
            additional_filters (list): SQLAlchemy 표현식을 활용한 추가 필터 (예: [func.lower(Model.name) == "test"]).

        Returns:
            ORM 객체 또는 None.
        """
        async with self.async_session() as session:
            try:
                query = select(model)
                # 디버깅: 쿼리 조건 확인
                if filters:
                    query = query.filter_by(**filters)
                if additional_filters:
                    query = query.filter(*additional_filters)
                if options:
                    query = query.options(*options)
                # 쿼리 실행
                result = await session.execute(query)
                # result.scalars() 또는 result.fetchone() 등 사용
                data = result.unique().scalars().first()
                return data

            except Exception as e:
                # 에러 로그
                print(
                    f"[ERROR] {model.__tablename__} 테이블에서 데이터를 조회하는 중 오류 발생: {e}"
                )
                raise

    async def get_last_insert_id(self) -> int:
        """
        마지막으로 삽입된 ID를 가져옵니다.

        Returns:
            int: 마지막으로 삽입된 ID.
        """
        async with self.async_session() as session:
            try:
                result = await session.execute(select(func.LAST_INSERT_ID()))
                last_id = result.scalar()
                logger.info(f"마지막 삽입된 ID를 가져왔습니다: {last_id}")
                return last_id
            except Exception as e:
                logger.error("마지막 삽입된 ID를 가져오는 중 오류가 발생했습니다.")
                raise

    async def get_prompt_data(
        self, prompt_name: str
    ) -> Tuple[str, List[str], List[str], int]:
        """
        프롬프트 데이터를 조회합니다.

        Args:
            prompt_name (str): 조회할 프롬프트 이름.

        Returns:
            Tuple[str, List[str], List[str], int]: 시스템 프롬프트, 사용자 질문 리스트,
                답변 리스트, Few-shot 데이터 수.
        """
        async with self.async_session() as session:
            try:
                query = select(PromptStore).filter_by(name=prompt_name)
                result = await session.execute(query)
                prompt = result.scalars().first()

                if not prompt:
                    raise ValueError(
                        f"프롬프트 이름 '{prompt_name}'에 해당하는 데이터를 찾을 수 없습니다."
                    )

                few_shots_query = select(FewShotStore).filter_by(prompt_id=prompt.id)
                few_shots_result = await session.execute(few_shots_query)
                few_shots = few_shots_result.scalars().all()
                few_shots_num = len(few_shots)

                questions = [fs.user for fs in few_shots]
                answers = [fs.assistants for fs in few_shots]

                logger.info(f"프롬프트 '{prompt_name}' 데이터를 조회했습니다.")
                return (
                    prompt.system,
                    prompt.user,
                    questions,
                    answers,
                    few_shots_num,
                    prompt.response_format,
                )
            except Exception as e:
                logger.error(f"프롬프트 데이터를 조회하는 중 오류가 발생했습니다: {e}")
                raise

    async def insert_prompt(
        self,
        name: str,
        system: str,
        user: str,
        few_shot: Optional[Tuple[List[str], List[str]]] = None,
    ) -> None:
        """
        프롬프트 데이터를 추가합니다. 필요한 경우 Few-Shot 데이터를 함께 추가합니다.

        Args:
            name (str): 프롬프트 이름.
            system (str): 시스템 설명.
            user (str): 사용자 입력.
            few_shot (Optional[Tuple[List[str], List[str]]]): 질문과 답변 리스트 (없으면 None).
        """
        async with self.async_session() as session:
            try:
                prompt = PromptStore(
                    name=name, system=system, user=user, few_shot=bool(few_shot)
                )
                session.add(prompt)
                await session.commit()
                logger.info(f"프롬프트 데이터가 추가되었습니다: {prompt}")

                if few_shot:
                    await self.insert_few_shot(session, prompt.id, few_shot)
            except Exception as e:
                logger.error(f"프롬프트 데이터 삽입 중 오류가 발생했습니다: {e}")
                raise

    async def insert_few_shot(
        self,
        session: AsyncSession,
        prompt_id: int,
        few_shot: Tuple[List[str], List[str]],
    ) -> None:
        """
        Few-Shot 데이터를 추가합니다.

        Args:
            session (AsyncSession): 활성화된 세션 객체.
            prompt_id (int): 프롬프트 ID.
            few_shot (Tuple[List[str], List[str]]): 질문과 답변 리스트.
        """
        try:
            questions, answers = few_shot
            for question, answer in zip(questions, answers):
                few_shot_entry = FewShotStore(
                    prompt_id=prompt_id, user=question, assistants=answer
                )
                session.add(few_shot_entry)
            await session.commit()
            logger.info(f"Few-Shot 데이터가 추가되었습니다: 프롬프트 ID {prompt_id}")
        except Exception as e:
            logger.error(f"Few-Shot 데이터 삽입 중 오류가 발생했습니다: {e}")
            raise

    async def get_all_with_pagination(
        self, model, skip: int = 0, limit: Optional[int] = None, order_by=None
    ) -> List[Any]:
        """
        페이지네이션을 적용하여 데이터를 조회합니다.

        Args:
            model: 조회할 SQLAlchemy 모델.
            skip (int): 건너뛸 데이터 수.
            limit (Optional[int]): 가져올 데이터 수. None이면 제한 없음.
            order_by: 정렬 기준.

        Returns:
            List[Any]: 조회된 데이터 리스트.
        """
        async with self.async_session() as session:
            try:
                query = select(model)
                if order_by:
                    query = query.order_by(order_by)
                if limit is not None:
                    query = query.offset(skip).limit(limit)
                else:
                    query = query.offset(skip)
                result = await session.execute(query)
                data = result.scalars().all()
                return data
            except SQLAlchemyError as e:
                logger.error(
                    f"{model.__tablename__}에서 데이터 조회 중 오류 발생: {str(e)}"
                )
                raise DatabaseError("데이터 조회 중 오류가 발생했습니다.")

    async def count(self, model) -> int:
        """
        테이블의 전체 데이터 개수를 반환합니다.

        Args:
            model: 개수를 구할 SQLAlchemy 모델.

        Returns:
            int: 전체 데이터 개수.
        """
        async with self.async_session() as session:
            try:
                result = await session.execute(select(func.count()).select_from(model))
                total_count = result.scalar()
                return total_count
            except SQLAlchemyError as e:
                logger.error(
                    f"{model.__tablename__}에서 데이터 개수 조회 중 오류 발생: {str(e)}"
                )
                raise DatabaseError("데이터 개수 조회 중 오류가 발생했습니다.")

    async def assign_group_ids(self, session: AsyncSession, model):
        """
        info_id와 passage로 그룹화하여 그룹화된 항목 중 가장 낮은 id 값을 group_id에 할당합니다.

        Args:
            session (AsyncSession): 활성화된 세션 객체.
            model (Base): 처리할 SQLAlchemy ORM 모델.

        Raises:
            DatabaseError: 데이터 처리 중 오류가 발생하면 예외를 발생시킵니다.
        """
        try:
            # Aliased table for selecting minimum id per group
            min_id_alias = aliased(model)

            # Query to find the minimum id for each group of info_id and passage
            subquery = (
                select(
                    min_id_alias.info_id,
                    min_id_alias.passage,
                    func.min(min_id_alias.id).label("min_id"),
                )
                .group_by(min_id_alias.info_id, min_id_alias.passage)
                .subquery()
            )

            # Update the original table with the corresponding group_id
            stmt = (
                update(model)
                .where(
                    (model.info_id == subquery.c.info_id)
                    & (model.passage == subquery.c.passage)
                )
                .values(group_id=subquery.c.min_id)
            )

            await session.execute(stmt)
            await session.commit()

            logger.info("group_id가 성공적으로 업데이트되었습니다.")
        except SQLAlchemyError as e:
            logger.error(f"group_id 업데이트 중 오류 발생: {str(e)}")
            await session.rollback()
            raise DatabaseError("group_id 업데이트 중 오류가 발생했습니다.")

    async def create_entry(self, model, data: dict) -> Any:
        """
        주어진 데이터를 기반으로 ORM 모델 객체를 생성하고 데이터베이스에 삽입합니다.

        Args:
            model: SQLAlchemy ORM 모델 클래스.
            data (dict): 삽입할 데이터 딕셔너리.

        Returns:
            Any: 생성된 ORM 모델 객체.
        """
        async with self.async_session() as session:
            try:
                # 모델 인스턴스 생성
                entry = model(**data)
                session.add(entry)
                await session.commit()
                logger.info(
                    f"{model.__tablename__}에 데이터가 성공적으로 추가되었습니다: {data}"
                )
                return entry
            except SQLAlchemyError as e:
                logger.error(f"{model.__tablename__}에 데이터 추가 중 오류 발생: {e}")
                await session.rollback()
                raise DatabaseError("데이터 추가 중 오류가 발생했습니다.")


from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base_oci = declarative_base()


# 1) problem 테이블
class Problem(Base_oci):
    __tablename__ = "problem"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    group_id = Column(Integer, ForeignKey("problem_group.id"), nullable=True)
    number = Column(String(255), nullable=True)
    point = Column(Integer, nullable=True)
    type = Column(
        Enum(
            "multiple_choice",
            "short_answer",
            "essay",
            "ox",
            "etc",
            name="problem_type_enum",
        ),
        nullable=True,
    )
    level = Column(Integer, nullable=True)
    question = Column(Text, nullable=True)
    refer = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    solution = Column(Text, nullable=True)
    has_table = Column(Boolean, nullable=True)
    similarity = Column(Integer, nullable=True)
    is_verified = Column(Boolean, nullable=True)
    memo = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=True
    )
    grade = Column(Integer, nullable=True)
    school_level = Column(
        Enum("elementary", "middle", "high", name="school_level_enum"), nullable=False
    )
    subject = Column(
        Enum(
            "math",
            "science",
            "korean",
            "english",
            "social",
            "history",
            "etc",
            name="subject_enum",
        ),
        nullable=False,
    )
    source_type = Column(
        Enum("ai", "extracted", "manual", name="source_type_enum"), nullable=False
    )
    purpose = Column(Text, nullable=True)
    choice1 = Column(Text, nullable=True)
    choice2 = Column(Text, nullable=True)
    choice3 = Column(Text, nullable=True)
    choice4 = Column(Text, nullable=True)
    choice5 = Column(Text, nullable=True)
    main_category_tag_id = Column(Integer, nullable=True)
    variation_level = Column(Integer, nullable=True, comment="변형 정도")
    format = Column(String(255), nullable=True)
    error_memo = Column(Text, nullable=True)
    ai_answer = Column(Text, nullable=True)
    origin_img_url = Column(Text, nullable=True, comment="원본 문제 이미지 url")
    sourced_by = Column(String(100), nullable=True)
    human_review = Column(
        Enum("GOOD", "BAD", "UNVERIFIED", name="human_review_enum"),
        nullable=False,
        default="UNVERIFIED",
    )

    # 관계 설정
    problem_group = relationship("ProblemGroup", back_populates="problems")
    choices = relationship("Choice", back_populates="problem")
    tags = relationship("Tag", secondary="problem_tag_bind", back_populates="problems")


# 2) problem_group 테이블
class ProblemGroup(Base_oci):
    __tablename__ = "problem_group"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    source_id = Column(Integer, ForeignKey("source_info.id"), nullable=True)
    problem_passage_id = Column(
        Integer, ForeignKey("problem_passage.id"), nullable=True
    )
    instruction = Column(Text, nullable=True)

    # 관계
    source_info = relationship("SourceInfo", back_populates="problem_groups")
    problem_passage = relationship("ProblemPassage", back_populates="problem_group")
    problems = relationship("Problem", back_populates="problem_group")


# 3) problem_passage 테이블
class ProblemPassage(Base_oci):
    __tablename__ = "problem_passage"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    passage = Column(Text, nullable=True)
    similarity = Column(Integer, nullable=True)
    has_table = Column(Boolean, nullable=True)
    is_verified = Column(Boolean, nullable=True)

    # 관계
    problem_group = relationship("ProblemGroup", back_populates="problem_passage")
    # textbook_passages와의 N:N 관계를 이어주는 중간 테이블 = textbook_problem_passage_bind
    textbook_passages = relationship(
        "TextbookPassage",
        secondary="textbook_problem_passage_bind",
        back_populates="problem_passages",
    )


# 4) problem_tag_bind 테이블 (Problem <-> Tag M:N 중간 테이블)
class ProblemTagBind(Base_oci):
    __tablename__ = "problem_tag_bind"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    problem_id = Column(Integer, ForeignKey("problem.id"), nullable=True)
    tag_id = Column(Integer, ForeignKey("tag.id"), nullable=True)


# 5) choice 테이블
class Choice(Base_oci):
    __tablename__ = "choice"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    problem_id = Column(Integer, ForeignKey("problem.id"), nullable=True)
    number = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    is_answer = Column(Boolean, nullable=True)

    # 관계
    problem = relationship("Problem", back_populates="choices")


# 6) eng_category 테이블
class EngCategory(Base_oci):
    __tablename__ = "eng_category"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    parent_id = Column(Integer, nullable=True, comment="상위 id")
    name = Column(String(200), nullable=True, comment="이름")
    category = Column(String(100), nullable=True, comment="대분류, 소분류")


# 7) few_shot_store 테이블
class FewShotStore(Base_oci):
    __tablename__ = "few_shot_store"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    prompt_id = Column(Integer, nullable=True)
    user = Column(Text, nullable=True)
    assistants = Column(Text, nullable=True)


# 8) kor_category 테이블
class KorCategory(Base_oci):
    __tablename__ = "kor_category"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    parent_id = Column(Integer, nullable=True, comment="상위 id")
    name = Column(String(200), nullable=True, comment="이름")
    category = Column(String(100), nullable=True, comment="대분류, 중분류, 소분류")


# 9) kor_school_grade_category 테이블
class KorSchoolGradeCategory(Base_oci):
    __tablename__ = "kor_school_grade_category"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    parent_id = Column(Integer, nullable=True, comment="상위 id")
    name = Column(String(200), nullable=True, comment="이름")
    category = Column(String(100), nullable=True, comment="대분류, 중분류, 소분류")


# 10) math_high_school_category 테이블
class MathHighSchoolCategory(Base_oci):
    __tablename__ = "math_high_school_category"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    parent_id = Column(Integer, nullable=True, comment="상위 id")
    name = Column(String(200), nullable=True, comment="이름")
    category = Column(String(100), nullable=True, comment="대분류, 중분류, 소분류")


# 11) math_middle_school_category 테이블
class MathMiddleSchoolCategory(Base_oci):
    __tablename__ = "math_middle_school_category"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")
    parent_id = Column(Integer, nullable=True, comment="상위 id")
    name = Column(String(200), nullable=True, comment="이름")
    category = Column(String(100), nullable=True, comment="대분류, 중분류, 소분류")


# 12) prompt_store 테이블
class PromptStore(Base_oci):
    __tablename__ = "prompt_store"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=True)
    system = Column(Text, nullable=True)
    user = Column(Text, nullable=True)
    few_shot = Column(Boolean, nullable=True)
    response_format = Column(Text, nullable=True)


# 13) school 테이블
class School(Base_oci):
    __tablename__ = "school"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    kor_name = Column(String(255), nullable=True)
    eng_name = Column(String(255), nullable=True)
    level = Column(Enum("elementary", "middle", "high"), nullable=True)
    city = Column(String(255), nullable=True)
    district = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    phone = Column(String(255), nullable=True)

    # 관계
    source_infos = relationship("SourceInfo", back_populates="school")


# 14) source_info 테이블
class SourceInfo(Base_oci):
    __tablename__ = "source_info"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=True)
    type = Column(Enum("ai", "extracted", "manual"), nullable=True)
    subject = Column(
        Enum("math", "science", "korean", "english", "social", "history", "etc"),
        nullable=True,
    )
    year = Column(Integer, nullable=True)
    grade = Column(Integer, nullable=True)
    semester = Column(Integer, nullable=True)
    exam_type = Column(
        Enum("mid", "final", "quiz", "trial", "sat", "etc"), nullable=True
    )
    school_id = Column(Integer, ForeignKey("school.id"), nullable=True)
    textbook_passage_id = Column(
        Integer, ForeignKey("textbook_passage.id"), nullable=True
    )
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, nullable=True)

    # 관계
    problem_groups = relationship("ProblemGroup", back_populates="source_info")
    school = relationship("School", back_populates="source_infos")
    textbook_passage = relationship("TextbookPassage", back_populates="source_infos")


# 15) tag 테이블
class Tag(Base_oci):
    __tablename__ = "tag"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_id = Column(Integer, ForeignKey("tag.id"), nullable=True)
    name = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    desc = Column(Text, nullable=True)

    # 자기참조 관계
    parent_tag = relationship("Tag", backref="children", remote_side=[id])

    # Problem과 M:N
    problems = relationship(
        "Problem", secondary="problem_tag_bind", back_populates="tags"
    )
    # TextbookPassage와 M:N
    textbook_passages = relationship(
        "TextbookPassage", secondary="textbook_passage_tag_bind", back_populates="tags"
    )


# 16) textbook 테이블
class Textbook(Base_oci):
    __tablename__ = "textbook"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    publisher = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    revision_year = Column(String(255), nullable=True)
    subject = Column(
        Enum("math", "science", "korean", "english", "social", "history", "etc"),
        nullable=True,
    )
    level = Column(Enum("elementary", "middle", "high"), nullable=True)
    grade = Column(String(50), nullable=True)
    # 관계
    textbook_passages = relationship("TextbookPassage", back_populates="textbook")


# 17) textbook_passage 테이블
class TextbookPassage(Base_oci):
    __tablename__ = "textbook_passage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    textbook_id = Column(Integer, ForeignKey("textbook.id"), nullable=True)
    passage = Column(Text, nullable=True)
    article = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    additional_info = Column(Text, nullable=True)

    # 관계
    textbook = relationship("Textbook", back_populates="textbook_passages")
    source_infos = relationship("SourceInfo", back_populates="textbook_passage")

    # Tag와 M:N
    tags = relationship(
        "Tag", secondary="textbook_passage_tag_bind", back_populates="textbook_passages"
    )
    # problem_passage와 N:N
    problem_passages = relationship(
        "ProblemPassage",
        secondary="textbook_problem_passage_bind",
        back_populates="textbook_passages",
    )


# 18) textbook_passage_tag_bind 테이블 (TextbookPassage <-> Tag M:N)
class TextbookPassageTagBind(Base_oci):
    __tablename__ = "textbook_passage_tag_bind"

    id = Column(Integer, primary_key=True, autoincrement=True)
    textbook_passage_id = Column(
        Integer, ForeignKey("textbook_passage.id"), nullable=True
    )
    tag_id = Column(Integer, ForeignKey("tag.id"), nullable=True)


# 19) textbook_problem_passage_bind 테이블 (TextbookPassage <-> ProblemPassage N:N)
class TextbookProblemPassageBind(Base_oci):
    __tablename__ = "textbook_problem_passage_bind"

    id = Column(Integer, primary_key=True, autoincrement=True)
    textbook_passage_id = Column(
        Integer, ForeignKey("textbook_passage.id"), nullable=True
    )
    problem_passage_id = Column(
        Integer, ForeignKey("problem_passage.id"), nullable=True
    )
    similarity = Column(Integer, nullable=True)


# --------------------------------------------------------------------------
# ML/AI 용도 (few_shot_store, prompt_store)는 이미 추가했으므로 여기서는 제외하거나,
# 필요 시 별도로 정리
# --------------------------------------------------------------------------
class MathProblemTagBind(Base_oci):
    __tablename__ = "math_problem_tag_bind"

    id = Column(Integer, primary_key=True, autoincrement=True)
    problem_id = Column(Integer)
    tag_id = Column(Integer)
