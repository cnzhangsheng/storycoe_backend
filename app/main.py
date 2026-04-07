"""StoryBird Backend Application."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import BusinessException
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db
from app.api import auth_router, books_router, users_router, reading_router, ocr_router, generate_router
from app.api.admin import router as admin_router

# 配置日志
setup_logging(settings.log_level)
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info(f"🚀 {settings.app_name} v{settings.app_version} starting...")
    logger.info(f"Environment: debug={settings.debug}, log_level={settings.log_level}")

    # 创建上传目录
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory: {upload_dir.absolute()}")

    # 初始化数据库表
    logger.info("Initializing database...")
    init_db()

    yield
    # Shutdown
    logger.info(f"👋 {settings.app_name} shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Storycoe（绘本创）Backend API - 自己做绘本，逐句跟读练口语",
    lifespan=lifespan,
)

# 静态文件服务（用于访问上传的图片）
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.upload_dir), name="static")

# CORS middleware - 配置更详细的 CORS 支持 Flutter Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
    expose_headers=["*"],  # 暴露所有响应头
)


# ============================================
# Global Exception Handlers
# ============================================

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    """业务异常统一处理器。

    将所有 BusinessException 转换为统一的 JSON 响应格式。
    """
    logger.warning(f"业务异常: {exc.code} - {exc.message} | path={request.url.path}")
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """通用异常处理器。

    处理未捕获的异常，返回统一格式响应。
    """
    logger.error(f"未处理异常: {type(exc).__name__} - {str(exc)} | path={request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误" if not settings.debug else str(exc),
            "data": None,
        },
    )


# ============================================
# Routes
# ============================================

# Include routers
app.include_router(auth_router)
app.include_router(books_router)
app.include_router(users_router)
app.include_router(reading_router)
app.include_router(ocr_router)
app.include_router(generate_router)
app.include_router(admin_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}