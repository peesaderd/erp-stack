import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "54517"))
    secret_token: str = os.getenv("SECRET_TOKEN", "")

    # Plane
    plane_base_url: str = os.getenv("PLANE_URL", "http://localhost:54512")
    plane_workspace_slug: str = os.getenv("PLANE_WORKSPACE_SLUG", "erp-roadmap")
    plane_cookie: str = os.getenv("PLANE_COOKIE_VALUE", "")
    plane_email: str = os.getenv("PLANE_EMAIL", "admin@plane.local")
    plane_password: str = os.getenv("PLANE_PASSWORD", "")

    # Planka
    planka_base_url: str = os.getenv("PLANKA_URL", "http://localhost:54513")
    planka_api_token: str = os.getenv("PLANKA_API_TOKEN", "")

    # BookStack
    bookstack_base_url: str = os.getenv("BOOKSTACK_URL", "http://localhost:54515")
    bookstack_token_id: str = os.getenv("BOOKSTACK_API_TOKEN_ID", "")
    bookstack_token_secret: str = os.getenv("BOOKSTACK_API_TOKEN_SECRET", "")

    # OpenObserve
    openobserve_base_url: str = os.getenv("OPENOBSERVE_URL", "http://localhost:54514")
    openobserve_org: str = os.getenv("OPENOBSERVE_ORG", "default")
    openobserve_stream: str = os.getenv("OPENOBSERVE_STREAM", "bridge_logs")
    openobserve_login: str = os.getenv("OPENOBSERVE_LOGIN", "")
    openobserve_password: str = os.getenv("OPENOBSERVE_PASSWORD", "")


settings = Settings()
