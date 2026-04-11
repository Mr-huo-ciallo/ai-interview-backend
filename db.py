from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 改成你自己的 MySQL 账号密码
DATABASE_URL = "mysql+pymysql://root:36970508@127.0.0.1:3306/ai_interview"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()